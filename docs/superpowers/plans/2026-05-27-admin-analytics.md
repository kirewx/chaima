# Admin Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a superuser-only Analytics section under Settings that shows per-user activity (logins, searches, creates, photo-extracts), top searches, and slow endpoints — backed by an event log, login counters on the user, and a slow-request log. All telemetry is best-effort (must not block or fail user requests).

**Architecture:** Two new SQLite tables (`event`, `event_daily`, `slow_request`) + two new columns on `user` (`last_login_at`, `login_count`). A `services/events.py` helper schedules writes via FastAPI `BackgroundTasks` so they run after the response is sent. A new `/api/v1/admin/analytics/*` router exposes aggregated read endpoints behind the superuser guard. A nightly external cron calls `_compact` to roll old events into `event_daily` and prune.

**Tech Stack:** FastAPI, SQLModel, SQLAlchemy 2.x async, fastapi-users, aiosqlite, Alembic, Pydantic v2, React + MUI v9 (core only, no `@mui/x-data-grid`), React-Query, axios.

**Spec:** `docs/superpowers/specs/2026-05-27-admin-analytics-design.md` (committed as `02f9294`).

---

## File Map

**Backend — create:**
- `src/chaima/models/analytics.py` — Event, EventDaily, SlowRequest
- `src/chaima/services/events.py` — `log_event` helper + `_persist_event`
- `src/chaima/services/analytics.py` — read-side aggregations + compaction
- `src/chaima/middleware/__init__.py` — empty package marker
- `src/chaima/middleware/slow_request.py` — ASGI middleware
- `src/chaima/routers/admin_analytics.py` — 5 admin endpoints
- `alembic/versions/<rev>_add_analytics_tables.py`
- `tests/test_models/test_analytics.py`
- `tests/test_services/test_events.py`
- `tests/test_services/test_analytics.py`
- `tests/test_middleware/__init__.py`
- `tests/test_middleware/test_slow_request.py`
- `tests/test_api/test_admin_analytics.py`
- `tests/test_api/test_admin_analytics_writes.py` — checks events emitted by existing endpoints

**Backend — modify:**
- `src/chaima/db.py` — set `PRAGMA journal_mode=WAL` on connect via event listener
- `src/chaima/models/__init__.py` — re-export Event, EventDaily, SlowRequest
- `src/chaima/models/user.py` — add `last_login_at`, `login_count`
- `src/chaima/auth.py` — override `UserManager.on_after_login` + `authenticate`
- `src/chaima/app.py` — mount slow-request middleware, include analytics router
- `src/chaima/routers/chemicals.py` — emit `search_executed`, `chemical_created`, `photo_extract`
- `src/chaima/routers/containers.py` — emit `container_created`
- `src/chaima/routers/orders.py` — emit `order_created`
- `src/chaima/routers/wishlist.py` — emit `wishlist_added`
- `src/chaima/services/enrich.py` — emit `pubchem_fetch` after each `enrich_one`
- `tests/conftest.py` — add `patch_events_session_maker` fixture
- `tests/test_api/conftest.py` — same

**Frontend — create:**
- `frontend/src/api/hooks/useAdminAnalytics.ts` — 4 useQuery hooks
- `frontend/src/components/settings/AnalyticsSection.tsx`

**Frontend — modify:**
- `frontend/src/types/index.ts` — add analytics response types
- `frontend/src/components/settings/SettingsNav.tsx` — extend `SettingsSectionKey`
- `frontend/src/pages/SettingsPage.tsx` — add nav item + render branch

---

## Phase 1 — Foundation

### Task 1: SQLite WAL mode

**Files:**
- Modify: `src/chaima/db.py`
- Create: `tests/test_db_pragmas.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_db_pragmas.py`:

```python
"""Verify SQLite WAL mode is enabled for the production engine."""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from chaima.db import _set_sqlite_pragmas


@pytest.mark.asyncio
async def test_wal_mode_pragma_applied_on_file_engine(tmp_path):
    """When connecting to a real file DB, journal_mode should be WAL."""
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    # Attach the same pragma listener the app uses.
    from sqlalchemy import event as sa_event
    sync_engine = engine.sync_engine
    sa_event.listen(sync_engine, "connect", _set_sqlite_pragmas)

    async with engine.connect() as conn:
        result = await conn.exec_driver_sql("PRAGMA journal_mode")
        mode = result.scalar_one()
    await engine.dispose()
    assert mode.lower() == "wal"


def test_pragma_listener_is_idempotent():
    """Calling _set_sqlite_pragmas twice on the same connection should not raise."""
    import sqlite3
    raw = sqlite3.connect(":memory:")
    _set_sqlite_pragmas(raw, None)
    _set_sqlite_pragmas(raw, None)
    raw.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_db_pragmas.py -v`
Expected: `ImportError: cannot import name '_set_sqlite_pragmas' from 'chaima.db'`.

- [ ] **Step 3: Add the pragma listener to `db.py`**

Replace the entire body of `src/chaima/db.py` with:

