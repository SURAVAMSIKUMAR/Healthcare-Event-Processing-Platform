from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import get_settings
from app.core.metrics import metrics_response
from app.core.middleware import CorrelationAndLoggingMiddleware
from app.db.session import SessionLocal
from app.services.auth import seed_admin_user
from app.services.rule_engine import seed_default_rules
from app.workers.celery_app import celery_app
from app import models  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with SessionLocal() as session:
        try:
            await seed_default_rules(session)
            await seed_admin_user(session)
        except SQLAlchemyError:
            logger.warning("Bootstrap seeding skipped. Run Alembic migrations first.")
    yield


async def check_database() -> bool:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def _check_broker_sync() -> bool:
    conn = celery_app.connection_for_read()
    try:
        conn.ensure_connection(max_retries=1)
        return True
    except Exception:
        return False
    finally:
        conn.release()


async def check_broker() -> bool:
    return await asyncio.to_thread(_check_broker_sync)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(CorrelationAndLoggingMiddleware)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed for event payload.",
                "details": exc.errors(),
                "correlation_id": getattr(request.state, "correlation_id", "unknown"),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_ERROR",
                "message": str(exc.detail),
                "correlation_id": getattr(request.state, "correlation_id", "unknown"),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Unexpected server error",
                "correlation_id": getattr(request.state, "correlation_id", "unknown"),
            },
        )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict:
        db_ok = await check_database()
        broker_ok = await check_broker()
        status_text = "ready" if db_ok and broker_ok else "degraded"
        return {
            "status": status_text,
            "database": "ok" if db_ok else "down",
            "broker": "ok" if broker_ok else "down",
        }

    @app.get("/metrics", tags=["observability"])
    async def metrics():
        return metrics_response()

    return app


app = create_app()
