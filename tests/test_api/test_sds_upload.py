import io

import pytest


async def test_sds_upload_stores_pdf_and_sets_path(client, group, membership):
    # Create chemical
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "SDSTest"},
    )
    assert r.status_code in (200, 201)
    cid = r.json()["id"]

    pdf_bytes = b"%PDF-1.4\n%EOF\n"
    files = {"file": ("msds.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/{cid}/sds",
        files=files,
    )
    assert r.status_code == 200
    assert r.json()["sds_path"].endswith(".pdf")


async def test_sds_upload_rejects_non_pdf(client, group, membership):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "BadSDS"},
    )
    cid = r.json()["id"]

    files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/{cid}/sds",
        files=files,
    )
    assert r.status_code == 415
