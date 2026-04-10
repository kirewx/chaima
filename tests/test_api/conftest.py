import pytest_asyncio
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.app import app
from chaima.db import get_async_session
from chaima.auth import current_active_user, current_superuser
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
async def admin_membership(session, user, group):
    link = UserGroupLink(user_id=user.id, group_id=group.id, is_admin=True)
    session.add(link)
    await session.flush()
    return link


@pytest_asyncio.fixture
async def client(engine, session, user):
    """AsyncClient with session and auth overrides."""
    async def _override_session():
        yield session

    def _raise_forbidden():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required")

    app.dependency_overrides[get_async_session] = _override_session
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[current_superuser] = _raise_forbidden

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def superuser_client(engine, session, superuser):
    """AsyncClient authenticated as a superuser."""
    async def _override_session():
        yield session

    app.dependency_overrides[get_async_session] = _override_session
    app.dependency_overrides[current_active_user] = lambda: superuser
    app.dependency_overrides[current_superuser] = lambda: superuser

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
