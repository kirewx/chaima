# Group Membership & Invites Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the group system so every user has a mandatory main group, registration only happens via single-use invite links, and search supports multi-group filtering via parallel frontend queries.

**Architecture:** Backend adds an `Invite` model, `AdminSettings` (pydantic-settings), and a seed-on-startup flow. The User model gains `main_group_id`. Frontend replaces localStorage-based `GroupContext` with a server-derived `useMainGroup()` hook, adds group chips to `FilterDrawer`, and fires parallel queries per selected group. A new public `InvitePage` handles registration + group joining.

**Tech Stack:** FastAPI, SQLModel, pydantic-settings, fastapi-users, React 19, MUI 9, React Query 5, axios

---

## File Structure

### Backend — New files
- `src/chaima/models/invite.py` — Invite SQLModel
- `src/chaima/schemas/invite.py` — Invite Pydantic schemas
- `src/chaima/services/invites.py` — Invite business logic
- `src/chaima/routers/invites.py` — Invite API endpoints
- `tests/test_models/test_invite.py` — Invite model tests
- `tests/test_services/test_invites.py` — Invite service tests
- `tests/test_api/test_invites.py` — Invite API tests
- `tests/test_api/test_seed.py` — Superuser seed tests

### Backend — Modified files
- `src/chaima/config.py` — Add `AdminSettings`
- `src/chaima/models/user.py` — Add `main_group_id` column
- `src/chaima/schemas/user.py` — Add `main_group_id` to `UserRead`
- `src/chaima/schemas/__init__.py` — Export new invite schemas
- `src/chaima/models/__init__.py` — Export Invite model (if exists)
- `src/chaima/app.py` — Add seed logic to lifespan, remove register router, add invite router
- `src/chaima/routers/groups.py` — Restrict `create_group` to superuser, add list-members endpoint
- `src/chaima/dependencies.py` — Add `SuperuserDep` usage note
- `tests/conftest.py` — Update user fixture with `main_group_id`
- `tests/test_api/conftest.py` — Update user/superuser fixtures with `main_group_id`

### Frontend — New files
- `src/api/hooks/useInvites.ts` — Invite API hooks
- `src/pages/InvitePage.tsx` — Public invite landing page

### Frontend — Modified files
- `src/types/index.ts` — Add `InviteInfo`, update `UserRead` with `main_group_id`
- `src/components/GroupContext.tsx` — Rewrite: derive from `useCurrentUser().main_group_id`
- `src/components/FilterDrawer.tsx` — Add group chips section
- `src/components/FilterBadges.tsx` — No changes needed (existing badge system works)
- `src/pages/SearchPage.tsx` — Multi-group parallel queries
- `src/pages/SettingsPage.tsx` — Main group selector + superuser admin panel
- `src/pages/LoginPage.tsx` — Remove "Register" link, add invite redirect support
- `src/components/ProtectedRoute.tsx` — Simplify (no auto-select, user always has main group)
- `src/App.tsx` — Add `/invite/:token` route, remove `/register` route
- `src/api/hooks/useAuth.ts` — Remove `useRegister`, add `useUpdateMainGroup`

---

## Task 1: AdminSettings in config.py

**Files:**
- Modify: `src/chaima/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from chaima.config import AdminSettings


def test_admin_settings_defaults():
    s = AdminSettings()
    assert s.admin_email == "admin@chaima.local"
    assert s.admin_password.get_secret_value() == "changeme"
    assert s.admin_group_name == "Admin"
    assert s.invite_ttl_hours == 48
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_admin_settings_defaults -v`
Expected: FAIL with `ImportError: cannot import name 'AdminSettings'`

- [ ] **Step 3: Implement AdminSettings**

In `src/chaima/config.py`, add after the existing `Settings` class:

```python
class AdminSettings(BaseSettings):
    """Configuration for the initial superuser seed account.

    Attributes
    ----------
    admin_email : str
        Email address for the seed superuser.
    admin_password : SecretStr
        Password for the seed superuser.
    admin_group_name : str
        Name of the seed group.
    invite_ttl_hours : int
        Default time-to-live for invite links in hours.
    """

    admin_email: str = "admin@chaima.local"
    admin_password: SecretStr = SecretStr("changeme")
    admin_group_name: str = "Admin"
    invite_ttl_hours: int = 48

    model_config = SettingsConfigDict(env_prefix="CHAIMA_")


admin_settings = AdminSettings()
```

Also update the import at the top to include `SettingsConfigDict`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
```

And update the existing `Settings` class to use `SettingsConfigDict`:

```python
class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./chaima.db"
    secret_key: SecretStr = SecretStr("CHANGE-ME-IN-PRODUCTION")

    model_config = SettingsConfigDict(env_prefix="CHAIMA_")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chaima/config.py tests/test_config.py
git commit -m "feat: add AdminSettings with pydantic-settings for superuser seed"
```

---

## Task 2: User model — add main_group_id

**Files:**
- Modify: `src/chaima/models/user.py`
- Modify: `src/chaima/schemas/user.py`
- Test: `tests/test_models/test_user.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models/test_user.py — add or update
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.group import Group
from chaima.models.user import User


@pytest_asyncio.fixture
async def engine():
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


@pytest.mark.asyncio
async def test_user_main_group_id(session):
    group = Group(name="Test Group")
    session.add(group)
    await session.flush()

    user = User(
        email="test@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        main_group_id=group.id,
    )
    session.add(user)
    await session.flush()

    assert user.main_group_id == group.id


@pytest.mark.asyncio
async def test_user_without_main_group(session):
    user = User(
        email="orphan@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.flush()

    assert user.main_group_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models/test_user.py::test_user_main_group_id -v`
Expected: FAIL with `TypeError: ... unexpected keyword argument 'main_group_id'`

- [ ] **Step 3: Add main_group_id to User model**

In `src/chaima/models/user.py`:

```python
import datetime
import uuid as uuid_pkg

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chaima.db import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"

    main_group_id: Mapped[uuid_pkg.UUID | None] = mapped_column(
        ForeignKey("group.id"), nullable=True, default=None
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    created_chemicals: Mapped[list["Chemical"]] = relationship(
        "Chemical", back_populates="creator", foreign_keys="[Chemical.created_by]"
    )
    created_containers: Mapped[list["Container"]] = relationship(
        "Container", back_populates="creator", foreign_keys="[Container.created_by]"
    )
```

- [ ] **Step 4: Update UserRead schema**

In `src/chaima/schemas/user.py`:

```python
import datetime
import uuid

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    created_at: datetime.datetime | None = None
    main_group_id: uuid.UUID | None = None


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_models/test_user.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/chaima/models/user.py src/chaima/schemas/user.py tests/test_models/test_user.py
git commit -m "feat: add main_group_id to User model and UserRead schema"
```

---

## Task 3: Invite model

**Files:**
- Create: `src/chaima/models/invite.py`
- Test: `tests/test_models/test_invite.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models/test_invite.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.group import Group
from chaima.models.invite import Invite
from chaima.models.user import User


@pytest_asyncio.fixture
async def engine():
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


@pytest.mark.asyncio
async def test_invite_creation(session):
    group = Group(name="Lab Alpha")
    session.add(group)
    await session.flush()

    creator = User(
        email="admin@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=True,
        is_verified=True,
        main_group_id=group.id,
    )
    session.add(creator)
    await session.flush()

    invite = Invite(group_id=group.id, created_by=creator.id)
    session.add(invite)
    await session.flush()

    assert invite.id is not None
    assert invite.token is not None
    assert len(invite.token) > 0
    assert invite.group_id == group.id
    assert invite.created_by == creator.id
    assert invite.expires_at is not None
    assert invite.used_by is None
    assert invite.used_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models/test_invite.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'chaima.models.invite'`

- [ ] **Step 3: Create the Invite model**

```python
# src/chaima/models/invite.py
import datetime
import secrets
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel

from chaima.config import admin_settings


def _default_expiry() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        hours=admin_settings.invite_ttl_hours
    )


class Invite(SQLModel, table=True):
    __tablename__ = "invite"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        unique=True,
        index=True,
    )
    created_by: uuid_pkg.UUID = Field(foreign_key="user.id")
    expires_at: datetime.datetime = Field(
        default_factory=_default_expiry,
    )
    used_by: uuid_pkg.UUID | None = Field(default=None, foreign_key="user.id")
    used_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models/test_invite.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/invite.py tests/test_models/test_invite.py
