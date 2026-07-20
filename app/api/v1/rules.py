from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.processing import AlertRule, AlertSeverity, RuleOperator
from app.models.security import User, UserRole
from app.services.audit import write_audit_log
from app.services.auth import require_roles

router = APIRouter()


class RuleUpdateRequest(BaseModel):
    enabled: bool | None = None
    severity: str | None = None
    operator: str | None = None
    value_num: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    reason: str = Field(min_length=1, max_length=300)


@router.patch("/rules/{rule_code}")
async def update_rule(
    rule_code: str,
    body: RuleUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> dict:
    result = await session.execute(select(AlertRule).where(AlertRule.code == rule_code))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    if body.enabled is not None:
        rule.enabled = body.enabled
    if body.severity is not None:
        try:
            rule.severity = AlertSeverity(body.severity)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid severity") from exc
    if body.operator is not None:
        try:
            rule.operator = RuleOperator(body.operator)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid operator") from exc
    if body.value_num is not None:
        rule.value_num = body.value_num
    if body.value_min is not None:
        rule.value_min = body.value_min
    if body.value_max is not None:
        rule.value_max = body.value_max

    await write_audit_log(
        session=session,
        request=request,
        action="RULE_CHANGE",
        resource_type="alert_rule",
        resource_id=rule.code,
        outcome="SUCCESS",
        user=admin_user,
        details={"reason": body.reason},
    )
    await session.commit()

    return {
        "code": rule.code,
        "enabled": rule.enabled,
        "severity": rule.severity.value,
        "operator": rule.operator.value,
    }
