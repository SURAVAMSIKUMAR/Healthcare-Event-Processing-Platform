from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.processing import Alert, AlertSeverity, AlertStatus, PatientState
from app.models.security import User
from app.schemas.alerts import (
    AcknowledgeAlertRequest,
    AcknowledgeAlertResponse,
    AlertsListResponse,
    AlertOut,
)
from app.services.audit import write_audit_log
from app.services.auth import get_current_user

router = APIRouter()


@router.get("/alerts", response_model=AlertsListResponse)
async def list_alerts(
    request: Request,
    hospital: str | None = Query(default=None),
    department: str | None = Query(default=None),
    patient_id: str | None = Query(default=None),
    severity: AlertSeverity | None = Query(default=None),
    status_filter: AlertStatus | None = Query(default=None, alias="status"),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AlertsListResponse:
    stmt = select(Alert, PatientState).outerjoin(
        PatientState, PatientState.patient_id == Alert.patient_id
    )

    effective_hospital = hospital
    if current_user.role.value != "ADMIN" and current_user.hospital:
        effective_hospital = current_user.hospital

    if effective_hospital is not None:
        stmt = stmt.where(PatientState.hospital == effective_hospital)
    if hospital is not None and current_user.role.value == "ADMIN":
        stmt = stmt.where(PatientState.hospital == hospital)
    if department is not None:
        stmt = stmt.where(PatientState.department == department)
    if patient_id is not None:
        stmt = stmt.where(Alert.patient_id == patient_id)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if status_filter is not None:
        stmt = stmt.where(Alert.status == status_filter)
    if start_date is not None:
        stmt = stmt.where(Alert.triggered_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(Alert.triggered_at <= end_date)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = stmt.order_by(Alert.triggered_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    rows = result.all()

    items: list[AlertOut] = []
    for alert, state in rows:
        items.append(
            AlertOut(
                id=alert.id,
                event_id=alert.event_id,
                patient_id=alert.patient_id,
                rule_code=alert.rule_code,
                severity=alert.severity.value,
                status=alert.status.value,
                message=alert.message,
                triggered_at=alert.triggered_at,
                acknowledged_at=alert.acknowledged_at,
                acknowledged_by=alert.acknowledged_by,
                acknowledgement_note=alert.acknowledgement_note,
                hospital=state.hospital if state else None,
                department=state.department if state else None,
            )
        )

    await write_audit_log(
        session=session,
        request=request,
        action="PATIENT_DATA_ACCESS",
        resource_type="alerts_list",
        resource_id=None,
        outcome="SUCCESS",
        user=current_user,
        details={"rows": len(items)},
    )
    await session.commit()

    return AlertsListResponse(items=items, page=page, page_size=page_size, total=total)


@router.patch(
    "/alerts/{alert_id}/acknowledge",
    response_model=AcknowledgeAlertResponse,
    status_code=status.HTTP_200_OK,
)
async def acknowledge_alert(
    alert_id: int,
    body: AcknowledgeAlertRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AcknowledgeAlertResponse:
    async with session.begin():
        result = await session.execute(select(Alert).where(Alert.id == alert_id).with_for_update())
        alert = result.scalar_one_or_none()
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")

        if alert.status == AlertStatus.ACKNOWLEDGED:
            raise HTTPException(
                status_code=409,
                detail="Alert already acknowledged; repeat acknowledgement blocked.",
            )

        if current_user.role.value != "ADMIN" and current_user.hospital:
            state_res = await session.execute(
                select(PatientState).where(PatientState.patient_id == alert.patient_id)
            )
            state = state_res.scalar_one_or_none()
            if state is None or state.hospital != current_user.hospital:
                raise HTTPException(status_code=403, detail="Hospital scope violation")

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now(UTC)
        alert.acknowledged_by = body.user
        alert.acknowledgement_note = body.comments

        await write_audit_log(
            session=session,
            request=request,
            action="ALERT_ACKNOWLEDGEMENT",
            resource_type="alert",
            resource_id=str(alert.id),
            outcome="SUCCESS",
            user=current_user,
            patient_id=alert.patient_id,
            details={"acknowledged_by": body.user},
        )

    return AcknowledgeAlertResponse(
        id=alert.id,
        status=alert.status.value,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
        acknowledgement_note=alert.acknowledgement_note,
    )
