"""Tests for admin-issued reset token generation."""
import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.password import PasswordHelper

from chaima.auth import UserManager
from chaima.models.user import User


def _manager(session) -> UserManager:
    return UserManager(SQLAlchemyUserDatabase(session, User))


@pytest.mark.asyncio
async def test_generated_token_is_accepted_by_reset_password(session, user):
    """A token from generate_reset_token must round-trip through reset_password."""
    user.hashed_password = PasswordHelper().hash("oldpassword")
    session.add(user)
    await session.flush()

    manager = _manager(session)
    token = manager.generate_reset_token(user)

    updated = await manager.reset_password(token, "brandnewpassword")

    verified, _ = PasswordHelper().verify_and_update(
        "brandnewpassword", updated.hashed_password
    )
    assert verified is True


@pytest.mark.asyncio
async def test_token_is_rejected_after_password_changed(session, user):
    """The password_fgpt claim makes a token single-use.

    Redeeming it changes the hash the fingerprint was taken from, so a
    second redemption of the same token must fail. This is the property
    the design relies on instead of keeping a token table.
    """
    from fastapi_users import exceptions

    user.hashed_password = PasswordHelper().hash("oldpassword")
    session.add(user)
    await session.flush()

    manager = _manager(session)
    token = manager.generate_reset_token(user)
    await manager.reset_password(token, "brandnewpassword")

    with pytest.raises(exceptions.InvalidResetPasswordToken):
        await manager.reset_password(token, "yetanotherpassword")


@pytest.mark.asyncio
async def test_tampered_token_is_rejected(session, user):
    from fastapi_users import exceptions

    user.hashed_password = PasswordHelper().hash("oldpassword")
    session.add(user)
    await session.flush()

    manager = _manager(session)
    token = manager.generate_reset_token(user)

    with pytest.raises(exceptions.InvalidResetPasswordToken):
        await manager.reset_password(token + "x", "brandnewpassword")


@pytest.mark.asyncio
async def test_expired_token_is_rejected(session, user, monkeypatch):
    """A negative lifetime puts `exp` in the past, so decode_jwt raises.

    generate_jwt only writes an `exp` claim when lifetime_seconds is
    truthy, and -60 is truthy — so this produces a genuinely expired
    token rather than one without an expiry.
    """
    from fastapi_users import exceptions

    user.hashed_password = PasswordHelper().hash("oldpassword")
    session.add(user)
    await session.flush()

    manager = _manager(session)
    monkeypatch.setattr(UserManager, "reset_password_token_lifetime_seconds", -60)
    token = manager.generate_reset_token(user)

    with pytest.raises(exceptions.InvalidResetPasswordToken):
        await manager.reset_password(token, "brandnewpassword")


def test_reset_token_lifetime_comes_from_setting():
    from chaima.config import admin_settings

    assert (
        UserManager.reset_password_token_lifetime_seconds
        == admin_settings.password_reset_ttl_hours * 3600
    )


def test_password_reset_ttl_default_is_24_hours():
    from chaima.config import AdminSettings

    assert AdminSettings().password_reset_ttl_hours == 24
