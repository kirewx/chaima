"""Tests for the UserManager overrides that drive analytics."""
import datetime

import pytest
from sqlmodel import select

from chaima.models.analytics import Event


@pytest.mark.asyncio
async def test_on_after_login_bumps_counters_and_logs_event(
    session, user, patch_events_session_maker
):
    """Calling on_after_login should increment login_count, set last_login_at, log event."""
    from fastapi_users.db import SQLAlchemyUserDatabase
    from chaima.auth import UserManager
    from chaima.models.user import User

    user_db = SQLAlchemyUserDatabase(session, User)
    manager = UserManager(user_db)

    before = user.login_count
    await manager.on_after_login(user, request=None, response=None)

    await session.refresh(user)
    assert user.login_count == before + 1
    assert user.last_login_at is not None
    assert isinstance(user.last_login_at, datetime.datetime)

    events = (await session.exec(select(Event).where(Event.type == "login_success"))).all()
    assert len(events) == 1
    assert events[0].user_id == user.id


@pytest.mark.asyncio
async def test_authenticate_logs_login_failure_for_bad_credentials(
    session, user, patch_events_session_maker, monkeypatch
):
    """authenticate() returning None should log a login_failure event."""
    from types import SimpleNamespace
    from fastapi_users.db import SQLAlchemyUserDatabase
    from chaima.auth import UserManager
    from chaima.models.user import User

    user_db = SQLAlchemyUserDatabase(session, User)
    manager = UserManager(user_db)

    # Bypass the real password check — simulate "no such user".
    async def _none(self, _creds):
        return None

    from fastapi_users import BaseUserManager
    monkeypatch.setattr(BaseUserManager, "authenticate", _none)

    creds = SimpleNamespace(username="nope@example.com", password="x")
    result = await manager.authenticate(creds)
    assert result is None

    events = (await session.exec(select(Event).where(Event.type == "login_failure"))).all()
    assert len(events) == 1
    assert events[0].user_id is None
    assert events[0].payload == {"email_attempted": "nope@example.com"}


@pytest.mark.asyncio
async def test_authenticate_does_not_log_failure_for_successful_login(
    session, user, patch_events_session_maker, monkeypatch
):
    from types import SimpleNamespace
    from fastapi_users.db import SQLAlchemyUserDatabase
    from chaima.auth import UserManager
    from chaima.models.user import User

    user_db = SQLAlchemyUserDatabase(session, User)
    manager = UserManager(user_db)

    async def _ok(self, _creds):
        return user

    from fastapi_users import BaseUserManager
    monkeypatch.setattr(BaseUserManager, "authenticate", _ok)

    creds = SimpleNamespace(username=user.email, password="x")
    result = await manager.authenticate(creds)
    assert result is user

    events = (await session.exec(select(Event).where(Event.type == "login_failure"))).all()
    assert len(events) == 0
