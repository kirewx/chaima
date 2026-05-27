"""Background-task event logger for the analytics pipeline.

Public surface
--------------
* ``log_event`` — schedule a write. Call from request handlers.
* ``_persist_event`` — the function that actually writes. Exported for tests.

Both are best-effort: telemetry failures are swallowed so they cannot break
the user-facing request.
"""
from __future__ import annotations

import uuid as uuid_pkg

from fastapi import BackgroundTasks

from chaima.db import async_session_maker
from chaima.models.analytics import Event, EventType


async def _persist_event(
    user_id: uuid_pkg.UUID | None,
    group_id: uuid_pkg.UUID | None,
    type: str | EventType,
    payload: dict | None,
) -> None:
    """Insert an Event row in a fresh session.

    Wrapped in try/except so a broken DB never propagates into the
    BackgroundTasks runner (which would log a noisy traceback).
    """
    type_str = type.value if isinstance(type, EventType) else type
    try:
        async with async_session_maker() as session:
            session.add(
                Event(
                    user_id=user_id,
                    group_id=group_id,
                    type=type_str,
                    payload=payload,
                )
            )
            await session.commit()
    except Exception:  # noqa: BLE001
        # Telemetry is best-effort. Never break the user's request.
        pass


def log_event(
    background_tasks: BackgroundTasks,
    *,
    user_id: uuid_pkg.UUID | None,
    group_id: uuid_pkg.UUID | None,
    type: str | EventType,
    payload: dict | None = None,
) -> None:
    """Schedule an event write to run after the current response is sent.

    Always returns immediately. The actual DB write happens via
    ``BackgroundTasks`` in Starlette's post-response phase.
    """
    background_tasks.add_task(_persist_event, user_id, group_id, type, payload)
