import pytest


@pytest.mark.asyncio
async def test_create_and_list_project(client, group, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/projects", json={"name": "Catalysis"}
    )
    assert resp.status_code == 201
    proj_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/groups/{group.id}/projects")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(p["id"] == proj_id and p["name"] == "Catalysis" for p in items)


@pytest.mark.asyncio
async def test_create_project_dedupes_case_insensitively(client, group, membership):
    r1 = await client.post(f"/api/v1/groups/{group.id}/projects", json={"name": "X"})
    r2 = await client.post(f"/api/v1/groups/{group.id}/projects", json={"name": "x"})
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_archive_project_admin_only(client, group, membership):
    """Members can create but not archive."""
    r = await client.post(f"/api/v1/groups/{group.id}/projects", json={"name": "Y"})
    pid = r.json()["id"]
    resp = await client.post(f"/api/v1/groups/{group.id}/projects/{pid}/archive")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_archive_project_as_admin(client, group, admin_membership):
    r = await client.post(f"/api/v1/groups/{group.id}/projects", json={"name": "Y"})
    pid = r.json()["id"]
    resp = await client.post(f"/api/v1/groups/{group.id}/projects/{pid}/archive")
    assert resp.status_code == 200
    assert resp.json()["is_archived"] is True
