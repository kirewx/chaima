"""ASGI middleware that logs slow or failing requests.

Adds a row to ``slow_request`` only when ``duration_ms > threshold`` OR
``status >= 500``. Writes happen in a fire-and-forget background task so
the response is never blocked.
"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from chaima.db import async_session_maker
from chaima.models.analytics import SlowRequest


class SlowRequestMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, threshold_ms: int = 500):
        super().__init__(app)
        self.threshold_ms = threshold_ms

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        if duration_ms <= self.threshold_ms and response.status_code < 500:
            return response

        # Resolve the route-pattern path so we don't explode cardinality.
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)

        user = request.scope.get("user")
        user_id = getattr(user, "id", None) if user is not None else None

        response.background = _make_background(
            response.background,
            method=request.method,
            path=path,
            status=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id,
        )
        return response


def _make_background(existing, **kwargs):
    """Compose an existing BackgroundTask with our slow-request insert.

    Starlette responses carry an optional ``background`` task; we wrap it
    so we don't clobber anything the handler already scheduled.
    """
    from starlette.background import BackgroundTask, BackgroundTasks

    async def _insert():
        try:
            async with async_session_maker() as session:
                session.add(SlowRequest(**kwargs))
                await session.commit()
        except Exception:  # noqa: BLE001
            pass

    new_task = BackgroundTask(_insert)
    if existing is None:
        return new_task
    if isinstance(existing, BackgroundTasks):
        existing.tasks.append(new_task)
        return existing
    bundle = BackgroundTasks()
    bundle.tasks.append(existing)
    bundle.tasks.append(new_task)
    return bundle
