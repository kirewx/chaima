"""API tests for admin-issued password reset links."""
import pytest
import pytest_asyncio
from sqlmodel import select

from chaima.models.analytics import Event
from chaima.models.group import Group, UserGroupLink


@pytest_asyncio.fixture
async def admin_link(session, user, group):
    """Make `user` (alice) an admin of `group`."""
    link = UserGroupLink(user_id=user.id, group_id=group.id, is_admin=True)
    session.add(link)
    await session.flush()
    return link


@pytest_asyncio.fixture
async def target_link(session, other_user, group):
    """Make `other_user` (bob) a plain member of `group`."""
    link = UserGroupLink(user_id=other_user.id, group_id=group.id, is_admin=False)
    session.add(link)
    await session.flush()
    return link


@pytest.mark.asyncio
async def test_admin_can_issue_reset_link(
    client, session, group, other_user, admin_link, target_link
):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["token"]
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_issuing_writes_an_audit_event_naming_the_actor(
    client, session, group, user, other_user, admin_link, target_link
):
    """The event records WHO authorised the reset, with the target in the payload."""
    await client.post(f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link")

    events = (
        await session.exec(
            select(Event).where(Event.type == "password_reset_link_created")
        )
    ).all()
    assert len(events) == 1
    assert events[0].user_id == user.id
    assert events[0].group_id == group.id
    assert events[0].payload == {"target_user_id": str(other_user.id)}


@pytest.mark.asyncio
async def test_plain_member_cannot_issue(
    client, session, group, other_user, membership, target_link
):
    """`membership` makes alice a NON-admin member, so GroupAdminDep refuses."""
    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_issue_for_user_in_an_unadministered_group(
    client, session, group, other_user, admin_link, target_link
):
    """Bob also belongs to a group alice does not administer."""
    foreign = Group(name="Lab Beta")
    session.add(foreign)
    await session.flush()
    session.add(UserGroupLink(user_id=other_user.id, group_id=foreign.id, is_admin=False))
    await session.flush()

    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_issue_for_superuser(
    client, session, group, superuser, admin_link
):
    session.add(UserGroupLink(user_id=superuser.id, group_id=group.id, is_admin=True))
    await session.flush()

    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{superuser.id}/reset-link"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_target_must_be_a_member_of_the_group_in_the_path(
    client, session, group, other_user, admin_link
):
    """GroupAdminDep only proves alice administers THIS group.

    Without an explicit membership check the caller could put any user ID
    in the path and reset a stranger's password.
    """
    resp = await client.post(
        f"/api/v1/groups/{group.id}/members/{other_user.id}/reset-link"
    )
    assert resp.status_code == 404