git commit -m "feat: add Invite model for single-use invite links"
```

---

## Task 4: Invite schemas

**Files:**
- Create: `src/chaima/schemas/invite.py`
- Modify: `src/chaima/schemas/__init__.py`

- [ ] **Step 1: Create invite schemas**

```python
# src/chaima/schemas/invite.py
import datetime
from uuid import UUID

from pydantic import BaseModel


class InviteCreate(BaseModel):
    """Schema for creating an invite — no body fields needed, group_id comes from path."""

    pass


class InviteRead(BaseModel):
    """Full invite details for admin views.

    Attributes
    ----------
    id : UUID
        The invite ID.
    group_id : UUID
        The group this invite is for.
    token : str
        The invite token.
    created_by : UUID
        The user who created the invite.
    expires_at : datetime.datetime
        When the invite expires.
    used_by : UUID or None
        The user who accepted the invite, if any.
    used_at : datetime.datetime or None
        When the invite was accepted.
    """

    id: UUID
    group_id: UUID
    token: str
    created_by: UUID
    expires_at: datetime.datetime
    used_by: UUID | None
    used_at: datetime.datetime | None

    model_config = {"from_attributes": True}


class InviteInfo(BaseModel):
    """Public invite info for the landing page.

    Attributes
    ----------
    group_name : str
        Name of the group being invited to.
    expires_at : datetime.datetime
        When the invite expires.
    is_valid : bool
        Whether the invite can still be used.
    """

    group_name: str
    expires_at: datetime.datetime
    is_valid: bool


class InviteAccept(BaseModel):
    """Schema for accepting an invite as a new user.

    Attributes
    ----------
    email : str
        Email for the new account.
    password : str
        Password for the new account.
    """

    email: str
    password: str
```

- [ ] **Step 2: Add exports to schemas/__init__.py**

Add to `src/chaima/schemas/__init__.py`:

```python
from chaima.schemas.invite import InviteAccept, InviteCreate, InviteInfo, InviteRead
```

And add `"InviteAccept"`, `"InviteCreate"`, `"InviteInfo"`, `"InviteRead"` to the `__all__` list.

- [ ] **Step 3: Commit**

```bash
git add src/chaima/schemas/invite.py src/chaima/schemas/__init__.py
git commit -m "feat: add invite Pydantic schemas"
```

---

## Task 5: Invite service

**Files:**
- Create: `src/chaima/services/invites.py`
- Test: `tests/test_services/test_invites.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_services/test_invites.py
import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.group import Group, UserGroupLink
from chaima.models.invite import Invite
from chaima.models.user import User
from chaima.services import invites as invite_service


@pytest_asyncio.fixture
async def engine():
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


@pytest_asyncio.fixture
async def group(session):
    g = Group(name="Lab Alpha")
    session.add(g)
    await session.flush()
    return g


@pytest_asyncio.fixture
async def admin(session, group):
    u = User(
        email="admin@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=True,
        is_verified=True,
        main_group_id=group.id,
    )
    session.add(u)
    await session.flush()
    link = UserGroupLink(user_id=u.id, group_id=group.id, is_admin=True)
    session.add(link)
    await session.flush()
    return u


@pytest.mark.asyncio
async def test_create_invite(session, group, admin):
    invite = await invite_service.create_invite(
        session, group_id=group.id, created_by=admin.id
    )
    assert invite.group_id == group.id
    assert invite.created_by == admin.id
    assert invite.token is not None
    assert invite.used_by is None


@pytest.mark.asyncio
async def test_get_invite_by_token(session, group, admin):
    invite = await invite_service.create_invite(
        session, group_id=group.id, created_by=admin.id
    )
    found = await invite_service.get_invite_by_token(session, invite.token)
    assert found is not None
    assert found.id == invite.id


@pytest.mark.asyncio
async def test_get_invite_by_token_not_found(session):
    found = await invite_service.get_invite_by_token(session, "nonexistent")
    assert found is None


@pytest.mark.asyncio
async def test_accept_invite_new_user(session, group, admin):
    invite = await invite_service.create_invite(
        session, group_id=group.id, created_by=admin.id
    )
    user = await invite_service.accept_invite_new_user(
        session,
        invite=invite,
        email="newuser@example.com",
        password="securepass123",
    )
    assert user.email == "newuser@example.com"
    assert user.main_group_id == group.id
    assert user.is_superuser is False

    refreshed = await session.get(Invite, invite.id)
    assert refreshed.used_by == user.id
    assert refreshed.used_at is not None

    link_result = await session.get(UserGroupLink, (user.id, group.id))
    assert link_result is not None


@pytest.mark.asyncio
async def test_accept_invite_existing_user(session, group, admin):
    other_group = Group(name="Other Lab")
    session.add(other_group)
    await session.flush()

    existing = User(
        email="existing@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        main_group_id=other_group.id,
    )
    session.add(existing)
    await session.flush()

    invite = await invite_service.create_invite(
        session, group_id=group.id, created_by=admin.id
    )
    await invite_service.accept_invite_existing_user(
        session, invite=invite, user=existing
    )

    refreshed = await session.get(Invite, invite.id)
    assert refreshed.used_by == existing.id
    assert existing.main_group_id == other_group.id  # unchanged

    link_result = await session.get(UserGroupLink, (existing.id, group.id))
    assert link_result is not None


@pytest.mark.asyncio
async def test_accept_expired_invite(session, group, admin):
    invite = await invite_service.create_invite(
        session, group_id=group.id, created_by=admin.id
    )
    invite.expires_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
    session.add(invite)
    await session.flush()

    with pytest.raises(invite_service.InviteExpiredError):
        await invite_service.accept_invite_new_user(
            session, invite=invite, email="late@example.com", password="pass"
        )


@pytest.mark.asyncio
async def test_accept_used_invite(session, group, admin):
    invite = await invite_service.create_invite(
        session, group_id=group.id, created_by=admin.id
    )
    await invite_service.accept_invite_new_user(
        session, invite=invite, email="first@example.com", password="pass"
    )

    with pytest.raises(invite_service.InviteUsedError):
        await invite_service.accept_invite_new_user(
            session, invite=invite, email="second@example.com", password="pass"
        )


@pytest.mark.asyncio
async def test_list_invites(session, group, admin):
    await invite_service.create_invite(session, group_id=group.id, created_by=admin.id)
    await invite_service.create_invite(session, group_id=group.id, created_by=admin.id)

    invites = await invite_service.list_invites(session, group_id=group.id)
    assert len(invites) == 2


@pytest.mark.asyncio
async def test_revoke_invite(session, group, admin):
    invite = await invite_service.create_invite(
        session, group_id=group.id, created_by=admin.id
    )
    await invite_service.revoke_invite(session, invite)

    found = await invite_service.get_invite_by_token(session, invite.token)
    assert found is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_invites.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'chaima.services.invites'`

- [ ] **Step 3: Implement the invite service**

```python
# src/chaima/services/invites.py
"""Service layer for invite link operations."""

import datetime
from uuid import UUID

from fastapi_users.password import PasswordHelper
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.group import UserGroupLink
from chaima.models.invite import Invite
from chaima.models.user import User


class InviteExpiredError(Exception):
    """Raised when an invite has expired."""


class InviteUsedError(Exception):
    """Raised when an invite has already been used."""


password_helper = PasswordHelper()


async def create_invite(
    session: AsyncSession,
    *,
    group_id: UUID,
    created_by: UUID,
) -> Invite:
    """Create a new single-use invite for a group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group to invite to.
    created_by : UUID
        The admin creating the invite.

    Returns
    -------
    Invite
        The newly created invite.
    """
    invite = Invite(group_id=group_id, created_by=created_by)
    session.add(invite)
    await session.flush()
    return invite


async def get_invite_by_token(
    session: AsyncSession,
    token: str,
) -> Invite | None:
    """Look up an invite by its token.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    token : str
        The invite token string.

    Returns
    -------
    Invite or None
        The invite if found, otherwise None.
    """
    result = await session.exec(select(Invite).where(Invite.token == token))
    return result.first()


def _validate_invite(invite: Invite) -> None:
    """Check that an invite is still usable.

    Raises
    ------
    InviteUsedError
        If the invite has already been accepted.
    InviteExpiredError
        If the invite has expired.
    """
    if invite.used_by is not None:
        raise InviteUsedError("This invite has already been used")
    if invite.expires_at < datetime.datetime.now(datetime.UTC):
        raise InviteExpiredError("This invite has expired")


