"""Simple in-memory rate limiter.

Good enough for a single-process take-home; a real multi-instance deployment
would back this with Redis instead (see docs/adr) — no infra added here
beyond what the project already needs.
"""

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.utils.config import get_config_dict


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        rate_limit_config = get_config_dict()["RATE_LIMIT"]
        self._max_requests: int = rate_limit_config["MAX_REQUESTS"]
        self._window_seconds: float = rate_limit_config["WINDOW_SECONDS"]
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client_key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[client_key]
        while hits and now - hits[0] > self._window_seconds:
            hits.popleft()

        if len(hits) >= self._max_requests:
            return JSONResponse(
                status_code=429, content={"message": "Too many requests, please slow down."}
            )

        hits.append(now)
        return await call_next(request)
