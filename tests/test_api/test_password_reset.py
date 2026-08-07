"""API tests for admin-issued password reset links."""
import datetime

import pytest
from fastapi_users.jwt import decode_jwt
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from chaima.auth import UserManager
from chaima.models.analytics import Event
from chaima.models.group import Group, UserGroupLink


@pytest.mark.asyncio
async def test_admin_can_issue_reset_link(
    client, session, group, other_user, admin_membership, other_membership
):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["token"]
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_issuing_writes_an_audit_event_naming_the_actor(
    client, session, group, user, other_user, admin_membership, other_membership
):
    """The event records WHO authorised the reset, with the target in the payload."""
    await client.post(f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link")

    events = (
        await session.exec(
            select(Event).where(Event.type == "password_reset_link_created")
        )
    ).all()
    assert len(events) == 1
    assert events[0].user_id == user.id
    assert events[0].group_id == group.id
    assert events[0].payload == {"target_user_id": str(other_user.id)}


@pytest.mark.asyncio
async def test_plain_member_cannot_issue(
    client, session, group, other_user, membership, other_membership
):
    """`membership` makes alice a NON-admin member, so GroupAdminDep refuses."""
    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_issue_for_user_in_an_unadministered_group(
    client, session, group, other_user, admin_membership, other_membership
):
    """Bob also belongs to a group alice does not administer."""
    foreign = Group(name="Lab Beta")
    session.add(foreign)
    await session.flush()
    session.add(UserGroupLink(user_id=other_user.id, group_id=foreign.id, is_admin=False))
    await session.flush()

    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_issue_for_superuser(
    client, session, group, superuser, admin_membership
):
    session.add(UserGroupLink(user_id=superuser.id, group_id=group.id, is_admin=True))
    await session.flush()

    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{superuser.id}/reset-link"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_target_must_be_a_member_of_the_group_in_the_path(
    client, session, group, other_user, admin_membership
):
    """GroupAdminDep only proves alice administers THIS group.

    Without an explicit membership check the caller could put any user ID
    in the path and reset a stranger's password.
    """
    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_expires_at_matches_the_token_s_own_exp_claim(
    client, session, group, other_user, admin_membership, other_membership
):
    """`expires_at` and the JWT `exp` claim are computed separately (one in
    routers/groups.py from admin_settings, one in auth.py from the
    UserManager) and could silently drift apart if either changes alone.
    """
    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    assert resp.status_code == 201
    data = resp.json()

    payload = decode_jwt(
        data["token"],
        UserManager.reset_password_token_secret,
        [UserManager.reset_password_token_audience],
    )
    token_exp = datetime.datetime.fromtimestamp(payload["exp"], tz=datetime.UTC)
    expires_at = datetime.datetime.fromisoformat(data["expires_at"])

    assert abs((token_exp - expires_at).total_seconds()) < 5


@pytest.mark.asyncio
async def test_redeem_sets_the_new_password(
    client, session, group, other_user, admin_membership, other_membership
):
    from fastapi_users.password import PasswordHelper

    issue = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    token = issue.json()["token"]

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "brandnewpassword"},
    )
    assert resp.status_code == 200

    await session.refresh(other_user)
    verified, _ = PasswordHelper().verify_and_update(
        "brandnewpassword", other_user.hashed_password
    )
    assert verified is True


@pytest.mark.asyncio
async def test_redeeming_twice_fails(
    client, session, group, other_user, admin_membership, other_membership
):
    """Single use, enforced by the password_fgpt claim rather than a table."""
    issue = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    token = issue.json()["token"]

    first = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "brandnewpassword"},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "yetanotherpassword"},
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_redeeming_a_tampered_token_fails(client):
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "password": "brandnewpassword"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_redeeming_writes_an_audit_event(
    client, session, group, other_user, admin_membership, other_membership
):
    issue = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    token = issue.json()["token"]
    await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "brandnewpassword"},
    )

    events = (
        await session.exec(
            select(Event).where(Event.type == "password_reset_completed")
        )
    ).all()
    assert len(events) == 1
    assert events[0].user_id == other_user.id


@pytest.mark.asyncio
async def test_short_password_is_rejected(
    client, session, group, other_user, admin_membership, other_membership
):
    issue = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    token = issue.json()["token"]

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_session_survives_password_reset(
    session, group, user, other_user, admin_membership, other_membership, monkeypatch
):
    """Pins a deliberately-accepted trade-off, not a bug.

    The design spec (docs/superpowers/specs/2026-08-07-admin-password-reset-
    link-design.md, "Known Limitations") states that sessions are a stateless
    signed JWT: nothing consults the database per-request, so a token issued
    before a password reset remains valid until its own expiry, regardless
    of the reset. This test proves that behaviour end-to-end through real
    cookie-login and real token validation (unlike the other tests in this
    file, which use the `client` fixture's `current_active_user` override —
    that override would bypass token validation entirely and make an
    assertion like this one pass vacuously, pinning nothing).

    If this test ever starts failing because someone added session
    eviction/invalidation on password reset (e.g. switched to
    `DatabaseStrategy`, or added a token-blacklist / password-changed-at
    check), that is a *behaviour change*, and the correct response is to
    update the spec's Known Limitations section to describe the new
    behaviour -- not to delete or weaken this test.
    """
    from fastapi_users.password import PasswordHelper

    import chaima.auth as auth_module
    from chaima.db import get_async_session
    from chaima.app import app

    admin_password = "adminpassword123"
    target_password = "targetpassword123"
    helper = PasswordHelper()
    user.hashed_password = helper.hash(admin_password)
    other_user.hashed_password = helper.hash(target_password)
    await session.flush()

    # Login sets a `Secure` cookie by default (chaima.config.Settings.
    # cookie_secure); httpx's cookie jar will not replay a Secure cookie
    # back over the plain-http ASGI test transport, which would break this
    # test for a reason unrelated to the behaviour under test. Relax it for
    # the duration of the test, exactly as CHAIMA_COOKIE_SECURE=false does
    # for real local-network testing (see config.py).
    monkeypatch.setattr(auth_module.cookie_transport, "cookie_secure", False)

    async def _override_session():
        yield session

    app.dependency_overrides[get_async_session] = _override_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as admin_client, AsyncClient(
            transport=transport, base_url="http://test"
        ) as target_client:
            # Admin logs in for real (no auth override active) and issues a
            # reset link for the target user.
            admin_login = await admin_client.post(
                "/api/v1/auth/cookie/login",
                data={"username": user.email, "password": admin_password},
            )
            assert admin_login.status_code == 204

            issue = await admin_client.post(
                f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
            )
            assert issue.status_code == 201
            token = issue.json()["token"]

            # Target user establishes a real session BEFORE the reset.
            target_login = await target_client.post(
                "/api/v1/auth/cookie/login",
                data={"username": other_user.email, "password": target_password},
            )
            assert target_login.status_code == 204

            pre_reset = await target_client.get("/api/v1/users/me")
            assert pre_reset.status_code == 200
            assert pre_reset.json()["id"] == str(other_user.id)

            # Redeem the reset link, changing the target's password.
            reset = await admin_client.post(
                "/api/v1/auth/reset-password",
                json={"token": token, "password": "brandnewpassword456"},
            )
            assert reset.status_code == 200

            # The session cookie obtained BEFORE the reset must still work:
            # this is the documented, deliberately-accepted trade-off.
            post_reset = await target_client.get("/api/v1/users/me")
            assert post_reset.status_code == 200
            assert post_reset.json()["id"] == str(other_user.id)
    finally:
        app.dependency_overrides.clear()
