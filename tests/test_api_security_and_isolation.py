from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.db.session import get_db_session
from app.models.processing import Alert, AlertStatus
from app.models.security import User
from app.services.auth import get_current_user
from conftest import FakeScalarResult, FakeSession


@pytest.mark.api
def test_events_reject_auditor_role(client_with_overrides, auditor_user: User):
    client, _session = client_with_overrides

    async def user_dep() -> User:
        return auditor_user

    from app.main import app

    app.dependency_overrides[get_current_user] = user_dep

    payload = {
        "event_id": "evt-auditor",
        "event_type": "VITALS",
        "occurred_at": "2026-07-17T10:00:00Z",
        "patient_id": "p-aud-1",
        "payload": {
            "heart_rate": 90,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "temperature_c": 36.7,
            "respiratory_rate": 16,
            "oxygen_saturation": 98,
        },
    }

    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 403


@pytest.mark.api
def test_events_duplicate_handling_response(client_with_overrides, monkeypatch):
    client, _session = client_with_overrides

    async def fake_ingest_event(session, event):
        return SimpleNamespace(
            event_id=event.event_id,
            accepted=True,
            duplicate=True,
            status="duplicate",
            detail="Event with this event_id already ingested; skipping reprocessing.",
        )

    monkeypatch.setattr("app.api.v1.events.ingest_event", fake_ingest_event)

    payload = {
        "event_id": "evt-dup-api",
        "event_type": "VITALS",
        "occurred_at": "2026-07-17T10:00:00Z",
        "patient_id": "p-api-1",
        "payload": {
            "heart_rate": 90,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "temperature_c": 36.7,
            "respiratory_rate": 16,
            "oxygen_saturation": 98,
        },
    }

    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 202
    body = response.json()
    assert body["duplicate"] is True
    assert body["status"] == "duplicate"


@pytest.mark.api
def test_invalid_payload_returns_consistent_error_envelope(client_with_overrides):
    client, _session = client_with_overrides

    payload = {
        "event_id": "evt-bad",
        "event_type": "VITALS",
        "occurred_at": "2026-07-17T10:00:00Z",
        "patient_id": "p-api-2",
        "payload": {
            "heart_rate": 1000,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "temperature_c": 36.7,
            "respiratory_rate": 16,
            "oxygen_saturation": 98,
        },
    }

    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR"
    assert "correlation_id" in body


@pytest.mark.api
def test_patient_timeline_hospital_isolation_returns_empty(client_with_overrides, scoped_user: User):
    client, _session = client_with_overrides

    state = SimpleNamespace(patient_id="p-other", hospital="Another Hospital")
    fake_session = FakeSession(responses=[FakeScalarResult(state)])

    async def db_dep():
        yield fake_session

    async def user_dep() -> User:
        return scoped_user

    from app.main import app

    app.dependency_overrides[get_db_session] = db_dep
    app.dependency_overrides[get_current_user] = user_dep

    response = client.get("/api/v1/patients/p-other/timeline")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


@pytest.mark.api
def test_acknowledge_blocks_repeat_acknowledgement(client_with_overrides):
    client, _session = client_with_overrides

    alert = Alert(
        id=101,
        event_id="evt-ack-1",
        patient_id="p-ack-1",
        rule_code="LOW_SPO2",
        severity="CRITICAL",
        status=AlertStatus.ACKNOWLEDGED,
        message="already acked",
        triggered_at=datetime(2026, 7, 17, 10, 0, tzinfo=UTC),
    )
    fake_session = FakeSession(responses=[FakeScalarResult(alert)])

    async def db_dep():
        yield fake_session

    from app.main import app

    app.dependency_overrides[get_db_session] = db_dep

    response = client.patch(
        "/api/v1/alerts/101/acknowledge",
        json={"user": "doctor1", "comments": "ack"},
    )
    assert response.status_code == 409