async def accept_invite_new_user(
    session: AsyncSession,
    *,
    invite: Invite,
    email: str,
    password: str,
) -> User:
    """Accept an invite by creating a new user account.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    invite : Invite
        The invite to accept.
    email : str
        Email for the new account.
    password : str
        Password for the new account.

    Returns
    -------
    User
        The newly created user.

    Raises
    ------
    InviteExpiredError
        If the invite has expired.
    InviteUsedError
        If the invite has already been used.
    """
    _validate_invite(invite)

    hashed = password_helper.hash(password)
    user = User(
        email=email,
        hashed_password=hashed,
        is_active=True,
        is_superuser=False,
        is_verified=True,
        main_group_id=invite.group_id,
    )
    session.add(user)
    await session.flush()

    link = UserGroupLink(user_id=user.id, group_id=invite.group_id)
    session.add(link)

    invite.used_by = user.id
    invite.used_at = datetime.datetime.now(datetime.UTC)
    session.add(invite)
    await session.flush()

    return user


async def accept_invite_existing_user(
    session: AsyncSession,
    *,
    invite: Invite,
    user: User,
) -> None:
    """Accept an invite for an existing user (adds them to the group).

    Parameters
    ----------
    session : AsyncSession
        The database session.
    invite : Invite
        The invite to accept.
    user : User
        The existing authenticated user.

    Raises
    ------
    InviteExpiredError
        If the invite has expired.
    InviteUsedError
        If the invite has already been used.
    """
    _validate_invite(invite)

    link = UserGroupLink(user_id=user.id, group_id=invite.group_id)
    session.add(link)

    invite.used_by = user.id
    invite.used_at = datetime.datetime.now(datetime.UTC)
    session.add(invite)
    await session.flush()


async def list_invites(
    session: AsyncSession,
    group_id: UUID,
) -> list[Invite]:
    """List all invites for a group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group to list invites for.

    Returns
    -------
    list[Invite]
        All invites for the group.
    """
    result = await session.exec(
        select(Invite).where(Invite.group_id == group_id)
    )
    return list(result.all())


async def revoke_invite(
    session: AsyncSession,
    invite: Invite,
) -> None:
    """Delete an unused invite.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    invite : Invite
        The invite to revoke.
    """
    await session.delete(invite)
    await session.flush()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_invites.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/invites.py tests/test_services/test_invites.py
git commit -m "feat: add invite service with create, accept, revoke, list"
```

---

## Task 6: Superuser seed logic

**Files:**
- Modify: `src/chaima/app.py`
- Test: `tests/test_seed.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.group import Group, UserGroupLink
from chaima.models.user import User


@pytest_asyncio.fixture
async def engine():
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


@pytest.mark.asyncio
async def test_seed_creates_superuser(session):
    from chaima.app import seed_admin

    await seed_admin(session)

    result = await session.exec(select(User).where(User.is_superuser == True))
    user = result.first()
    assert user is not None
    assert user.email == "admin@chaima.local"
    assert user.main_group_id is not None

    group = await session.get(Group, user.main_group_id)
    assert group is not None
    assert group.name == "Admin"

    link_result = await session.exec(
        select(UserGroupLink).where(
            UserGroupLink.user_id == user.id,
            UserGroupLink.group_id == group.id,
        )
    )
    link = link_result.first()
    assert link is not None
    assert link.is_admin is True


@pytest.mark.asyncio
async def test_seed_is_idempotent(session):
    from chaima.app import seed_admin

    await seed_admin(session)
    await seed_admin(session)

    result = await session.exec(select(User).where(User.is_superuser == True))
    users = list(result.all())
    assert len(users) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_seed.py -v`
Expected: FAIL with `ImportError: cannot import name 'seed_admin'`

- [ ] **Step 3: Add seed_admin function and update lifespan**

In `src/chaima/app.py`:

```python
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.staticfiles import StaticFiles

from chaima.auth import auth_backend, fastapi_users
from chaima.config import admin_settings
from chaima.db import async_session_maker, create_db_and_tables
from chaima.models.group import Group, UserGroupLink
from chaima.models.user import User
from chaima.routers.chemicals import router as chemicals_router
from chaima.routers.containers import router as containers_router
from chaima.routers.ghs import router as ghs_router
from chaima.routers.groups import router as groups_router
from chaima.routers.hazard_tags import router as hazard_tags_router
from chaima.routers.invites import router as invites_router
from chaima.routers.storage_locations import router as storage_locations_router
from chaima.routers.suppliers import router as suppliers_router
from chaima.schemas import UserRead, UserUpdate


async def seed_admin(session: AsyncSession) -> None:
    """Create the initial superuser and group if no superuser exists.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    """
    from fastapi_users.password import PasswordHelper

    result = await session.exec(select(User).where(User.is_superuser == True))
    if result.first() is not None:
        return

    group = Group(name=admin_settings.admin_group_name)
    session.add(group)
    await session.flush()

    ph = PasswordHelper()
    user = User(
        email=admin_settings.admin_email,
        hashed_password=ph.hash(admin_settings.admin_password.get_secret_value()),
        is_active=True,
        is_superuser=True,
        is_verified=True,
        main_group_id=group.id,
    )
    session.add(user)
    await session.flush()

    link = UserGroupLink(user_id=user.id, group_id=group.id, is_admin=True)
    session.add(link)
    await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    async with async_session_maker() as session:
        await seed_admin(session)
    yield


app = FastAPI(title="ChAIMa", lifespan=lifespan)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/api/v1/auth/cookie",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/api/v1/users",
    tags=["users"],
)
app.include_router(groups_router)
app.include_router(ghs_router)
app.include_router(suppliers_router)
app.include_router(storage_locations_router)
app.include_router(hazard_tags_router)
app.include_router(chemicals_router)
app.include_router(containers_router)
app.include_router(invites_router)

_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"))

    @app.get("/{path:path}", include_in_schema=False)
    async def _spa_catch_all(path: str) -> FileResponse:  # noqa: ARG001
        return FileResponse(_static_dir / "index.html")
```

Note: this removes the register router (`get_register_router`) and adds the invites router. The invites router doesn't exist yet — create a stub first:

```python
# src/chaima/routers/invites.py (stub — will be filled in Task 7)
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/invites", tags=["invites"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_seed.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chaima/app.py src/chaima/routers/invites.py tests/test_seed.py
git commit -m "feat: add superuser seed on startup, remove register router"
```

---

## Task 7: Invite router

**Files:**
- Modify: `src/chaima/routers/invites.py`
- Modify: `src/chaima/routers/groups.py` (add invites sub-routes + list members)
- Test: `tests/test_api/test_invites.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api/test_invites.py
import pytest
import pytest_asyncio
from chaima.models.group import Group, UserGroupLink
from chaima.models.invite import Invite
from chaima.models.user import User
from chaima.services.invites import create_invite


@pytest_asyncio.fixture
async def admin_group(session):
    g = Group(name="Admin Lab")
    session.add(g)
    await session.flush()
    return g


@pytest_asyncio.fixture
async def admin_with_group(session, superuser, admin_group):
    superuser.main_group_id = admin_group.id
    session.add(superuser)
    link = UserGroupLink(user_id=superuser.id, group_id=admin_group.id, is_admin=True)
    session.add(link)
    await session.flush()
    return superuser


@pytest.mark.asyncio
async def test_create_invite(superuser_client, session, admin_with_group, admin_group):
    resp = await superuser_client.post(f"/api/v1/groups/{admin_group.id}/invites")
    assert resp.status_code == 201
    data = resp.json()
    assert data["group_id"] == str(admin_group.id)
    assert "token" in data


