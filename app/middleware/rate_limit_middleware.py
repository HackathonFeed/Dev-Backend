import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter for public endpoints."""

    def __init__(self, app):
        super().__init__(app)
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = settings.rate_limit_window_seconds
        bucket = self.requests[client_ip]

        while bucket and now - bucket[0] > window:
            bucket.popleft()

        if len(bucket) >= settings.rate_limit_requests:
            return Response(
                content='{"success":false,"message":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        bucket.append(now)
        return await call_next(request)
