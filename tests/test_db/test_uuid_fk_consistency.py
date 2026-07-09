"""Regression: UUID encoding must be consistent across FK boundaries.

fastapi-users stored ``user.id`` as a dashed CHAR(36) string while the app's
own ``uuid.UUID`` columns store an undashed 32-hex string. Same logical value,
different bytes — so every FK to ``user.id`` dangled. With SQLite FK
enforcement OFF (the historical default) this was silently accepted; once the
app turned ``PRAGMA foreign_keys=ON`` on, every insert referencing a user
(container, chemical, invite, order, ...) failed with IntegrityError.

This test runs against an engine configured exactly like production (FK
enforcement on) and pins that a container can be inserted for a real user.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.db import _set_sqlite_pragmas
from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.group import Group
from chaima.models.storage import StorageKind, StorageLocation
from chaima.models.user import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def fk_session():
    """A session on an engine with production SQLite pragmas (FK enforced)."""
    from sqlalchemy import event as sa_event

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    sa_event.listen(engine.sync_engine, "connect", _set_sqlite_pragmas)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        # Prove FK enforcement is actually active on this connection.
        assert (await sess.execute(text("PRAGMA foreign_keys"))).scalar() == 1
        yield sess
    await engine.dispose()


async def test_container_insert_references_user_under_fk_enforcement(fk_session):
    """Inserting a container whose created_by points at a real user must work."""
    session = fk_session
    group = Group(name="Lab Alpha")
    session.add(group)
    await session.flush()

    user = User(
        email="alice@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        main_group_id=group.id,
    )
    session.add(user)
    await session.flush()

    chem = Chemical(group_id=group.id, name="Acetone", created_by=user.id)
    loc = StorageLocation(name="Shelf 1", kind=StorageKind.SHELF)
    session.add_all([chem, loc])
    await session.flush()

    container = Container(
        chemical_id=chem.id,
        location_id=loc.id,
        identifier="ID-1",
        amount=400.0,
        unit="ml",
        created_by=user.id,
    )
    session.add(container)
    # Under the encoding mismatch this raises IntegrityError: FK constraint failed.
    await session.flush()

    assert container.id is not None


async def test_user_id_and_referencing_columns_share_encoding(fk_session):
    """user.id and container.created_by must serialize to the same string."""
    session = fk_session
    group = Group(name="Lab Alpha")
    session.add(group)
    await session.flush()
    user = User(
        email="bob@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_verified=True,
        main_group_id=group.id,
    )
    session.add(user)
    await session.flush()

    stored_user_id = (
        await session.execute(
            text("SELECT id FROM user WHERE id = :hexid"), {"hexid": user.id.hex}
        )
    ).scalar()
    # The row must be findable by the SAME encoding the FK columns use (.hex).
    assert stored_user_id is not None
    assert "-" not in stored_user_id
