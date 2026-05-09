"""
middleware.py — HTTP observability middleware for FastAPI.

Responsibilities:
- Generate / propagate X-Request-ID per request
- Propagate request_id to Opik ContextVar so all trace root spans include it
- Log structured HTTP request/response telemetry
- Mirror request_id to the logging ContextVar (for log correlation)
"""
from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import backend.observability.opik_manager as opik_manager
from backend.utils.logging_config import set_request_id as _log_set_request_id

logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Injects request_id into every request context and logs HTTP telemetry.

    Order of operations:
    1. Read X-Request-ID header or generate a fresh one.
    2. Set it in opik_manager._cv_request_id (propagates to all Opik traces).
    3. Set it in logging_config ContextVar (propagates to all log records).
    4. Call the next handler.
    5. Attach X-Request-ID to the response headers.
    6. Log HTTP duration + status code as structured event.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid4().hex[:12]

        opik_manager.set_request_id(rid)
        _log_set_request_id(rid)

        t0 = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - t0) * 1000)

        response.headers["X-Request-ID"] = rid

        logger.info(
            "http request",
            extra={
                "event": "http_request",
                "request_id": rid,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": elapsed_ms,
                "client": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "")[:200],
            },
        )
        return response