@pytest.mark.asyncio
async def test_list_invites(superuser_client, session, admin_with_group, admin_group):
    await create_invite(session, group_id=admin_group.id, created_by=admin_with_group.id)
    resp = await superuser_client.get(f"/api/v1/groups/{admin_group.id}/invites")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_invite_info_public(superuser_client, session, admin_with_group, admin_group):
    invite = await create_invite(session, group_id=admin_group.id, created_by=admin_with_group.id)
    resp = await superuser_client.get(f"/api/v1/invites/{invite.token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["group_name"] == "Admin Lab"
    assert data["is_valid"] is True


@pytest.mark.asyncio
async def test_accept_invite_new_user(superuser_client, session, admin_with_group, admin_group):
    invite = await create_invite(session, group_id=admin_group.id, created_by=admin_with_group.id)
    resp = await superuser_client.patch(
        f"/api/v1/invites/{invite.token}",
        json={"email": "newuser@example.com", "password": "secret123"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_revoke_invite(superuser_client, session, admin_with_group, admin_group):
    invite = await create_invite(session, group_id=admin_group.id, created_by=admin_with_group.id)
    resp = await superuser_client.delete(f"/api/v1/invites/{invite.id}")
    assert resp.status_code == 204
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_invites.py -v`
Expected: FAIL (routes not implemented)

- [ ] **Step 3: Implement the invite router**

```python
# src/chaima/routers/invites.py
"""Router for invite link endpoints."""

import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.auth import current_active_user
from chaima.db import get_async_session
from chaima.dependencies import GroupAdminDep, SessionDep, SuperuserDep
from chaima.models.group import Group
from chaima.models.invite import Invite
from chaima.models.user import User
from chaima.schemas.invite import InviteAccept, InviteInfo, InviteRead
from chaima.services import invites as invite_service
from chaima.services.invites import InviteExpiredError, InviteUsedError

router = APIRouter(tags=["invites"])

OptionalUserDep = Annotated[User | None, Depends(current_active_user)]


# --- Group-scoped invite management (authenticated) ---

@router.post(
    "/api/v1/groups/{group_id}/invites",
    response_model=InviteRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite(
    session: SessionDep,
    member: GroupAdminDep,
) -> InviteRead:
    """Create a single-use invite link for this group.

    Parameters
    ----------
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and admin membership link (injected, requires admin role).

    Returns
    -------
    InviteRead
        The newly created invite details.
    """
    group, link = member
    invite = await invite_service.create_invite(
        session, group_id=group.id, created_by=link.user_id
    )
    return InviteRead.model_validate(invite)


@router.get(
    "/api/v1/groups/{group_id}/invites",
    response_model=list[InviteRead],
)
async def list_invites(
    session: SessionDep,
    member: GroupAdminDep,
) -> list[InviteRead]:
    """List all invites for this group.

    Parameters
    ----------
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and admin membership link (injected, requires admin role).

    Returns
    -------
    list[InviteRead]
        All invites for the group.
    """
    group, _link = member
    invites = await invite_service.list_invites(session, group_id=group.id)
    return [InviteRead.model_validate(i) for i in invites]


# --- Public invite endpoints ---

@router.get("/api/v1/invites/{token}", response_model=InviteInfo)
async def get_invite_info(
    token: str,
    session: SessionDep,
) -> InviteInfo:
    """Get public info about an invite for the landing page.

    Parameters
    ----------
    token : str
        The invite token.
    session : AsyncSession
        The database session (injected).

    Returns
    -------
    InviteInfo
        Group name, expiry, and whether the invite is valid.

    Raises
    ------
    HTTPException
        404 if the invite token is not found.
    """
    invite = await invite_service.get_invite_by_token(session, token)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )
    group = await session.get(Group, invite.group_id)
    is_valid = (
        invite.used_by is None
        and invite.expires_at > datetime.datetime.now(datetime.UTC)
    )
    return InviteInfo(
        group_name=group.name,
        expires_at=invite.expires_at,
        is_valid=is_valid,
    )


@router.patch("/api/v1/invites/{token}")
async def accept_invite(
    token: str,
    session: SessionDep,
    body: InviteAccept | None = None,
    user: User | None = Depends(current_active_user),
) -> dict:
    """Accept an invite — register new user or join existing user to group.

    Parameters
    ----------
    token : str
        The invite token.
    session : AsyncSession
        The database session (injected).
    body : InviteAccept or None
        Email/password for new user registration. None if existing user.
    user : User or None
        The authenticated user, if logged in.

    Returns
    -------
    dict
        Success message.

    Raises
    ------
    HTTPException
        404 if invite not found, 400 if expired/used, 422 if no auth and no body.
    """
    invite = await invite_service.get_invite_by_token(session, token)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )

    try:
        if user is not None:
            await invite_service.accept_invite_existing_user(
                session, invite=invite, user=user
            )
            return {"detail": "Joined group successfully"}
        elif body is not None:
            new_user = await invite_service.accept_invite_new_user(
                session, invite=invite, email=body.email, password=body.password
            )
            return {"detail": "Account created and joined group", "user_id": str(new_user.id)}
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Must provide credentials or be logged in",
            )
    except InviteExpiredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invite has expired"
        )
    except InviteUsedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invite has already been used"
        )


@router.delete(
    "/api/v1/invites/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_invite(
    invite_id: UUID,
    session: SessionDep,
    user: SuperuserDep,
) -> None:
    """Revoke an unused invite.

    Parameters
    ----------
    invite_id : UUID
        The invite ID to revoke.
    session : AsyncSession
        The database session (injected).
    user : User
        The authenticated superuser (injected).

    Raises
    ------
    HTTPException
        404 if invite not found.
    """
    invite = await session.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )
    await invite_service.revoke_invite(session, invite)
```

**Note on the `accept_invite` endpoint:** The `current_active_user` dependency will raise 401 for unauthenticated requests. We need to make auth optional. Replace the dependency with a custom one that returns `None` for unauthenticated users:

Add to the top of the file:

```python
from fastapi_users.authentication import Authenticator

async def get_optional_user(
    session: AsyncSession = Depends(get_async_session),
    user: User | None = Depends(
        fastapi_users.current_user(optional=True)
    ),
) -> User | None:
    return user
```

Wait — `fastapi_users` isn't imported in the router. Use the dependency from auth.py instead. Add to `src/chaima/auth.py`:

```python
optional_current_user = fastapi_users.current_user(active=True, optional=True)
```

Then in the router, use:
```python
from chaima.auth import optional_current_user

