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
async def test_seed_admin_email_passes_schema_validation(session):
    """The seeded admin email must pass UserRead (pydantic EmailStr) validation."""
    from chaima.app import seed_admin
    from chaima.schemas.user import UserRead

    await seed_admin(session)

    result = await session.exec(select(User).where(User.is_superuser == True))
    user = result.first()
    assert user is not None

    # This is the exact call fastapi-users makes on GET /users/me
    validated = UserRead.model_validate(user)
    assert validated.email == user.email


@pytest.mark.asyncio
async def test_seed_creates_superuser(session):
    from chaima.app import seed_admin

    await seed_admin(session)

    result = await session.exec(select(User).where(User.is_superuser == True))
    user = result.first()
    assert user is not None
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
