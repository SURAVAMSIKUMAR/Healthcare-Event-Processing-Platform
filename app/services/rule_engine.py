from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import EventType, RawEvent
from app.models.processing import Alert, AlertRule, AlertSeverity, AlertStatus, RuleOperator


@dataclass(slots=True)
class RuleMatch:
    rule_code: str
    severity: AlertSeverity
    message: str


def _as_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def evaluate_operator(rule: AlertRule, actual_value: object) -> bool:
    numeric = _as_float(actual_value)
    if numeric is None:
        if rule.operator == RuleOperator.EQ and rule.value_num is not None:
            return str(actual_value) == str(rule.value_num)
        return False

    if rule.operator == RuleOperator.LT and rule.value_num is not None:
        return numeric < rule.value_num
    if rule.operator == RuleOperator.LTE and rule.value_num is not None:
        return numeric <= rule.value_num
    if rule.operator == RuleOperator.GT and rule.value_num is not None:
        return numeric > rule.value_num
    if rule.operator == RuleOperator.GTE and rule.value_num is not None:
        return numeric >= rule.value_num
    if rule.operator == RuleOperator.EQ and rule.value_num is not None:
        return numeric == rule.value_num
    if (
        rule.operator == RuleOperator.BETWEEN
        and rule.value_min is not None
        and rule.value_max is not None
    ):
        return rule.value_min <= numeric <= rule.value_max
    if (
        rule.operator == RuleOperator.OUTSIDE_RANGE
        and rule.value_min is not None
        and rule.value_max is not None
    ):
        return numeric < rule.value_min or numeric > rule.value_max
    return False


async def load_enabled_rules(session: AsyncSession, event_type: str) -> list[AlertRule]:
    stmt: Select[tuple[AlertRule]] = select(AlertRule).where(
        AlertRule.enabled.is_(True), AlertRule.event_type == event_type
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def is_after_discharge(session: AsyncSession, event: RawEvent) -> bool:
    if event.event_type == EventType.PATIENT_DISCHARGE:
        return False

    stmt = (
        select(RawEvent)
        .where(
            RawEvent.patient_id == event.patient_id,
            RawEvent.event_type == EventType.PATIENT_DISCHARGE,
            RawEvent.occurred_at <= event.occurred_at,
        )
        .order_by(RawEvent.occurred_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    discharge_event = result.scalar_one_or_none()
    return discharge_event is not None


async def build_alerts_for_event(
    session: AsyncSession,
    event: RawEvent,
    normalized_data: dict,
) -> list[Alert]:
    alerts: list[Alert] = []
    rules = await load_enabled_rules(session, event.event_type.value)

    for rule in rules:
        actual = normalized_data.get(rule.field_name)
        if evaluate_operator(rule, actual):
            message = (
                f"Rule {rule.code} triggered for {rule.field_name}: "
                f"actual={actual}, operator={rule.operator.value}"
            )
            alerts.append(
                Alert(
                    event_id=event.event_id,
                    patient_id=event.patient_id,
                    rule_code=rule.code,
                    severity=rule.severity,
                    status=AlertStatus.OPEN,
                    message=message,
                )
            )

    if await is_after_discharge(session, event):
        alerts.append(
            Alert(
                event_id=event.event_id,
                patient_id=event.patient_id,
                rule_code="EVENT_AFTER_DISCHARGE",
                severity=AlertSeverity.HIGH,
                status=AlertStatus.OPEN,
                message="Event received after patient discharge.",
            )
        )

    return alerts


DEFAULT_RULES: list[dict] = [
    {
        "code": "LOW_SPO2",
        "name": "Low oxygen saturation",
        "event_type": "VITALS",
        "field_name": "oxygen_saturation",
        "operator": RuleOperator.LT,
        "value_num": 92.0,
        "value_min": None,
        "value_max": None,
        "severity": AlertSeverity.CRITICAL,
    },
    {
        "code": "HIGH_HEART_RATE",
        "name": "High heart rate",
        "event_type": "VITALS",
        "field_name": "heart_rate",
        "operator": RuleOperator.GT,
        "value_num": 120.0,
        "value_min": None,
        "value_max": None,
        "severity": AlertSeverity.HIGH,
    },
    {
        "code": "LOW_SYSTOLIC_BP",
        "name": "Low systolic blood pressure",
        "event_type": "VITALS",
        "field_name": "systolic_bp",
        "operator": RuleOperator.LT,
        "value_num": 90.0,
        "value_min": None,
        "value_max": None,
        "severity": AlertSeverity.HIGH,
    },
    {
        "code": "HIGH_TEMPERATURE",
        "name": "High temperature",
        "event_type": "VITALS",
        "field_name": "temperature_c",
        "operator": RuleOperator.GTE,
        "value_num": 38.0,
        "value_min": None,
        "value_max": None,
        "severity": AlertSeverity.MEDIUM,
    },
    {
        "code": "ABNORMAL_LAB_FLAG",
        "name": "Abnormal lab result flag",
        "event_type": "LAB_RESULT",
        "field_name": "abnormal_flag",
        "operator": RuleOperator.EQ,
        "value_num": 1.0,
        "value_min": None,
        "value_max": None,
        "severity": AlertSeverity.HIGH,
    },
]


async def seed_default_rules(session: AsyncSession) -> None:
    for rule in DEFAULT_RULES:
        stmt = select(AlertRule).where(AlertRule.code == rule["code"])
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is None:
            session.add(AlertRule(**rule))
    await session.commit()
