from __future__ import annotations

from uuid import uuid4
import structlog

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Attaches a unique request_id to every request and response.

    WHY this matters in production:
    Every log line emitted during a request carries the same request_id.
    When a transfer fails at 3am, you grep for the request_id and see
    the complete story — lock acquired, debit failed, rollback triggered —
    all from one ID.

    The client can supply X-Request-ID for end-to-end tracing across
    their system and ours. If they don't, we generate one.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
