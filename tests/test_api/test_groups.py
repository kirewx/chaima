"""API tests for the groups router."""

import pytest

from chaima.models.group import Group, UserGroupLink
from chaima.models.user import User
from chaima.schemas.group import GroupRead, MemberRead


@pytest.mark.asyncio
async def test_create_group_returns_201(superuser_client):
    """POST /api/v1/groups should create a group and return 201 (superuser only)."""
    resp = await superuser_client.post(
        "/api/v1/groups",
        json={"name": "New Lab", "description": "A new lab group"},
    )
    assert resp.status_code == 201

    result = GroupRead.model_validate(resp.json())
    assert result.name == "New Lab"
    assert result.description == "A new lab group"
    assert result.id is not None
    assert result.created_at is not None


@pytest.mark.asyncio
async def test_create_group_minimal(superuser_client):
    """POST /api/v1/groups should work with only a name (superuser only)."""
    resp = await superuser_client.post(
        "/api/v1/groups",
        json={"name": "Minimal Group"},
    )
    assert resp.status_code == 201

    result = GroupRead.model_validate(resp.json())
    assert result.name == "Minimal Group"
    assert result.description is None


@pytest.mark.asyncio
async def test_list_groups_returns_user_groups(client, session, user):
    """GET /api/v1/groups should return groups the current user belongs to."""
    # Create a group and add user as member
    group = Group(name="My Group")
    session.add(group)
    await session.flush()
    link = UserGroupLink(user_id=user.id, group_id=group.id, is_admin=False)
    session.add(link)
    await session.flush()

    resp = await client.get("/api/v1/groups")
    assert resp.status_code == 200

    groups_data = resp.json()
    assert len(groups_data) == 1
    result = GroupRead.model_validate(groups_data[0])
    assert result.name == "My Group"


@pytest.mark.asyncio
async def test_list_groups_excludes_non_member_groups(client, session, user):
    """GET /api/v1/groups should not return groups the user is not in."""
    other_group = Group(name="Not My Group")
    session.add(other_group)
    await session.flush()

    resp = await client.get("/api/v1/groups")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_group_as_member(client, group, membership):
    """GET /api/v1/groups/{group_id} should return the group if user is a member."""
    resp = await client.get(f"/api/v1/groups/{group.id}")
    assert resp.status_code == 200

    result = GroupRead.model_validate(resp.json())
    assert result.id == group.id
    assert result.name == group.name


@pytest.mark.asyncio
async def test_get_group_not_member_returns_403(client, session):
    """GET /api/v1/groups/{group_id} should return 403 if user is not a member."""
    other_group = Group(name="Private Group")
    session.add(other_group)
    await session.flush()

    resp = await client.get(f"/api/v1/groups/{other_group.id}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_group_not_found_returns_404(client):
    """GET /api/v1/groups/{group_id} should return 404 if group does not exist."""
    import uuid

    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/groups/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_group_as_admin(client, group, admin_membership):
    """PATCH /api/v1/groups/{group_id} should update the group when user is admin."""
    resp = await client.patch(
        f"/api/v1/groups/{group.id}",
        json={"name": "Updated Lab", "description": "New description"},
    )
    assert resp.status_code == 200

    result = GroupRead.model_validate(resp.json())
    assert result.name == "Updated Lab"
    assert result.description == "New description"


@pytest.mark.asyncio
async def test_update_group_not_admin_returns_403(client, group, membership):
    """PATCH /api/v1/groups/{group_id} should return 403 when user is not admin."""
    resp = await client.patch(
        f"/api/v1/groups/{group.id}",
        json={"name": "Should Fail"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_group_partial(client, group, admin_membership):
    """PATCH /api/v1/groups/{group_id} should support partial updates."""
    resp = await client.patch(
        f"/api/v1/groups/{group.id}",
        json={"description": "Only description updated"},
    )
    assert resp.status_code == 200

    result = GroupRead.model_validate(resp.json())
    assert result.name == group.name
    assert result.description == "Only description updated"


@pytest.mark.asyncio
async def test_add_member_as_admin(client, session, group, admin_membership):
    """POST /api/v1/groups/{group_id}/members should add a member when admin."""
    new_user = User(
        email="bob@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(new_user)
    await session.flush()

    resp = await client.post(
        f"/api/v1/groups/{group.id}/members",
        json={"user_id": str(new_user.id), "is_admin": False},
    )
    assert resp.status_code == 201

    result = MemberRead.model_validate(resp.json())
    assert result.user_id == new_user.id
    assert result.group_id == group.id
    assert result.email == "bob@example.com"
    assert result.is_admin is False


@pytest.mark.asyncio
async def test_add_member_duplicate_returns_409(client, session, group, admin_membership, user):
    """POST /api/v1/groups/{group_id}/members should return 409 for duplicate."""
    # user is already a member via admin_membership
    resp = await client.post(
        f"/api/v1/groups/{group.id}/members",
        json={"user_id": str(user.id), "is_admin": False},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_remove_member_as_admin(client, session, group, admin_membership):
    """DELETE /api/v1/groups/{group_id}/members/{user_id} should remove member."""
    other_user = User(
        email="carol@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(other_user)
    await session.flush()
    other_link = UserGroupLink(
        user_id=other_user.id, group_id=group.id, is_admin=False
    )
    session.add(other_link)
    await session.flush()

    resp = await client.delete(
        f"/api/v1/groups/{group.id}/members/{other_user.id}"
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_remove_member_not_found_returns_404(client, session, group, admin_membership):
    """DELETE /api/v1/groups/{group_id}/members/{user_id} returns 404 if not member."""
    import uuid

    fake_id = uuid.uuid4()
    resp = await client.delete(f"/api/v1/groups/{group.id}/members/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_member_role_as_admin(client, session, group, admin_membership):
    """PATCH /api/v1/groups/{group_id}/members/{user_id} should update role."""
    other_user = User(
        email="dave@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(other_user)
    await session.flush()
    other_link = UserGroupLink(
        user_id=other_user.id, group_id=group.id, is_admin=False
    )
    session.add(other_link)
    await session.flush()

    resp = await client.patch(
        f"/api/v1/groups/{group.id}/members/{other_user.id}",
        json={"is_admin": True},
    )
    assert resp.status_code == 200

    result = MemberRead.model_validate(resp.json())
    assert result.user_id == other_user.id
    assert result.is_admin is True
    assert result.email == "dave@example.com"