# In accept_invite:
user: User | None = Depends(optional_current_user),
```

- [ ] **Step 4: Add optional_current_user to auth.py**

Add at the bottom of `src/chaima/auth.py`:

```python
optional_current_user = fastapi_users.current_user(active=True, optional=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_invites.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/chaima/routers/invites.py src/chaima/auth.py tests/test_api/test_invites.py
git commit -m "feat: add invite API endpoints (create, list, info, accept, revoke)"
```

---

## Task 8: Restrict group creation to superuser + add list members endpoint

**Files:**
- Modify: `src/chaima/routers/groups.py`
- Test: `tests/test_api/test_groups.py` (update existing)

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_api/test_groups.py or create if not exists

@pytest.mark.asyncio
async def test_create_group_requires_superuser(client, session, user, membership):
    resp = await client.post("/api/v1/groups", json={"name": "New Lab"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_group_as_superuser(superuser_client, session, superuser):
    resp = await superuser_client.post("/api/v1/groups", json={"name": "New Lab"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_list_members(client, session, user, group, membership):
    resp = await client.get(f"/api/v1/groups/{group.id}/members")
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) >= 1
```

- [ ] **Step 2: Modify the groups router**

In `src/chaima/routers/groups.py`, change `create_group` to require `SuperuserDep`:

```python
@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    session: SessionDep,
    current_user: SuperuserDep,
) -> GroupRead:
```

Add a `list_members` endpoint:

```python
@router.get("/{group_id}/members", response_model=list[MemberRead])
async def list_members(
    session: SessionDep,
    member: GroupMemberDep,
) -> list[MemberRead]:
    """List all members of a group.

    Parameters
    ----------
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and membership link (injected, requires group membership).

    Returns
    -------
    list[MemberRead]
        All members of the group with their user info.
    """
    group, _link = member
    pairs = await group_service.list_members(session, group.id)
    return [
        MemberRead(
            user_id=link.user_id,
            group_id=link.group_id,
            is_admin=link.is_admin,
            joined_at=link.joined_at,
            email=user.email,
        )
        for link, user in pairs
    ]
```

Import `SuperuserDep` from dependencies (already defined there).

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_api/test_groups.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/chaima/routers/groups.py tests/test_api/test_groups.py
git commit -m "feat: restrict group creation to superuser, add list members endpoint"
```

---

## Task 9: PATCH /users/me/main-group endpoint

**Files:**
- Modify: `src/chaima/routers/groups.py` (or create a new user router)
- Test: `tests/test_api/test_user_main_group.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_api/test_user_main_group.py
import pytest
import pytest_asyncio
from chaima.models.group import Group, UserGroupLink


@pytest_asyncio.fixture
async def second_group(session):
    g = Group(name="Second Lab")
    session.add(g)
    await session.flush()
    return g


@pytest_asyncio.fixture
async def second_membership(session, user, second_group):
    link = UserGroupLink(user_id=user.id, group_id=second_group.id)
    session.add(link)
    await session.flush()
    return link


@pytest.mark.asyncio
async def test_update_main_group(client, session, user, group, membership, second_group, second_membership):
    resp = await client.patch(
        "/api/v1/users/me/main-group",
        json={"group_id": str(second_group.id)},
    )
    assert resp.status_code == 200
    assert resp.json()["main_group_id"] == str(second_group.id)


@pytest.mark.asyncio
async def test_update_main_group_not_member(client, session, user, group, membership):
    other = Group(name="Other")
    session.add(other)
    await session.flush()

    resp = await client.patch(
        "/api/v1/users/me/main-group",
        json={"group_id": str(other.id)},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Add the endpoint**

Add to `src/chaima/routers/groups.py` (or a dedicated user router — groups router is fine since it's group-related):

```python
from pydantic import BaseModel

class MainGroupUpdate(BaseModel):
    group_id: UUID


@router.patch("/me/main-group", response_model=None)
```

Actually, this route conflicts with the groups router prefix `/api/v1/groups`. Let's put it on a new mini-router in `app.py` or create `src/chaima/routers/users.py`:

```python
# src/chaima/routers/users.py
"""Router for custom user endpoints (beyond fastapi-users defaults)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from chaima.dependencies import CurrentUserDep, SessionDep
from chaima.models.group import UserGroupLink
from chaima.schemas.user import UserRead


class MainGroupUpdate(BaseModel):
    """Schema for updating a user's main group.

    Attributes
    ----------
    group_id : UUID
        The ID of the group to set as the user's main group.
    """

    group_id: UUID


router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.patch("/me/main-group", response_model=UserRead)
async def update_main_group(
    body: MainGroupUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> UserRead:
    """Update the current user's main group.

    Parameters
    ----------
    body : MainGroupUpdate
        The group ID to set as main group.
    session : AsyncSession
        The database session (injected).
    current_user : User
        The authenticated user (injected).

    Returns
    -------
    UserRead
        The updated user.

    Raises
    ------
    HTTPException
        403 if the user is not a member of the target group.
    """
    result = await session.exec(
        select(UserGroupLink).where(
            UserGroupLink.user_id == current_user.id,
            UserGroupLink.group_id == body.group_id,
        )
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group",
        )
    current_user.main_group_id = body.group_id
    session.add(current_user)
    await session.flush()
    return UserRead.model_validate(current_user)
```

Register in `app.py`:

```python
from chaima.routers.users import router as users_custom_router
# ...
app.include_router(users_custom_router)
```

**Important:** Add this router BEFORE the fastapi-users users router so it takes priority for `/me/main-group`.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_api/test_user_main_group.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/chaima/routers/users.py src/chaima/app.py tests/test_api/test_user_main_group.py
git commit -m "feat: add PATCH /users/me/main-group endpoint"
```

---

## Task 10: Update test fixtures

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_api/conftest.py`

- [ ] **Step 1: Update root conftest user fixture**

In `tests/conftest.py`, update the `user` fixture to set `main_group_id`:

```python
@pytest_asyncio.fixture
async def user(session, group):
    from chaima.models.user import User

    u = User(
        email="alice@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=False,
        main_group_id=group.id,
    )
    session.add(u)
    await session.flush()
    return u
```

Note: `user` now depends on `group` — ensure the `group` fixture is defined before it.

- [ ] **Step 2: Update API test conftest user fixtures**

In `tests/test_api/conftest.py`, update `user` and `superuser`:

```python
@pytest_asyncio.fixture
async def user(session, group):
    u = User(
        email="alice@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        main_group_id=group.id,
    )
    session.add(u)
    await session.flush()
    return u


@pytest_asyncio.fixture
async def superuser(session, group):
    u = User(
        email="admin@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=True,
        is_verified=True,
        main_group_id=group.id,
    )
    session.add(u)
    await session.flush()
    return u
```

Note: both now depend on `group`.

- [ ] **Step 3: Run all tests**

Run: `uv run pytest -v`
Expected: All existing + new tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_api/conftest.py
git commit -m "fix: update test fixtures with main_group_id"
```

---

## Task 11: Frontend types + invite hooks

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/api/hooks/useInvites.ts`
- Modify: `frontend/src/api/hooks/useAuth.ts`

- [ ] **Step 1: Update TypeScript types**

In `frontend/src/types/index.ts`, add `main_group_id` to `UserRead`:

```typescript
export interface UserRead {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  created_at: string;
  main_group_id: string | null;
}
```

Add invite types at the bottom:

```typescript
export interface InviteInfo {
  group_name: string;
  expires_at: string;
  is_valid: boolean;
}

export interface InviteRead {
  id: string;
  group_id: string;
  token: string;
  created_by: string;
  expires_at: string;
  used_by: string | null;
  used_at: string | null;
}

export interface InviteAccept {
  email: string;
  password: string;
}
```

- [ ] **Step 2: Create invite hooks**

```typescript
// frontend/src/api/hooks/useInvites.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { InviteInfo, InviteRead } from "../../types";

export function useInviteInfo(token: string) {
  return useQuery<InviteInfo>({
    queryKey: ["invite", token],
    queryFn: () => client.get(`/invites/${token}`).then((r) => r.data),
    enabled: !!token,
    retry: false,
  });
}

export function useAcceptInviteNewUser(token: string) {
  return useMutation({
    mutationFn: (data: { email: string; password: string }) =>
      client.patch(`/invites/${token}`, data).then((r) => r.data),
  });
}

export function useAcceptInviteExistingUser(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => client.patch(`/invites/${token}`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["currentUser"] });
    },
  });
}

export function useCreateInvite(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      client.post(`/groups/${groupId}/invites`).then((r) => r.data as InviteRead),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invites", groupId] });
    },
  });
}

export function useGroupInvites(groupId: string) {
  return useQuery<InviteRead[]>({
    queryKey: ["invites", groupId],
    queryFn: () => client.get(`/groups/${groupId}/invites`).then((r) => r.data),
    enabled: !!groupId,
  });
}

export function useRevokeInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (inviteId: string) => client.delete(`/invites/${inviteId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invites"] });
    },
  });
}
```

- [ ] **Step 3: Update useAuth — remove useRegister, add useUpdateMainGroup**

In `frontend/src/api/hooks/useAuth.ts`, remove `useRegister` and add:

```typescript
export function useUpdateMainGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) =>
      client.patch("/users/me/main-group", { group_id: groupId }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["currentUser"] });
    },
  });
}
```

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/types/index.ts src/api/hooks/useInvites.ts src/api/hooks/useAuth.ts
git commit -m "feat(frontend): add invite types, hooks, and useUpdateMainGroup"
```

---

## Task 12: InvitePage

