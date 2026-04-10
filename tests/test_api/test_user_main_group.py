# tests/test_api/test_user_main_group.py
import pytest
import pytest_asyncio
from chaima.models.group import Group, UserGroupLink


@pytest_asyncio.fixture
async def second_group(session):
    g = Group(name="Second Lab")
    session.add(g)
    await session.flush()
    return g


@pytest_asyncio.fixture
async def second_membership(session, user, second_group):
    link = UserGroupLink(user_id=user.id, group_id=second_group.id)
    session.add(link)
    await session.flush()
    return link


@pytest.mark.asyncio
async def test_update_main_group(client, session, user, group, membership, second_group, second_membership):
    resp = await client.patch(
        "/api/v1/users/me/main-group",
        json={"group_id": str(second_group.id)},
    )
    assert resp.status_code == 200
    assert resp.json()["main_group_id"] == str(second_group.id)


@pytest.mark.asyncio
async def test_update_main_group_not_member(client, session, user, group, membership):
    other = Group(name="Other")
    session.add(other)
    await session.flush()

    resp = await client.patch(
        "/api/v1/users/me/main-group",
        json={"group_id": str(other.id)},
    )
    assert resp.status_code == 403
