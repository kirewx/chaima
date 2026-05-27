"""Tests for the log_event helper and its background-task persister."""
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks
from sqlmodel import select

from chaima.models.analytics import Event, EventType
from chaima.services.events import _persist_event, log_event


def test_log_event_schedules_a_background_task():
    bg = MagicMock(spec=BackgroundTasks)
    log_event(
        bg,
        user_id=None, group_id=None,
        type=EventType.LOGIN_FAILURE,
        payload={"email_attempted": "x@example.com"},
    )
    bg.add_task.assert_called_once()
    args, _kwargs = bg.add_task.call_args
    assert args[0] is _persist_event


@pytest.mark.asyncio
async def test_persist_event_writes_row(session, user, group, patch_events_session_maker):
    await _persist_event(
        user_id=user.id, group_id=group.id,
        type="search_executed",
        payload={"query": "acetone", "result_count": 3},
    )
    fetched = (await session.exec(select(Event).where(Event.user_id == user.id))).first()
    assert fetched is not None
    assert fetched.type == "search_executed"
    assert fetched.payload == {"query": "acetone", "result_count": 3}


@pytest.mark.asyncio
async def test_persist_event_swallows_db_errors(monkeypatch):
    """A broken session must not propagate — telemetry is best-effort."""
    class _Boom:
        async def __aenter__(self):
            raise RuntimeError("db down")

        async def __aexit__(self, *_):
            return False

    def _broken_maker():
        return _Boom()

    monkeypatch.setattr("chaima.services.events.async_session_maker", _broken_maker)
    # Must not raise:
    await _persist_event(user_id=None, group_id=None, type="login_success", payload={})


@pytest.mark.asyncio
async def test_persist_event_accepts_enum_type(session, user, patch_events_session_maker):
    """EventType.<MEMBER> values should be stored as their string value."""
    await _persist_event(
        user_id=user.id, group_id=None, type=EventType.LOGIN_SUCCESS, payload=None,
    )
    fetched = (await session.exec(select(Event).where(Event.user_id == user.id))).first()
    assert fetched is not None
    assert fetched.type == "login_success"