**Files:**
- Create: `frontend/src/pages/InvitePage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create InvitePage**

```tsx
// frontend/src/pages/InvitePage.tsx
import { useState, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Divider,
} from "@mui/material";
import { useInviteInfo, useAcceptInviteNewUser, useAcceptInviteExistingUser } from "../api/hooks/useInvites";
import { useCurrentUser, useLogin } from "../api/hooks/useAuth";

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const inviteQuery = useInviteInfo(token ?? "");
  const userQuery = useCurrentUser();
  const acceptNew = useAcceptInviteNewUser(token ?? "");
  const acceptExisting = useAcceptInviteExistingUser(token ?? "");
  const login = useLogin();

  const [mode, setMode] = useState<"choice" | "login" | "register">("choice");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const isLoggedIn = !!userQuery.data;
  const invite = inviteQuery.data;

  if (inviteQuery.isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (inviteQuery.isError || !invite) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
        <Paper sx={{ p: 4, maxWidth: 400, width: "100%", textAlign: "center" }}>
          <Typography variant="h5" sx={{ mb: 2 }}>Invalid Invite</Typography>
          <Typography color="text.secondary">This invite link is invalid or has been removed.</Typography>
        </Paper>
      </Box>
    );
  }

  if (!invite.is_valid) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
        <Paper sx={{ p: 4, maxWidth: 400, width: "100%", textAlign: "center" }}>
          <Typography variant="h5" sx={{ mb: 2 }}>Invite Expired</Typography>
          <Typography color="text.secondary">This invite has expired or has already been used.</Typography>
        </Paper>
      </Box>
    );
  }

  const handleAcceptLoggedIn = () => {
    acceptExisting.mutate(undefined, {
      onSuccess: () => navigate("/"),
    });
  };

  const handleRegister = (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (password !== confirmPassword) {
      setLocalError("Passwords do not match");
      return;
    }
    acceptNew.mutate(
      { email, password },
      {
        onSuccess: () => {
          login.mutate(
            { username: email, password },
            { onSuccess: () => navigate("/") },
          );
        },
        onError: () => setLocalError("Registration failed. Email may already be in use."),
      },
    );
  };

  const handleLogin = (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    login.mutate(
      { username: email, password },
      {
        onSuccess: () => {
          acceptExisting.mutate(undefined, {
            onSuccess: () => navigate("/"),
          });
        },
        onError: () => setLocalError("Invalid email or password"),
      },
    );
  };

  const errorMessage = localError ?? (acceptNew.isError ? "Failed to create account" : null);

  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
      <Paper sx={{ p: 4, maxWidth: 400, width: "100%" }}>
        <Typography variant="h4" sx={{ mb: 1, fontWeight: 700 }}>ChAIMa</Typography>
        <Typography variant="h6" sx={{ mb: 1 }}>
          You've been invited to <strong>{invite.group_name}</strong>
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Accept to join this group.
        </Typography>

        {errorMessage && <Alert severity="error" sx={{ mb: 2 }}>{errorMessage}</Alert>}

        {isLoggedIn ? (
          <Box>
            <Typography variant="body2" sx={{ mb: 2 }}>
              Logged in as {userQuery.data?.email}
            </Typography>
            <Button variant="contained" fullWidth onClick={handleAcceptLoggedIn} disabled={acceptExisting.isPending}>
              {acceptExisting.isPending ? "Joining..." : "Accept Invite"}
            </Button>
          </Box>
        ) : mode === "choice" ? (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <Button variant="contained" fullWidth onClick={() => setMode("register")}>
              Create Account
            </Button>
            <Button variant="outlined" fullWidth onClick={() => setMode("login")}>
              I already have an account
            </Button>
          </Box>
        ) : mode === "register" ? (
          <Box component="form" onSubmit={handleRegister}>
            <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} fullWidth required autoFocus sx={{ mb: 2 }} />
            <TextField label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} fullWidth required sx={{ mb: 2 }} />
            <TextField label="Confirm Password" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} fullWidth required sx={{ mb: 3 }} />
            <Button type="submit" variant="contained" fullWidth disabled={acceptNew.isPending}>
              {acceptNew.isPending ? "Creating account..." : "Create Account & Join"}
            </Button>
            <Divider sx={{ my: 2 }} />
            <Button variant="text" fullWidth onClick={() => setMode("choice")}>Back</Button>
          </Box>
        ) : (
          <Box component="form" onSubmit={handleLogin}>
            <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} fullWidth required autoFocus sx={{ mb: 2 }} />
            <TextField label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} fullWidth required sx={{ mb: 3 }} />
            <Button type="submit" variant="contained" fullWidth disabled={login.isPending}>
              {login.isPending ? "Signing in..." : "Sign in & Join"}
            </Button>
            <Divider sx={{ my: 2 }} />
            <Button variant="text" fullWidth onClick={() => setMode("choice")}>Back</Button>
          </Box>
        )}
      </Paper>
    </Box>
  );
}
```

- [ ] **Step 2: Update App.tsx routes**

In `frontend/src/App.tsx`:
- Add `/invite/:token` as a public route (outside ProtectedRoute)
- Remove `/register` route
- Remove RegisterPage import

```tsx
import InvitePage from "./pages/InvitePage";
// Remove: import RegisterPage from "./pages/RegisterPage";

// In routes:
<Route path="/login" element={<LoginPage />} />
<Route path="/invite/:token" element={<InvitePage />} />
// Remove: <Route path="/register" element={<RegisterPage />} />
```

- [ ] **Step 3: Update LoginPage — remove Register link**

In `frontend/src/pages/LoginPage.tsx`, remove the "No account? Register" link at the bottom (lines 30-32).

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/pages/InvitePage.tsx src/App.tsx src/pages/LoginPage.tsx
git commit -m "feat(frontend): add InvitePage, remove register route"
```

---

## Task 13: Refactor GroupContext to use main_group_id

**Files:**
- Modify: `frontend/src/components/GroupContext.tsx`
- Modify: `frontend/src/components/ProtectedRoute.tsx`

- [ ] **Step 1: Rewrite GroupContext**

```tsx
// frontend/src/components/GroupContext.tsx
import { createContext, useContext, type ReactNode } from "react";
import { useCurrentUser, useUpdateMainGroup } from "../api/hooks/useAuth";

interface GroupContextValue {
  groupId: string | null;
  setGroupId: (id: string) => void;
}

const GroupContext = createContext<GroupContextValue>({
  groupId: null,
  setGroupId: () => {},
});

export function GroupProvider({ children }: { children: ReactNode }) {
  const { data: user } = useCurrentUser();
  const updateMainGroup = useUpdateMainGroup();

  const groupId = user?.main_group_id ?? null;

  const setGroupId = (id: string) => {
    updateMainGroup.mutate(id);
  };

  return (
    <GroupContext.Provider value={{ groupId, setGroupId }}>
      {children}
    </GroupContext.Provider>
  );
}

export function useGroup() {
  const ctx = useContext(GroupContext);
  if (!ctx.groupId) {
    throw new Error("No active group selected");
  }
  return { groupId: ctx.groupId, setGroupId: ctx.setGroupId };
}

export function useGroupOptional() {
  return useContext(GroupContext);
}
```

- [ ] **Step 2: Simplify ProtectedRoute**

```tsx
// frontend/src/components/ProtectedRoute.tsx
import { Navigate, Outlet } from "react-router-dom";
import { CircularProgress, Box } from "@mui/material";
import { useCurrentUser } from "../api/hooks/useAuth";

export default function ProtectedRoute() {
  const { data: user, isLoading, isError } = useCurrentUser();

  if (isLoading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "100vh",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (isError || !user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
```

No more auto-selecting groups or redirecting to settings — every user has a `main_group_id`.

- [ ] **Step 3: Remove localStorage cleanup**

Delete the old `chaima_group_id` from localStorage if it exists. Add a one-time cleanup effect in `GroupProvider`:

```tsx
import { useEffect } from "react";

// Inside GroupProvider:
useEffect(() => {
  localStorage.removeItem("chaima_group_id");
}, []);
```

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/components/GroupContext.tsx src/components/ProtectedRoute.tsx
git commit -m "refactor(frontend): derive group from user.main_group_id, remove localStorage"
```

---

## Task 14: FilterDrawer group chips + multi-group search

**Files:**
- Modify: `frontend/src/components/FilterDrawer.tsx`
- Modify: `frontend/src/pages/SearchPage.tsx`

- [ ] **Step 1: Add group chips to FilterDrawer**

Update `FilterState` to include `selectedGroupIds`:

```typescript
export interface FilterState {
  hasContainers: boolean | undefined;
  hazardTagId: string | undefined;
  ghsCodeId: string | undefined;
  sort: string;
  order: "asc" | "desc";
  selectedGroupIds: string[];
}
```

Update `FilterDrawerProps` to accept groups:

```typescript
import type { HazardTagRead, GHSCodeRead, GroupRead } from "../types";

interface FilterDrawerProps {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  filters: FilterState;
  onApply: (filters: FilterState) => void;
  hazardTags: HazardTagRead[];
  ghsCodes: GHSCodeRead[];
  groups: GroupRead[];
  mainGroupId: string;
}
```

Add group chips section at the top of the drawer (before "Has stock"):

```tsx
export default function FilterDrawer({ open, onOpen, onClose, filters, onApply, hazardTags, ghsCodes, groups, mainGroupId }: FilterDrawerProps) {
  const handleChange = (patch: Partial<FilterState>) => { onApply({ ...filters, ...patch }); };

  const toggleGroup = (groupId: string) => {
    const current = filters.selectedGroupIds;
    const updated = current.includes(groupId)
      ? current.filter((id) => id !== groupId)
      : [...current, groupId];
    if (updated.length > 0) {
      handleChange({ selectedGroupIds: updated });
    }
  };

  return (
    <SwipeableDrawer anchor="bottom" open={open} onOpen={onOpen} onClose={onClose}
      PaperProps={{ sx: { borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: "70vh", px: 3, py: 2 } }}>
      <Box sx={{ width: 40, height: 4, bgcolor: "#444", borderRadius: 2, mx: "auto", mb: 2 }} />
      <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>Filters</Typography>

      {groups.length > 1 && (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>Groups</Typography>
          <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5, mb: 2 }}>
            {groups.map((g) => (
              <Chip
                key={g.id}
                label={g.name}
                size="small"
                color={filters.selectedGroupIds.includes(g.id) ? "primary" : "default"}
                variant={filters.selectedGroupIds.includes(g.id) ? "filled" : "outlined"}
                onClick={() => toggleGroup(g.id)}
              />
            ))}
          </Stack>
          <Divider sx={{ my: 2 }} />
        </>
      )}

      {/* ... rest of existing filters unchanged ... */}
    </SwipeableDrawer>
  );
}
```

- [ ] **Step 2: Update SearchPage for multi-group queries**

In `frontend/src/pages/SearchPage.tsx`:

```tsx
import { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Box, IconButton, CircularProgress, Typography } from "@mui/material";
import TuneIcon from "@mui/icons-material/Tune";
import { useGroup } from "../components/GroupContext";
import { useMultiGroupChemicals } from "../api/hooks/useChemicals";
import { useHazardTags } from "../api/hooks/useHazardTags";
import { useGHSCodes } from "../api/hooks/useGHSCodes";
import { useGroups } from "../api/hooks/useGroups";
import SearchBar from "../components/SearchBar";
import FilterDrawer, { type FilterState } from "../components/FilterDrawer";
import FilterBadges, { type FilterBadge } from "../components/FilterBadges";
import ChemicalCard from "../components/ChemicalCard";
import SwipeableRow from "../components/SwipeableRow";
import UndoSnackbar from "../components/UndoSnackbar";
import { useArchiveContainer, useUnarchiveContainer } from "../api/hooks/useContainers";

