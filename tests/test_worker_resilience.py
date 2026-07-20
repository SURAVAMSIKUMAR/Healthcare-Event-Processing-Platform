from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.models.event import EventType, IngestionStatus, RawEvent
from app.services.processing import dead_letter_event
from app.workers import tasks
from conftest import FakeScalarResult, FakeSession


def test_exponential_backoff_countdown_for_retry(monkeypatch) -> None:
    def fake_asyncio_run(_):
        raise ConnectionError("temporary issue")

    calls: dict = {}

    def fake_retry(exc, countdown):
        calls["countdown"] = countdown
        raise RuntimeError("retry-called")

    monkeypatch.setattr(tasks.asyncio, "run", fake_asyncio_run)
    monkeypatch.setattr(tasks.process_event, "retry", fake_retry, raising=False)
    monkeypatch.setattr(tasks.process_event, "request", SimpleNamespace(retries=2), raising=False)

    with pytest.raises(RuntimeError, match="retry-called"):
        tasks.process_event.run("evt-r1")

    assert calls["countdown"] == 8


@pytest.mark.asyncio
async def test_dead_letter_event_marks_failed() -> None:
    raw = RawEvent(
        id=11,
        event_id="evt-dead-1",
        event_type=EventType.VITALS,
        patient_id="patient-1",
        occurred_at=datetime(2026, 7, 17, 10, 0, tzinfo=UTC),
        payload={
            "heart_rate": 190,
            "systolic_bp": 85,
            "diastolic_bp": 60,
            "temperature_c": 39.5,
            "respiratory_rate": 26,
            "oxygen_saturation": 84,
        },
        status=IngestionStatus.ENQUEUED,
    )

    session = FakeSession(
        responses=[
            FakeScalarResult(raw),
            FakeScalarResult(None),
            FakeScalarResult(SimpleNamespace(hospital="UNKNOWN", department="UNKNOWN")),
            FakeScalarResult(SimpleNamespace(event_count=0, failure_count=0, total_processing_time_ms=0, processed_event_count=0, active_patient_count=0, critical_alert_count=0)),
            FakeScalarResult(0),
            FakeScalarResult(0),
        ]
    )

    await dead_letter_event(
        session=session,
        event_id="evt-dead-1",
        reason="boom",
        error_type="RuntimeError",
        retry_count=3,
    )

    assert raw.status == IngestionStatus.FAILED
    assert len(session.added) >= 2
