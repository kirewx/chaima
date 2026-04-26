import pytest


@pytest.mark.asyncio
async def test_create_wishlist_with_chemical_id(client, group, chemical, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/wishlist",
        json={"chemical_id": str(chemical.id), "comment": "please"},
    )
    assert resp.status_code == 201
    assert resp.json()["chemical_id"] == str(chemical.id)


@pytest.mark.asyncio
async def test_create_wishlist_freeform(client, group, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/wishlist",
        json={"freeform_name": "Mystery reagent", "freeform_cas": "1-2-3"},
    )
    assert resp.status_code == 201
    assert resp.json()["freeform_name"] == "Mystery reagent"


@pytest.mark.asyncio
async def test_list_wishlist_only_open(client, group, chemical, membership):
    r1 = await client.post(f"/api/v1/groups/{group.id}/wishlist", json={"chemical_id": str(chemical.id)})
    await client.post(f"/api/v1/groups/{group.id}/wishlist/{r1.json()['id']}/dismiss")

    r2 = await client.post(f"/api/v1/groups/{group.id}/wishlist", json={"chemical_id": str(chemical.id), "comment": "still open"})

    resp = await client.get(f"/api/v1/groups/{group.id}/wishlist")
    ids = [item["id"] for item in resp.json()["items"]]
    assert r2.json()["id"] in ids
    assert r1.json()["id"] not in ids


@pytest.mark.asyncio
async def test_promote_with_chemical_id_returns_chemical(
    client, group, chemical, membership
):
    r = await client.post(
        f"/api/v1/groups/{group.id}/wishlist", json={"chemical_id": str(chemical.id)},
    )
    wid = r.json()["id"]
    resp = await client.post(f"/api/v1/groups/{group.id}/wishlist/{wid}/promote")
    assert resp.status_code == 200
    assert resp.json()["chemical_id"] == str(chemical.id)