export default function SearchPage() {
  const { groupId: mainGroupId } = useGroup();
  const navigate = useNavigate();
  const groupsQuery = useGroups();
  const allGroups = groupsQuery.data ?? [];
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<FilterState>({
    hasContainers: undefined,
    hazardTagId: undefined,
    ghsCodeId: undefined,
    sort: "name",
    order: "asc",
    selectedGroupIds: [mainGroupId],
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [undoState, setUndoState] = useState<{ open: boolean; containerId: string; message: string }>({ open: false, containerId: "", message: "" });

  const searchParams = {
    search: search || undefined,
    has_containers: filters.hasContainers,
    hazard_tag_id: filters.hazardTagId,
    ghs_code_id: filters.ghsCodeId,
    sort: filters.sort as "name" | "created_at" | "updated_at" | "cas",
    order: filters.order,
  };

  // Fire one query per selected group using useQueries (see useMultiGroupChemicals below)
  const chemicalQueries = useMultiGroupChemicals(filters.selectedGroupIds, searchParams);

  // Merge results from all groups
  const chemicals = useMemo(() => {
    return chemicalQueries.flatMap((q) => q.data?.items ?? []);
  }, [chemicalQueries]);

  const isLoading = chemicalQueries.some((q) => q.isLoading);
  const isError = chemicalQueries.some((q) => q.isError);

  const hazardTagsQuery = useHazardTags(mainGroupId);
  const ghsCodesQuery = useGHSCodes();
  const archiveContainer = useArchiveContainer(mainGroupId);
  const unarchiveContainer = useUnarchiveContainer(mainGroupId);

  const hazardTags = hazardTagsQuery.data?.items ?? [];
  const ghsCodes = ghsCodesQuery.data?.items ?? [];

  // Build group name lookup
  const groupNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const g of allGroups) map[g.id] = g.name;
    return map;
  }, [allGroups]);

  const badges = useMemo(() => {
    const result: FilterBadge[] = [];
    // Show group badges only if not just the main group
    if (
      filters.selectedGroupIds.length !== 1 ||
      filters.selectedGroupIds[0] !== mainGroupId
    ) {
      for (const gid of filters.selectedGroupIds) {
        if (gid !== mainGroupId && groupNames[gid]) {
          result.push({ key: `group:${gid}`, label: groupNames[gid], color: "primary" });
        }
      }
    }
    if (filters.hasContainers) result.push({ key: "hasContainers", label: "Has stock", color: "success" });
    if (filters.hazardTagId) {
      const tag = hazardTags.find((t) => t.id === filters.hazardTagId);
      if (tag) result.push({ key: "hazardTagId", label: tag.name, color: "error" });
    }
    if (filters.ghsCodeId) {
      const code = ghsCodes.find((c) => c.id === filters.ghsCodeId);
      if (code) result.push({ key: "ghsCodeId", label: code.code, color: "warning" });
    }
    return result;
  }, [filters, hazardTags, ghsCodes, mainGroupId, groupNames]);

  const handleRemoveBadge = useCallback((key: string) => {
    if (key.startsWith("group:")) {
      const gid = key.slice(6);
      setFilters((prev) => ({
        ...prev,
        selectedGroupIds: prev.selectedGroupIds.filter((id) => id !== gid),
      }));
    } else {
      setFilters((prev) => ({ ...prev, [key]: undefined }));
    }
  }, []);

  const handleArchive = useCallback((containerId: string, identifier: string) => {
    archiveContainer.mutate(containerId, {
      onSuccess: () => { setUndoState({ open: true, containerId, message: `Container ${identifier} archived` }); },
    });
  }, [archiveContainer]);

  const handleUndo = useCallback(() => {
    unarchiveContainer.mutate(undoState.containerId);
    setUndoState((prev) => ({ ...prev, open: false }));
  }, [unarchiveContainer, undoState.containerId]);

  return (
    <Box sx={{ p: 2, pb: 4 }}>
      <Box sx={{ display: "flex", gap: 1, mb: 1 }}>
        <Box sx={{ flex: 1 }}><SearchBar value={search} onChange={setSearch} /></Box>
        <IconButton onClick={() => setDrawerOpen(true)} sx={{ bgcolor: "background.paper", border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
          <TuneIcon />
        </IconButton>
      </Box>
      <FilterBadges badges={badges} onRemove={handleRemoveBadge} />
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1, mt: 1 }}>
        {isLoading && <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress /></Box>}
        {isError && <Typography color="error" sx={{ textAlign: "center", py: 4 }}>Failed to load chemicals</Typography>}
        {chemicals.map((chemical) => (
          <SwipeableRow key={chemical.id} onSwipeRight={() => navigate(`/containers/new?chemicalId=${chemical.id}`)}>
            <ChemicalCard chemical={chemical} containers={[]} hazardTags={[]} locationPaths={{}} supplierNames={{}} onAddContainer={() => navigate(`/containers/new?chemicalId=${chemical.id}`)} />
          </SwipeableRow>
        ))}
        {!isLoading && chemicals.length === 0 && (
          <Typography color="text.secondary" sx={{ textAlign: "center", py: 4 }}>
            {search ? "No chemicals found" : "No chemicals yet"}
          </Typography>
        )}
      </Box>
      <FilterDrawer
        open={drawerOpen}
        onOpen={() => setDrawerOpen(true)}
        onClose={() => setDrawerOpen(false)}
        filters={filters}
        onApply={setFilters}
        hazardTags={hazardTags}
        ghsCodes={ghsCodes}
        groups={allGroups}
        mainGroupId={mainGroupId}
      />
      <UndoSnackbar open={undoState.open} message={undoState.message} onUndo={handleUndo} onClose={() => setUndoState((prev) => ({ ...prev, open: false }))} />
    </Box>
  );
}
```

**Note on hooks in a loop:** React hooks can't be called in a loop/map. Instead, create a custom hook `useMultiGroupChemicals` that uses `useQueries`:

```typescript
// Add to frontend/src/api/hooks/useChemicals.ts

import { useQueries } from "@tanstack/react-query";

export function useMultiGroupChemicals(groupIds: string[], params: ChemicalSearchParams) {
  return useQueries({
    queries: groupIds.map((gid) => ({
      queryKey: ["chemicals", gid, params],
      queryFn: ({ pageParam }: { pageParam?: number }) =>
        client.get(`/groups/${gid}/chemicals`, {
          params: { ...params, offset: 0, limit: params.limit ?? 100 },
        }).then((r) => r.data as PaginatedResponse<ChemicalRead>),
    })),
  });
}
```

Then in SearchPage, replace the loop with:

```typescript
import { useMultiGroupChemicals } from "../api/hooks/useChemicals";

const chemicalQueries = useMultiGroupChemicals(filters.selectedGroupIds, searchParams);

const chemicals = useMemo(() => {
  return chemicalQueries.flatMap((q) => q.data?.items ?? []);
}, [chemicalQueries]);

const isLoading = chemicalQueries.some((q) => q.isLoading);
const isError = chemicalQueries.some((q) => q.isError);
```

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/components/FilterDrawer.tsx src/pages/SearchPage.tsx src/api/hooks/useChemicals.ts
git commit -m "feat(frontend): multi-group search with group chips in FilterDrawer"
```

---

## Task 15: Settings page redesign

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Rewrite SettingsPage**

Replace the "Active Group" card with a "Main Group" card, and add a superuser panel:

