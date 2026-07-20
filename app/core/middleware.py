import json
import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import HTTP_REQUEST_DURATION, HTTP_REQUEST_TOTAL

logger = logging.getLogger("app.request")


class CorrelationAndLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        response.headers["x-correlation-id"] = correlation_id

        HTTP_REQUEST_TOTAL.labels(
            method=request.method,
            path=request.url.path,
            status=str(response.status_code),
        ).inc()
        HTTP_REQUEST_DURATION.labels(
            method=request.method,
            path=request.url.path,
        ).observe(elapsed)

        log_payload = {
            "event": "http_request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(elapsed * 1000, 2),
            "correlation_id": correlation_id,
            "source_ip": request.client.host if request.client else "unknown",
        }
        logger.info(json.dumps(log_payload))
        return response
