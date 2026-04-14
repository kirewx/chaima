import datetime

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


async def test_create_user(session):
    u = User(
        email="bob@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=False,
    )
    session.add(u)
    await session.commit()

    result = await session.get(User, u.id)
    assert result is not None
    assert result.email == "bob@example.com"
    assert result.is_superuser is False
    assert isinstance(result.created_at, datetime.datetime)


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


async def test_user_dark_mode_defaults_to_false(user):
    assert user.dark_mode is False


async def test_user_dark_mode_can_be_enabled(session, user):
    user.dark_mode = True
    session.add(user)
    await session.commit()
    await session.refresh(user)
    assert user.dark_mode is True
