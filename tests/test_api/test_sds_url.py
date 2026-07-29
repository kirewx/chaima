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


PDF = b"%PDF-1.4\n%EOF\n"


async def _make_chem_with_url(client, group, url="https://example.com/sds.pdf"):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": f"Fetch-{url[-10:]}", "sds_url": url},
    )
    assert r.status_code in (200, 201)
    return r.json()["id"]


async def test_sds_fetch_stores_pdf(client, group, admin_membership, monkeypatch):
    from chaima.services import sds_fetch

    async def fake_fetch(url, **kwargs):
        assert url == "https://example.com/sds.pdf"
        return PDF

    monkeypatch.setattr(sds_fetch, "fetch_sds_pdf", fake_fetch)
    cid = await _make_chem_with_url(client, group)

    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/{cid}/sds-fetch")
    assert r.status_code == 200
    assert r.json()["sds_path"].endswith(".pdf")

    r = await client.get(f"/api/v1/groups/{group.id}/chemicals/{cid}/sds")
    assert r.status_code == 200
    assert r.content == PDF


async def test_sds_fetch_409_without_url(client, group, admin_membership):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals", json={"name": "NoUrl"},
    )
    cid = r.json()["id"]
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/{cid}/sds-fetch")
    assert r.status_code == 409


async def test_sds_fetch_409_when_pdf_already_stored(client, group, admin_membership, monkeypatch):
    from chaima.services import sds_fetch

    async def fake_fetch(url, **kwargs):
        return PDF

    monkeypatch.setattr(sds_fetch, "fetch_sds_pdf", fake_fetch)
    cid = await _make_chem_with_url(client, group, "https://example.com/twice.pdf")
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/{cid}/sds-fetch")
    assert r.status_code == 200
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/{cid}/sds-fetch")
    assert r.status_code == 409


async def test_sds_fetch_502_on_fetch_error(client, group, admin_membership, monkeypatch):
    from chaima.services import sds_fetch

    async def fake_fetch(url, **kwargs):
        raise sds_fetch.SdsFetchError("The link is not a PDF")

    monkeypatch.setattr(sds_fetch, "fetch_sds_pdf", fake_fetch)
    cid = await _make_chem_with_url(client, group, "https://example.com/bad.pdf")
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/{cid}/sds-fetch")
    assert r.status_code == 502
    assert "not a PDF" in r.json()["detail"]


async def test_sds_fetch_502_on_empty_body(client, group, admin_membership, monkeypatch):
    from chaima.services import sds_fetch

    async def fake_fetch(url, **kwargs):
        return b""

    monkeypatch.setattr(sds_fetch, "fetch_sds_pdf", fake_fetch)
    cid = await _make_chem_with_url(client, group, "https://example.com/empty.pdf")
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/{cid}/sds-fetch")
    assert r.status_code == 502


async def test_sds_fetch_forbidden_for_non_admin(client, group, membership):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "MemberFetch", "sds_url": "https://example.com/sds.pdf"},
    )
    cid = r.json()["id"]
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/{cid}/sds-fetch")
    assert r.status_code == 403
