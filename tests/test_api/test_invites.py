import pytest
import pytest_asyncio
from chaima.models.group import Group, UserGroupLink
from chaima.models.invite import Invite
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
