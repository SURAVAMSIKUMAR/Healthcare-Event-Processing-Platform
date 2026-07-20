from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.security import User, UserRole
from app.schemas.events import EventIn, EventIngestionResponse
from app.services.audit import write_audit_log
from app.services.auth import get_current_user
from app.services.event_ingestion import ingest_event

router = APIRouter()


@router.post(
    "/events",
    response_model=EventIngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a healthcare event",
)
async def create_event(
    event: EventIn,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> EventIngestionResponse:
    if current_user.role == UserRole.AUDITOR:
        raise HTTPException(status_code=403, detail="Auditor role cannot ingest events")

    if (
        current_user.role != UserRole.ADMIN
        and current_user.hospital
        and event.event_type == "PATIENT_ADMISSION"
        and getattr(event.payload, "facility", None) != current_user.hospital
    ):
        raise HTTPException(status_code=403, detail="Hospital scope violation")

    result = await ingest_event(session=session, event=event)
    await write_audit_log(
        session=session,
        request=request,
        action="EVENT_INGEST",
        resource_type="raw_event",
        resource_id=result.event_id,
        outcome="SUCCESS" if result.accepted else "FAILURE",
        user=current_user,
        patient_id=event.patient_id,
        details={"status": result.status, "duplicate": result.duplicate},
    )
    await session.commit()

    return EventIngestionResponse(
        event_id=result.event_id,
        accepted=result.accepted,
        duplicate=result.duplicate,
        status=result.status,
        detail=result.detail,
    )
