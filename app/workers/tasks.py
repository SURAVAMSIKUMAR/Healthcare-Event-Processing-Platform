import asyncio

from sqlalchemy.exc import OperationalError

from app.db.session import worker_session
from app.services.processing import (
    PermanentProcessingError,
    TransientProcessingError,
    dead_letter_event,
    process_event_by_id,
)
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.process_event", bind=True, max_retries=3)
def process_event(self, event_id: str) -> dict[str, str]:
    async def _run() -> dict[str, int | str]:
        async with worker_session() as session:
            return await process_event_by_id(
                session=session,
                event_id=event_id,
                retry_count=self.request.retries,
            )

    try:
        result = asyncio.run(_run())
        return {
            "event_id": str(result["event_id"]),
            "status": str(result["status"]),
            "alerts_created": str(result["alerts_created"]),
        }
    except (OperationalError, ConnectionError, TimeoutError, TransientProcessingError) as exc:
        countdown = 2 ** (self.request.retries + 1)
        raise self.retry(exc=exc, countdown=countdown)
    except PermanentProcessingError as exc:
        asyncio.run(
            _dead_letter(
                event_id=event_id,
                reason=str(exc),
                error_type=exc.__class__.__name__,
                retry_count=self.request.retries,
            )
        )
        return {
            "event_id": event_id,
            "status": "dead_lettered",
            "alerts_created": "0",
        }
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                _dead_letter(
                    event_id=event_id,
                    reason=str(exc),
                    error_type=exc.__class__.__name__,
                    retry_count=self.request.retries,
                )
            )
            return {
                "event_id": event_id,
                "status": "dead_lettered",
                "alerts_created": "0",
            }
        countdown = 2 ** (self.request.retries + 1)
        raise self.retry(exc=exc, countdown=countdown)


async def _dead_letter(event_id: str, reason: str, error_type: str, retry_count: int) -> None:
    async with worker_session() as session:
        await dead_letter_event(
            session=session,
            event_id=event_id,
            reason=reason,
            error_type=error_type,
            retry_count=retry_count,
        )
