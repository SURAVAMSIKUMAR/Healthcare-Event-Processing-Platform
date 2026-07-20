from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.clinical import HospitalSummaryDaily
from app.models.security import User
from app.schemas.reports import HospitalSummaryItem, HospitalSummaryResponse
from app.services.audit import write_audit_log
from app.services.auth import get_current_user

router = APIRouter()


@router.get("/reports/hospital-summary", response_model=HospitalSummaryResponse)
async def get_hospital_summary(
    request: Request,
    hospital: str | None = Query(default=None),
    department: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> HospitalSummaryResponse:
    stmt = select(
        HospitalSummaryDaily.hospital,
        HospitalSummaryDaily.department,
        func.sum(HospitalSummaryDaily.event_count).label("event_count"),
        func.sum(HospitalSummaryDaily.failure_count).label("failure_count"),
        func.max(HospitalSummaryDaily.active_patient_count).label("active_patient_count"),
        func.sum(HospitalSummaryDaily.critical_alert_count).label("critical_alert_count"),
        func.sum(HospitalSummaryDaily.total_processing_time_ms).label("total_processing_time_ms"),
        func.sum(HospitalSummaryDaily.processed_event_count).label("processed_event_count"),
    ).group_by(HospitalSummaryDaily.hospital, HospitalSummaryDaily.department)

    filters = []
    if current_user.role.value != "ADMIN" and current_user.hospital:
        filters.append(HospitalSummaryDaily.hospital == current_user.hospital)
    elif hospital is not None:
        filters.append(HospitalSummaryDaily.hospital == hospital)
    if department is not None:
        filters.append(HospitalSummaryDaily.department == department)
    if start_date is not None:
        filters.append(HospitalSummaryDaily.summary_date >= start_date)
    if end_date is not None:
        filters.append(HospitalSummaryDaily.summary_date <= end_date)
    if filters:
        stmt = stmt.where(and_(*filters))

    result = await session.execute(stmt)
    rows = result.all()

    grouped: list[HospitalSummaryItem] = []
    for row in rows:
        processed_count = int(row.processed_event_count or 0)
        total_time = int(row.total_processing_time_ms or 0)
        avg = float(total_time / processed_count) if processed_count > 0 else 0.0
        grouped.append(
            HospitalSummaryItem(
                hospital=row.hospital,
                department=row.department,
                event_count=int(row.event_count or 0),
                failure_count=int(row.failure_count or 0),
                active_patient_count=int(row.active_patient_count or 0),
                critical_alert_count=int(row.critical_alert_count or 0),
                avg_processing_time_ms=round(avg, 2),
            )
        )

    await write_audit_log(
        session=session,
        request=request,
        action="PATIENT_DATA_ACCESS",
        resource_type="hospital_summary",
        resource_id=None,
        outcome="SUCCESS",
        user=current_user,
        details={"rows": len(grouped)},
    )
    await session.commit()

    return HospitalSummaryResponse(generated_rows=len(grouped), grouped=grouped)
