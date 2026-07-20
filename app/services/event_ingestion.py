from dataclasses import dataclass

from celery.exceptions import CeleryError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import EventType, IngestionStatus, RawEvent
from app.schemas.events import EventIn
from app.workers.tasks import process_event


@dataclass(slots=True)
class IngestionResult:
    event_id: str
    accepted: bool
    duplicate: bool
    status: str
    detail: str


async def ingest_event(session: AsyncSession, event: EventIn) -> IngestionResult:
    raw_event = RawEvent(
        event_id=event.event_id,
        event_type=EventType(event.event_type),
        patient_id=event.patient_id,
        occurred_at=event.occurred_at,
        payload=event.payload.model_dump(),
        status=IngestionStatus.RECEIVED,
    )

    session.add(raw_event)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return IngestionResult(
            event_id=event.event_id,
            accepted=True,
            duplicate=True,
            status="duplicate",
            detail="Event with this event_id already ingested; skipping reprocessing.",
        )

    try:
        process_event.delay(event.event_id)
        raw_event.status = IngestionStatus.ENQUEUED
        await session.commit()
        return IngestionResult(
            event_id=event.event_id,
            accepted=True,
            duplicate=False,
            status="enqueued",
            detail="Event stored and queued for asynchronous processing.",
        )
    except CeleryError as exc:
        raw_event.status = IngestionStatus.FAILED
        await session.commit()
        return IngestionResult(
            event_id=event.event_id,
            accepted=False,
            duplicate=False,
            status="queue_error",
            detail=f"Event stored for audit, but queue publish failed: {exc}",
        )
