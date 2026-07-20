from datetime import UTC, datetime

from app.models.event import EventType, RawEvent
from app.services.processing import normalize_event_payload, should_apply_event_to_state


def test_normalization_includes_common_fields() -> None:
    event = RawEvent(
        event_id="evt-norm-1",
        event_type=EventType.VITALS,
        patient_id="pat-1",
        occurred_at=datetime(2026, 7, 17, 10, 0, tzinfo=UTC),
        payload={
            "heart_rate": 130,
            "systolic_bp": 88,
            "temperature_c": 38.5,
            "oxygen_saturation": 89,
            "abnormal_flag": True,
        },
    )

    normalized = normalize_event_payload(event)
    assert normalized["event_id"] == "evt-norm-1"
    assert normalized["event_type"] == "VITALS"
    assert normalized["patient_id"] == "pat-1"
    assert normalized["abnormal_flag"] == 1.0


def test_state_updates_when_incoming_is_newer() -> None:
    latest = datetime(2026, 7, 17, 10, 0, tzinfo=UTC)
    incoming = datetime(2026, 7, 17, 10, 5, tzinfo=UTC)
    assert should_apply_event_to_state(latest, incoming) is True


def test_state_does_not_update_when_incoming_is_older() -> None:
    latest = datetime(2026, 7, 17, 10, 5, tzinfo=UTC)
    incoming = datetime(2026, 7, 17, 10, 0, tzinfo=UTC)
    assert should_apply_event_to_state(latest, incoming) is False