```python
from collections.abc import AsyncGenerator

from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.config import settings

# Share metadata AND registry so fastapi-users (DeclarativeBase) and SQLModel
# models all register in the same metadata and can cross-reference each other.
# Alembic uses one target.


class Base(DeclarativeBase):
    metadata = SQLModel.metadata
    registry = SQLModel._sa_registry


def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    """Apply SQLite pragmas on every new connection.

    WAL mode lets readers and writers operate concurrently; without it,
    an analytics SELECT could briefly block a user-facing INSERT.

    Idempotent: re-running on the same connection is a no-op for journal_mode.
    """
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


engine = create_async_engine(settings.database_url, echo=False)

# Only attach to SQLite engines — Postgres etc. ignore these pragmas anyway,
# but the listener would fail on non-sqlite connections.
if engine.dialect.name == "sqlite":
    sa_event.listen(engine.sync_engine, "connect", _set_sqlite_pragmas)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_db_and_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
        await session.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_db_pragmas.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Confirm the existing test suite still passes**

Run: `uv run pytest -q`
Expected: no regressions. (`:memory:` in-memory engines used by existing fixtures default to WAL silently for in-memory DBs anyway — pragma is a no-op there.)

- [ ] **Step 6: Commit**

```
git add src/chaima/db.py tests/test_db_pragmas.py
git commit -m "feat(db): enable SQLite WAL mode for concurrent reads"
```

---

### Task 2: User columns — `last_login_at`, `login_count`

**Files:**
- Modify: `src/chaima/models/user.py`
- Create: `tests/test_models/test_user_login_counters.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models/test_user_login_counters.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models/test_user_login_counters.py -v`
Expected: FAIL with `AttributeError` on `last_login_at` / `login_count`.

- [ ] **Step 3: Add the columns**

In `src/chaima/models/user.py`, replace the entire class body with:

```python
import datetime
import uuid as uuid_pkg

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chaima.db import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"

    main_group_id: Mapped[uuid_pkg.UUID | None] = mapped_column(
        ForeignKey("group.id"), nullable=True, default=None
    )
    dark_mode: Mapped[bool] = mapped_column(default=False, server_default="0", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Analytics: cheap counters bumped from UserManager.on_after_login.
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    login_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    created_chemicals: Mapped[list["Chemical"]] = relationship(
        "Chemical", back_populates="creator", foreign_keys="[Chemical.created_by]"
    )
    created_containers: Mapped[list["Container"]] = relationship(
        "Container", back_populates="creator", foreign_keys="[Container.created_by]"
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_models/test_user_login_counters.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Confirm no regressions in other user-related tests**

Run: `uv run pytest tests/test_models/ tests/test_api/test_users.py -q`
Expected: no failures.

- [ ] **Step 6: Commit**

```
git add src/chaima/models/user.py tests/test_models/test_user_login_counters.py
git commit -m "feat(user): add last_login_at and login_count columns"
```

---

### Task 3: Analytics models — Event, EventDaily, SlowRequest

**Files:**
- Create: `src/chaima/models/analytics.py`
- Modify: `src/chaima/models/__init__.py`
- Create: `tests/test_models/test_analytics.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models/test_analytics.py`:

```python
import datetime
import uuid as uuid_pkg

import pytest
from sqlmodel import select

from chaima.models.analytics import Event, EventDaily, EventType, SlowRequest


@pytest.mark.asyncio
async def test_event_round_trip(session, user, group):
    e = Event(
        user_id=user.id,
        group_id=group.id,
        type=EventType.SEARCH_EXECUTED,
        payload={"query": "acetone", "result_count": 3},
    )
    session.add(e)
    await session.flush()
    fetched = (await session.exec(select(Event).where(Event.id == e.id))).first()
    assert fetched is not None
    assert fetched.type == "search_executed"
    assert fetched.payload == {"query": "acetone", "result_count": 3}
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_event_user_id_and_group_id_can_be_null(session):
    """login_failure uses NULL user_id; non-group events use NULL group_id."""
    e = Event(
        user_id=None, group_id=None,
        type=EventType.LOGIN_FAILURE,
        payload={"email_attempted": "x@example.com"},
    )
    session.add(e)
    await session.flush()
    assert e.id is not None


@pytest.mark.asyncio
async def test_event_daily_round_trip(session, user):
    today = datetime.date(2026, 5, 1)
    d = EventDaily(day=today, user_id=user.id, type="login_success", count=14)
    session.add(d)
    await session.flush()
    fetched = (await session.exec(
        select(EventDaily).where(EventDaily.day == today, EventDaily.user_id == user.id)
    )).first()
    assert fetched is not None
    assert fetched.count == 14


@pytest.mark.asyncio
async def test_slow_request_round_trip(session, user):
    r = SlowRequest(
        user_id=user.id,
        method="POST",
        path="/api/v1/groups/{group_id}/chemicals/extract-from-photo",
        status=200,
        duration_ms=1850,
    )
    session.add(r)
    await session.flush()
    fetched = (await session.exec(
        select(SlowRequest).where(SlowRequest.id == r.id)
    )).first()
    assert fetched is not None
    assert fetched.duration_ms == 1850


def test_event_type_enum_has_all_expected_values():
    expected = {
        "login_success", "login_failure", "search_executed",
        "chemical_created", "container_created", "order_created",
        "wishlist_added", "photo_extract", "pubchem_fetch",
    }
    assert {v.value for v in EventType} == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models/test_analytics.py -v`
Expected: `ModuleNotFoundError: No module named 'chaima.models.analytics'`.

- [ ] **Step 3: Create the models**

Create `src/chaima/models/analytics.py`:

```python
"""Analytics tables: raw events, daily aggregates, slow-request log."""
from __future__ import annotations

import datetime
import enum
import uuid as uuid_pkg

from sqlalchemy import JSON, Column, DateTime, Index, func
from sqlmodel import Field, SQLModel


class EventType(str, enum.Enum):
    """Whitelist of valid event.type values.

    Stored as plain ``str`` in the DB (no SQL Enum) so we can add new types
    later without a migration. Use these constants when writing events.
    """
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    SEARCH_EXECUTED = "search_executed"
    CHEMICAL_CREATED = "chemical_created"
    CONTAINER_CREATED = "container_created"
    ORDER_CREATED = "order_created"
    WISHLIST_ADDED = "wishlist_added"
    PHOTO_EXTRACT = "photo_extract"
    PUBCHEM_FETCH = "pubchem_fetch"


class Event(SQLModel, table=True):
    __tablename__ = "event"
    __table_args__ = (
        Index("ix_event_user_created", "user_id", "created_at"),
        Index("ix_event_type_created", "type", "created_at"),
    )

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    user_id: uuid_pkg.UUID | None = Field(
        default=None, foreign_key="user.id", index=True, nullable=True,
    )
    group_id: uuid_pkg.UUID | None = Field(
        default=None, foreign_key="group.id", index=True, nullable=True,
    )
    type: str = Field(index=True)
    payload: dict | None = Field(
        default=None, sa_column=Column(JSON, nullable=True),
    )
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
            index=True,
        ),
    )


class EventDaily(SQLModel, table=True):
    """Per-day aggregate row written by the nightly compaction job."""
    __tablename__ = "event_daily"

    day: datetime.date = Field(primary_key=True)
    user_id: uuid_pkg.UUID = Field(primary_key=True, foreign_key="user.id")
    type: str = Field(primary_key=True)
    group_id: uuid_pkg.UUID | None = Field(default=None, foreign_key="group.id")
    count: int = Field(default=0, nullable=False)


class SlowRequest(SQLModel, table=True):
    __tablename__ = "slow_request"
    __table_args__ = (
        Index("ix_slow_path_created", "path", "created_at"),
    )

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    user_id: uuid_pkg.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True,
    )
    method: str
    path: str = Field(index=True)
    status: int
    duration_ms: int
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
            index=True,
        ),
    )
```

- [ ] **Step 4: Re-export from `models/__init__.py`**

In `src/chaima/models/__init__.py`, add the import line in alphabetical order:

```python
from chaima.models.analytics import Event, EventDaily, EventType, SlowRequest
```

Add to `__all__`:

```python
    "Event",
    "EventDaily",
    "EventType",
    "SlowRequest",
```

(Maintain alphabetic order in `__all__`.)

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_models/test_analytics.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```
git add src/chaima/models/analytics.py src/chaima/models/__init__.py tests/test_models/test_analytics.py
git commit -m "feat(analytics): add Event, EventDaily, SlowRequest models"
```

---

### Task 4: Alembic migration for User columns + analytics tables

**Files:**
- Create: `alembic/versions/<rev>_add_analytics_tables.py` (generate the rev hash)

- [ ] **Step 1: Generate the migration**

Run: `uv run alembic revision -m "add analytics tables and user login counters"`
Note the generated revision hash; the file will be `alembic/versions/<hash>_add_analytics_tables_and_user_login_counters.py`.

- [ ] **Step 2: Replace the file body with the hand-written migration**

Open the generated file and replace `upgrade()` and `downgrade()` with:

```python
def upgrade() -> None:
    """Upgrade schema."""
    # --- analytics tables ---
    op.create_table(
        "event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_event_user_id"), "event", ["user_id"], unique=False)
    op.create_index(op.f("ix_event_group_id"), "event", ["group_id"], unique=False)
    op.create_index(op.f("ix_event_type"), "event", ["type"], unique=False)
    op.create_index(op.f("ix_event_created_at"), "event", ["created_at"], unique=False)
    op.create_index("ix_event_user_created", "event", ["user_id", "created_at"], unique=False)
    op.create_index("ix_event_type_created", "event", ["type", "created_at"], unique=False)

    op.create_table(
        "event_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("day", "user_id", "type"),
    )

    op.create_table(
        "slow_request",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("method", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_slow_request_path"), "slow_request", ["path"], unique=False)
    op.create_index(op.f("ix_slow_request_created_at"), "slow_request", ["created_at"], unique=False)
    op.create_index("ix_slow_path_created", "slow_request", ["path", "created_at"], unique=False)

    # --- user counters ---
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("login_count", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("login_count")
        batch_op.drop_column("last_login_at")

    op.drop_index("ix_slow_path_created", table_name="slow_request")
    op.drop_index(op.f("ix_slow_request_created_at"), table_name="slow_request")
    op.drop_index(op.f("ix_slow_request_path"), table_name="slow_request")
    op.drop_table("slow_request")

    op.drop_table("event_daily")

    op.drop_index("ix_event_type_created", table_name="event")
    op.drop_index("ix_event_user_created", table_name="event")
    op.drop_index(op.f("ix_event_created_at"), table_name="event")
    op.drop_index(op.f("ix_event_type"), table_name="event")
    op.drop_index(op.f("ix_event_group_id"), table_name="event")
    op.drop_index(op.f("ix_event_user_id"), table_name="event")
    op.drop_table("event")
```

Confirm the file's top still contains:

```python
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel
```

And the `revision` / `down_revision` lines were auto-filled by Alembic — leave them.

- [ ] **Step 3: Run the migration against the dev DB**

Run: `uv run alembic upgrade head`
Expected: no errors; `chaima.db` (or whichever `database_url` is configured) gains the new tables.

- [ ] **Step 4: Verify the downgrade is reversible**

Run: `uv run alembic downgrade -1`
Then: `uv run alembic upgrade head`
Expected: both succeed.

- [ ] **Step 5: Commit**

```
git add alembic/versions/
git commit -m "feat(alembic): add analytics tables and user login counters"
```

---

### Task 5: `services/events.py` — `log_event` helper

**Files:**
- Create: `src/chaima/services/events.py`
- Modify: `tests/conftest.py` — add `patch_events_session_maker` fixture
- Modify: `tests/test_api/conftest.py` — same
- Create: `tests/test_services/test_events.py`

- [ ] **Step 1: Add the shared fixture to both conftests**

In `tests/conftest.py`, append at the bottom:

```python
@pytest_asyncio.fixture
async def patch_events_session_maker(engine, monkeypatch):
    """Point `services.events` at the test engine so background-task writes hit it."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession
    test_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("chaima.services.events.async_session_maker", test_maker)
    return test_maker
```

In `tests/test_api/conftest.py`, append the same fixture verbatim.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_services/test_events.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_events.py -v`
Expected: `ModuleNotFoundError: No module named 'chaima.services.events'`.

- [ ] **Step 4: Implement the helper**

Create `src/chaima/services/events.py`:

```python
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
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_services/test_events.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```
git add src/chaima/services/events.py tests/conftest.py tests/test_api/conftest.py tests/test_services/test_events.py
git commit -m "feat(events): add log_event helper with background-task persistence"
```

---

## Phase 2 — Write Paths

### Task 6: Login success + failure hooks

**Files:**
- Modify: `src/chaima/auth.py`
- Create: `tests/test_services/test_auth_login_hooks.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_services/test_auth_login_hooks.py`:

```python
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
    async def _none(_creds):
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

    async def _ok(_creds):
        return user

    from fastapi_users import BaseUserManager
    monkeypatch.setattr(BaseUserManager, "authenticate", _ok)

    creds = SimpleNamespace(username=user.email, password="x")
    result = await manager.authenticate(creds)
    assert result is user

    events = (await session.exec(select(Event).where(Event.type == "login_failure"))).all()
    assert len(events) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_auth_login_hooks.py -v`
Expected: tests fail because `UserManager` does not yet override `on_after_login` or `authenticate`.

- [ ] **Step 3: Override the UserManager methods**

In `src/chaima/auth.py`, replace the existing `UserManager` class with:

```python
class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key.get_secret_value()
    verification_token_secret = settings.secret_key.get_secret_value()

    async def on_after_login(self, user, request=None, response=None):
        """Bump login counters and emit a login_success event.

        Login is a low-frequency, intrinsically slow path (password hashing),
        so writing inline is fine — no BackgroundTasks needed.
        """
        import datetime as _dt

        from chaima.services.events import _persist_event

        now = _dt.datetime.now(_dt.timezone.utc)
        try:
            await self.user_db.update(
                user, {"last_login_at": now, "login_count": (user.login_count or 0) + 1}
            )
        except Exception:  # noqa: BLE001
            pass  # never fail the login over telemetry

        await _persist_event(
            user_id=user.id,
            group_id=getattr(user, "main_group_id", None),
            type="login_success",
            payload=None,
        )

    async def authenticate(self, credentials):
        """Wrap fastapi-users' authenticate to log failed-login attempts."""
        from chaima.services.events import _persist_event

        result = await super().authenticate(credentials)
        if result is None:
            email = getattr(credentials, "username", None)
            await _persist_event(
                user_id=None,
                group_id=None,
                type="login_failure",
                payload={"email_attempted": email},
            )
        return result
```

Keep the rest of `auth.py` unchanged.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_services/test_auth_login_hooks.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Confirm no regression in existing user/auth tests**

Run: `uv run pytest tests/test_api/test_users.py tests/test_api/test_user_main_group.py -q`
Expected: green.

- [ ] **Step 6: Commit**

```
git add src/chaima/auth.py tests/test_services/test_auth_login_hooks.py
git commit -m "feat(auth): log login_success/failure + bump login counters"
```

---

### Task 7: `search_executed` event from chemicals.list

**Files:**
- Modify: `src/chaima/routers/chemicals.py`
- Create: `tests/test_api/test_admin_analytics_writes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_api/test_admin_analytics_writes.py`:

```python
"""End-to-end checks that user-facing endpoints emit the right events."""
import pytest
from sqlmodel import select

from chaima.models.analytics import Event


@pytest.mark.asyncio
async def test_chemicals_list_with_search_emits_search_executed(
    client, group, membership, session, patch_events_session_maker
):
    r = await client.get(
        f"/api/v1/groups/{group.id}/chemicals",
        params={"search": "acetone"},
    )
    assert r.status_code == 200
    rows = (await session.exec(select(Event).where(Event.type == "search_executed"))).all()
    assert len(rows) == 1
    assert rows[0].payload["query"] == "acetone"
    assert rows[0].payload["result_count"] == r.json()["total"]
    assert rows[0].group_id == group.id


@pytest.mark.asyncio
async def test_chemicals_list_short_search_does_not_emit(
    client, group, membership, session, patch_events_session_maker
):
    """Queries under 3 chars are noise (incremental typing) — no event."""
    r = await client.get(
        f"/api/v1/groups/{group.id}/chemicals",
        params={"search": "ac"},
    )
    assert r.status_code == 200
    rows = (await session.exec(select(Event).where(Event.type == "search_executed"))).all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_chemicals_list_without_search_does_not_emit(
    client, group, membership, session, patch_events_session_maker
):
    r = await client.get(f"/api/v1/groups/{group.id}/chemicals")
    assert r.status_code == 200
    rows = (await session.exec(select(Event).where(Event.type == "search_executed"))).all()
    assert len(rows) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_admin_analytics_writes.py::test_chemicals_list_with_search_emits_search_executed -v`
Expected: FAIL — assert `len(rows) == 1` finds 0.

- [ ] **Step 3: Add the emit call**

In `src/chaima/routers/chemicals.py`, add the import (near the top, with the other `fastapi` imports):

```python
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, Response, UploadFile, status
```

(`BackgroundTasks` added to the existing line.)

Then add this import near the other service imports:

```python
from chaima.services.events import log_event
from chaima.models.analytics import EventType
```

Modify the `list_chemicals` handler signature to accept `background_tasks` and emit the event after a successful query. Replace the handler with:

```python
@router.get("", response_model=PaginatedResponse[ChemicalRead])
async def list_chemicals(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    user: CurrentUserDep,
    background_tasks: BackgroundTasks,
    search: str | None = Query(None),
    hazard_tag_id: UUID | None = Query(None),
    ghs_code_id: UUID | None = Query(None),
    has_containers: bool | None = Query(None),
    my_secrets: bool = Query(False),
    location_id: UUID | None = Query(None),
    include_archived: bool = Query(False),
    sort: str = Query("name"),
    order: str = Query("asc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ChemicalRead]:
    items, total = await chemical_service.list_chemicals(
        session,
        group_id,
        viewer=user,
        search=search,
        hazard_tag_id=hazard_tag_id,
        ghs_code_id=ghs_code_id,
        has_containers=has_containers,
        my_secrets=my_secrets,
        location_id=location_id,
        include_archived=include_archived,
        sort=sort,
        order=order,
        offset=offset,
        limit=limit,
    )
    # Analytics: only log "real" searches; sub-3-char queries are typing noise.
    if search and len(search.strip()) >= 3:
        log_event(
            background_tasks,
            user_id=user.id,
            group_id=group_id,
            type=EventType.SEARCH_EXECUTED,
            payload={"query": search.strip(), "result_count": total},
        )
    return PaginatedResponse(
        items=[ChemicalRead.model_validate(i, from_attributes=True) for i in items],
        total=total,
        offset=offset,
        limit=limit,
    )
```

Drop the old docstring — it duplicates the parameter list and isn't needed.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api/test_admin_analytics_writes.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Confirm no regression in existing chemicals tests**

Run: `uv run pytest tests/test_api/test_chemicals.py -q`
Expected: green.

- [ ] **Step 6: Commit**

```
git add src/chaima/routers/chemicals.py tests/test_api/test_admin_analytics_writes.py
git commit -m "feat(analytics): emit search_executed from chemicals list endpoint"
```

---

### Task 8: Create events — chemical, container, order, wishlist

**Files:**
- Modify: `src/chaima/routers/chemicals.py`
- Modify: `src/chaima/routers/containers.py`
- Modify: `src/chaima/routers/orders.py`
- Modify: `src/chaima/routers/wishlist.py`
- Modify: `tests/test_api/test_admin_analytics_writes.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_api/test_admin_analytics_writes.py`:

```python
@pytest.mark.asyncio
async def test_create_chemical_emits_chemical_created(
    client, group, membership, session, patch_events_session_maker
):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "Acetone-X"},
    )
    assert r.status_code == 201, r.text
    chem_id = r.json()["id"]
    rows = (await session.exec(select(Event).where(Event.type == "chemical_created"))).all()
    assert len(rows) == 1
    assert rows[0].payload == {"chemical_id": chem_id}
    assert rows[0].group_id == group.id


@pytest.mark.asyncio
async def test_create_container_emits_container_created(
    client, group, membership, chemical, storage_location, session, patch_events_session_maker
):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/{chemical.id}/containers",
        json={"identifier": "C-001", "amount": 100, "unit": "mL", "location_id": str(storage_location.id)},
    )
    assert r.status_code == 201, r.text
    cont_id = r.json()["id"]
    rows = (await session.exec(select(Event).where(Event.type == "container_created"))).all()
    assert len(rows) == 1
    assert rows[0].payload == {"container_id": cont_id}


@pytest.mark.asyncio
async def test_create_wishlist_emits_wishlist_added(
    client, group, membership, chemical, session, patch_events_session_maker
):
    r = await client.post(
        f"/api/v1/groups/{group.id}/wishlist",
        json={"chemical_id": str(chemical.id)},
    )
    assert r.status_code == 201, r.text
    rows = (await session.exec(select(Event).where(Event.type == "wishlist_added"))).all()
    assert len(rows) == 1
    assert rows[0].user_id is not None


@pytest.mark.asyncio
async def test_create_order_emits_order_created(
    client, group, membership, chemical, supplier, session, patch_events_session_maker
):
    # Orders require a project — create one via direct DB write to avoid
    # needing the projects-admin endpoint here.
    from chaima.models.project import Project
    project = Project(group_id=group.id, name="GeneralA")
    session.add(project)
    await session.flush()

    r = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id),
            "supplier_id": str(supplier.id),
            "project_id": str(project.id),
            "amount_per_package": 100,
            "unit": "g",
            "package_count": 1,
        },
    )
    assert r.status_code == 201, r.text
    order_id = r.json()["id"]
    rows = (await session.exec(select(Event).where(Event.type == "order_created"))).all()
    assert len(rows) == 1
    assert rows[0].payload == {"order_id": order_id}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_admin_analytics_writes.py -v`
Expected: the 4 new tests fail (assert finds 0 rows).

- [ ] **Step 3: Add the emit calls to each router**

**In `src/chaima/routers/chemicals.py` `create_chemical`:**

Add `background_tasks: BackgroundTasks,` to the function signature (between `user: CurrentUserDep` and the function body). Just before the `return ChemicalRead.model_validate(chem, from_attributes=True)` line, add:

```python
    log_event(
        background_tasks,
        user_id=user.id,
        group_id=group_id,
        type=EventType.CHEMICAL_CREATED,
        payload={"chemical_id": str(chem.id)},
    )
```

**In `src/chaima/routers/containers.py`:**

Add to the imports at the top:

```python
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile, status

from chaima.services.events import log_event
from chaima.models.analytics import EventType
```

Modify the nested `create_container` handler: add `background_tasks: BackgroundTasks,` to the signature, and just before `return ContainerRead.model_validate(container, from_attributes=True)`:

```python
    log_event(
        background_tasks,
        user_id=user.id,
        group_id=group_id,
        type=EventType.CONTAINER_CREATED,
        payload={"container_id": str(container.id)},
    )
```

**In `src/chaima/routers/orders.py`:**

Add to imports:

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from chaima.services.events import log_event
from chaima.models.analytics import EventType
```

In `create_order`, add `background_tasks: BackgroundTasks,` to the signature. Just before the `return await _hydrate(...)` line, add:

```python
    log_event(
        background_tasks,
        user_id=current_user.id,
        group_id=group_id,
        type=EventType.ORDER_CREATED,
        payload={"order_id": str(order.id)},
    )
```

**In `src/chaima/routers/wishlist.py`:**

Add to imports:

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from chaima.services.events import log_event
from chaima.models.analytics import EventType
```

In `create_wishlist`, add `background_tasks: BackgroundTasks,` to the signature, and just before the `return await _hydrate(session, item)` line:

```python
    log_event(
        background_tasks,
        user_id=current_user.id,
        group_id=group_id,
        type=EventType.WISHLIST_ADDED,
        payload={"wishlist_item_id": str(item.id)},
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api/test_admin_analytics_writes.py -v`
Expected: all (3 + 4 = 7) tests PASS.

- [ ] **Step 5: Confirm no regression in the touched routers**

Run: `uv run pytest tests/test_api/test_chemicals.py tests/test_api/test_containers.py tests/test_api/test_orders.py tests/test_api/test_wishlist.py -q`
Expected: green.

- [ ] **Step 6: Commit**

```
git add src/chaima/routers/chemicals.py src/chaima/routers/containers.py src/chaima/routers/orders.py src/chaima/routers/wishlist.py tests/test_api/test_admin_analytics_writes.py
git commit -m "feat(analytics): emit create-events for chemicals/containers/orders/wishlist"
```

---

### Task 9: `photo_extract` + `pubchem_fetch` events

**Files:**
- Modify: `src/chaima/routers/chemicals.py`
- Modify: `src/chaima/services/enrich.py`
- Modify: `tests/test_api/test_admin_analytics_writes.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_api/test_admin_analytics_writes.py`:

```python
import io
from PIL import Image


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(50, 50, 50)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_photo_extract_success_emits_event(
    client, group, membership, session, patch_events_session_maker, monkeypatch
):
    from chaima.services.vision import ExtractedLabel
    monkeypatch.setattr(
        "chaima.routers.chemicals.vision_service.extract_from_image",
        lambda data, mime: ExtractedLabel(name="Acetone", confidence="high"),
    )
    files = {"file": ("label.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/extract-from-photo", files=files,
    )
    assert r.status_code == 200, r.text
    rows = (await session.exec(select(Event).where(Event.type == "photo_extract"))).all()
    assert len(rows) == 1
    assert rows[0].payload == {"success": True, "confidence": "high"}


@pytest.mark.asyncio
async def test_photo_extract_failure_still_emits_event(
    client, group, membership, session, patch_events_session_maker, monkeypatch
):
    from fastapi import HTTPException
    def _raise(data, mime):
        raise HTTPException(status_code=502, detail="vision_service_unavailable")
    monkeypatch.setattr(
        "chaima.routers.chemicals.vision_service.extract_from_image", _raise,
    )
    files = {"file": ("label.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/extract-from-photo", files=files,
    )
    assert r.status_code == 502
    rows = (await session.exec(select(Event).where(Event.type == "photo_extract"))).all()
    assert len(rows) == 1
    assert rows[0].payload == {"success": False, "confidence": None}


@pytest.mark.asyncio
async def test_enrich_one_emits_pubchem_fetch(session, patch_events_session_maker, monkeypatch):
    """services.enrich.enrich_one writes a pubchem_fetch event for every call."""
    from chaima.models.chemical import Chemical
    from chaima.services import enrich as enrich_service

    chem = Chemical(name="Acetone", cas="67-64-1")
    session.add(chem)
    await session.flush()

    # Fake a successful PubChem response.
    from types import SimpleNamespace
    async def _ok(_q):
        return SimpleNamespace(cid="180", cas="67-64-1", smiles="CC(=O)C", molar_mass=58.08)
    monkeypatch.setattr("chaima.services.enrich.pubchem_lookup", _ok)

    await enrich_service.enrich_one(session, chem)

    rows = (await session.exec(select(Event).where(Event.type == "pubchem_fetch"))).all()
    assert len(rows) == 1
    assert rows[0].payload == {"success": True, "cas_resolved": True}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_admin_analytics_writes.py::test_photo_extract_success_emits_event tests/test_api/test_admin_analytics_writes.py::test_enrich_one_emits_pubchem_fetch -v`
Expected: both fail (0 rows found).

- [ ] **Step 3: Add the photo-extract emit**

In `src/chaima/routers/chemicals.py`, replace the `extract_from_photo` handler with:

```python
@router.post("/extract-from-photo", response_model=vision_service.ExtractedLabel)
async def extract_from_photo(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    user: CurrentUserDep,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> vision_service.ExtractedLabel:
    """Extract chemical-label fields from a photo via the vision service.

    Stateless: image bytes are passed to Gemini and discarded; no DB writes.
    """
    data = await file.read()
    images_service.validate_image_upload(file, data)
    try:
        result = vision_service.extract_from_image(data, file.content_type or "image/jpeg")
    except Exception:
        # Log the failure event before re-raising so analytics still sees it.
        log_event(
            background_tasks,
            user_id=user.id, group_id=group_id,
            type=EventType.PHOTO_EXTRACT,
            payload={"success": False, "confidence": None},
        )
        raise

    log_event(
        background_tasks,
        user_id=user.id, group_id=group_id,
        type=EventType.PHOTO_EXTRACT,
        payload={"success": True, "confidence": result.confidence},
    )
    return result
```

Note the added `group_id` and `user` and `background_tasks` parameters.

- [ ] **Step 4: Add the pubchem-fetch emit inside `services/enrich.py`**

`services/enrich.py` is called from streaming generators that don't have access to `BackgroundTasks`. Use `_persist_event` directly here — the PubChem call is itself slow (~250ms+), so the additional event write is irrelevant.

In `src/chaima/services/enrich.py`, add the import near the top:

```python
from chaima.services.events import _persist_event
from chaima.models.analytics import EventType
```

Replace the `enrich_one` function with:

```python
async def enrich_one(session: AsyncSession, chemical: Chemical) -> EnrichStatus:
    if chemical.cid:
        return "skipped"

    query = chemical.cas or chemical.name
    if not query:
        return "skipped"

    success = False
    cas_resolved = False
    try:
        result = await pubchem_lookup(query)
        success = True
    except PubChemNotFound:
        await _persist_event(
            user_id=None, group_id=chemical.group_id,
            type=EventType.PUBCHEM_FETCH,
            payload={"success": False, "cas_resolved": False},
        )
        return "not_found"
    except Exception:
        await _persist_event(
            user_id=None, group_id=chemical.group_id,
            type=EventType.PUBCHEM_FETCH,
            payload={"success": False, "cas_resolved": False},
        )
        return "error"

    if result.cid and not chemical.cid:
        chemical.cid = str(result.cid)
    if result.cas and not chemical.cas:
        chemical.cas = result.cas
        cas_resolved = True
    elif result.cas:
        cas_resolved = True
    if result.smiles and not chemical.smiles:
        chemical.smiles = result.smiles
    if result.molar_mass is not None and chemical.molar_mass is None:
        chemical.molar_mass = result.molar_mass
    session.add(chemical)
    await session.flush()

    await _persist_event(
        user_id=None, group_id=chemical.group_id,
        type=EventType.PUBCHEM_FETCH,
        payload={"success": success, "cas_resolved": cas_resolved},
    )
    return "enriched"
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_api/test_admin_analytics_writes.py::test_photo_extract_success_emits_event tests/test_api/test_admin_analytics_writes.py::test_photo_extract_failure_still_emits_event tests/test_api/test_admin_analytics_writes.py::test_enrich_one_emits_pubchem_fetch -v`
Expected: 3 PASS.

- [ ] **Step 6: Confirm no regression**

Run: `uv run pytest tests/test_api/test_chemicals_extract.py tests/test_services/test_enrich.py -q`
Expected: green.

- [ ] **Step 7: Commit**

```
git add src/chaima/routers/chemicals.py src/chaima/services/enrich.py tests/test_api/test_admin_analytics_writes.py
git commit -m "feat(analytics): emit photo_extract and pubchem_fetch events"
```

---

### Task 10: Slow-request middleware

**Files:**
- Create: `src/chaima/middleware/__init__.py`
- Create: `src/chaima/middleware/slow_request.py`
- Create: `tests/test_middleware/__init__.py`
- Create: `tests/test_middleware/test_slow_request.py`

- [ ] **Step 1: Create the package markers**

Create empty file: `src/chaima/middleware/__init__.py`
Create empty file: `tests/test_middleware/__init__.py`

- [ ] **Step 2: Write the failing tests**

Create `tests/test_middleware/test_slow_request.py`:

```python
"""Tests for the slow-request logging middleware."""
import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from chaima.middleware.slow_request import SlowRequestMiddleware
from chaima.models.analytics import SlowRequest


def _make_app(threshold_ms: int):
    app = FastAPI()
    app.add_middleware(SlowRequestMiddleware, threshold_ms=threshold_ms)

    @app.get("/fast")
    async def fast():
        return {"ok": True}

    @app.get("/slow")
    async def slow():
        await asyncio.sleep(0.15)
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="bang")

    @app.get("/items/{item_id}")
    async def get_item(item_id: str):
        await asyncio.sleep(0.15)
        return {"id": item_id}

    return app


@pytest.mark.asyncio
async def test_fast_request_is_not_logged(session, patch_events_session_maker):
    app = _make_app(threshold_ms=100)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/fast")
        assert r.status_code == 200
    rows = (await session.exec(select(SlowRequest))).all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_slow_request_is_logged(session, patch_events_session_maker):
    app = _make_app(threshold_ms=100)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/slow")
        assert r.status_code == 200
    rows = (await session.exec(select(SlowRequest))).all()
    assert len(rows) == 1
    assert rows[0].method == "GET"
    assert rows[0].path == "/slow"
    assert rows[0].status == 200
    assert rows[0].duration_ms >= 100


@pytest.mark.asyncio
async def test_5xx_is_logged_even_when_fast(session, patch_events_session_maker):
    app = _make_app(threshold_ms=100)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/boom")
        assert r.status_code == 500
    rows = (await session.exec(select(SlowRequest))).all()
    assert len(rows) == 1
    assert rows[0].status == 500
    assert rows[0].path == "/boom"


@pytest.mark.asyncio
async def test_path_is_normalized_to_matched_route(session, patch_events_session_maker):
    """Path params like /items/{item_id} should not blow up the path cardinality."""
    app = _make_app(threshold_ms=100)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/items/abc")
        assert r.status_code == 200
    rows = (await session.exec(select(SlowRequest))).all()
    assert len(rows) == 1
    assert rows[0].path == "/items/{item_id}"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_middleware/test_slow_request.py -v`
Expected: `ModuleNotFoundError: No module named 'chaima.middleware.slow_request'`.

- [ ] **Step 4: Implement the middleware**

Create `src/chaima/middleware/slow_request.py`:

```python
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
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_middleware/test_slow_request.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 6: Mount the middleware in `app.py`**

In `src/chaima/app.py`, add an import:

```python
from chaima.middleware.slow_request import SlowRequestMiddleware
```

Immediately after `app = FastAPI(title="ChAIMa", lifespan=lifespan)`, add:

```python
app.add_middleware(SlowRequestMiddleware, threshold_ms=500)
```

- [ ] **Step 7: Confirm no app-level regression**

Run: `uv run pytest tests/test_api/ -q`
Expected: green. (The middleware will log slow tests as `slow_request` rows in the in-memory test DB, but since each test gets its own engine they're disposed at teardown.)

- [ ] **Step 8: Commit**

```
git add src/chaima/middleware/ src/chaima/app.py tests/test_middleware/
git commit -m "feat(analytics): add SlowRequestMiddleware for performance telemetry"
```

---

## Phase 3 — Read API

### Task 11: `services/analytics.py` — aggregations

**Files:**
- Create: `src/chaima/services/analytics.py`
- Create: `tests/test_services/test_analytics.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_services/test_analytics.py`:

```python
"""Tests for analytics aggregation queries."""
import datetime as dt

import pytest

from chaima.models.analytics import Event, EventDaily, SlowRequest
from chaima.services import analytics as analytics_service


def _utc(year, month, day, hour=12):
    return dt.datetime(year, month, day, hour, 0, 0, tzinfo=dt.timezone.utc)


@pytest.mark.asyncio
async def test_range_to_window_24h_returns_last_day():
    end = _utc(2026, 5, 27)
    start, _ = analytics_service.range_to_window("24h", now=end)
    assert (end - start) == dt.timedelta(hours=24)


@pytest.mark.asyncio
async def test_range_to_window_unknown_falls_back_to_7d():
    end = _utc(2026, 5, 27)
    start, _ = analytics_service.range_to_window("nope", now=end)
    assert (end - start) == dt.timedelta(days=7)


@pytest.mark.asyncio
async def test_summary_counts_only_within_range(session, user, group):
    now = _utc(2026, 5, 27)
    session.add_all([
        Event(user_id=user.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(hours=1)),
        Event(user_id=user.id, group_id=group.id, type="search_executed",
              payload={"query": "x", "result_count": 1},
              created_at=now - dt.timedelta(hours=2)),
        Event(user_id=user.id, group_id=group.id, type="chemical_created",
              payload={"chemical_id": "x"},
              created_at=now - dt.timedelta(hours=3)),
        # Outside the 24h window — must not be counted:
        Event(user_id=user.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(days=8)),
    ])
    await session.flush()

    summary = await analytics_service.summary(session, range_="24h", now=now)
    assert summary["active_users"] == 1
    assert summary["total_logins"] == 1
    assert summary["total_searches"] == 1
    assert summary["total_creates"] == 1
    assert summary["total_photo_extracts"] == 0
    assert summary["total_pubchem_fetches"] == 0


@pytest.mark.asyncio
async def test_user_stats_includes_last_login_and_counts(session, user, group):
    now = _utc(2026, 5, 27)
    user.last_login_at = now - dt.timedelta(minutes=5)
    user.login_count = 14
    session.add(user)
    session.add_all([
        Event(user_id=user.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(hours=1)),
        Event(user_id=user.id, group_id=group.id, type="search_executed",
              payload={"query": "x", "result_count": 1},
              created_at=now - dt.timedelta(hours=2)),
        Event(user_id=user.id, group_id=group.id, type="chemical_created",
              payload={"chemical_id": "x"},
              created_at=now - dt.timedelta(hours=3)),
    ])
    await session.flush()

    rows = await analytics_service.user_stats(session, range_="24h", now=now)
    assert len(rows) >= 1
    me = next(r for r in rows if r["user_id"] == user.id)
    assert me["email"] == user.email
    assert me["last_login_at"] is not None
    assert me["logins_in_range"] == 1
    assert me["searches"] == 1
    assert me["chemicals_created"] == 1


@pytest.mark.asyncio
async def test_top_searches_aggregates_and_sorts(session, user, group):
    now = _utc(2026, 5, 27)
    session.add_all([
        Event(user_id=user.id, group_id=group.id, type="search_executed",
              payload={"query": "acetone", "result_count": 3}, created_at=now - dt.timedelta(hours=1)),
        Event(user_id=user.id, group_id=group.id, type="search_executed",
              payload={"query": "acetone", "result_count": 3}, created_at=now - dt.timedelta(hours=2)),
        Event(user_id=user.id, group_id=group.id, type="search_executed",
              payload={"query": "ethanol", "result_count": 0}, created_at=now - dt.timedelta(hours=3)),
    ])
    await session.flush()

    rows = await analytics_service.top_searches(session, range_="24h", limit=10, now=now)
    assert rows[0]["query"] == "acetone"
    assert rows[0]["count"] == 2
    assert rows[1]["query"] == "ethanol"
    assert rows[1]["empty_count"] == 1


@pytest.mark.asyncio
async def test_slow_endpoints_aggregates_with_percentiles(session, user):
    now = _utc(2026, 5, 27)
    # 10 fast, 1 very slow → p95 ~ p99 ~ slow value
    for ms in [510, 520, 530, 540, 550, 560, 570, 580, 590, 600, 5000]:
        session.add(SlowRequest(
            user_id=user.id, method="POST", path="/api/v1/groups/{group_id}/chemicals/extract-from-photo",
            status=200, duration_ms=ms, created_at=now - dt.timedelta(minutes=ms),
        ))
    await session.flush()

    rows = await analytics_service.slow_endpoints(session, range_="24h", limit=10, now=now)
    assert len(rows) == 1
    row = rows[0]
    assert row["path"] == "/api/v1/groups/{group_id}/chemicals/extract-from-photo"
    assert row["count"] == 11
    assert row["p50_ms"] <= row["p95_ms"] <= row["p99_ms"]
    assert row["p99_ms"] >= 600
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_analytics.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the aggregations**

Create `src/chaima/services/analytics.py`:

```python
"""Read-side aggregations for the admin analytics dashboard.

All functions accept an explicit ``now`` for deterministic testing; in
production the routers pass ``datetime.now(timezone.utc)``.

Percentiles are computed in Python after fetching the matching rows —
SQLite has no ``percentile_cont``, and slow-request volumes are small
enough (capped at 30-day retention) that this stays cheap.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.analytics import Event, SlowRequest
from chaima.models.user import User

_RANGE_TO_DELTA = {
    "24h": dt.timedelta(hours=24),
    "7d": dt.timedelta(days=7),
    "30d": dt.timedelta(days=30),
    "90d": dt.timedelta(days=90),
}

_CREATE_TYPES = (
    "chemical_created", "container_created", "order_created", "wishlist_added",
)


def range_to_window(range_: str, *, now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    """Return (start, end) for a named range. Unknown ranges default to 7d."""
    delta = _RANGE_TO_DELTA.get(range_, _RANGE_TO_DELTA["7d"])
    return (now - delta, now)


async def summary(
    session: AsyncSession, *, range_: str, now: dt.datetime,
) -> dict[str, Any]:
    """Top-line KPI counters for the given range."""
    start, end = range_to_window(range_, now=now)

    distinct_users = await session.exec(
        select(func.count(func.distinct(Event.user_id))).where(
            Event.created_at >= start, Event.created_at <= end,
            Event.user_id.is_not(None),
        )
    )
    counts_by_type = await session.exec(
        select(Event.type, func.count(Event.id)).where(
            Event.created_at >= start, Event.created_at <= end,
        ).group_by(Event.type)
    )
    counts = dict(counts_by_type.all())

    return {
        "active_users": distinct_users.one() or 0,
        "total_logins": counts.get("login_success", 0),
        "total_searches": counts.get("search_executed", 0),
        "total_creates": sum(counts.get(t, 0) for t in _CREATE_TYPES),
        "total_photo_extracts": counts.get("photo_extract", 0),
        "total_pubchem_fetches": counts.get("pubchem_fetch", 0),
        "range_start": start,
        "range_end": end,
    }


async def user_stats(
    session: AsyncSession, *, range_: str, now: dt.datetime,
) -> list[dict[str, Any]]:
    """One row per user, with last_login_at and per-type counts in range."""
    start, end = range_to_window(range_, now=now)

    users = (await session.exec(select(User))).all()

    counts_rows = (await session.exec(
        select(Event.user_id, Event.type, func.count(Event.id)).where(
            Event.created_at >= start, Event.created_at <= end,
            Event.user_id.is_not(None),
        ).group_by(Event.user_id, Event.type)
    )).all()

    per_user: dict = defaultdict(lambda: defaultdict(int))
    for uid, type_, cnt in counts_rows:
        per_user[uid][type_] = cnt

    out: list[dict[str, Any]] = []
    for u in users:
        c = per_user.get(u.id, {})
        out.append({
            "user_id": u.id,
            "email": u.email,
            "last_login_at": u.last_login_at,
            "logins_in_range": c.get("login_success", 0),
            "searches": c.get("search_executed", 0),
            "chemicals_created": c.get("chemical_created", 0),
            "containers_created": c.get("container_created", 0),
            "orders_created": c.get("order_created", 0),
            "wishlist_added": c.get("wishlist_added", 0),
            "photo_extracts": c.get("photo_extract", 0),
        })
    # Sort: last_login DESC NULLS LAST.
    out.sort(key=lambda r: (r["last_login_at"] is None, -(r["last_login_at"].timestamp() if r["last_login_at"] else 0)))
    return out


async def top_searches(
    session: AsyncSession, *, range_: str, limit: int, now: dt.datetime,
) -> list[dict[str, Any]]:
    """Top search queries by count, with avg result count and empty-result count."""
    start, end = range_to_window(range_, now=now)
    rows = (await session.exec(
        select(Event.payload).where(
            Event.type == "search_executed",
            Event.created_at >= start, Event.created_at <= end,
        )
    )).all()

    counts: dict[str, dict[str, Any]] = {}
    for payload in rows:
        if not payload:
            continue
        q = payload.get("query")
        rc = payload.get("result_count", 0)
        if q is None:
            continue
        entry = counts.setdefault(q, {"count": 0, "sum": 0, "empty": 0})
        entry["count"] += 1
        entry["sum"] += rc
        if rc == 0:
            entry["empty"] += 1

    items = [
        {
            "query": q, "count": e["count"],
            "avg_result_count": (e["sum"] / e["count"]) if e["count"] else 0.0,
            "empty_count": e["empty"],
        }
        for q, e in counts.items()
    ]
    items.sort(key=lambda r: r["count"], reverse=True)
    return items[:limit]


def _percentile(values: list[int], pct: float) -> int:
    """Linear-interpolation percentile. ``values`` must be non-empty."""
    if not values:
        return 0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return int(s[lo] + (s[hi] - s[lo]) * frac)


async def slow_endpoints(
    session: AsyncSession, *, range_: str, limit: int, now: dt.datetime,
) -> list[dict[str, Any]]:
    """Per-endpoint percentile latencies + counts within the range."""
    start, end = range_to_window(range_, now=now)
    rows = (await session.exec(
        select(SlowRequest.method, SlowRequest.path, SlowRequest.status, SlowRequest.duration_ms).where(
            SlowRequest.created_at >= start, SlowRequest.created_at <= end,
        )
    )).all()

    grouped: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for method, path, status, dur in rows:
        grouped[(method, path)].append((status, dur))

    out: list[dict[str, Any]] = []
    for (method, path), entries in grouped.items():
        durations = [d for _s, d in entries]
        errors = sum(1 for s, _d in entries if s >= 500)
        out.append({
            "method": method, "path": path,
            "p50_ms": _percentile(durations, 0.50),
            "p95_ms": _percentile(durations, 0.95),
            "p99_ms": _percentile(durations, 0.99),
            "count": len(entries),
            "error_count": errors,
        })
    out.sort(key=lambda r: r["p95_ms"], reverse=True)
    return out[:limit]


async def compact(
    session: AsyncSession, *, now: dt.datetime,
) -> dict[str, int]:
    """Roll events older than 30 days into ``event_daily`` and prune.

    Steps (each in its own commit):
    1. For each ``(day, user_id, type)`` in ``event`` with ``created_at < now - 30d``,
       upsert ``event_daily`` with count and group_id. Then DELETE those events.
    2. DELETE ``event_daily`` rows with ``day < (now - 365d).date()``.
    3. DELETE ``slow_request`` rows with ``created_at < now - 30d``.

    Returns counts for each step.
    """
    from sqlalchemy import delete
    from chaima.models.analytics import EventDaily

    cutoff_30d = now - dt.timedelta(days=30)
    cutoff_365d = (now - dt.timedelta(days=365)).date()

    # --- Step 1: aggregate then delete ---
    agg_rows = (await session.exec(
        select(
            func.date(Event.created_at).label("day"),
            Event.user_id, Event.type, Event.group_id,
            func.count(Event.id).label("count"),
        ).where(
            Event.created_at < cutoff_30d,
            Event.user_id.is_not(None),
        ).group_by(
            func.date(Event.created_at), Event.user_id, Event.type, Event.group_id,
        )
    )).all()

    events_aggregated = 0
    for day_s, user_id, type_, group_id, count in agg_rows:
        if isinstance(day_s, str):
            day_v = dt.date.fromisoformat(day_s)
        else:
            day_v = day_s
        existing = await session.get(EventDaily, (day_v, user_id, type_))
        if existing is None:
            session.add(EventDaily(
                day=day_v, user_id=user_id, type=type_,
                group_id=group_id, count=count,
            ))
        else:
            existing.count += count
            session.add(existing)
        events_aggregated += count

    events_deleted_result = await session.exec(
        delete(Event).where(Event.created_at < cutoff_30d)
    )
    events_deleted = events_deleted_result.rowcount or 0

    # --- Step 2: prune ancient daily rows ---
    daily_deleted_result = await session.exec(
        delete(EventDaily).where(EventDaily.day < cutoff_365d)
    )
    daily_deleted = daily_deleted_result.rowcount or 0

    # --- Step 3: prune old slow_requests ---
    slow_deleted_result = await session.exec(
        delete(SlowRequest).where(SlowRequest.created_at < cutoff_30d)
    )
    slow_deleted = slow_deleted_result.rowcount or 0

    await session.commit()

    return {
        "events_aggregated": events_aggregated,
        "events_deleted": events_deleted,
        "event_daily_deleted": daily_deleted,
        "slow_requests_deleted": slow_deleted,
    }
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_services/test_analytics.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/chaima/services/analytics.py tests/test_services/test_analytics.py
git commit -m "feat(analytics): add read-side aggregations (summary, users, searches, slow endpoints)"
```

---

### Task 12: `routers/admin_analytics.py` — 4 read endpoints

**Files:**
- Create: `src/chaima/routers/admin_analytics.py`
- Modify: `src/chaima/app.py` — register router
- Create: `tests/test_api/test_admin_analytics.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api/test_admin_analytics.py`:

```python
"""API tests for the superuser-only admin analytics endpoints."""
import datetime as dt

import pytest

from chaima.models.analytics import Event, SlowRequest


def _utc(year, month, day, hour=12):
    return dt.datetime(year, month, day, hour, 0, 0, tzinfo=dt.timezone.utc)


@pytest.mark.asyncio
async def test_summary_requires_superuser(client):
    r = await client.get("/api/v1/admin/analytics/summary", params={"range": "7d"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_summary_returns_zeros_when_empty(superuser_client):
    r = await superuser_client.get(
        "/api/v1/admin/analytics/summary", params={"range": "7d"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["active_users"] == 0
    assert body["total_logins"] == 0
    assert body["total_searches"] == 0
    assert body["total_creates"] == 0
    assert body["total_photo_extracts"] == 0
    assert body["total_pubchem_fetches"] == 0


@pytest.mark.asyncio
async def test_summary_counts_seeded_events(superuser_client, session, superuser, group):
    now = dt.datetime.now(dt.timezone.utc)
    session.add_all([
        Event(user_id=superuser.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(hours=1)),
        Event(user_id=superuser.id, group_id=group.id, type="search_executed",
              payload={"query": "acetone", "result_count": 3},
              created_at=now - dt.timedelta(hours=2)),
        Event(user_id=superuser.id, group_id=group.id, type="chemical_created",
              payload={"chemical_id": "x"}, created_at=now - dt.timedelta(hours=3)),
    ])
    await session.flush()

    r = await superuser_client.get(
        "/api/v1/admin/analytics/summary", params={"range": "24h"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["active_users"] == 1
    assert body["total_logins"] == 1
    assert body["total_searches"] == 1
    assert body["total_creates"] == 1


@pytest.mark.asyncio
async def test_users_endpoint_includes_all_users(superuser_client, session, superuser, group):
    from chaima.models.user import User
    bob = User(
        email="bob@example.com", hashed_password="x",
        is_active=True, is_superuser=False, is_verified=True,
        main_group_id=group.id,
    )
    session.add(bob)
    await session.flush()

    r = await superuser_client.get(
        "/api/v1/admin/analytics/users", params={"range": "7d"},
    )
    assert r.status_code == 200
    rows = r.json()
    emails = {row["email"] for row in rows}
    assert "admin@example.com" in emails
    assert "bob@example.com" in emails


@pytest.mark.asyncio
async def test_top_searches_orders_by_count(superuser_client, session, superuser, group):
    now = dt.datetime.now(dt.timezone.utc)
    for q in ["acetone", "acetone", "acetone", "ethanol"]:
        session.add(Event(
            user_id=superuser.id, group_id=group.id, type="search_executed",
            payload={"query": q, "result_count": 0 if q == "ethanol" else 5},
            created_at=now - dt.timedelta(minutes=10),
        ))
    await session.flush()

    r = await superuser_client.get(
        "/api/v1/admin/analytics/top-searches", params={"range": "24h", "limit": 5},
    )
    assert r.status_code == 200
    rows = r.json()
    assert rows[0]["query"] == "acetone"
    assert rows[0]["count"] == 3
    assert rows[1]["query"] == "ethanol"
    assert rows[1]["empty_count"] == 1


@pytest.mark.asyncio
async def test_slow_endpoints_returns_percentiles(superuser_client, session, superuser):
    now = dt.datetime.now(dt.timezone.utc)
    for ms in [510, 520, 530, 540, 550, 560, 570, 580, 590, 600, 5000]:
        session.add(SlowRequest(
            user_id=superuser.id, method="GET", path="/api/v1/groups/{group_id}/chemicals",
            status=200, duration_ms=ms, created_at=now - dt.timedelta(minutes=5),
        ))
    await session.flush()

    r = await superuser_client.get(
        "/api/v1/admin/analytics/slow-endpoints", params={"range": "24h", "limit": 10},
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["count"] == 11
    assert rows[0]["p50_ms"] <= rows[0]["p95_ms"] <= rows[0]["p99_ms"]


@pytest.mark.asyncio
async def test_users_endpoint_requires_superuser(client):
    r = await client.get("/api/v1/admin/analytics/users", params={"range": "7d"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_top_searches_requires_superuser(client):
    r = await client.get("/api/v1/admin/analytics/top-searches", params={"range": "7d"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_slow_endpoints_requires_superuser(client):
    r = await client.get("/api/v1/admin/analytics/slow-endpoints", params={"range": "7d"})
    assert r.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_admin_analytics.py -v`
Expected: all FAIL (404 — routes don't exist).

- [ ] **Step 3: Create the router**

Create `src/chaima/routers/admin_analytics.py`:

```python
"""Superuser-only analytics endpoints.

Endpoints all return JSON; auth via the existing ``SuperuserDep``. Range
filtering accepts ``24h | 7d | 30d | 90d`` (unknown values fall back to 7d).
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from fastapi import APIRouter, Query

from chaima.dependencies import SessionDep, SuperuserDep
from chaima.services import analytics as analytics_service

router = APIRouter(prefix="/api/v1/admin/analytics", tags=["admin-analytics"])

Range = Literal["24h", "7d", "30d", "90d"]


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


@router.get("/summary")
async def get_summary(
    session: SessionDep,
    user: SuperuserDep,
    range: Range = Query("7d"),
) -> dict[str, Any]:
    return await analytics_service.summary(session, range_=range, now=_now())


@router.get("/users")
async def get_user_stats(
    session: SessionDep,
    user: SuperuserDep,
    range: Range = Query("7d"),
) -> list[dict[str, Any]]:
    return await analytics_service.user_stats(session, range_=range, now=_now())


@router.get("/top-searches")
async def get_top_searches(
    session: SessionDep,
    user: SuperuserDep,
    range: Range = Query("7d"),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    return await analytics_service.top_searches(
        session, range_=range, limit=limit, now=_now(),
    )


@router.get("/slow-endpoints")
async def get_slow_endpoints(
    session: SessionDep,
    user: SuperuserDep,
    range: Range = Query("7d"),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    return await analytics_service.slow_endpoints(
        session, range_=range, limit=limit, now=_now(),
    )
```

- [ ] **Step 4: Register the router in `app.py`**

In `src/chaima/app.py`, add the import near the other router imports:

```python
from chaima.routers.admin_analytics import router as admin_analytics_router
```

Add the `include_router` call alongside the others (any position works):

```python
app.include_router(admin_analytics_router)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_api/test_admin_analytics.py -v`
Expected: all 9 tests PASS.

- [ ] **Step 6: Commit**

```
git add src/chaima/routers/admin_analytics.py src/chaima/app.py tests/test_api/test_admin_analytics.py
git commit -m "feat(analytics): add /api/v1/admin/analytics read endpoints"
```

---

### Task 13: Compaction endpoint

**Files:**
- Modify: `src/chaima/routers/admin_analytics.py` — add `_compact` endpoint
- Modify: `tests/test_api/test_admin_analytics.py` — add compaction tests

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_api/test_admin_analytics.py`:

```python
@pytest.mark.asyncio
async def test_compact_endpoint_requires_superuser(client):
    r = await client.post("/api/v1/admin/analytics/_compact")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_compact_rolls_old_events_into_daily(superuser_client, session, superuser, group):
    """Events older than 30 days move from event → event_daily, then disappear."""
    from chaima.models.analytics import Event, EventDaily
    from sqlmodel import select
    now = dt.datetime.now(dt.timezone.utc)

    session.add_all([
        Event(user_id=superuser.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(days=40)),
        Event(user_id=superuser.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(days=40)),
        Event(user_id=superuser.id, group_id=group.id, type="search_executed",
              payload={"query": "x", "result_count": 1},
              created_at=now - dt.timedelta(days=45)),
        # Fresh — must NOT be compacted:
        Event(user_id=superuser.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(hours=1)),
    ])
    await session.flush()

    r = await superuser_client.post("/api/v1/admin/analytics/_compact")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["events_aggregated"] == 3
    assert body["events_deleted"] == 3

    remaining = (await session.exec(select(Event))).all()
    assert len(remaining) == 1  # the fresh one

    daily = (await session.exec(select(EventDaily))).all()
    assert len(daily) == 2  # 2 distinct (day, type) combos
    total = sum(d.count for d in daily)
    assert total == 3


@pytest.mark.asyncio
async def test_compact_prunes_slow_requests_older_than_30d(
    superuser_client, session, superuser,
):
    from chaima.models.analytics import SlowRequest
    from sqlmodel import select
    now = dt.datetime.now(dt.timezone.utc)

    session.add_all([
        SlowRequest(user_id=superuser.id, method="GET", path="/x", status=200,
                    duration_ms=600, created_at=now - dt.timedelta(days=40)),
        SlowRequest(user_id=superuser.id, method="GET", path="/x", status=200,
                    duration_ms=600, created_at=now - dt.timedelta(hours=1)),
    ])
    await session.flush()

    r = await superuser_client.post("/api/v1/admin/analytics/_compact")
    assert r.status_code == 200
    body = r.json()
    assert body["slow_requests_deleted"] == 1

    remaining = (await session.exec(select(SlowRequest))).all()
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_compact_prunes_daily_older_than_365d(superuser_client, session, superuser):
    from chaima.models.analytics import EventDaily
    from sqlmodel import select
    today = dt.date.today()

    session.add_all([
        EventDaily(day=today - dt.timedelta(days=400), user_id=superuser.id,
                   type="login_success", count=5),
        EventDaily(day=today - dt.timedelta(days=10), user_id=superuser.id,
                   type="login_success", count=1),
    ])
    await session.flush()

    r = await superuser_client.post("/api/v1/admin/analytics/_compact")
    assert r.status_code == 200
    body = r.json()
    assert body["event_daily_deleted"] == 1

    remaining = (await session.exec(select(EventDaily))).all()
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_compact_is_idempotent(superuser_client):
    r1 = await superuser_client.post("/api/v1/admin/analytics/_compact")
    r2 = await superuser_client.post("/api/v1/admin/analytics/_compact")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Second call has nothing to do.
    assert r2.json()["events_aggregated"] == 0
    assert r2.json()["events_deleted"] == 0
    assert r2.json()["slow_requests_deleted"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_admin_analytics.py -v -k compact`
Expected: tests fail (route does not exist).

- [ ] **Step 3: Add the endpoint**

In `src/chaima/routers/admin_analytics.py`, append:

```python
@router.post("/_compact")
async def compact_analytics(
    session: SessionDep,
    user: SuperuserDep,
) -> dict[str, Any]:
    """Roll old events into the daily summary and prune retention."""
    result = await analytics_service.compact(session, now=_now())
    return result
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api/test_admin_analytics.py -v -k compact`
Expected: all 5 compaction tests PASS.

- [ ] **Step 5: Confirm everything else still green**

Run: `uv run pytest -q`
Expected: green.

- [ ] **Step 6: Commit**

```
git add src/chaima/routers/admin_analytics.py tests/test_api/test_admin_analytics.py
git commit -m "feat(analytics): add POST /_compact for retention cron"
```

---

## Phase 4 — Frontend

### Task 14: Types + React-Query hooks

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/api/hooks/useAdminAnalytics.ts`

- [ ] **Step 1: Add the response types**

Append to `frontend/src/types/index.ts`:

```ts
export type AnalyticsRange = "24h" | "7d" | "30d" | "90d";

export interface AnalyticsSummary {
  active_users: number;
  total_logins: number;
  total_searches: number;
  total_creates: number;
  total_photo_extracts: number;
  total_pubchem_fetches: number;
  range_start: string;
  range_end: string;
}

export interface UserStatsRow {
  user_id: string;
  email: string;
  last_login_at: string | null;
  logins_in_range: number;
  searches: number;
  chemicals_created: number;
  containers_created: number;
  orders_created: number;
  wishlist_added: number;
  photo_extracts: number;
}

export interface TopSearchRow {
  query: string;
  count: number;
  avg_result_count: number;
  empty_count: number;
}

export interface SlowEndpointRow {
  method: string;
  path: string;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  count: number;
  error_count: number;
}
```

- [ ] **Step 2: Create the hooks**

Create `frontend/src/api/hooks/useAdminAnalytics.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import client from "../client";
import type {
  AnalyticsRange,
  AnalyticsSummary,
  SlowEndpointRow,
  TopSearchRow,
  UserStatsRow,
} from "../../types";

export function useAnalyticsSummary(range: AnalyticsRange) {
  return useQuery<AnalyticsSummary>({
    queryKey: ["admin-analytics", "summary", range],
    queryFn: () =>
      client
        .get<AnalyticsSummary>(`/admin/analytics/summary`, { params: { range } })
        .then((r) => r.data),
  });
}

export function useAnalyticsUsers(range: AnalyticsRange) {
  return useQuery<UserStatsRow[]>({
    queryKey: ["admin-analytics", "users", range],
    queryFn: () =>
      client
        .get<UserStatsRow[]>(`/admin/analytics/users`, { params: { range } })
        .then((r) => r.data),
  });
}

export function useAnalyticsTopSearches(range: AnalyticsRange, limit = 20) {
  return useQuery<TopSearchRow[]>({
    queryKey: ["admin-analytics", "top-searches", range, limit],
    queryFn: () =>
      client
        .get<TopSearchRow[]>(`/admin/analytics/top-searches`, {
          params: { range, limit },
        })
        .then((r) => r.data),
  });
}

export function useAnalyticsSlowEndpoints(range: AnalyticsRange, limit = 20) {
  return useQuery<SlowEndpointRow[]>({
    queryKey: ["admin-analytics", "slow-endpoints", range, limit],
    queryFn: () =>
      client
        .get<SlowEndpointRow[]>(`/admin/analytics/slow-endpoints`, {
          params: { range, limit },
        })
        .then((r) => r.data),
  });
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```
git add frontend/src/types/index.ts frontend/src/api/hooks/useAdminAnalytics.ts
git commit -m "feat(api): admin analytics types + react-query hooks"
```

---

### Task 15: AnalyticsSection — KPIs + per-user table

**Files:**
- Create: `frontend/src/components/settings/AnalyticsSection.tsx`

- [ ] **Step 1: Create the component skeleton with KPIs and user table**

Create `frontend/src/components/settings/AnalyticsSection.tsx`:

```tsx
import { useState } from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  MenuItem,
  Select,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TableSortLabel,
  Typography,
} from "@mui/material";
import type { SelectChangeEvent } from "@mui/material";
import { SectionHeader } from "./SectionHeader";
import {
  useAnalyticsSummary,
  useAnalyticsUsers,
} from "../../api/hooks/useAdminAnalytics";
import type { AnalyticsRange, UserStatsRow } from "../../types";

const RANGE_OPTIONS: { value: AnalyticsRange; label: string }[] = [
  { value: "24h", label: "Letzte 24h" },
  { value: "7d", label: "Letzte 7 Tage" },
  { value: "30d", label: "Letzte 30 Tage" },
  { value: "90d", label: "Letzte 90 Tage" },
];

type UserSortField = "email" | "last_login_at" | "logins_in_range" | "searches" | "chemicals_created" | "containers_created" | "photo_extracts";

export function AnalyticsSection() {
  const [range, setRange] = useState<AnalyticsRange>("7d");
  const [sortField, setSortField] = useState<UserSortField>("last_login_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const summary = useAnalyticsSummary(range);
  const users = useAnalyticsUsers(range);

  const onRangeChange = (e: SelectChangeEvent<AnalyticsRange>) => {
    setRange(e.target.value as AnalyticsRange);
  };

  const handleSort = (field: UserSortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const sortedUsers = sortUsers(users.data ?? [], sortField, sortDir);

  return (
    <Box>
      <SectionHeader
        title="Analytics"
        subtitle="Nutzungs- und Performance-Daten dieser Instanz. Superuser-only."
      />

      <Stack spacing={2}>
        <Box>
          <Select<AnalyticsRange>
            size="small"
            value={range}
            onChange={onRangeChange}
            sx={{ minWidth: 200 }}
          >
            {RANGE_OPTIONS.map((o) => (
              <MenuItem key={o.value} value={o.value}>
                {o.label}
              </MenuItem>
            ))}
          </Select>
        </Box>

        {summary.isError && (
          <Alert severity="error">
            Konnte Summary nicht laden — bitte neu laden.
          </Alert>
        )}

        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: {
              xs: "1fr 1fr",
              md: "repeat(4, 1fr)",
            },
          }}
        >
          <KpiCard
            label="Aktive User"
            value={summary.data?.active_users}
            loading={summary.isLoading}
          />
          <KpiCard
            label="Logins"
            value={summary.data?.total_logins}
            loading={summary.isLoading}
          />
          <KpiCard
            label="Suchen"
            value={summary.data?.total_searches}
            loading={summary.isLoading}
          />
          <KpiCard
            label="Foto-Extract"
            value={summary.data?.total_photo_extracts}
            loading={summary.isLoading}
          />
        </Box>

        <Box>
          <Typography variant="h5" sx={{ mb: 1 }}>
            Per User
          </Typography>
          {users.isError && (
            <Alert severity="error">
              Konnte User-Liste nicht laden.
            </Alert>
          )}
          {users.isLoading ? (
            <Stack spacing={1}>
              <Skeleton height={32} />
              <Skeleton height={32} />
              <Skeleton height={32} />
            </Stack>
          ) : sortedUsers.length === 0 ? (
            <Typography color="text.secondary">
              Keine User im Zeitraum aktiv.
            </Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <SortHeader field="email" current={sortField} dir={sortDir} onClick={handleSort}>
                    User
                  </SortHeader>
                  <SortHeader field="last_login_at" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Last seen
                  </SortHeader>
                  <SortHeader field="logins_in_range" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Logins
                  </SortHeader>
                  <SortHeader field="searches" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Suchen
                  </SortHeader>
                  <SortHeader field="chemicals_created" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Chemicals
                  </SortHeader>
                  <SortHeader field="containers_created" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Container
                  </SortHeader>
                  <SortHeader field="photo_extracts" current={sortField} dir={sortDir} onClick={handleSort} align="right">
                    Foto
                  </SortHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {sortedUsers.map((row) => (
                  <TableRow key={row.user_id}>
                    <TableCell>{row.email}</TableCell>
                    <TableCell align="right">{formatLastSeen(row.last_login_at)}</TableCell>
                    <TableCell align="right">{row.logins_in_range}</TableCell>
                    <TableCell align="right">{row.searches}</TableCell>
                    <TableCell align="right">{row.chemicals_created}</TableCell>
                    <TableCell align="right">{row.containers_created}</TableCell>
                    <TableCell align="right">{row.photo_extracts}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Box>
      </Stack>
    </Box>
  );
}

function KpiCard({ label, value, loading }: { label: string; value: number | undefined; loading: boolean }) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        {loading ? (
          <Skeleton width={60} height={36} />
        ) : (
          <Typography variant="h3">{value ?? 0}</Typography>
        )}
      </CardContent>
    </Card>
  );
}

function SortHeader({
  field, current, dir, onClick, children, align,
}: {
  field: UserSortField;
  current: UserSortField;
  dir: "asc" | "desc";
  onClick: (f: UserSortField) => void;
  children: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <TableCell align={align ?? "left"}>
      <TableSortLabel
        active={current === field}
        direction={current === field ? dir : "desc"}
        onClick={() => onClick(field)}
      >
        {children}
      </TableSortLabel>
    </TableCell>
  );
}

function sortUsers(rows: UserStatsRow[], field: UserSortField, dir: "asc" | "desc"): UserStatsRow[] {
  const out = [...rows];
  out.sort((a, b) => {
    const av = a[field];
    const bv = b[field];
    // last_login_at: null sorts last regardless of dir.
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    if (typeof av === "string" && typeof bv === "string") {
      return dir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
    }
    return dir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
  });
  return out;
}

function formatLastSeen(iso: string | null): string {
  if (!iso) return "nie";
  const date = new Date(iso);
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "gerade eben";
  if (diffMin < 60) return `vor ${diffMin}min`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `vor ${diffHr}h`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `vor ${diffDay}d`;
  return date.toLocaleDateString();
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/components/settings/AnalyticsSection.tsx
git commit -m "feat(settings): AnalyticsSection — KPI cards + per-user table"
```

---

### Task 16: AnalyticsSection — Top searches + Slow endpoints

**Files:**
- Modify: `frontend/src/components/settings/AnalyticsSection.tsx`

- [ ] **Step 1: Extend imports**

In `frontend/src/components/settings/AnalyticsSection.tsx`, extend the hooks import:

```tsx
import {
  useAnalyticsSummary,
  useAnalyticsUsers,
  useAnalyticsTopSearches,
  useAnalyticsSlowEndpoints,
} from "../../api/hooks/useAdminAnalytics";
```

And the types import:

```tsx
import type { AnalyticsRange, SlowEndpointRow, TopSearchRow, UserStatsRow } from "../../types";
```

Add MUI imports for `Divider` and `List`/`ListItem`/`ListItemText`:

```tsx
import {
  Alert,
  Box,
  Card,
  CardContent,
  Divider,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Select,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TableSortLabel,
  Typography,
} from "@mui/material";
```

- [ ] **Step 2: Wire the two additional queries inside the component**

Just below the existing `const users = useAnalyticsUsers(range);` line, add:

```tsx
const topSearches = useAnalyticsTopSearches(range);
const slowEndpoints = useAnalyticsSlowEndpoints(range);
```

- [ ] **Step 3: Render the two lists side-by-side after the user table**

Just before the closing `</Stack>` of the main layout, add:

```tsx
<Divider />

<Box
  sx={{
    display: "grid",
    gap: 3,
    gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
  }}
>
  <Box>
    <Typography variant="h5" sx={{ mb: 1 }}>
      Top Suchen
    </Typography>
    {topSearches.isError && <Alert severity="error">Konnte Suchen nicht laden.</Alert>}
    {topSearches.isLoading ? (
      <Skeleton height={200} />
    ) : (topSearches.data ?? []).length === 0 ? (
      <Typography color="text.secondary">Keine Suchen im Zeitraum.</Typography>
    ) : (
      <List dense disablePadding>
        {(topSearches.data ?? []).map((row: TopSearchRow) => (
          <ListItem key={row.query} disableGutters>
            <ListItemText
              primary={row.query}
              secondary={
                row.empty_count > 0
                  ? `${row.count}× · ${row.empty_count} ohne Treffer`
                  : `${row.count}×`
              }
            />
          </ListItem>
        ))}
      </List>
    )}
  </Box>

  <Box>
    <Typography variant="h5" sx={{ mb: 1 }}>
      Slow Endpoints
    </Typography>
    {slowEndpoints.isError && (
      <Alert severity="error">Konnte Endpoints nicht laden.</Alert>
    )}
    {slowEndpoints.isLoading ? (
      <Skeleton height={200} />
    ) : (slowEndpoints.data ?? []).length === 0 ? (
      <Typography color="text.secondary">Alles schnell im Zeitraum.</Typography>
    ) : (
      <List dense disablePadding>
        {(slowEndpoints.data ?? []).map((row: SlowEndpointRow) => (
          <ListItem key={`${row.method}-${row.path}`} disableGutters>
            <ListItemText
              primary={`${row.method} ${row.path}`}
              secondary={
                row.error_count > 0
                  ? `p95 ${row.p95_ms}ms · ${row.count}× · ${row.error_count} Fehler`
                  : `p95 ${row.p95_ms}ms · ${row.count}×`
              }
            />
          </ListItem>
        ))}
      </List>
    )}
  </Box>
</Box>
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```
git add frontend/src/components/settings/AnalyticsSection.tsx
git commit -m "feat(settings): AnalyticsSection — top searches + slow endpoints lists"
```

---

### Task 17: Wire AnalyticsSection into SettingsPage

**Files:**
- Modify: `frontend/src/components/settings/SettingsNav.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Extend the section-key union**

In `frontend/src/components/settings/SettingsNav.tsx`, replace the `SettingsSectionKey` union:

```ts
export type SettingsSectionKey =
  | "account"
  | "group"
  | "members"
  | "hazard-tags"
  | "suppliers"
  | "projects"
  | "import"
  | "chemicals-admin"
  | "groups"
  | "buildings"
  | "system"
  | "analytics";
```

- [ ] **Step 2: Add the nav item and the render branch**

In `frontend/src/pages/SettingsPage.tsx`, add the import:

```tsx
import { AnalyticsSection } from "../components/settings/AnalyticsSection";
```

In the `items` array, insert a new entry between `groups` and `buildings`:

```tsx
{ key: "analytics", label: "Analytics", group: "SUPERUSER", visible: isSuperuser },
```

In the JSX, add the render branch alongside the other superuser sections (next to the `system` line):

```tsx
{active === "analytics" && isSuperuser && <AnalyticsSection />}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```
git add frontend/src/components/settings/SettingsNav.tsx frontend/src/pages/SettingsPage.tsx
git commit -m "feat(settings): expose Analytics section to superusers"
```

---

## Phase 5 — Smoke Test

### Task 18: End-to-end manual smoke

**Files:** none

- [ ] **Step 1: Start the backend**

Run: `uv run uvicorn chaima.app:app --reload --port 8000`

- [ ] **Step 2: Start the frontend dev server**

In another terminal: `cd frontend && npm run dev`

- [ ] **Step 3: Walk through the smoke list — mark ✓ or ✗ in the conversation**

1. ☐ Log in as the superuser. Settings → SUPERUSER group shows **Analytics** entry.
2. ☐ Log in as a regular user (or open in incognito). Settings does **not** show Analytics.
3. ☐ Click Analytics. KPI cards render with at least `0`s, no errors.
4. ☐ Switch the range select to `24h`, then `30d`. Page reloads counts each time without errors.
5. ☐ Open a Chemicals page. Search for "acet" — no event. Search for "aceto" — within seconds, refresh Analytics, the search appears in **Top Suchen** with count 1.
6. ☐ Create a new container — refresh Analytics, **Per User** count for "Container" increments by 1.
7. ☐ Trigger a Photo-Extract from the chemical drawer — **Foto-Extract** KPI increments.
8. ☐ Hit a `404` URL (e.g. `/api/v1/nope`) — that is NOT logged. Now hit an endpoint that returns `500` (force one by killing PubChem and triggering enrich) — **Slow Endpoints** should show that path.
9. ☐ Log out and back in — `last_login_at` updates, `Logins` counter for your user increments.
10. ☐ Enter wrong password twice — refresh Analytics, **Logins** for users does NOT increment, but a `login_failure` event exists (check via direct query or wait for it to show in a future "failed logins" widget — out of scope for v1 UI).
11. ☐ Hit `POST /api/v1/admin/analytics/_compact` from the network tab — returns `{ ok-ish counts }`. Refresh Analytics — fresh-period numbers unchanged.

- [ ] **Step 4: Capture any fixes in a follow-up commit**

If anything needed adjusting, fix it and commit. Otherwise no commit needed.

---

## Self-Review

**Spec coverage:**
- Data model: User counters (T2), Event/EventDaily/SlowRequest (T3), Alembic migration (T4) ✓
- Performance guarantees: WAL pragma (T1), BackgroundTasks helper (T5), middleware (T10), failure tolerance baked into `_persist_event` (T5) and `_make_background` (T10) ✓
- Write paths: login_success/failure (T6), search_executed (T7), 4× create events (T8), photo_extract + pubchem_fetch (T9), slow_request (T10) ✓
- Read API: summary / users / top-searches / slow-endpoints (T12), _compact (T13) ✓
- Frontend: SettingsPage wiring (T17), AnalyticsSection w/ KPIs + tables + lists (T15+T16), types + hooks (T14) ✓
- Retention: 30d for `event`, 365d for `event_daily`, 30d for `slow_request` — all in `services.analytics.compact` (T11) ✓
- Cron trigger: external cron calling `_compact` — endpoint exists (T13); the cron itself is ops, not code ✓

**Placeholder scan:** None — every step has a runnable command or complete code block. The Alembic revision hash is generated by the `alembic revision` command in Task 4, not a placeholder.

**Type consistency:**
- `EventType` enum defined in T3, used identically in T5/T6/T7/T8/T9 ✓
- `log_event` signature stable across T5 (definition), T7/T8/T9 (callers) ✓
- `_persist_event` signature stable across T5 (definition), T6/T9 (direct callers without BackgroundTasks) ✓
- `range_to_window` / `summary` / `user_stats` / `top_searches` / `slow_endpoints` / `compact` signatures match between `services/analytics.py` (T11) and `routers/admin_analytics.py` (T12/T13) ✓
- Frontend `AnalyticsRange = "24h" | "7d" | "30d" | "90d"` matches backend `Range` literal ✓
- `UserStatsRow` / `TopSearchRow` / `SlowEndpointRow` / `AnalyticsSummary` shapes match the dict shapes returned by `services/analytics.py` ✓
