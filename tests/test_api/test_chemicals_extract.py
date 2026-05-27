import io

import pytest
from PIL import Image

from chaima.services.vision import ExtractedLabel


def _jpeg(width=64, height=64) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 100, 50)).save(buf, format="JPEG")
    return buf.getvalue()


async def test_extract_happy_path(client, group, membership, monkeypatch):
    monkeypatch.setattr(
        "chaima.routers.chemicals.vision_service.extract_from_image",
        lambda data, mime: ExtractedLabel(
            cas="67-64-1", name="Acetone", amount=1000, unit="mL", confidence="high",
        ),
    )
    files = {"file": ("label.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/extract-from-photo", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["cas"] == "67-64-1"
    assert body["name"] == "Acetone"
    assert body["amount"] == 1000
    assert body["unit"] == "mL"
    assert body["confidence"] == "high"


async def test_extract_rejects_text_mime(client, group, membership):
    files = {"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")}
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/extract-from-photo", files=files)
    assert r.status_code == 415


async def test_extract_rejects_invalid_image_data(client, group, membership):
    # Claims to be JPEG but isn't
    files = {"file": ("fake.jpg", io.BytesIO(b"not an image"), "image/jpeg")}
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/extract-from-photo", files=files)
    assert r.status_code == 415


async def test_extract_rejects_oversize(client, group, membership):
    big = b"\xff\xd8\xff" + b"\x00" * (10 * 1024 * 1024 + 1)
    files = {"file": ("big.jpg", io.BytesIO(big), "image/jpeg")}
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/extract-from-photo", files=files)
    assert r.status_code == 413


async def test_extract_503_when_key_missing(client, group, membership, monkeypatch):
    from fastapi import HTTPException
    def _raise(data, mime):
        raise HTTPException(status_code=503, detail="vision_not_configured")
    monkeypatch.setattr(
        "chaima.routers.chemicals.vision_service.extract_from_image", _raise,
    )
    files = {"file": ("label.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/extract-from-photo", files=files)
    assert r.status_code == 503
    assert r.json()["detail"] == "vision_not_configured"


async def test_extract_502_when_vision_fails(client, group, membership, monkeypatch):
    from fastapi import HTTPException
    def _raise(data, mime):
        raise HTTPException(status_code=502, detail="vision_service_unavailable")
    monkeypatch.setattr(
        "chaima.routers.chemicals.vision_service.extract_from_image", _raise,
    )
    files = {"file": ("label.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await client.post(f"/api/v1/groups/{group.id}/chemicals/extract-from-photo", files=files)
    assert r.status_code == 502