```tsx
// frontend/src/pages/SettingsPage.tsx
import { useState } from "react";
import {
  Box,
  Typography,
  TextField,
  MenuItem,
  Button,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  Stack,
  Alert,
  Snackbar,
} from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import AddIcon from "@mui/icons-material/Add";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { useGroupOptional } from "../components/GroupContext";
import { useGroups } from "../api/hooks/useGroups";
import { useCurrentUser, useLogout, useUpdateMainGroup } from "../api/hooks/useAuth";
import {
  useSuppliers,
  useCreateSupplier,
  useUpdateSupplier,
  useDeleteSupplier,
} from "../api/hooks/useSuppliers";
import {
  useHazardTags,
  useCreateHazardTag,
  useUpdateHazardTag,
  useDeleteHazardTag,
} from "../api/hooks/useHazardTags";
import {
  useCreateInvite,
  useGroupInvites,
  useRevokeInvite,
} from "../api/hooks/useInvites";
import { useGroupMembers, useUpdateMember, useCreateGroup } from "../api/hooks/useGroups";
import type { GroupRead } from "../types";

export default function SettingsPage() {
  const { groupId } = useGroupOptional();
  const groupsQuery = useGroups();
  const userQuery = useCurrentUser();
  const logout = useLogout();
  const updateMainGroup = useUpdateMainGroup();

  const groups = groupsQuery.data ?? [];
  const isSuperuser = userQuery.data?.is_superuser ?? false;

  return (
    <Box sx={{ p: 2, maxWidth: 600 }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        Settings
      </Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            Account
          </Typography>
          <Typography variant="body2">
            {userQuery.data?.email ?? "Loading..."}
          </Typography>
        </CardContent>
      </Card>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            Main Group
          </Typography>
          <TextField
            select
            value={groupId ?? ""}
            onChange={(e) => updateMainGroup.mutate(e.target.value)}
            fullWidth
            size="small"
          >
            {groups.map((g) => (
              <MenuItem key={g.id} value={g.id}>
                {g.name}
              </MenuItem>
            ))}
          </TextField>
        </CardContent>
      </Card>

      {groupId && <SupplierSection groupId={groupId} />}
      {groupId && <HazardTagSection groupId={groupId} />}

      {isSuperuser && <SuperuserPanel groups={groups} />}

      <Button
        variant="outlined"
        color="error"
        fullWidth
        sx={{ mt: 2 }}
        onClick={() =>
          logout.mutate(undefined, {
            onSuccess: () => (window.location.href = "/login"),
          })
        }
      >
        Logout
      </Button>
    </Box>
  );
}

// SupplierSection and HazardTagSection remain unchanged from existing code

function SuperuserPanel({ groups }: { groups: GroupRead[] }) {
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [groupDescription, setGroupDescription] = useState("");
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const createGroup = useCreateGroup();

  const handleCreateGroup = () => {
    createGroup.mutate(
      { name: groupName, description: groupDescription || undefined },
      { onSuccess: () => { setCreateDialogOpen(false); setGroupName(""); setGroupDescription(""); } },
    );
  };

  return (
    <>
      <Typography variant="h6" fontWeight={600} sx={{ mt: 3, mb: 1 }}>
        Admin Panel
      </Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="subtitle2" color="text.secondary">
              Groups
            </Typography>
            <IconButton size="small" onClick={() => setCreateDialogOpen(true)}>
              <AddIcon fontSize="small" />
            </IconButton>
          </Box>
          <List dense disablePadding>
            {groups.map((g) => (
              <ListItem
                key={g.id}
                disablePadding
                onClick={() => setSelectedGroupId(g.id)}
                sx={{ cursor: "pointer", borderRadius: 1, "&:hover": { bgcolor: "action.hover" } }}
              >
                <ListItemText primary={g.name} secondary={g.description} />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      {selectedGroupId && (
        <GroupAdminPanel
          groupId={selectedGroupId}
          onClose={() => setSelectedGroupId(null)}
        />
      )}

      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Create Group</DialogTitle>
        <DialogContent>
          <TextField label="Name" value={groupName} onChange={(e) => setGroupName(e.target.value)} fullWidth autoFocus sx={{ mt: 1, mb: 2 }} />
          <TextField label="Description" value={groupDescription} onChange={(e) => setGroupDescription(e.target.value)} fullWidth multiline rows={2} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreateGroup} disabled={!groupName}>Create</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}


function GroupAdminPanel({ groupId, onClose }: { groupId: string; onClose: () => void }) {
  const membersQuery = useGroupMembers(groupId);
  const invitesQuery = useGroupInvites(groupId);
  const createInvite = useCreateInvite(groupId);
  const revokeInvite = useRevokeInvite();
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const members = membersQuery.data ?? [];
  const invites = invitesQuery.data ?? [];
  const pendingInvites = invites.filter((i) => !i.used_by);

  const handleCreateInvite = () => {
    createInvite.mutate(undefined, {
      onSuccess: (data) => {
        const url = `${window.location.origin}/invite/${data.token}`;
        navigator.clipboard.writeText(url);
        setCopiedToken(data.token);
      },
    });
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: "flex", justifyContent: "space-between", mb: 2 }}>
          <Typography variant="subtitle2" color="text.secondary">Group Details</Typography>
          <Button size="small" onClick={onClose}>Close</Button>
        </Box>

        <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>Members</Typography>
        <List dense disablePadding>
          {members.map((m) => (
            <ListItem key={m.user_id} disablePadding>
              <ListItemText
                primary={m.email}
                secondary={m.is_admin ? "Admin" : "Member"}
              />
            </ListItem>
          ))}
        </List>

        <Box sx={{ mt: 2, mb: 1, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Typography variant="body2" fontWeight={600}>Invite Links</Typography>
          <Button size="small" variant="outlined" onClick={handleCreateInvite} disabled={createInvite.isPending}>
            Generate Link
          </Button>
        </Box>

        {pendingInvites.length === 0 && (
          <Typography variant="body2" color="text.secondary">No pending invites</Typography>
        )}
        <List dense disablePadding>
          {pendingInvites.map((inv) => (
            <ListItem
              key={inv.id}
              disablePadding
              secondaryAction={
                <Box>
                  <IconButton
                    size="small"
                    onClick={() => {
                      navigator.clipboard.writeText(`${window.location.origin}/invite/${inv.token}`);
                      setCopiedToken(inv.token);
                    }}
                  >
                    <ContentCopyIcon fontSize="small" />
                  </IconButton>
                  <IconButton size="small" onClick={() => revokeInvite.mutate(inv.id)}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Box>
              }
            >
              <ListItemText
                primary={`...${inv.token.slice(-8)}`}
                secondary={`Expires: ${new Date(inv.expires_at).toLocaleDateString()}`}
              />
            </ListItem>
          ))}
        </List>

        <Snackbar
          open={!!copiedToken}
          autoHideDuration={2000}
          onClose={() => setCopiedToken(null)}
          message="Invite link copied to clipboard"
        />
      </CardContent>
    </Card>
  );
}
```

Keep the existing `SupplierSection` and `HazardTagSection` functions unchanged — just copy them from the current file.

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/pages/SettingsPage.tsx
git commit -m "feat(frontend): redesign SettingsPage with main group + superuser admin panel"
```

---

## Task 16: Delete RegisterPage

**Files:**
- Delete: `frontend/src/pages/RegisterPage.tsx`

- [ ] **Step 1: Remove the file**

```bash
rm frontend/src/pages/RegisterPage.tsx
```

- [ ] **Step 2: Verify no remaining imports**

Search for `RegisterPage` in the frontend — it should already be removed from `App.tsx` in Task 12.

- [ ] **Step 3: Commit**

```bash
git add -u frontend/src/pages/RegisterPage.tsx
git commit -m "chore(frontend): remove RegisterPage (registration via invite only)"
```

---

## Task 17: Final integration test

- [ ] **Step 1: Run all backend tests**

```bash
uv run pytest -v
```

Expected: All PASS

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors

- [ ] **Step 3: Manual smoke test**

Start the app:
```bash
uv run chaima run
```

Verify:
1. App starts, seeds admin@chaima.local superuser + "Admin" group
2. Login with admin@chaima.local / changeme works
3. Settings page shows "Main Group" (not "Active Group"), superuser panel visible
4. Create a new group in admin panel
5. Generate invite link, open in incognito → InvitePage shows
6. Create account via invite → logged in → redirected to search
7. FilterDrawer shows group chips when user is in multiple groups
8. Toggling groups on/off changes search results

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: integration fixes from smoke test"
```
