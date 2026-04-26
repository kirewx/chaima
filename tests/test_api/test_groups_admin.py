"""API tests for the superuser-only ``?scope=all`` group listing."""

import pytest

from chaima.models.group import Group
from chaima.schemas.group import GroupRead


@pytest.mark.asyncio
async def test_list_groups_scope_all_as_superuser_returns_all(
    superuser_client, session
):
    """GET /api/v1/groups?scope=all should return every group for superusers."""
    # The ``superuser`` fixture is created with a ``main_group_id`` pointing at
    # the ``group`` fixture (Lab Alpha), so that group already exists.
    other_a = Group(name="Other A", description="A other")
    other_b = Group(name="Other B")
    session.add(other_a)
    session.add(other_b)
    await session.flush()

    resp = await superuser_client.get("/api/v1/groups", params={"scope": "all"})
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 3
    items = body["items"]
    assert isinstance(items, list)
    names = sorted(GroupRead.model_validate(d).name for d in items)
    # All groups in the system, regardless of superuser membership.
    assert names == ["Lab Alpha", "Other A", "Other B"]


@pytest.mark.asyncio
async def test_list_groups_scope_all_as_regular_user_returns_403(
    client, session
):
    """GET /api/v1/groups?scope=all should be forbidden for non-superusers."""
    # Add a group the user is not in to make the test meaningful.
    session.add(Group(name="Hidden Group"))
    await session.flush()

    resp = await client.get("/api/v1/groups", params={"scope": "all"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_groups_default_scope_mine_for_regular_user(
    client, session, user, membership, group
):
    """Default GET /api/v1/groups (no scope) still returns only the user's groups."""
    # Add a group the user is NOT a member of; it must be excluded.
    other = Group(name="Not Mine")
    session.add(other)
    await session.flush()

    resp = await client.get("/api/v1/groups")
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 1
    items = body["items"]
    assert len(items) == 1
    result = GroupRead.model_validate(items[0])
    assert result.id == group.id
    assert result.name == "Lab Alpha"


@pytest.mark.asyncio
async def test_list_groups_default_scope_mine_for_superuser(
    superuser_client, session, superuser, group
):
    """Default scope for a superuser still returns only their memberships, not all groups."""
    # Superuser has main_group_id but is NOT linked via UserGroupLink.
    # The ``mine`` scope filters by UserGroupLink, so without a link no groups appear.
    extra = Group(name="Extra Lab")
    session.add(extra)
    await session.flush()

    resp = await superuser_client.get("/api/v1/groups")
    assert resp.status_code == 200

    # The superuser fixture has no UserGroupLink, so default scope yields [].
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_list_groups_pagination_limits_and_offsets(superuser_client, session):
    """GET /api/v1/groups?scope=all should respect limit and offset."""
    # Add a couple of groups; the ``group`` fixture's "Lab Alpha" already exists.
    session.add(Group(name="Other A"))
    session.add(Group(name="Other B"))
    await session.flush()

    # First page (limit=2): should return 2 items but total=3.
    resp = await superuser_client.get(
        "/api/v1/groups", params={"scope": "all", "limit": 2, "offset": 0}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2

    # Second page (offset=2, limit=2): should return the remaining 1 item.
    resp2 = await superuser_client.get(
        "/api/v1/groups", params={"scope": "all", "limit": 2, "offset": 2}
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["total"] == 3
    assert body2["offset"] == 2
    assert len(body2["items"]) == 1

    # Pages should not overlap.
    page1_names = {GroupRead.model_validate(d).name for d in body["items"]}
    page2_names = {GroupRead.model_validate(d).name for d in body2["items"]}
    assert page1_names.isdisjoint(page2_names)
    assert page1_names | page2_names == {"Lab Alpha", "Other A", "Other B"}
