from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.event_ingestion import ingest_event
from app.schemas.events import VitalsEvent
from conftest import FakeSession


@pytest.mark.asyncio
async def test_ingest_event_duplicate_returns_duplicate_status() -> None:
    session = FakeSession()

    async def failing_flush():
        raise IntegrityError("duplicate", {}, None)

    session.flush = failing_flush  # type: ignore[assignment]

    event = VitalsEvent(
        event_id="dup-1",
        event_type="VITALS",
        occurred_at=datetime(2026, 7, 17, 10, 0, tzinfo=UTC),
        patient_id="p-1",
        payload={
            "heart_rate": 80,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "temperature_c": 36.6,
            "respiratory_rate": 16,
            "oxygen_saturation": 98,
        },
    )

    result = await ingest_event(session=session, event=event)
    assert result.duplicate is True
    assert result.status == "duplicate"


@pytest.mark.asyncio
async def test_ingest_event_success_enqueues() -> None:
    session = FakeSession()

    event = VitalsEvent(
        event_id="ok-1",
        event_type="VITALS",
        occurred_at=datetime(2026, 7, 17, 10, 0, tzinfo=UTC),
        patient_id="p-2",
        payload={
            "heart_rate": 80,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "temperature_c": 36.6,
            "respiratory_rate": 16,
            "oxygen_saturation": 98,
        },
    )

    with patch("app.services.event_ingestion.process_event.delay") as delay_mock:
        result = await ingest_event(session=session, event=event)

    delay_mock.assert_called_once_with("ok-1")
    assert result.accepted is True
    assert result.status == "enqueued"
