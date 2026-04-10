import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


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
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def group(session):
    from chaima.models.group import Group

    g = Group(name="Lab Alpha")
    session.add(g)
    await session.flush()
    return g


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


@pytest_asyncio.fixture
async def chemical(session, group, user):
    from chaima.models.chemical import Chemical

    c = Chemical(group_id=group.id, name="Ethanol", created_by=user.id)
    session.add(c)
    await session.flush()
    return c


@pytest_asyncio.fixture
async def storage_location(session):
    from chaima.models.storage import StorageLocation

    loc = StorageLocation(name="Room A")
    session.add(loc)
    await session.flush()
    return loc


@pytest_asyncio.fixture
async def supplier(session, group):
    from chaima.models.supplier import Supplier

    s = Supplier(name="Sigma Aldrich", group_id=group.id)
    session.add(s)
    await session.flush()
    return s
