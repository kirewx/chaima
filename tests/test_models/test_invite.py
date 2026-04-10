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
