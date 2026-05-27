import io

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from chaima.services.images import MAX_IMAGE_BYTES, validate_image_upload


def _jpeg_bytes(width: int = 64, height: int = 64) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(255, 0, 0)).save(buf, format="JPEG")
    return buf.getvalue()


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(0, 255, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _upload(name: str, mime: str, data: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(data), headers={"content-type": mime})


def test_validate_image_accepts_jpeg():
    data = _jpeg_bytes()
    validate_image_upload(_upload("a.jpg", "image/jpeg", data), data)


def test_validate_image_accepts_png():
    data = _png_bytes()
    validate_image_upload(_upload("a.png", "image/png", data), data)


def test_validate_image_accepts_webp():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(0, 0, 255)).save(buf, format="WEBP")
    data = buf.getvalue()
    validate_image_upload(_upload("a.webp", "image/webp", data), data)


def test_validate_image_rejects_text_mime():
    with pytest.raises(HTTPException) as exc:
        validate_image_upload(_upload("a.txt", "text/plain", b"hello"), b"hello")
    assert exc.value.status_code == 415


def test_validate_image_rejects_bytes_not_matching_mime():
    with pytest.raises(HTTPException) as exc:
        validate_image_upload(_upload("fake.jpg", "image/jpeg", b"not an image"), b"not an image")
    assert exc.value.status_code == 415


def test_validate_image_rejects_oversize():
    big = b"\x00" * (MAX_IMAGE_BYTES + 1)
    with pytest.raises(HTTPException) as exc:
        validate_image_upload(_upload("big.jpg", "image/jpeg", big), big)
    assert exc.value.status_code == 413


def test_validate_image_accepts_heic_by_mime_only():
    # Pillow may not support HEIC magic-byte validation; accept by MIME, skip image.verify.
    # We pass a tiny JPEG body but with heic mime — should pass (MIME whitelist allows heic,
    # and we don't run verify on heic). See implementation note.
    data = b"\x00\x00\x00\x20ftypheic" + b"\x00" * 32  # minimal HEIC-ish header
    validate_image_upload(_upload("a.heic", "image/heic", data), data)
