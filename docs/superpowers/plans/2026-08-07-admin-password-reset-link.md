# Admin-Generated Password Reset Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a group administrator issue a single-use password reset link for a member, and raise session lifetime from one hour to 30 days.

**Architecture:** The reset token is the JWT `fastapi-users` already produces — it carries a `password_fgpt` claim (a hash of the user's current `hashed_password`) that is re-verified on redemption, so changing the password invalidates every outstanding token and single use needs no token table. An admin endpoint issues the token behind a permission rule that forbids resetting an account the admin does not fully control; a public endpoint redeems it. Both actions are recorded in the existing `event` table. Sessions stay stateless.

**Tech Stack:** FastAPI, fastapi-users 15.0.5, SQLModel/SQLAlchemy 2.0, Alembic (no migration needed here), React 18 + MUI + TanStack Query, pytest/pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-08-07-admin-password-reset-link-design.md`

**Branch:** `feat/admin-password-reset-link` (spec already committed as `7e2ea9a`, `db9cdec`)

---

## File Structure

Backend:

| File | Responsibility |
|---|---|
| `src/chaima/config.py` | Two new settings: session lifetime, reset-token lifetime |
| `src/chaima/auth.py` | Drive both session values from one setting; add `generate_reset_token` |
| `src/chaima/services/password_reset.py` | **New.** The permission rule, and nothing else |
| `src/chaima/schemas/password_reset.py` | **New.** `ResetLinkRead`, `PasswordResetPerform` |
| `src/chaima/routers/groups.py` | Issue endpoint, beside the existing member routes |
| `src/chaima/routers/password_reset.py` | **New.** Redeem endpoint (public, unauthenticated) |
| `src/chaima/app.py` | Mount the redeem router |
| `src/chaima/models/analytics.py` | Two `EventType` constants |

Frontend:

| File | Responsibility |
|---|---|
| `frontend/src/types/index.ts` | `ResetLinkRead` type |
| `frontend/src/api/hooks/usePasswordReset.ts` | **New.** Both mutations |
| `frontend/src/components/settings/MembersInvitesSection.tsx` | Menu entry + dialog |
| `frontend/src/pages/ResetPasswordPage.tsx` | **New.** Public redeem page |
| `frontend/src/App.tsx` | Route |
| `frontend/src/pages/LoginPage.tsx` | Recovery hint |

The permission rule lives in its own service file rather than inside the router because it is the security-critical part of this feature and must be testable without HTTP. The redeem endpoint gets its own router file rather than joining `routers/users.py` because it is unauthenticated and mounting it beside authenticated routes invites mistakes.

**No Alembic migration.** Nothing in this plan changes the schema. `EventType` values are stored as plain strings by design (`src/chaima/models/analytics.py:15`).

---

## Task 1: Session Lifetime — 30 Days, One Setting

Two values enforce session length and both must move together: `cookie_max_age` on the transport and `lifetime_seconds` on the JWT strategy. Raising only one breaks the session in a different way each time, so they are driven from a single setting and a test pins that.

**Files:**
- Modify: `src/chaima/config.py:17` (inside `Settings`, beside `cookie_secure`)
- Modify: `src/chaima/auth.py:76-85`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_session_ttl_default_is_30_days():
    from chaima.config import Settings

    s = Settings()
    assert s.session_ttl_hours == 720


def test_session_ttl_env_override(monkeypatch):
    from chaima.config import Settings

    monkeypatch.setenv("CHAIMA_SESSION_TTL_HOURS", "48")
    s = Settings()
    assert s.session_ttl_hours == 48


def test_cookie_and_jwt_lifetimes_agree():
    """The cookie's max-age and the JWT's expiry must never drift apart.

    A cookie that outlives its token logs the user out with a 401 on a
    request the browser still considers authenticated; a token that
    outlives its cookie wastes the remaining validity. Both come from
    ``session_ttl_hours``.
    """
    from chaima.auth import cookie_transport, get_jwt_strategy
    from chaima.config import settings

    expected = settings.session_ttl_hours * 3600
    assert cookie_transport.cookie_max_age == expected
    assert get_jwt_strategy().lifetime_seconds == expected
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v -k "session or lifetimes"`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'session_ttl_hours'`

- [ ] **Step 3: Add the setting**

In `src/chaima/config.py`, inside `class Settings`, directly after the `cookie_secure` field and its comment block:

```python
    # Session lifetime. Feeds BOTH the cookie's max-age and the JWT's own
    # expiry (see chaima.auth) so the two can never drift apart. 720 h is
    # 30 days: users reach ChAiMa from a phone and a desktop and should not
    # have to re-authenticate on every visit.
    #
    # Sessions are stateless — the signed token IS the session and no
    # server-side record of issued tokens exists. A longer lifetime is
    # therefore also a longer window in which a leaked token stays usable,
    # and a password reset does not evict an existing session. To invalidate
    # every session on the instance at once, change CHAIMA_SECRET_KEY.
    session_ttl_hours: int = 720
```

- [ ] **Step 4: Drive both values from it**

In `src/chaima/auth.py`, replace lines 76-85 (the `cookie_transport` assignment and `get_jwt_strategy`) with:

```python
_SESSION_LIFETIME_SECONDS = settings.session_ttl_hours * 3600

cookie_transport = CookieTransport(
    cookie_max_age=_SESSION_LIFETIME_SECONDS,
    cookie_secure=settings.cookie_secure,
)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret_key.get_secret_value(),
        lifetime_seconds=_SESSION_LIFETIME_SECONDS,
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS, all tests in the file

- [ ] **Step 6: Run the full backend suite**

Run: `uv run pytest tests/ -q`
Expected: PASS. If any test asserted a one-hour session, update it to read from `settings.session_ttl_hours` rather than hard-coding 3600.

- [ ] **Step 7: Commit**

```bash
git add src/chaima/config.py src/chaima/auth.py tests/test_config.py
git commit -m "feat(auth): raise session lifetime to 30 days

Both the cookie max-age and the JWT expiry now derive from
CHAIMA_SESSION_TTL_HOURS so they cannot drift apart."
```

---

## Task 2: Reset Token Lifetime and Generation

`UserManager.forgot_password()` does not return the token — it hands it to `on_after_forgot_password`. We need the value itself, so a sibling method builds the same claims. The claim set must match `manager.py:374-378` exactly, or `reset_password()` will reject what we issue.

**Files:**
- Modify: `src/chaima/config.py:57` (inside `AdminSettings`, beside `invite_ttl_hours`)
- Modify: `src/chaima/auth.py:25-27` (class attributes) and the `UserManager` body
- Test: `tests/test_services/test_password_reset_token.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_password_reset_token.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_services/test_password_reset_token.py -v`
Expected: FAIL — `AttributeError: 'UserManager' object has no attribute 'generate_reset_token'`

- [ ] **Step 3: Add the setting**

In `src/chaima/config.py`, inside `class AdminSettings`, after `invite_ttl_hours`:

```python
    password_reset_ttl_hours: int = 24
```

And add to that class's docstring Attributes block, after the `invite_ttl_hours` entry:

```
    password_reset_ttl_hours : int
        How long an admin-issued password reset link stays valid, in hours.
        Separate from session length: how long a recovery link works and how
        long someone stays logged in are unrelated questions.
```

- [ ] **Step 4: Add the token method**

In `src/chaima/auth.py`, add the import beside the other `fastapi_users` imports:

```python
from fastapi_users.jwt import generate_jwt
```

Change the config import to pull in `admin_settings`:

```python
from chaima.config import admin_settings, settings
```

Then in `class UserManager`, after the two existing token-secret attributes:

```python
    reset_password_token_lifetime_seconds = (
        admin_settings.password_reset_ttl_hours * 3600
    )

    def generate_reset_token(self, user: User) -> str:
        """Build a password-reset token without delivering it anywhere.

        ``forgot_password()`` passes its token to ``on_after_forgot_password``
        and returns None, which is the wrong shape when an admin needs the
        value to hand over out of band. The claims below must stay identical
        to the ones that method builds, or ``reset_password()`` will reject
        what we issue.

        The ``password_fgpt`` claim is a hash of the user's current password
        hash; ``reset_password()`` re-verifies it against the stored value,
        so any password change invalidates every outstanding token.

        Parameters
        ----------
        user : User
            The user whose password is to be reset.

        Returns
        -------
        str
            A signed JWT accepted by ``reset_password()``.
        """
        token_data = {
            "sub": str(user.id),
            "password_fgpt": self.password_helper.hash(user.hashed_password),
            "aud": self.reset_password_token_audience,
        }
        return generate_jwt(
            token_data,
            self.reset_password_token_secret,
            self.reset_password_token_lifetime_seconds,
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_services/test_password_reset_token.py -v`
Expected: PASS, 6 tests

- [ ] **Step 6: Commit**

```bash
git add src/chaima/config.py src/chaima/auth.py tests/test_services/test_password_reset_token.py
git commit -m "feat(auth): generate password reset tokens for admin handover"
```

---

## Task 3: The Permission Rule

Issuing a reset link hands over the account. Users may belong to several groups, so an unrestricted rule would let an admin of group A take over a member who also belongs to group B and read B's data through that account.

**Files:**
- Create: `src/chaima/services/password_reset.py`
- Test: `tests/test_services/test_password_reset.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_password_reset.py`:

```python
"""Tests for the admin password-reset permission rule."""
import pytest

from chaima.models.group import Group, UserGroupLink
from chaima.services.password_reset import ResetNotPermittedError, assert_may_reset


async def _link(session, user, group, *, is_admin: bool) -> None:
    session.add(UserGroupLink(user_id=user.id, group_id=group.id, is_admin=is_admin))
    await session.flush()


@pytest.mark.asyncio
async def test_superuser_actor_is_always_permitted(session, superuser, other_user, group):
    """A superuser bypasses the subset rule entirely."""
    await _link(session, other_user, group, is_admin=False)

    await assert_may_reset(session, actor=superuser, target=other_user)


@pytest.mark.asyncio
async def test_superuser_target_is_refused(session, user, superuser, group):
    """A group admin must never be able to take over a superuser account."""
    await _link(session, user, group, is_admin=True)
    await _link(session, superuser, group, is_admin=True)

    with pytest.raises(ResetNotPermittedError):
        await assert_may_reset(session, actor=user, target=superuser)


@pytest.mark.asyncio
async def test_permitted_when_target_groups_are_subset(session, user, other_user, group):
    await _link(session, user, group, is_admin=True)
    await _link(session, other_user, group, is_admin=False)

    await assert_may_reset(session, actor=user, target=other_user)


@pytest.mark.asyncio
async def test_refused_when_target_is_in_an_unadministered_group(
    session, user, other_user, group
):
    """The escalation path this rule exists to close."""
    foreign = Group(name="Lab Beta")
    session.add(foreign)
    await session.flush()

    await _link(session, user, group, is_admin=True)
    await _link(session, other_user, group, is_admin=False)
    await _link(session, other_user, foreign, is_admin=False)

    with pytest.raises(ResetNotPermittedError):
        await assert_may_reset(session, actor=user, target=other_user)


@pytest.mark.asyncio
async def test_refused_when_actor_is_only_a_plain_member(session, user, other_user, group):
    """Membership is not enough — the actor must hold is_admin."""
    await _link(session, user, group, is_admin=False)
    await _link(session, other_user, group, is_admin=False)

    with pytest.raises(ResetNotPermittedError):
        await assert_may_reset(session, actor=user, target=other_user)


@pytest.mark.asyncio
async def test_permitted_when_target_has_no_memberships(session, user, other_user, group):
    """The empty set is a subset of anything.

    A user removed from every group is a real case, and refusing to reset
    them would leave the account unrecoverable.
    """
    await _link(session, user, group, is_admin=True)

    await assert_may_reset(session, actor=user, target=other_user)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_services/test_password_reset.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'chaima.services.password_reset'`

- [ ] **Step 3: Write the service**

Create `src/chaima/services/password_reset.py`:

```python
"""Permission rule for admin-issued password reset links.

Issuing a reset link is equivalent to handing over the account, so the
rule here is deliberately stricter than plain group-admin rights.
"""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.group import UserGroupLink
from chaima.models.user import User


class ResetNotPermittedError(Exception):
    """Raised when the actor may not reset the target user's password."""


async def _group_ids(session: AsyncSession, user_id, *, admin_only: bool) -> set:
    """Collect the group IDs a user belongs to, optionally only as admin."""
    statement = select(UserGroupLink.group_id).where(UserGroupLink.user_id == user_id)
    if admin_only:
        statement = statement.where(UserGroupLink.is_admin == True)  # noqa: E712
    result = await session.exec(statement)
    return set(result.all())


async def assert_may_reset(
    session: AsyncSession,
    *,
    actor: User,
    target: User,
) -> None:
    """Check whether ``actor`` may issue a reset link for ``target``.

    A user may belong to several groups. If an administrator of one group
    could reset any member, they would gain that member's access to every
    other group as well — so the target's memberships must be fully covered
    by the groups the actor administers.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    actor : User
        The user requesting the reset link.
    target : User
        The user whose password would be reset.

    Raises
    ------
    ResetNotPermittedError
        If the actor may not reset this target.
    """
    if actor.is_superuser:
        return

    if target.is_superuser:
        raise ResetNotPermittedError(
            "Only a superuser can reset another superuser's password"
        )

    target_groups = await _group_ids(session, target.id, admin_only=False)
    actor_admin_groups = await _group_ids(session, actor.id, admin_only=True)

    if not target_groups <= actor_admin_groups:
        raise ResetNotPermittedError(
            "This user belongs to a group you do not administer, "
            "so you cannot reset their password"
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_services/test_password_reset.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/password_reset.py tests/test_services/test_password_reset.py
git commit -m "feat(auth): add permission rule for admin password resets"
```

---

## Task 4: Issue Endpoint

**Files:**
- Create: `src/chaima/schemas/password_reset.py`
- Modify: `src/chaima/models/analytics.py:26` (add one `EventType` constant)
- Modify: `src/chaima/routers/groups.py` (imports, plus a new route after `update_member_role`)
- Test: `tests/test_api/test_password_reset.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_api/test_password_reset.py`:

```python
"""API tests for admin-issued password reset links."""
import pytest
import pytest_asyncio
from sqlmodel import select

from chaima.models.analytics import Event
from chaima.models.group import Group, UserGroupLink


@pytest_asyncio.fixture
async def admin_link(session, user, group):
    """Make `user` (alice) an admin of `group`."""
    link = UserGroupLink(user_id=user.id, group_id=group.id, is_admin=True)
    session.add(link)
    await session.flush()
    return link


@pytest_asyncio.fixture
async def target_link(session, other_user, group):
    """Make `other_user` (bob) a plain member of `group`."""
    link = UserGroupLink(user_id=other_user.id, group_id=group.id, is_admin=False)
    session.add(link)
    await session.flush()
    return link


@pytest.mark.asyncio
async def test_admin_can_issue_reset_link(
    client, session, group, other_user, admin_link, target_link
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
    client, session, group, user, other_user, admin_link, target_link
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
    client, session, group, other_user, membership, target_link
):
    """`membership` makes alice a NON-admin member, so GroupAdminDep refuses."""
    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_issue_for_user_in_an_unadministered_group(
    client, session, group, other_user, admin_link, target_link
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
    client, session, group, superuser, admin_link
):
    session.add(UserGroupLink(user_id=superuser.id, group_id=group.id, is_admin=True))
    await session.flush()

    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{superuser.id}/reset-link"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_target_must_be_a_member_of_the_group_in_the_path(
    client, session, group, other_user, admin_link
):
    """GroupAdminDep only proves alice administers THIS group.

    Without an explicit membership check the caller could put any user ID
    in the path and reset a stranger's password.
    """
    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api/test_password_reset.py -v`
Expected: FAIL — all with 404, since the route does not exist yet

- [ ] **Step 3: Add the schema**

Create `src/chaima/schemas/password_reset.py`:

```python
import datetime

from pydantic import BaseModel, Field


class ResetLinkRead(BaseModel):
    """An admin-issued password reset link.

    Attributes
    ----------
    token : str
        The reset token.
    reset_url : str or None
        Full URL to hand to the user. ``None`` when ``public_base_url`` is
        unset, in which case the frontend falls back to its own origin.
    expires_at : datetime.datetime
        When the token stops working. Returned for display only; the JWT
        carries its own ``exp`` claim, which is what is actually enforced.
    """

    token: str
    reset_url: str | None = None
    expires_at: datetime.datetime


class PasswordResetPerform(BaseModel):
    """Body for redeeming a reset token.

    Attributes
    ----------
    token : str
        The token from the reset link.
    password : str
        The new password (minimum 8 characters).
    """

    token: str
    password: str = Field(min_length=8)
```

- [ ] **Step 4: Add the event type**

In `src/chaima/models/analytics.py`, inside `class EventType`, after `PUBCHEM_FETCH`:

```python
    PASSWORD_RESET_LINK_CREATED = "password_reset_link_created"
```

- [ ] **Step 5: Add the endpoint**

In `src/chaima/routers/groups.py`, extend the imports:

```python
import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from chaima.auth import UserManager, get_user_manager
from chaima.config import admin_settings, settings
from chaima.models.analytics import EventType
from chaima.models.group import UserGroupLink
from chaima.schemas.password_reset import ResetLinkRead
from chaima.services.events import log_event
from chaima.services.password_reset import ResetNotPermittedError, assert_may_reset
```

Then append this route at the end of the file:

```python
@router.post(
    "/{group_id}/members/{user_id}/reset-link",
    response_model=ResetLinkRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_password_reset_link(
    user_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
    member: GroupAdminDep,
    background_tasks: BackgroundTasks,
    user_manager: UserManager = Depends(get_user_manager),
) -> ResetLinkRead:
    """Issue a password reset link for a group member.

    The link grants control of the target account, so it must be delivered
    out of band and only to that person.

    Parameters
    ----------
    user_id : UUID
        The member whose password is to be reset.
    session : AsyncSession
        The database session (injected).
    current_user : User
        The authenticated user (injected). Needed in addition to ``member``
        because the permission rule tests ``is_superuser``, which the
        membership link does not carry.
    member : tuple[Group, UserGroupLink]
        The group and admin membership link (injected, requires admin role).
    background_tasks : BackgroundTasks
        Runner for the audit write (injected).
    user_manager : UserManager
        Builds the token (injected).

    Returns
    -------
    ResetLinkRead
        The token, its URL and its expiry.

    Raises
    ------
    HTTPException
        404 if the target is not a member of this group,
        403 if the caller may not reset this account.
    """
    group, _link = member

    # GroupAdminDep only proves the caller administers {group_id}. Without
    # this check any user ID could be put in the path.
    link_result = await session.exec(
        select(UserGroupLink).where(
            UserGroupLink.user_id == user_id,
            UserGroupLink.group_id == group.id,
        )
    )
    if link_result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this group",
        )

    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        await assert_may_reset(session, actor=current_user, target=target)
    except ResetNotPermittedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    token = user_manager.generate_reset_token(target)
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        hours=admin_settings.password_reset_ttl_hours
    )

    base = settings.public_base_url
    reset_url = f"{base.rstrip('/')}/reset-password/{token}" if base else None

    log_event(
        background_tasks,
        user_id=current_user.id,
        group_id=group.id,
        type=EventType.PASSWORD_RESET_LINK_CREATED,
        payload={"target_user_id": str(user_id)},
    )

    return ResetLinkRead(token=token, reset_url=reset_url, expires_at=expires_at)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api/test_password_reset.py -v`
Expected: PASS, 6 tests

- [ ] **Step 7: Commit**

```bash
git add src/chaima/schemas/password_reset.py src/chaima/models/analytics.py \
        src/chaima/routers/groups.py tests/test_api/test_password_reset.py
git commit -m "feat(api): issue admin password reset links"
```

---

## Task 5: Redeem Endpoint

Written by hand rather than mounted from `fastapi_users.get_reset_password_router()`, because that router also exposes `/forgot-password`, which without mail delivery would answer `202` and do nothing.

**Files:**
- Create: `src/chaima/routers/password_reset.py`
- Modify: `src/chaima/models/analytics.py` (second `EventType` constant)
- Modify: `src/chaima/app.py` (import + mount)
- Test: `tests/test_api/test_password_reset.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api/test_password_reset.py`:

```python
@pytest.mark.asyncio
async def test_redeem_sets_the_new_password(
    client, session, group, other_user, admin_link, target_link
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
    client, session, group, other_user, admin_link, target_link
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
    client, session, group, other_user, admin_link, target_link
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
    client, session, group, other_user, admin_link, target_link
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api/test_password_reset.py -v -k redeem`
Expected: FAIL with 404 — the route does not exist yet

- [ ] **Step 3: Add the event type**

In `src/chaima/models/analytics.py`, inside `class EventType`, after the constant added in Task 4:

```python
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
```

- [ ] **Step 4: Write the router**

Create `src/chaima/routers/password_reset.py`:

```python
"""Public endpoint for redeeming a password reset token.

Deliberately separate from the authenticated user routes: everything here
is reachable without a session, and mounting it beside routes that assume
one invites mistakes.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi_users import exceptions

from chaima.auth import UserManager, get_user_manager
from chaima.models.analytics import EventType
from chaima.schemas.password_reset import PasswordResetPerform
from chaima.services.events import log_event

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/reset-password")
async def reset_password(
    body: PasswordResetPerform,
    background_tasks: BackgroundTasks,
    user_manager: UserManager = Depends(get_user_manager),
) -> dict:
    """Set a new password using an admin-issued reset token.

    There is deliberately no companion endpoint for inspecting a token
    before redemption — it would let anyone probe whether a token is live.

    Parameters
    ----------
    body : PasswordResetPerform
        The token and the new password.
    background_tasks : BackgroundTasks
        Runner for the audit write (injected).
    user_manager : UserManager
        Verifies the token and writes the new password (injected).

    Returns
    -------
    dict
        A detail message.

    Raises
    ------
    HTTPException
        400 if the token is invalid, expired or already used, or if the
        password fails validation.
    """
    try:
        user = await user_manager.reset_password(body.token, body.password)
    except (
        exceptions.InvalidResetPasswordToken,
        exceptions.UserNotExists,
        exceptions.UserInactive,
    ):
        # One message for all three: distinguishing them would tell an
        # unauthenticated caller whether an account exists.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This link is invalid or has expired",
        )
    except exceptions.InvalidPasswordException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc.reason),
        )

    log_event(
        background_tasks,
        user_id=user.id,
        group_id=None,
        type=EventType.PASSWORD_RESET_COMPLETED,
        payload=None,
    )

    return {"detail": "Password updated"}
```

- [ ] **Step 5: Mount it**

In `src/chaima/app.py`, add to the router imports:

```python
from chaima.routers.password_reset import router as password_reset_router
```

And beside the other `include_router` calls, after `app.include_router(users_custom_router)`:

```python
app.include_router(password_reset_router)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api/test_password_reset.py -v`
Expected: PASS, 11 tests

- [ ] **Step 7: Run the full backend suite**

Run: `uv run pytest tests/ -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/chaima/routers/password_reset.py src/chaima/models/analytics.py \
        src/chaima/app.py tests/test_api/test_password_reset.py
git commit -m "feat(api): redeem password reset tokens"
```

---

## Task 6: Frontend Types and Hooks

**Files:**
- Modify: `frontend/src/types/index.ts` (after `InviteAccept`, around line 349)
- Create: `frontend/src/api/hooks/usePasswordReset.ts`

- [ ] **Step 1: Add the type**

In `frontend/src/types/index.ts`, after the `InviteAccept` interface:

```typescript
export interface ResetLinkRead {
  token: string;
  reset_url: string | null;
  expires_at: string;
}
```

- [ ] **Step 2: Add the hooks**

Create `frontend/src/api/hooks/usePasswordReset.ts`:

```typescript
import { useMutation } from "@tanstack/react-query";
import client from "../client";
import type { ResetLinkRead } from "../../types";

export function useCreateResetLink(groupId: string) {
  return useMutation({
    mutationFn: (userId: string) =>
      client
        .post(`/groups/${groupId}/members/${userId}/reset-link`)
        .then((r) => r.data as ResetLinkRead),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: (data: { token: string; password: string }) =>
      client.post("/auth/reset-password", data).then((r) => r.data),
  });
}
```

No cache invalidation on either: issuing a link changes no listed resource, and redeeming happens while logged out.

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/hooks/usePasswordReset.ts
git commit -m "feat(frontend): add password reset types and hooks"
```

---

## Task 7: Members List Menu Entry

**Files:**
- Modify: `frontend/src/components/settings/MembersInvitesSection.tsx` (the `MemberRow` component, lines 84-164)

- [ ] **Step 1: Extend the imports**

At the top of the file, add to the existing `@mui/material` import list: `Dialog`, `DialogTitle`, `DialogContent`, `DialogActions`, `TextField`, `Alert`, `Snackbar` are already imported. Add the hook import beside the others:

```typescript
import { useCreateResetLink } from "../../api/hooks/usePasswordReset";
import { errorMessage } from "../../utils/errorMessage";
```

- [ ] **Step 2: Replace the `MemberRow` component**

Replace the whole `MemberRow` function (lines 84-164) with:

```typescript
function MemberRow({
  groupId,
  member,
  divider,
}: {
  groupId: string;
  member: MemberRead;
  divider: boolean;
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetUrl, setResetUrl] = useState<string | null>(null);
  const [toast, setToast] = useState(false);
  const update = useUpdateMember(groupId, member.user_id);
  const remove = useRemoveMember(groupId);
  const createResetLink = useCreateResetLink(groupId);
  const close = () => setAnchor(null);

  const handleResetLink = () => {
    setResetUrl(null);
    setResetOpen(true);
    close();
    createResetLink.mutate(member.user_id, {
      onSuccess: (data) => {
        setResetUrl(
          data.reset_url ?? `${window.location.origin}/reset-password/${data.token}`,
        );
      },
    });
  };

  const copyUrl = (url: string) => {
    void navigator.clipboard.writeText(url);
    setToast(true);
  };

  return (
    <Stack
      direction="row"
      sx={{
        px: 2,
        py: 1.25,
        gap: 2,
        alignItems: "center",
        borderBottom: divider ? "1px solid" : "none",
        borderColor: "divider",
      }}
    >
      <Box
        sx={{
          width: 28,
          height: 28,
          borderRadius: "50%",
          bgcolor: "action.selected",
          color: "text.secondary",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 12,
          fontWeight: 600,
        }}
      >
        {member.email[0]?.toUpperCase() ?? "?"}
      </Box>
      <Typography variant="body1" sx={{ flex: 1, minWidth: 0 }} noWrap>
        {member.email}
      </Typography>
      <Chip
        label={member.is_admin ? "Admin" : "User"}
        size="small"
        sx={{
          bgcolor: member.is_admin ? "primary.light" : "action.selected",
          color: member.is_admin ? "primary.dark" : "text.secondary",
          fontSize: 10,
          height: 20,
        }}
      />
      <IconButton size="small" onClick={(e) => setAnchor(e.currentTarget)} aria-label="Member actions">
        <MoreHorizIcon fontSize="small" />
      </IconButton>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={close}>
        <MenuItem
          onClick={async () => {
            await update.mutateAsync({ is_admin: !member.is_admin });
            close();
          }}
        >
          {member.is_admin ? "Demote to user" : "Promote to admin"}
        </MenuItem>
        <MenuItem onClick={handleResetLink}>Generate password reset link</MenuItem>
        <MenuItem
          onClick={async () => {
            if (window.confirm(`Remove ${member.email} from the group?`)) {
              await remove.mutateAsync(member.user_id);
            }
            close();
          }}
        >
          Remove from group
        </MenuItem>
      </Menu>

      <Dialog open={resetOpen} onClose={() => setResetOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Password reset link</DialogTitle>
        <DialogContent>
          {createResetLink.isPending && <Typography variant="body2">Generating…</Typography>}
          {createResetLink.isError && (
            <Alert severity="error">{errorMessage(createResetLink.error)}</Alert>
          )}
          {resetUrl && (
            <Stack spacing={1.5} sx={{ mt: 1 }}>
              <Alert severity="warning">
                Anyone with this link can set a new password for {member.email} and
                take over the account. Give it to that person directly.
              </Alert>
              <TextField
                size="small"
                fullWidth
                value={resetUrl}
                slotProps={{
                  input: {
                    readOnly: true,
                    sx: { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
                  },
                }}
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          {resetUrl && (
            <Button onClick={() => copyUrl(resetUrl)} startIcon={<ContentCopyIcon />}>
              Copy
            </Button>
          )}
          <Button variant="contained" onClick={() => setResetOpen(false)}>
            Done
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar
        open={toast}
        autoHideDuration={2000}
        onClose={() => setToast(false)}
        message="Copied to clipboard"
      />
    </Stack>
  );
}
```

The warning wording is deliberately stronger than the invite dialog's "Share this link. It is valid once." — an invite adds someone to a group, a reset link hands over an account.

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors. If `errorMessage` is not exported from `frontend/src/utils/errorMessage.ts`, check its actual export name — `InvitePage.tsx:15` imports it the same way.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/settings/MembersInvitesSection.tsx
git commit -m "feat(frontend): issue password reset links from the members list"
```

---

## Task 8: Reset Page

**Files:**
- Create: `frontend/src/pages/ResetPasswordPage.tsx`
- Modify: `frontend/src/App.tsx` (route, beside line 15)

- [ ] **Step 1: Write the page**

Create `frontend/src/pages/ResetPasswordPage.tsx`:

```typescript
import { useState, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Box, Paper, Typography, TextField, Button, Alert } from "@mui/material";
import { useResetPassword } from "../api/hooks/usePasswordReset";
import { errorMessage } from "../utils/errorMessage";
import { Wordmark } from "../components/Wordmark";

export default function ResetPasswordPage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const reset = useResetPassword();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (password !== confirmPassword) {
      setLocalError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setLocalError("Password must be at least 8 characters");
      return;
    }
    reset.mutate(
      { token: token ?? "", password },
      { onSuccess: () => setDone(true) },
    );
  };

  if (done) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
        <Paper sx={{ p: 4, maxWidth: 400, width: "100%", textAlign: "center" }}>
          <Typography variant="h5" sx={{ mb: 2 }}>Password updated</Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            You can now sign in with your new password.
          </Typography>
          <Button variant="contained" fullWidth onClick={() => navigate("/login")}>
            Go to sign in
          </Button>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
      <Paper sx={{ p: 4, maxWidth: 400, width: "100%" }}>
        <Typography variant="h4" sx={{ mb: 1 }}><Wordmark /></Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Choose a new password
        </Typography>
        {localError && <Alert severity="error" sx={{ mb: 2 }}>{localError}</Alert>}
        {reset.isError && (
          <Alert severity="error" sx={{ mb: 2 }}>{errorMessage(reset.error)}</Alert>
        )}
        <Box component="form" onSubmit={handleSubmit}>
          <TextField
            label="New password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            fullWidth
            required
            autoFocus
            sx={{ mb: 2 }}
          />
          <TextField
            label="Repeat new password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            fullWidth
            required
            sx={{ mb: 3 }}
          />
          <Button type="submit" variant="contained" fullWidth size="large" disabled={reset.isPending}>
            {reset.isPending ? "Saving…" : "Set new password"}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
```

The page shows its form unconditionally. There is no pre-flight validity check by design — an endpoint for that would let anyone probe whether a token is live.

- [ ] **Step 2: Add the route**

In `frontend/src/App.tsx`, add the import beside the other page imports:

```typescript
import ResetPasswordPage from "./pages/ResetPasswordPage";
```

And the route immediately after the `/invite/:token` line, still **outside** `ProtectedRoute` — the user is locked out by definition:

```typescript
      <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
```

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ResetPasswordPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add public password reset page"
```

---

## Task 9: Login Page Hint

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx:29` (after the submit button, inside the form `Box`)

- [ ] **Step 1: Add the hint**

In `frontend/src/pages/LoginPage.tsx`, directly after the closing `</Button>` of the submit button and before the closing `</Box>` of the form:

```typescript
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, textAlign: "center" }}>
            Forgot your password? Ask a group administrator to send you a reset link.
          </Typography>
```

With no mail delivery there is no self-service path, and saying so plainly beats letting users hunt for one.

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds. Run it as a verification step only — Vite writes to `src/chaima/static/` (`frontend/vite.config.ts:7`), which is **gitignored** (`.gitignore:221`) and has never been tracked. The bundle is built at deploy time, not shipped in git, so do NOT stage it and do NOT force-add it.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx
git commit -m "feat(frontend): point users at their group admin for password recovery"
```

---

## Task 10: Full Verification

- [ ] **Step 1: Run the whole backend suite**

Run: `uv run pytest tests/ -q`
Expected: PASS. Report the actual count.

- [ ] **Step 2: Lint the frontend**

Run: `cd frontend && npm run lint`
Expected: no **new** findings. There are 19 pre-existing problems on `main` — count them there first if unsure, and do not "fix" unrelated ones in this branch.

There is no backend linter. Ruff is not installed and `pyproject.toml` carries no lint configuration, so do not add one as part of this work.

- [ ] **Step 3: Type-check the frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Manual smoke test**

Start the app (`uv run chaima run`), then:

1. Sign in as an admin, open Settings → Members & Invites → Members.
2. Open the `…` menu on another member, choose "Generate password reset link", copy the URL.
3. Sign out, open the URL, set a new password, confirm the success screen appears.
4. Sign in as that member with the new password.
5. Open the same reset URL again — it must now be refused.

Expected: steps 3-4 succeed, step 5 shows "This link is invalid or has expired".

- [ ] **Step 5: Confirm the session change took effect**

In the browser devtools, inspect the `fastapiusersauth` cookie after signing in.
Expected: its expiry is roughly 30 days out, not one hour.

---

## Notes for the Implementer

**Do not add frontend e2e tests.** Nine e2e tests already fail on `main` for unrelated historical reasons. New tests there would be parked where nobody is looking.

**Do not switch to `DatabaseStrategy`.** Long-lived stateless sessions were chosen deliberately; the consequences are documented under "Known Limitations" in the spec. Raise it as a follow-up if it comes up, do not implement it here.

**Do not add `/forgot-password`.** Mail delivery is deferred; see the spec's Scope section for why. An endpoint that answers `202` and does nothing is worse than an absent one.

**`_persist_event` swallows its own exceptions.** If an audit assertion fails in a test, the cause is more likely the event never being scheduled than the write failing. Check that `log_event` is reached before the response returns.
