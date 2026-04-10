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
