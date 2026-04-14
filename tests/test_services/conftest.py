import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
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


@pytest_asyncio.fixture
async def user(session):
    u = User(
        email="alice@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(u)
    await session.flush()
    return u


@pytest_asyncio.fixture
async def group(session):
    g = Group(name="Lab Alpha")
    session.add(g)
    await session.flush()
    return g


@pytest_asyncio.fixture
async def membership(session, user, group):
    link = UserGroupLink(user_id=user.id, group_id=group.id, is_admin=False)
    session.add(link)
    await session.flush()
    return link


@pytest_asyncio.fixture
async def other_user(session):
    u = User(
        email="bob@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(u)
    await session.flush()
    return u


@pytest_asyncio.fixture
async def superuser(session):
    u = User(
        email="admin@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    session.add(u)
    await session.flush()
    return u


@pytest_asyncio.fixture
async def chemical(session, group, user):
    from chaima.models.chemical import Chemical

    c = Chemical(group_id=group.id, name="Ethanol", created_by=user.id)
    session.add(c)
    await session.flush()
    return c
