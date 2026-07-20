from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.event import EventType, RawEvent
from app.models.processing import PatientState
from app.models.security import User
from app.schemas.timeline import TimelineItem, TimelineResponse
from app.services.audit import write_audit_log
from app.services.auth import get_current_user

router = APIRouter()


@router.get("/patients/{patient_id}/timeline", response_model=TimelineResponse)
async def get_patient_timeline(
    patient_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    event_type: EventType | None = Query(default=None),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> TimelineResponse:
    if current_user.hospital and current_user.role.value != "ADMIN":
        state_result = await session.execute(
            select(PatientState).where(PatientState.patient_id == patient_id)
        )
        state = state_result.scalar_one_or_none()
        if state is None or state.hospital != current_user.hospital:
            await write_audit_log(
                session=session,
                request=request,
                action="PATIENT_DATA_ACCESS",
                resource_type="timeline",
                resource_id=patient_id,
                outcome="DENIED",
                user=current_user,
                patient_id=patient_id,
                details={"reason": "hospital_scope_violation"},
            )
            await session.commit()
            return TimelineResponse(items=[], page=page, page_size=page_size, total=0)

    stmt = select(RawEvent).where(RawEvent.patient_id == patient_id)

    if start_date is not None:
        stmt = stmt.where(RawEvent.occurred_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(RawEvent.occurred_at <= end_date)
    if event_type is not None:
        stmt = stmt.where(RawEvent.event_type == event_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    if sort_order == "asc":
        stmt = stmt.order_by(RawEvent.occurred_at.asc())
    else:
        stmt = stmt.order_by(RawEvent.occurred_at.desc())

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    events = result.scalars().all()

    await write_audit_log(
        session=session,
        request=request,
        action="PATIENT_DATA_ACCESS",
        resource_type="timeline",
        resource_id=patient_id,
        outcome="SUCCESS",
        user=current_user,
        patient_id=patient_id,
        details={"rows": len(events)},
    )
    await session.commit()

    return TimelineResponse(
        items=[
            TimelineItem(
                event_id=e.event_id,
                patient_id=e.patient_id,
                event_type=e.event_type.value,
                occurred_at=e.occurred_at,
                payload=e.payload,
                processing_status=e.status.value,
            )
            for e in events
        ],
        page=page,
        page_size=page_size,
        total=total,
    )
