import datetime

import pytest

from chaima.models.user import User


@pytest.mark.asyncio
async def test_user_login_counters_default_to_zero_and_none(session, group):
    u = User(
        email="z@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=False,
        main_group_id=group.id,
    )
    session.add(u)
    await session.flush()
    assert u.last_login_at is None
    assert u.login_count == 0


@pytest.mark.asyncio
async def test_user_login_counters_can_be_updated(session, user):
    user.last_login_at = datetime.datetime(2026, 5, 27, 10, 0, 0, tzinfo=datetime.timezone.utc)
    user.login_count = 5
    session.add(user)
    await session.flush()
    await session.refresh(user)
    assert user.login_count == 5
    assert user.last_login_at.year == 2026
