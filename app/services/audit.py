import json

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security import AuditLog, User


async def write_audit_log(
    session: AsyncSession,
    request: Request,
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: str,
    user: User | None = None,
    patient_id: str | None = None,
    details: dict | None = None,
) -> None:
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    source_ip = request.client.host if request.client else "unknown"
    audit = AuditLog(
        action=action,
        user_id=user.id if user else None,
        username=user.username if user else None,
        role=user.role.value if user else None,
        patient_id=patient_id,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        details=json.dumps(details or {}, default=str),
        correlation_id=correlation_id,
        source_ip=source_ip,
    )
    session.add(audit)
