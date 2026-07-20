import pytest
from pydantic import ValidationError

from app.schemas.events import EventIngestionResponse, VitalsEvent


def test_vitals_schema_accepts_valid_payload() -> None:
    event = VitalsEvent(
        event_id="evt-100",
        event_type="VITALS",
        occurred_at="2026-07-17T10:00:00Z",
        patient_id="pat-1",
        payload={
            "heart_rate": 81,
            "systolic_bp": 122,
            "diastolic_bp": 79,
            "temperature_c": 36.7,
            "respiratory_rate": 17,
            "oxygen_saturation": 99,
        },
    )
    assert event.event_type == "VITALS"


def test_vitals_schema_rejects_invalid_payload() -> None:
    with pytest.raises(ValidationError):
        VitalsEvent(
            event_id="evt-101",
            event_type="VITALS",
            occurred_at="2026-07-17T10:00:00Z",
            patient_id="pat-2",
            payload={
                "heart_rate": 900,
                "systolic_bp": 122,
                "diastolic_bp": 79,
                "temperature_c": 36.7,
                "respiratory_rate": 17,
                "oxygen_saturation": 99,
            },
        )


def test_ingestion_response_schema() -> None:
    response = EventIngestionResponse(
        event_id="evt-102",
        accepted=True,
        duplicate=False,
        status="enqueued",
        detail="ok",
    )
    assert response.accepted is True
