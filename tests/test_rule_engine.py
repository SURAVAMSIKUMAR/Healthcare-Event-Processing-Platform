from app.models.processing import AlertRule, AlertSeverity, RuleOperator
from app.services.rule_engine import evaluate_operator


def make_rule(operator: RuleOperator, value_num=None, value_min=None, value_max=None) -> AlertRule:
    return AlertRule(
        code="R1",
        name="test",
        event_type="VITALS",
        field_name="heart_rate",
        operator=operator,
        value_num=value_num,
        value_min=value_min,
        value_max=value_max,
        severity=AlertSeverity.HIGH,
        enabled=True,
    )


def test_operators_supported() -> None:
    assert evaluate_operator(make_rule(RuleOperator.LT, value_num=100), 90)
    assert evaluate_operator(make_rule(RuleOperator.LTE, value_num=100), 100)
    assert evaluate_operator(make_rule(RuleOperator.GT, value_num=100), 101)
    assert evaluate_operator(make_rule(RuleOperator.GTE, value_num=100), 100)
    assert evaluate_operator(make_rule(RuleOperator.EQ, value_num=100), 100)
    assert evaluate_operator(make_rule(RuleOperator.BETWEEN, value_min=90, value_max=100), 95)
    assert evaluate_operator(make_rule(RuleOperator.OUTSIDE_RANGE, value_min=90, value_max=100), 101)
