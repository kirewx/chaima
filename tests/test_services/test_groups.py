"""Service layer tests for group management."""

import pytest
from sqlmodel import select

from chaima.models.group import Group, UserGroupLink
from chaima.models.project import Project
from chaima.models.supplier import Supplier
from chaima.models.user import User
from chaima.services import groups as svc
from chaima.services.groups import (
    MemberExistsError,
    MemberNotFoundError,
    add_member,
    create_group,
    get_group,
    list_groups_for_user,
    list_members,
    remove_member,
    update_group,
    update_member_role,
)


@pytest.mark.asyncio
async def test_create_group_creates_group_and_admin_link(session, user):
    """create_group should create the group and add the creator as admin."""
    group = await create_group(
        session,
        name="Test Group",
        description="A test group",
        creator_id=user.id,
    )

    assert isinstance(group, Group)
    assert group.id is not None
    assert group.name == "Test Group"
    assert group.description == "A test group"

    # Verify admin link was created
    from sqlmodel import select

    result = await session.exec(
        select(UserGroupLink).where(
            UserGroupLink.user_id == user.id,
            UserGroupLink.group_id == group.id,
        )
    )
    link = result.first()
    assert link is not None
    assert link.is_admin is True


@pytest.mark.asyncio
async def test_list_groups_for_user_returns_groups(session, user, group, membership):
    """list_groups_for_user should return all groups the user belongs to."""
    groups = await list_groups_for_user(session, user.id)

    assert len(groups) == 1
    assert groups[0].id == group.id
    assert groups[0].name == group.name


@pytest.mark.asyncio
async def test_list_groups_for_user_excludes_other_groups(session, user):
    """list_groups_for_user should not return groups the user is not in."""
    other_group = Group(name="Other Group")
    session.add(other_group)
    await session.flush()

    groups = await list_groups_for_user(session, user.id)
    assert groups == []


@pytest.mark.asyncio
async def test_get_group_returns_existing_group(session, group):
    """get_group should return the group when it exists."""
    result = await get_group(session, group.id)

    assert result is not None
    assert result.id == group.id
    assert result.name == group.name


@pytest.mark.asyncio
async def test_get_group_returns_none_for_missing_group(session):
    """get_group should return None when group does not exist."""
    import uuid

    result = await get_group(session, uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_update_group_name(session, group):
    """update_group should update the group's name."""
    updated = await update_group(session, group, name="New Name")

    assert updated.name == "New Name"
    assert updated.id == group.id


@pytest.mark.asyncio
async def test_update_group_description(session, group):
    """update_group should update the group's description."""
    updated = await update_group(session, group, description="New description")

    assert updated.description == "New description"
    assert updated.name == group.name


@pytest.mark.asyncio
async def test_update_group_no_changes(session, group):
    """update_group with no arguments should leave the group unchanged."""
    original_name = group.name
    updated = await update_group(session, group)

    assert updated.name == original_name


@pytest.mark.asyncio
async def test_add_member_creates_link(session, group):
    """add_member should create a UserGroupLink."""
    new_user = User(
        email="bob@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(new_user)
    await session.flush()

    link = await add_member(session, group.id, new_user.id, is_admin=False)

    assert isinstance(link, UserGroupLink)
    assert link.user_id == new_user.id
    assert link.group_id == group.id
    assert link.is_admin is False


@pytest.mark.asyncio
async def test_add_member_as_admin(session, group):
    """add_member with is_admin=True should create an admin link."""
    new_user = User(
        email="carol@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(new_user)
    await session.flush()

    link = await add_member(session, group.id, new_user.id, is_admin=True)

    assert link.is_admin is True


@pytest.mark.asyncio
async def test_add_member_duplicate_raises_error(session, user, group, membership):
    """add_member should raise MemberExistsError when the user is already a member."""
    with pytest.raises(MemberExistsError):
        await add_member(session, group.id, user.id)


@pytest.mark.asyncio
async def test_remove_member_deletes_link(session, user, group, membership):
    """remove_member should delete the membership link."""
    await remove_member(session, group.id, user.id)

    from sqlmodel import select

    result = await session.exec(
        select(UserGroupLink).where(
            UserGroupLink.user_id == user.id,
            UserGroupLink.group_id == group.id,
        )
    )
    assert result.first() is None


@pytest.mark.asyncio
async def test_remove_member_not_found_raises_error(session, user, group):
    """remove_member should raise MemberNotFoundError when user is not a member."""
    with pytest.raises(MemberNotFoundError):
        await remove_member(session, group.id, user.id)


@pytest.mark.asyncio
async def test_update_member_role_promotes_to_admin(session, user, group, membership):
    """update_member_role should promote a member to admin."""
    assert membership.is_admin is False

    updated_link = await update_member_role(
        session, group.id, user.id, is_admin=True
    )

    assert updated_link.is_admin is True


@pytest.mark.asyncio
async def test_update_member_role_demotes_from_admin(session, user, group):
    """update_member_role should demote an admin to regular member."""
    admin_link = UserGroupLink(user_id=user.id, group_id=group.id, is_admin=True)
    session.add(admin_link)
    await session.flush()

    updated_link = await update_member_role(
        session, group.id, user.id, is_admin=False
    )

    assert updated_link.is_admin is False


@pytest.mark.asyncio
async def test_update_member_role_not_found_raises_error(session, user, group):
    """update_member_role should raise MemberNotFoundError when user is not a member."""
    with pytest.raises(MemberNotFoundError):
        await update_member_role(session, group.id, user.id, is_admin=True)


@pytest.mark.asyncio
async def test_list_members_returns_all_members(session, group):
    """list_members should return all members with their user data."""
    user_a = User(
        email="alice@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    user_b = User(
        email="bob@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user_a)
    session.add(user_b)
    await session.flush()

    link_a = UserGroupLink(user_id=user_a.id, group_id=group.id, is_admin=True)
    link_b = UserGroupLink(user_id=user_b.id, group_id=group.id, is_admin=False)
    session.add(link_a)
    session.add(link_b)
    await session.flush()

    members = await list_members(session, group.id)

    assert len(members) == 2
    emails = {u.email for _link, u in members}
    assert "alice@example.com" in emails
    assert "bob@example.com" in emails


@pytest.mark.asyncio
async def test_create_group_pre_seeds_general_project(session, user):
    g = await svc.create_group(session, name="New Lab", creator_id=user.id)
    rows = (await session.exec(select(Project).where(Project.group_id == g.id))).all()
    names = sorted(p.name for p in rows)
    assert names == ["General"]


@pytest.mark.asyncio
async def test_create_group_pre_seeds_ten_suppliers(session, user):
    g = await svc.create_group(session, name="New Lab", creator_id=user.id)
    rows = (await session.exec(select(Supplier).where(Supplier.group_id == g.id))).all()
    assert len(rows) == 10
    assert {s.name for s in rows} == {
        "Sigma-Aldrich", "Merck", "Carl Roth", "abcr", "BLDPharm",
        "TCI", "Alfa Aesar", "Fisher Scientific", "Thermo Fisher", "VWR",
    }
