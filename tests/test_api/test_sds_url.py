async def test_create_chemical_with_sds_url(client, group, admin_membership):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "UrlChem", "sds_url": "https://example.com/sds.pdf"},
    )
    assert r.status_code in (200, 201)
    assert r.json()["sds_url"] == "https://example.com/sds.pdf"


async def test_create_chemical_rejects_non_http_sds_url(client, group, admin_membership):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "BadUrl", "sds_url": "javascript:alert(1)"},
    )
    assert r.status_code == 422


async def test_create_chemical_rejects_overlong_sds_url(client, group, admin_membership):
    long_url = "https://example.com/" + "a" * 2000
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "LongUrl", "sds_url": long_url},
    )
    assert r.status_code == 422


async def test_create_chemical_empty_sds_url_becomes_null(client, group, admin_membership):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "EmptyUrl", "sds_url": "   "},
    )
    assert r.status_code in (200, 201)
    assert r.json()["sds_url"] is None


async def test_update_chemical_sets_and_clears_sds_url(client, group, admin_membership):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals", json={"name": "PatchUrl"},
    )
    cid = r.json()["id"]

    r = await client.patch(
        f"/api/v1/groups/{group.id}/chemicals/{cid}",
        json={"sds_url": "https://example.com/a.pdf"},
    )
    assert r.status_code == 200
    assert r.json()["sds_url"] == "https://example.com/a.pdf"

    r = await client.patch(
        f"/api/v1/groups/{group.id}/chemicals/{cid}", json={"sds_url": None},
    )
    assert r.status_code == 200
    assert r.json()["sds_url"] is None
