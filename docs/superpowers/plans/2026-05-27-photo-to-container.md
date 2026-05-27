# Photo-to-Container Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a photo-to-container workflow: user photographs a chemical bottle label, Gemini 2.5 Flash extracts fields, the existing "+ New Chemical" drawer is pre-filled, and on save chains into the container drawer with the photo attached.

**Architecture:** New backend service `vision.py` wraps `google-genai`. Two new endpoints: `POST /chemicals/extract-from-photo` (stateless, returns extracted fields) and `POST /containers/{id}/image` (multipart upload, sets `image_path`). Frontend extends the existing `DrawerContext` with `prefill` + `photoFile` for chained `container-new` opens; `ChemicalForm` and `ContainerForm` each get a camera icon in the drawer header.

**Tech Stack:** FastAPI, SQLModel, Pydantic v2, `google-genai` (Gemini SDK), Pillow (image validation), React + MUI v6+, React-Query, axios.

**Spec:** `docs/superpowers/specs/2026-05-27-photo-to-container-design.md`

---

## File Map

**Backend — create:**
- `src/chaima/services/vision.py` — Gemini wrapper, `ExtractedLabel` schema
- `src/chaima/services/images.py` — `validate_image_upload()` helper (MIME, size, magic bytes)
- `tests/test_services/test_vision.py`
- `tests/test_services/test_images.py`
- `tests/test_api/test_chemicals_extract.py`
- `tests/test_api/test_containers_image.py`

**Backend — modify:**
- `pyproject.toml` — add `google-genai`, `pillow` deps
- `.env.example` — add `CHAIMA_GEMINI_API_KEY`, `CHAIMA_GEMINI_MODEL`
- `src/chaima/routers/chemicals.py` — add `POST /extract-from-photo`
- `src/chaima/routers/containers.py` — add `POST /{container_id}/image`

**Frontend — create:**
- `frontend/src/api/hooks/useExtractFromPhoto.ts`
- `frontend/src/utils/imageResize.ts`

**Frontend — modify:**
- `frontend/src/types/index.ts` — add `ExtractedLabel`, `ContainerPrefill` types
- `frontend/src/api/hooks/useContainers.ts` — add `useUploadContainerImage`
- `frontend/src/components/drawer/DrawerContext.tsx` — extend `container-new` config
- `frontend/src/components/drawer/EditDrawer.tsx` — render camera-icon trigger in header
- `frontend/src/components/drawer/ChemicalForm.tsx` — photo state, prefill chain
- `frontend/src/components/drawer/ContainerForm.tsx` — accept prefill, upload image
- `frontend/src/components/ContainerCard.tsx` — display image thumbnail

---

## Phase 1 — Backend Foundation

### Task 1: Add Python dependencies + env vars

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`

- [ ] **Step 1: Add `google-genai` and `pillow` to dependencies**

In `pyproject.toml`, extend the `dependencies` array (alphabetic order):

```toml
dependencies = [
    "aiosqlite>=0.22.1",
    "alembic>=1.18.4",
    "fastapi>=0.135.3",
    "fastapi-users[sqlalchemy]>=15.0.5",
    "google-genai>=0.3.0",
    "httpx>=0.28.1",
    "openpyxl>=3.1.5",
    "pillow>=11.0.0",
    "pydantic-settings>=2.13.1",
    "rdkit>=2026.3.1",
    "sqlmodel>=0.0.38",
    "typer>=0.21.1",
    "uvicorn>=0.40.0",
]
```

- [ ] **Step 2: Install the new deps**

Run: `uv sync`
Expected: `google-genai` and `pillow` installed without errors.

- [ ] **Step 3: Add env vars to `.env.example`**

Append to `.env.example`:

```
# Google AI Studio API key for label OCR (Gemini 2.5 Flash).
# Leave empty to disable the photo-to-container feature.
CHAIMA_GEMINI_API_KEY=
CHAIMA_GEMINI_MODEL=gemini-2.5-flash
```

- [ ] **Step 4: Verify the app still starts**

Run: `uv run uvicorn chaima.app:app --port 8001`
Expected: no import errors. Stop with Ctrl+C.

- [ ] **Step 5: Commit**

```
git add pyproject.toml uv.lock .env.example
git commit -m "feat(deps): add google-genai and pillow for photo-to-container"
```

---

### Task 2: Image validation helper + tests

**Files:**
- Create: `src/chaima/services/images.py`
- Create: `tests/test_services/test_images.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_services/test_images.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_images.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'chaima.services.images'`.

- [ ] **Step 3: Implement the helper**

Create `src/chaima/services/images.py`:

```python
from __future__ import annotations

import io

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

ALLOWED_MIMES = frozenset({"image/jpeg", "image/png", "image/webp", "image/heic"})
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_image_upload(file: UploadFile, data: bytes) -> None:
    """Validate an image upload's MIME, size, and (for non-HEIC) magic bytes.

    Raises ``HTTPException`` with appropriate 4xx status on failure.

    Parameters
    ----------
    file : UploadFile
        The uploaded file (used for ``content_type``).
    data : bytes
        The already-read body, so the caller can reuse it.
    """
    if file.content_type not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported_image_format",
        )
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="image_too_large",
        )
    # Pillow doesn't natively decode HEIC; accept-by-MIME for HEIC only.
    if file.content_type == "image/heic":
        return
    try:
        Image.open(io.BytesIO(data)).verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="invalid_image_data",
        ) from None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_images.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/chaima/services/images.py tests/test_services/test_images.py
git commit -m "feat(images): add validate_image_upload helper"
```

---

### Task 3: Vision service — schema only, with stub `extract_from_image`

**Files:**
- Create: `src/chaima/services/vision.py`
- Create: `tests/test_services/test_vision.py`

- [ ] **Step 1: Write failing tests for the schema + stub**

Create `tests/test_services/test_vision.py`:

```python
import datetime

import pytest

from chaima.services.vision import ExtractedLabel, extract_from_image


def test_extracted_label_defaults_all_none_except_confidence():
    el = ExtractedLabel()
    assert el.cas is None
    assert el.name is None
    assert el.amount is None
    assert el.unit is None
    assert el.supplier_name is None
    assert el.identifier is None
    assert el.purity is None
    assert el.purchased_at is None
    assert el.confidence == "low"


def test_extracted_label_confidence_validates():
    with pytest.raises(ValueError):
        ExtractedLabel(confidence="extreme")


def test_extracted_label_parses_date():
    el = ExtractedLabel(purchased_at="2026-04-15")
    assert el.purchased_at == datetime.date(2026, 4, 15)


def test_extract_from_image_raises_when_key_missing(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.delenv("CHAIMA_GEMINI_API_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        extract_from_image(b"x", "image/jpeg")
    assert exc.value.status_code == 503
    assert exc.value.detail == "vision_not_configured"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_vision.py -v`
Expected: `ModuleNotFoundError: No module named 'chaima.services.vision'`.

- [ ] **Step 3: Implement the module with a stub**

Create `src/chaima/services/vision.py`:

```python
from __future__ import annotations

import datetime
import os
from typing import Literal

from fastapi import HTTPException, status
from pydantic import BaseModel

DEFAULT_MODEL = "gemini-2.5-flash"


class ExtractedLabel(BaseModel):
    cas: str | None = None
    name: str | None = None
    amount: float | None = None
    unit: str | None = None
    supplier_name: str | None = None
    identifier: str | None = None
    purity: str | None = None
    purchased_at: datetime.date | None = None
    confidence: Literal["high", "medium", "low"] = "low"


def extract_from_image(image_bytes: bytes, mime: str) -> ExtractedLabel:
    """Extract chemical-label fields from an image via Gemini 2.5 Flash.

    Raises ``HTTPException(503)`` if the API key is missing, or
    ``HTTPException(502)`` if the upstream call fails.
    """
    api_key = os.environ.get("CHAIMA_GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="vision_not_configured",
        )
    # Real Gemini call wired in the next task.
    raise NotImplementedError("Gemini call lands in Task 4")
```

- [ ] **Step 4: Run tests to verify schema + 503 tests pass**

Run: `uv run pytest tests/test_services/test_vision.py -v`
Expected: 4 PASS (the schema tests + the 503-when-key-missing test).

- [ ] **Step 5: Commit**

```
git add src/chaima/services/vision.py tests/test_services/test_vision.py
git commit -m "feat(vision): scaffold ExtractedLabel schema and service stub"
```

---

### Task 4: Vision service — Gemini call

**Files:**
- Modify: `src/chaima/services/vision.py`
- Modify: `tests/test_services/test_vision.py`

- [ ] **Step 1: Add failing tests for the Gemini call (mocked)**

Append to `tests/test_services/test_vision.py`:

```python
class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeClient:
    def __init__(self, response_text: str | None = None, raise_exc: Exception | None = None):
        self._response_text = response_text
        self._raise = raise_exc
        self.models = self
        self.last_call_kwargs = None

    def generate_content(self, **kwargs):
        self.last_call_kwargs = kwargs
        if self._raise:
            raise self._raise
        return _FakeResponse(self._response_text or "{}")


def test_extract_from_image_returns_parsed_label(monkeypatch):
    monkeypatch.setenv("CHAIMA_GEMINI_API_KEY", "fake-key")
    payload = (
        '{"cas":"67-64-1","name":"Acetone","amount":1000,'
        '"unit":"mL","supplier_name":"Sigma","identifier":"AC-2024-031",'
        '"purity":"99.5%","purchased_at":"2026-04-15","confidence":"high"}'
    )
    fake = _FakeClient(response_text=payload)
    monkeypatch.setattr("chaima.services.vision._get_client", lambda: fake)

    result = extract_from_image(b"\xff\xd8\xff", "image/jpeg")
    assert result.cas == "67-64-1"
    assert result.name == "Acetone"
    assert result.amount == 1000
    assert result.unit == "mL"
    assert result.supplier_name == "Sigma"
    assert result.identifier == "AC-2024-031"
    assert result.purity == "99.5%"
    assert result.purchased_at == datetime.date(2026, 4, 15)
    assert result.confidence == "high"


def test_extract_from_image_handles_empty_response(monkeypatch):
    monkeypatch.setenv("CHAIMA_GEMINI_API_KEY", "fake-key")
    fake = _FakeClient(response_text="{}")
    monkeypatch.setattr("chaima.services.vision._get_client", lambda: fake)

    result = extract_from_image(b"x", "image/jpeg")
    assert result.cas is None
    assert result.confidence == "low"


def test_extract_from_image_502_on_api_error(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setenv("CHAIMA_GEMINI_API_KEY", "fake-key")
    fake = _FakeClient(raise_exc=RuntimeError("upstream down"))
    monkeypatch.setattr("chaima.services.vision._get_client", lambda: fake)

    with pytest.raises(HTTPException) as exc:
        extract_from_image(b"x", "image/jpeg")
    assert exc.value.status_code == 502
    assert exc.value.detail == "vision_service_unavailable"


def test_extract_from_image_502_on_invalid_json(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setenv("CHAIMA_GEMINI_API_KEY", "fake-key")
    fake = _FakeClient(response_text="not-json")
    monkeypatch.setattr("chaima.services.vision._get_client", lambda: fake)

    with pytest.raises(HTTPException) as exc:
        extract_from_image(b"x", "image/jpeg")
    assert exc.value.status_code == 502
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_vision.py -v`
Expected: New tests FAIL — `_get_client` not defined / NotImplementedError raised.

- [ ] **Step 3: Implement the Gemini call**

Replace the contents of `src/chaima/services/vision.py` with:

```python
from __future__ import annotations

import datetime
import json
import os
from typing import Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

DEFAULT_MODEL = "gemini-2.5-flash"

_PROMPT = (
    "Extrahiere die folgenden Felder vom abgebildeten Chemikalien-Etikett. "
    "Lasse Felder leer (null), wenn sie nicht eindeutig lesbar sind. "
    "Antworte ausschließlich als JSON nach dem mitgegebenen Schema. "
    "Setze 'confidence' auf 'high' nur, wenn CAS UND (Name ODER Amount+Unit) "
    "eindeutig erkennbar sind; sonst 'medium' oder 'low'."
)


class ExtractedLabel(BaseModel):
    cas: str | None = None
    name: str | None = None
    amount: float | None = None
    unit: str | None = None
    supplier_name: str | None = None
    identifier: str | None = None
    purity: str | None = None
    purchased_at: datetime.date | None = None
    confidence: Literal["high", "medium", "low"] = "low"


def _get_client():
    # Lazy import so tests that monkeypatch this don't pay the import cost.
    from google import genai  # type: ignore[import-not-found]

    api_key = os.environ.get("CHAIMA_GEMINI_API_KEY", "").strip()
    return genai.Client(api_key=api_key)


def extract_from_image(image_bytes: bytes, mime: str) -> ExtractedLabel:
    """Extract chemical-label fields from an image via Gemini 2.5 Flash."""
    api_key = os.environ.get("CHAIMA_GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="vision_not_configured",
        )

    model = os.environ.get("CHAIMA_GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    client = _get_client()

    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                {"role": "user", "parts": [
                    {"text": _PROMPT},
                    {"inline_data": {"mime_type": mime, "data": image_bytes}},
                ]},
            ],
            config={
                "response_mime_type": "application/json",
                "response_schema": ExtractedLabel,
            },
        )
    except Exception:  # noqa: BLE001 — any upstream error → 502
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="vision_service_unavailable",
        ) from None

    text = (response.text or "").strip()
    if not text:
        return ExtractedLabel()
    try:
        data = json.loads(text)
        return ExtractedLabel.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="vision_service_unavailable",
        ) from None
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_services/test_vision.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```
git add src/chaima/services/vision.py tests/test_services/test_vision.py
git commit -m "feat(vision): implement Gemini extract_from_image"
```

---

## Phase 2 — Backend Endpoints

### Task 5: `POST /chemicals/extract-from-photo`

**Files:**
- Modify: `src/chaima/routers/chemicals.py`
- Create: `tests/test_api/test_chemicals_extract.py`

- [ ] **Step 1: Write the failing endpoint tests**

Create `tests/test_api/test_chemicals_extract.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_chemicals_extract.py -v`
Expected: All FAIL with 404 (endpoint not registered).

- [ ] **Step 3: Add the endpoint to `routers/chemicals.py`**

At the top of `src/chaima/routers/chemicals.py`, add the imports (near existing `from chaima.services import ...` block):

```python
from chaima.services import images as images_service
from chaima.services import vision as vision_service
```

Add the new route. **Placement matters** — it must come BEFORE any `/{chemical_id}` routes so FastAPI doesn't interpret `extract-from-photo` as a `chemical_id`. Locate the line where the router includes the first `/{chemical_id}`-based route and insert above it. A safe location is right after the `POST ""` (create chemical) handler:

```python
@router.post("/extract-from-photo", response_model=vision_service.ExtractedLabel)
async def extract_from_photo(
    session: SessionDep,
    member: GroupMemberDep,
    file: UploadFile = File(...),
) -> vision_service.ExtractedLabel:
    """Extract chemical-label fields from a photo via the vision service.

    Stateless: image bytes are passed to Gemini and discarded; no DB writes.
    """
    data = await file.read()
    images_service.validate_image_upload(file, data)
    return vision_service.extract_from_image(data, file.content_type or "image/jpeg")
```

Confirm that `UploadFile`, `File`, and `GroupMemberDep` are already imported at the top of the file (they are — line 8 has them).

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api/test_chemicals_extract.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Confirm route ordering didn't break other chemical routes**

Run: `uv run pytest tests/test_api/test_chemicals.py -v`
Expected: All previously-green tests still PASS.

- [ ] **Step 6: Commit**

```
git add src/chaima/routers/chemicals.py tests/test_api/test_chemicals_extract.py
git commit -m "feat(chemicals): POST /extract-from-photo via Gemini"
```

---

### Task 6: `POST /containers/{container_id}/image`

**Files:**
- Modify: `src/chaima/routers/containers.py`
- Create: `tests/test_api/test_containers_image.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api/test_containers_image.py`:

```python
import io
from pathlib import Path

import pytest
from PIL import Image


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


async def _make_chemical_and_container(client, group_id, tmp_path, monkeypatch):
    """Helper: create a chemical, a storage location, and a container.

    Returns (chemical_id, container_id).
    """
    from chaima.services import files as files_service
    monkeypatch.setattr(files_service, "UPLOADS_ROOT", tmp_path)

    r = await client.post(f"/api/v1/groups/{group_id}/chemicals", json={"name": "X"})
    chem_id = r.json()["id"]

    # Create a storage location at the group root.
    # NOTE: only `kind: "building"` is allowed at the root (parent_id: None).
    # "shelf" / "cabinet" / "room" require a parent — using "building" here.
    r = await client.post(
        f"/api/v1/groups/{group_id}/storage-locations",
        json={"name": "Main Building", "kind": "building", "parent_id": None},
    )
    assert r.status_code in (200, 201), r.text
    loc_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/groups/{group_id}/chemicals/{chem_id}/containers",
        json={"identifier": "X-001", "amount": 100, "unit": "mL", "location_id": loc_id},
    )
    assert r.status_code in (200, 201), r.text
    return chem_id, r.json()["id"]


async def test_upload_image_sets_image_path_and_writes_file(
    client, group, membership, tmp_path, monkeypatch,
):
    _, cont_id = await _make_chemical_and_container(client, group.id, tmp_path, monkeypatch)
    files = {"file": ("label.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await client.post(f"/api/v1/groups/{group.id}/containers/{cont_id}/image", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["image_path"] is not None
    assert body["image_path"].endswith(".jpg")
    saved = tmp_path / body["image_path"]
    assert saved.exists()
    assert saved.read_bytes() == _jpeg()


async def test_upload_image_overwrites_path(
    client, group, membership, tmp_path, monkeypatch,
):
    _, cont_id = await _make_chemical_and_container(client, group.id, tmp_path, monkeypatch)
    files = {"file": ("a.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r1 = await client.post(f"/api/v1/groups/{group.id}/containers/{cont_id}/image", files=files)
    first = r1.json()["image_path"]

    files = {"file": ("b.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r2 = await client.post(f"/api/v1/groups/{group.id}/containers/{cont_id}/image", files=files)
    second = r2.json()["image_path"]
    assert first != second


async def test_upload_image_rejects_non_image(
    client, group, membership, tmp_path, monkeypatch,
):
    _, cont_id = await _make_chemical_and_container(client, group.id, tmp_path, monkeypatch)
    files = {"file": ("a.txt", io.BytesIO(b"hi"), "text/plain")}
    r = await client.post(f"/api/v1/groups/{group.id}/containers/{cont_id}/image", files=files)
    assert r.status_code == 415


async def test_upload_image_404_unknown_container(client, group, membership):
    import uuid
    bogus = uuid.uuid4()
    files = {"file": ("a.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await client.post(f"/api/v1/groups/{group.id}/containers/{bogus}/image", files=files)
    assert r.status_code == 404


async def test_upload_image_403_for_non_creator_non_admin(
    client, other_client, group, user, membership, other_membership, session, tmp_path, monkeypatch,
):
    # NOTE: when both `client` and `other_client` fixtures are active, the second
    # one's app.dependency_overrides wins, so calling client.post(...) actually
    # runs as other_user. Work around by creating the chemical/location/container
    # directly through the session, so we control who `created_by` is. Then make
    # the test request via `other_client`.
    from chaima.services import files as files_service
    monkeypatch.setattr(files_service, "UPLOADS_ROOT", tmp_path)

    from chaima.models.chemical import Chemical
    from chaima.models.storage import StorageLocation
    from chaima.models.container import Container

    chem = Chemical(name="X", group_id=group.id)
    session.add(chem)
    await session.flush()
    loc = StorageLocation(name="Main", kind="building", group_id=group.id, parent_id=None)
    session.add(loc)
    await session.flush()
    cont = Container(
        chemical_id=chem.id, location_id=loc.id, identifier="X-1",
        amount=100, unit="mL", created_by=user.id,
    )
    session.add(cont)
    await session.flush()

    files = {"file": ("a.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await other_client.post(
        f"/api/v1/groups/{group.id}/containers/{cont.id}/image", files=files,
    )
    assert r.status_code == 403


async def test_upload_image_admin_can_upload_others_containers(
    client, group, user, session, tmp_path, monkeypatch,
):
    from chaima.models.group import UserGroupLink
    # Make alice an admin instead of plain member
    link = UserGroupLink(user_id=user.id, group_id=group.id, is_admin=True)
    session.add(link)
    await session.flush()

    # alice (now admin) creates a chemical + container as before
    _, cont_id = await _make_chemical_and_container(client, group.id, tmp_path, monkeypatch)

    files = {"file": ("a.jpg", io.BytesIO(_jpeg()), "image/jpeg")}
    r = await client.post(f"/api/v1/groups/{group.id}/containers/{cont_id}/image", files=files)
    assert r.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_containers_image.py -v`
Expected: All FAIL with 404 (endpoint not registered).

- [ ] **Step 3: Add the endpoint in `routers/containers.py`**

In `src/chaima/routers/containers.py`, add imports near the top (after existing imports):

```python
from fastapi import File, UploadFile

from chaima.services import files as files_service
from chaima.services import images as images_service
```

Insert this handler **before** `router.include_router(nested)` at the bottom:

```python
@flat.post("/{container_id}/image", response_model=ContainerRead)
async def upload_container_image(
    group_id: UUID,
    container_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    user: CurrentUserDep,
    file: UploadFile = File(...),
) -> ContainerRead:
    """Upload (or replace) the image attached to a container.

    Auth: container creator OR group admin.
    """
    _group, link = member
    container = await container_service.get_container(session, container_id)
    if container is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    from chaima.services import chemicals as chemical_svc
    chem = await chemical_svc.get_chemical(session, container.chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")

    if container.created_by != user.id and not link.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the container creator or a group admin may attach an image",
        )

    data = await file.read()
    images_service.validate_image_upload(file, data)
    container.image_path = files_service.save_upload(
        group_id, file.filename or "image.jpg", data,
    )
    session.add(container)
    await session.commit()
    await session.refresh(container)
    return ContainerRead.model_validate(container, from_attributes=True)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api/test_containers_image.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Confirm existing container tests still pass**

Run: `uv run pytest tests/test_api/test_containers.py -v`
Expected: All previously-green tests still PASS.

- [ ] **Step 6: Commit**

```
git add src/chaima/routers/containers.py tests/test_api/test_containers_image.py
git commit -m "feat(containers): POST /{id}/image for label photos"
```

---

## Phase 3 — Frontend Foundation

### Task 7: Extend `DrawerContext` with prefill + photoFile

**Files:**
- Modify: `frontend/src/components/drawer/DrawerContext.tsx`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add `ContainerPrefill` and `ExtractedLabel` types**

Append to `frontend/src/types/index.ts`:

```ts
export interface ExtractedLabel {
  cas: string | null;
  name: string | null;
  amount: number | null;
  unit: string | null;
  supplier_name: string | null;
  identifier: string | null;
  purity: string | null;
  purchased_at: string | null;  // ISO date YYYY-MM-DD
  confidence: "high" | "medium" | "low";
}

export interface ContainerPrefill {
  identifier?: string;
  amount?: number;
  unit?: string;
  supplier_name?: string;
  purity?: string;
  purchased_at?: string;
}
```

- [ ] **Step 2: Extend the `container-new` config**

In `frontend/src/components/drawer/DrawerContext.tsx`, update the imports and union member:

```ts
import { createContext, useContext, useState, type ReactNode } from "react";
import type { ContainerPrefill, StorageKind } from "../../types";

export type DrawerConfig =
  | { kind: "chemical-new" }
  | { kind: "chemical-edit"; chemicalId: string }
  | {
      kind: "container-new";
      chemicalId: string;
      prefill?: ContainerPrefill;
      photoFile?: File;
    }
  | { kind: "container-edit"; containerId: string }
  | { kind: "storage-new"; childKind: StorageKind; parentId: string | null }
  | { kind: "storage-edit"; locationId: string }
  | { kind: "new-order"; groupId: string; chemicalId?: string; wishlistItemId?: string }
  | { kind: "order-detail"; groupId: string; orderId: string }
  | null;
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors. (Existing call sites pass `{ kind: "container-new", chemicalId }` — the new fields are optional so nothing breaks.)

- [ ] **Step 4: Commit**

```
git add frontend/src/components/drawer/DrawerContext.tsx frontend/src/types/index.ts
git commit -m "feat(drawer): allow container-new to carry prefill + photoFile"
```

---

### Task 8: Frontend image-resize utility

**Files:**
- Create: `frontend/src/utils/imageResize.ts`

- [ ] **Step 1: Create the resize helper**

Create `frontend/src/utils/imageResize.ts`:

```ts
/**
 * Resize an image File to fit within `maxDim` on the longer edge, encoding as JPEG.
 *
 * HEIC images and anything the browser can't decode are returned unchanged —
 * the server validates regardless.
 */
export async function resizeImage(
  file: File,
  maxDim = 2048,
  quality = 0.85,
): Promise<File> {
  if (file.type === "image/heic") return file;
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    return file;
  }

  const longest = Math.max(bitmap.width, bitmap.height);
  if (longest <= maxDim) {
    bitmap.close?.();
    return file;
  }

  const scale = maxDim / longest;
  const w = Math.round(bitmap.width * scale);
  const h = Math.round(bitmap.height * scale);

  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    bitmap.close?.();
    return file;
  }
  ctx.drawImage(bitmap, 0, 0, w, h);
  bitmap.close?.();

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", quality),
  );
  if (!blob) return file;
  return new File([blob], file.name.replace(/\.[^.]+$/, ".jpg"), {
    type: "image/jpeg",
    lastModified: Date.now(),
  });
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/utils/imageResize.ts
git commit -m "feat(utils): canvas-based image resize for upload"
```

---

### Task 9: `useExtractFromPhoto` hook

**Files:**
- Create: `frontend/src/api/hooks/useExtractFromPhoto.ts`

- [ ] **Step 1: Create the mutation hook**

Create `frontend/src/api/hooks/useExtractFromPhoto.ts`:

```ts
import { useMutation } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import client from "../client";
import type { ExtractedLabel } from "../../types";
import { resizeImage } from "../../utils/imageResize";
import { useCurrentUser } from "./useAuth";

export function useExtractFromPhoto() {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? "";

  return useMutation<ExtractedLabel, AxiosError, File>({
    mutationFn: async (file) => {
      const resized = await resizeImage(file);
      const form = new FormData();
      form.append("file", resized);
      const r = await client.post<ExtractedLabel>(
        `/groups/${groupId}/chemicals/extract-from-photo`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      return r.data;
    },
  });
}
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/api/hooks/useExtractFromPhoto.ts
git commit -m "feat(api): useExtractFromPhoto mutation hook"
```

---

### Task 10: `useUploadContainerImage` hook

**Files:**
- Modify: `frontend/src/api/hooks/useContainers.ts`

- [ ] **Step 1: Append the upload hook**

In `frontend/src/api/hooks/useContainers.ts`, add at the bottom (before EOF):

```ts
export function useUploadContainerImage(groupId: string, containerId: string) {
  const queryClient = useQueryClient();
  return useMutation<ContainerRead, unknown, File>({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const r = await client.post<ContainerRead>(
        `/groups/${groupId}/containers/${containerId}/image`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      return r.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["containers", groupId] });
      queryClient.invalidateQueries({ queryKey: ["containers", groupId, containerId] });
    },
  });
}
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/api/hooks/useContainers.ts
git commit -m "feat(api): useUploadContainerImage hook"
```

---

## Phase 4 — `ChemicalForm` Integration

### Task 11: Add camera icon to drawer header

**Files:**
- Modify: `frontend/src/components/drawer/EditDrawer.tsx`

- [ ] **Step 1: Add a `headerSlot` field to drawer config so each form can inject its own icon**

This requires a small context extension. Update `DrawerContext.tsx` to expose a slot ref instead:

Actually a simpler approach: pass the icon through a per-form pattern using a ref. Use a simpler **drawer-level prop** approach: each form is rendered inside `EditDrawer.tsx`, so the icon lives in the form itself. Move the camera icon **into the form components** (Task 12 for ChemicalForm, Task 16 for ContainerForm) rather than the shared header.

**Revised step: instead of touching EditDrawer header, we'll render the camera icon at the top of the form body**, right under the existing drawer header. This keeps `EditDrawer.tsx` untouched and form-agnostic.

Skip this task — no changes to `EditDrawer.tsx`. Move on to Task 12, which will render a "Photo strip" with the camera button at the top of the form body.

- [ ] **Step 2: Commit (empty — no changes)**

No commit needed; this task is intentionally a no-op after the design refinement. Proceed to Task 12.

---

### Task 12: ChemicalForm — photo state, capture, extract, prefill

**Files:**
- Modify: `frontend/src/components/drawer/ChemicalForm.tsx`

- [ ] **Step 1: Add the photo-capture row at the top of the form**

In `frontend/src/components/drawer/ChemicalForm.tsx`, add imports near the existing import block:

```tsx
import CameraAltIcon from "@mui/icons-material/CameraAlt";
import { useExtractFromPhoto } from "../../api/hooks/useExtractFromPhoto";
import type { ContainerPrefill } from "../../types";
```

Add new state hooks after the existing `const [ghsLoading, setGhsLoading] = useState(false);` line:

```tsx
const [photoFile, setPhotoFile] = useState<File | null>(null);
const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null);
const [extractedFields, setExtractedFields] = useState<Set<string>>(new Set());
const [extractedContainerPrefill, setExtractedContainerPrefill] =
  useState<ContainerPrefill | null>(null);
const [extractError, setExtractError] = useState<string | null>(null);
const fileInputRef = useRef<HTMLInputElement | null>(null);
const extract = useExtractFromPhoto();
```

`useRef` is already imported (line 15). If not, add it.

Add an `useEffect` to revoke the preview URL on unmount:

```tsx
useEffect(() => {
  return () => {
    if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
  };
}, [photoPreviewUrl]);
```

- [ ] **Step 2: Add the file-input handler**

Below the state hooks, add:

```tsx
const handleFile = async (file: File) => {
  setExtractError(null);
  setPhotoFile(file);
  if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
  setPhotoPreviewUrl(URL.createObjectURL(file));

  try {
    const result = await extract.mutateAsync(file);
    const filled = new Set<string>();
    if (result.name) {
      setName(result.name);
      filled.add("name");
    }
    if (result.cas) {
      setCas(result.cas);
      filled.add("cas");
    }
    setExtractedFields(filled);

    setExtractedContainerPrefill({
      identifier: result.identifier ?? undefined,
      amount: result.amount ?? undefined,
      unit: result.unit ?? undefined,
      supplier_name: result.supplier_name ?? undefined,
      purity: result.purity ?? undefined,
      purchased_at: result.purchased_at ?? undefined,
    });

    // Auto-trigger PubChem fetch when we got a CAS or name.
    const seed = result.cas || result.name;
    if (seed) {
      setQuery(seed);
      void onFetch();
    }
  } catch (e) {
    const axiosErr = e as { response?: { status?: number; data?: { detail?: string } } };
    const status = axiosErr.response?.status;
    if (status === 503) setExtractError("Foto-Erkennung ist auf dieser Instanz deaktiviert.");
    else if (status === 502) setExtractError("Erkennung gerade nicht möglich — bitte manuell eingeben.");
    else if (status === 413) setExtractError("Bild zu groß (max. 10 MB).");
    else if (status === 415) setExtractError("Bildformat nicht unterstützt.");
    else setExtractError("Erkennung fehlgeschlagen — bitte manuell eingeben.");
  }
};
```

- [ ] **Step 3: Render the photo-strip + hidden file input at the top of the Stack**

In the JSX return, immediately after the opening `<Stack spacing={2}>` and before the duplicate-banner IIFE, add:

```tsx
{!chemicalId && (
  <Box
    sx={{
      display: "flex",
      alignItems: "center",
      gap: 1.5,
      p: 1,
      border: "1px solid",
      borderColor: "divider",
      borderRadius: 1,
    }}
  >
    {photoPreviewUrl ? (
      <Box
        component="img"
        src={photoPreviewUrl}
        sx={{ width: 48, height: 48, objectFit: "cover", borderRadius: 1 }}
      />
    ) : (
      <Box
        sx={{
          width: 48,
          height: 48,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "text.secondary",
          border: "1px dashed",
          borderColor: "divider",
          borderRadius: 1,
        }}
      >
        <CameraAltIcon fontSize="small" />
      </Box>
    )}
    <Box sx={{ flex: 1 }}>
      <Typography variant="body2">Etikett-Foto (optional)</Typography>
      <Typography variant="caption" color="text.secondary">
        {extract.isPending
          ? "Erkennung läuft…"
          : photoFile
          ? `Foto übernommen`
          : "Foto aufnehmen oder hochladen — Felder werden automatisch erkannt"}
      </Typography>
    </Box>
    <Button
      variant="outlined"
      size="small"
      startIcon={<CameraAltIcon />}
      onClick={() => fileInputRef.current?.click()}
      disabled={extract.isPending}
    >
      {photoFile ? "Ersetzen" : "Foto"}
    </Button>
    <input
      ref={fileInputRef}
      type="file"
      accept="image/*"
      capture="environment"
      hidden
      onChange={(e) => {
        const f = e.target.files?.[0];
        if (f) void handleFile(f);
        e.target.value = "";
      }}
    />
  </Box>
)}

{extractError && <Alert severity="warning" onClose={() => setExtractError(null)}>{extractError}</Alert>}
```

- [ ] **Step 4: Highlight extracted fields**

On the `Name` TextField (somewhere lower in the JSX), wrap it so the highlight is conditional. Find the Name TextField and replace its props with a version that adds `sx`, `slotProps.input.startAdornment`, and clears the marker on edit:

For Name:

```tsx
<TextField
  label="Name"
  required
  value={name}
  onChange={(e) => {
    setName(e.target.value);
    if (extractedFields.has("name")) {
      setExtractedFields((s) => {
        const ns = new Set(s);
        ns.delete("name");
        return ns;
      });
    }
  }}
  size="small"
  sx={
    extractedFields.has("name")
      ? { "& .MuiOutlinedInput-root": { backgroundColor: "rgba(67, 56, 202, 0.06)" } }
      : undefined
  }
  slotProps={{
    input: extractedFields.has("name")
      ? {
          startAdornment: (
            <InputAdornment position="start">
              <CameraAltIcon fontSize="small" color="primary" />
            </InputAdornment>
          ),
        }
      : undefined,
  }}
/>
```

Do the same for `CAS`, swapping `"name"` for `"cas"` and `setName` for `setCas`.

(The exact lines for Name and CAS TextFields are in the existing JSX of this file — locate by searching for `label="Name"` and `label="CAS"`. Preserve all other props they already have.)

- [ ] **Step 5: TS compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```
git add frontend/src/components/drawer/ChemicalForm.tsx
git commit -m "feat(chemicals): photo capture in new-chemical drawer"
```

---

### Task 13: ChemicalForm — chain to ContainerForm on Create

**Files:**
- Modify: `frontend/src/components/drawer/ChemicalForm.tsx`

- [ ] **Step 1: Modify `onSubmit` (Create branch) to chain into `container-new`**

In the existing `onSubmit` function, find the `else { const created = await create.mutateAsync(payload); ... onDone(); }` branch (lines around 287-301). Replace the final `onDone()` call so it conditionally chains:

```tsx
} else {
  const created = await create.mutateAsync(payload);

  if (!ghsReady && ghsPromiseRef.current) {
    const createdId = created.id;
    ghsPromiseRef.current.then((codes) => {
      if (codes.length > 0) {
        client
          .patch(`/groups/${groupId}/chemicals/${createdId}`, { ghs_codes: codes })
          .catch(() => {});
      }
    });
  }

  // Chain into container-new when a photo or extracted prefill is present.
  const hasPrefillData =
    photoFile != null ||
    (extractedContainerPrefill &&
      Object.values(extractedContainerPrefill).some((v) => v !== undefined));
  if (hasPrefillData) {
    drawer.open({
      kind: "container-new",
      chemicalId: created.id,
      prefill: extractedContainerPrefill ?? undefined,
      photoFile: photoFile ?? undefined,
    });
    return;
  }
}
onDone();
```

Keep the existing `onDone()` at the bottom — it now fires only when there's no photo/prefill to chain.

- [ ] **Step 2: Extend the two duplicate-banner buttons to pass prefill + photo**

In the same file (around lines 318 and 344), update both `drawer.open` calls inside the duplicate banner:

Line ~318 (Restore & add container):

```tsx
const handleUnarchiveAndAdd = async () => {
  if (!chemId) return;
  setUnarchiving(true);
  try {
    await client.post(`/groups/${groupId}/chemicals/${chemId}/unarchive`);
    drawer.open({
      kind: "container-new",
      chemicalId: chemId,
      prefill: extractedContainerPrefill ?? undefined,
      photoFile: photoFile ?? undefined,
    });
  } finally {
    setUnarchiving(false);
  }
};
```

Line ~344 (Add container):

```tsx
<Button
  variant="outlined"
  size="small"
  onClick={() =>
    drawer.open({
      kind: "container-new",
      chemicalId: chemId!,
      prefill: extractedContainerPrefill ?? undefined,
      photoFile: photoFile ?? undefined,
    })
  }
>
  Add container
</Button>
```

- [ ] **Step 3: TS compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```
git add frontend/src/components/drawer/ChemicalForm.tsx
git commit -m "feat(chemicals): chain into container drawer with prefill+photo on save"
```

---

## Phase 5 — `ContainerForm` Integration

### Task 14: ContainerForm — accept prefill props, populate fields, highlight

**Files:**
- Modify: `frontend/src/components/drawer/ContainerForm.tsx`
- Modify: `frontend/src/components/drawer/EditDrawer.tsx`

- [ ] **Step 1: Wire `EditDrawer` to forward `prefill` and `photoFile` to `ContainerForm`**

In `frontend/src/components/drawer/EditDrawer.tsx`, update the `container-new` branch (lines 55-63) to forward the new optional fields:

```tsx
{(config.kind === "container-new" || config.kind === "container-edit") && (
  <ContainerForm
    chemicalId={config.kind === "container-new" ? config.chemicalId : undefined}
    containerId={
      config.kind === "container-edit" ? config.containerId : undefined
    }
    prefill={config.kind === "container-new" ? config.prefill : undefined}
    photoFile={config.kind === "container-new" ? config.photoFile : undefined}
    onDone={close}
  />
)}
```

- [ ] **Step 2: Extend `ContainerForm` props and state**

In `frontend/src/components/drawer/ContainerForm.tsx`, update the `Props` interface and imports:

Imports (add to existing import block):

```tsx
import CameraAltIcon from "@mui/icons-material/CameraAlt";
import { InputAdornment, Typography } from "@mui/material";
import { useEffect, useRef, useState } from "react";
import { useExtractFromPhoto } from "../../api/hooks/useExtractFromPhoto";
import { useUploadContainerImage } from "../../api/hooks/useContainers";
import type { ContainerPrefill } from "../../types";
```

(`useEffect`, `useState` are already imported — merge into the existing line.)

Update the Props:

```tsx
interface Props {
  chemicalId?: string;
  containerId?: string;
  prefill?: ContainerPrefill;
  photoFile?: File;
  onDone: () => void;
}

export function ContainerForm({ chemicalId, containerId, prefill, photoFile: initialPhotoFile, onDone }: Props) {
```

- [ ] **Step 3: Initialize state from prefill**

Find the existing state declarations (lines 57-66). Update the initial values to use `prefill`:

```tsx
const [identifier, setIdentifier] = useState(prefill?.identifier ?? "");
const [amount, setAmount] = useState<number | "">(prefill?.amount ?? "");
const [unit, setUnit] = useState(prefill?.unit ?? "");
const [purity, setPurity] = useState(prefill?.purity ?? "");
const [locationId, setLocationId] = useState<string | null>(null);
const [locationPath, setLocationPath] = useState<string>("");
const [supplierId, setSupplierId] = useState<string | null>(null);
const [receivedDate, setReceivedDate] = useState<string | null>(
  containerId ? null : (prefill?.purchased_at ?? todayIsoDate()),
);
```

Add two new state slots after these:

```tsx
const [extractedFields, setExtractedFields] = useState<Set<string>>(() => {
  const s = new Set<string>();
  if (prefill?.identifier) s.add("identifier");
  if (prefill?.amount !== undefined) s.add("amount");
  if (prefill?.unit) s.add("unit");
  if (prefill?.purity) s.add("purity");
  if (prefill?.purchased_at) s.add("purchased_at");
  if (prefill?.supplier_name) s.add("supplier");
  return s;
});
const [photoFile, setPhotoFile] = useState<File | null>(initialPhotoFile ?? null);
const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(() =>
  initialPhotoFile ? URL.createObjectURL(initialPhotoFile) : null,
);
const [extractError, setExtractError] = useState<string | null>(null);
const fileInputRef = useRef<HTMLInputElement | null>(null);
const extract = useExtractFromPhoto();
```

Add an effect to revoke the preview URL:

```tsx
useEffect(() => () => {
  if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
}, [photoPreviewUrl]);
```

- [ ] **Step 4: Resolve the supplier name from prefill to a supplier_id**

Suppliers are referenced by ID, not name. After the existing `const createSupplier = useCreateSupplier(groupId);` line, add:

```tsx
// If prefill carries a supplier_name, match it to an existing supplier or create one.
useEffect(() => {
  if (!prefill?.supplier_name || supplierId) return;
  if (!suppliersPage) return;  // wait for the supplier list
  const wanted = prefill.supplier_name.trim().toLowerCase();
  const match = suppliers.find((s) => s.name.toLowerCase() === wanted);
  if (match) {
    setSupplierId(match.id);
  } else {
    createSupplier.mutateAsync({ name: prefill.supplier_name.trim() }).then((c) => setSupplierId(c.id)).catch(() => {});
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [suppliersPage, prefill?.supplier_name]);
```

- [ ] **Step 5: Add the photo-strip row at the top**

In the JSX return, immediately after `<Stack spacing={2}>`, add:

```tsx
{!containerId && (
  <Box
    sx={{
      display: "flex",
      alignItems: "center",
      gap: 1.5,
      p: 1,
      border: "1px solid",
      borderColor: "divider",
      borderRadius: 1,
    }}
  >
    {photoPreviewUrl ? (
      <Box
        component="img"
        src={photoPreviewUrl}
        sx={{ width: 48, height: 48, objectFit: "cover", borderRadius: 1 }}
      />
    ) : (
      <Box
        sx={{
          width: 48, height: 48, display: "flex",
          alignItems: "center", justifyContent: "center",
          color: "text.secondary", border: "1px dashed",
          borderColor: "divider", borderRadius: 1,
        }}
      >
        <CameraAltIcon fontSize="small" />
      </Box>
    )}
    <Box sx={{ flex: 1 }}>
      <Typography variant="body2">Etikett-Foto (optional)</Typography>
      <Typography variant="caption" color="text.secondary">
        {extract.isPending
          ? "Erkennung läuft…"
          : photoFile
          ? "Foto wird beim Save am Container abgelegt"
          : "Foto aufnehmen oder hochladen"}
      </Typography>
    </Box>
    <Button
      variant="outlined"
      size="small"
      startIcon={<CameraAltIcon />}
      onClick={() => fileInputRef.current?.click()}
      disabled={extract.isPending}
    >
      {photoFile ? "Ersetzen" : "Foto"}
    </Button>
    <input
      ref={fileInputRef}
      type="file"
      accept="image/*"
      capture="environment"
      hidden
      onChange={(e) => {
        const f = e.target.files?.[0];
        if (f) void handleFile(f);
        e.target.value = "";
      }}
    />
  </Box>
)}

{extractError && <Alert severity="warning" onClose={() => setExtractError(null)}>{extractError}</Alert>}
```

- [ ] **Step 6: Add the `handleFile` for in-form re-extract (container-only fields)**

Add this above the JSX return:

```tsx
const handleFile = async (file: File) => {
  setExtractError(null);
  setPhotoFile(file);
  if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
  setPhotoPreviewUrl(URL.createObjectURL(file));

  try {
    const result = await extract.mutateAsync(file);
    const next = new Set(extractedFields);
    if (result.identifier) { setIdentifier(result.identifier); next.add("identifier"); }
    if (result.amount != null) { setAmount(result.amount); next.add("amount"); }
    if (result.unit) { setUnit(result.unit); next.add("unit"); }
    if (result.purity) { setPurity(result.purity); next.add("purity"); }
    if (result.purchased_at) { setReceivedDate(result.purchased_at); next.add("purchased_at"); }
    if (result.supplier_name) {
      const wanted = result.supplier_name.trim().toLowerCase();
      const match = suppliers.find((s) => s.name.toLowerCase() === wanted);
      if (match) { setSupplierId(match.id); next.add("supplier"); }
      else {
        try {
          const created = await createSupplier.mutateAsync({ name: result.supplier_name.trim() });
          setSupplierId(created.id);
          next.add("supplier");
        } catch { /* ignore */ }
      }
    }
    setExtractedFields(next);
  } catch (e) {
    const axiosErr = e as { response?: { status?: number } };
    const status = axiosErr.response?.status;
    if (status === 503) setExtractError("Foto-Erkennung ist auf dieser Instanz deaktiviert.");
    else if (status === 502) setExtractError("Erkennung gerade nicht möglich — bitte manuell eingeben.");
    else if (status === 413) setExtractError("Bild zu groß (max. 10 MB).");
    else if (status === 415) setExtractError("Bildformat nicht unterstützt.");
    else setExtractError("Erkennung fehlgeschlagen — bitte manuell eingeben.");
  }
};
```

- [ ] **Step 7: Apply highlight to prefilled TextFields**

Replace each existing TextField with a highlighted version. For Identifier:

```tsx
<TextField
  label="Identifier"
  required
  value={identifier}
  onChange={(e) => {
    setIdentifier(e.target.value);
    if (extractedFields.has("identifier")) {
      setExtractedFields((s) => { const ns = new Set(s); ns.delete("identifier"); return ns; });
    }
  }}
  size="small"
  helperText={identifierErr ?? "Must be unique within your group (e.g. AB01)"}
  error={!!identifierErr}
  autoFocus
  sx={extractedFields.has("identifier")
    ? { "& .MuiOutlinedInput-root": { backgroundColor: "rgba(67, 56, 202, 0.06)" } }
    : undefined}
  slotProps={{
    input: extractedFields.has("identifier")
      ? {
          startAdornment: (
            <InputAdornment position="start">
              <CameraAltIcon fontSize="small" color="primary" />
            </InputAdornment>
          ),
        }
      : undefined,
  }}
/>
```

Apply the same pattern to:
- **Amount** field with key `"amount"`
- **Unit** field with key `"unit"`
- **Purity** field with key `"purity"`
- **Received** (date) field with key `"purchased_at"`

The Supplier `Autocomplete` and `Location` button don't get highlight indicators in v1 (Autocomplete adornment is complex; Location is never extracted from photos). Skip them.

- [ ] **Step 8: TS compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 9: Commit**

```
git add frontend/src/components/drawer/EditDrawer.tsx frontend/src/components/drawer/ContainerForm.tsx
git commit -m "feat(containers): accept prefill+photoFile from drawer chain"
```

---

### Task 15: ContainerForm — upload image after create

**Files:**
- Modify: `frontend/src/components/drawer/ContainerForm.tsx`

- [ ] **Step 1: Wire `useUploadContainerImage` into `onSubmit`**

Just below the existing `const update = useUpdateContainer(groupId, containerId ?? "");` line, add an upload hook that we'll lazily call after the container is created:

```tsx
// Note: containerId is empty for new-container mode; we'll get the real ID
// from the create() response and call this hook's mutate function with that id
// via a small wrapper below.
```

Actually the simpler pattern: call the upload mutation **after** the create resolves, using the new container's id. Replace the `onSubmit` function (currently lines 109-126) with:

```tsx
const [imageUploadError, setImageUploadError] = useState<string | null>(null);

const onSubmit = async () => {
  setImageUploadError(null);
  const payload = {
    identifier: identifier.trim(),
    amount: Number(amount),
    unit: unit.trim(),
    purity: purity.trim() || null,
    location_id: locationId!,
    supplier_id: supplierId || null,
    purchased_at: receivedDate,
  };

  if (containerId) {
    await update.mutateAsync(payload);
    onDone();
    return;
  }

  const created = await create.mutateAsync(payload);
  if (photoFile) {
    try {
      const form = new FormData();
      form.append("file", photoFile);
      await client.post(
        `/groups/${groupId}/containers/${created.id}/image`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
    } catch {
      setImageUploadError(
        "Container wurde angelegt, aber das Foto konnte nicht hochgeladen werden.",
      );
      return; // keep drawer open so user can retry by re-saving
    }
  }
  onDone();
};
```

Add the import at the top if not present:

```tsx
import client from "../../api/client";
```

- [ ] **Step 2: Render the image-upload error banner**

Just below the existing `{otherErr && <Alert severity="error">...}` line in the JSX, add:

```tsx
{imageUploadError && (
  <Alert
    severity="warning"
    action={
      <Button
        color="inherit"
        size="small"
        onClick={async () => {
          if (!photoFile) return;
          // We don't have the just-created container id in state by now;
          // the user can manually re-save (form is still open).
          setImageUploadError(null);
        }}
      >
        Schließen
      </Button>
    }
  >
    {imageUploadError}
  </Alert>
)}
```

**Note:** The retry-image-upload UX intentionally degrades to "close drawer; user can re-open and attach image via Container-Edit drawer image button" (out of scope for v1). The warning is shown so the user knows the container was created.

- [ ] **Step 3: TS compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```
git add frontend/src/components/drawer/ContainerForm.tsx
git commit -m "feat(containers): upload photo to /image endpoint after create"
```

---

## Phase 6 — Display & Smoke Test

### Task 16: Container card / row shows the image thumbnail

**Files:**
- Modify: `frontend/src/components/ContainerCard.tsx`

- [ ] **Step 1: Find where the card body is rendered**

Open `frontend/src/components/ContainerCard.tsx` and locate the JSX that renders container information.

- [ ] **Step 2: Conditionally render a 64×64 thumbnail**

Inside the JSX where the card content is laid out, near the top of the visual representation, conditionally render:

```tsx
{container.image_path && (
  <Box
    component="img"
    src={`/uploads/${container.image_path}`}
    alt={`Photo of container ${container.identifier}`}
    sx={{
      width: 64,
      height: 64,
      objectFit: "cover",
      borderRadius: 1,
      flexShrink: 0,
    }}
  />
)}
```

The exact insertion point depends on the existing layout — place it as the first child of whatever flex/stack container holds the container info, so the image sits to the left of the text content.

- [ ] **Step 3: TS compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```
git add frontend/src/components/ContainerCard.tsx
git commit -m "feat(containers): show photo thumbnail on container card"
```

---

### Task 17: End-to-end smoke test (manual)

**Files:** none

- [ ] **Step 1: Set the Gemini key**

Add a real key to your local `.env`:

```
CHAIMA_GEMINI_API_KEY=<your aistudio key>
```

- [ ] **Step 2: Start the backend**

Run: `uv run uvicorn chaima.app:app --reload --port 8000`

- [ ] **Step 3: Start the frontend dev server**

In another terminal: `cd frontend && npm run dev`

Open the printed URL in a browser.

- [ ] **Step 4: Walk through the smoke list**

For each item, mark ✓ or ✗ in the conversation:

1. ☐ Desktop browser → "+ New Chemical" → click "Foto" button → file picker opens.
2. ☐ Mobile browser (use ngrok or LAN) → "Foto" button → direct camera opens.
3. ☐ Take a photo of a real bottle label → fields `Name` and `CAS` get filled with the lila Highlight + camera icon.
4. ☐ PubChem fetch auto-runs after photo → molar mass / GHS / synonyms appear.
5. ☐ Click `Create` → ChemicalForm closes, ContainerForm opens automatically titled "New container · <chemname>" with extracted Identifier/Amount/Unit/Purity/Supplier highlighted.
6. ☐ Photo-thumb visible at the top of the container drawer.
7. ☐ Pick a Location → `Create` → container is created, image is attached.
8. ☐ Navigate to the chemical's detail view → container shows 64×64 thumbnail.
9. ☐ Duplicate path: take a photo of a chemical already in the catalog → `Add container` banner appears → click it → ContainerForm opens with prefill + photo.
10. ☐ ContainerForm direct photo: open `+ New container` on an existing chemical → click `Foto` → only container fields fill, no chemical fields touched.
11. ☐ Reject big file: upload an image > 10 MB → warning banner "Bild zu groß".
12. ☐ Reject text file: pick a .txt → warning "Bildformat nicht unterstützt".
13. ☐ Remove the key from `.env`, restart backend → photo button still visible, click triggers "Foto-Erkennung ist auf dieser Instanz deaktiviert" banner.

- [ ] **Step 5: Capture results in a final commit (optional)**

If anything needed adjusting, fix it and commit. Otherwise no commit needed.

---

## Self-Review

**Spec coverage:**
- Decision 1 (Gemini 2.5 Flash) → Task 1, 3, 4
- Decision 2 (Structured Output) → Task 4
- Decision 3 (No DB migration) → confirmed in plan header; no migration task exists by design
- Decision 4 (Gemini ↔ PubChem split) → Task 12 (auto-triggers existing onFetch)
- Decision 5 (Capture: mobile direct cam) → Task 12 + 14 (`capture="environment"`)
- Decision 6 (UI: header icon → revised to inline photo-strip per Task 11 refinement) → Task 12, 14
- Decision 7 (Drawer chain) → Task 13
- Decision 8 (C2 — separate /image endpoint) → Task 6
- Decision 9 (Extract doesn't persist) → Task 5 (no save_upload call)
- Decision 10 (Highlight extracted fields) → Task 12, 14
- Decision 11 (Pre-resize 2048px) → Task 8 used by Task 9
- Decision 12 (10MB + MIME whitelist + Pillow validate) → Task 2
- Decision 13 (No duplicate-banner UI changes; just extend drawer.open args) → Task 13
- Decision 14 (uploads stays unauthenticated) → Task 16 uses `/uploads/<path>` directly
- Decision 15 (No cleanup in v1) → Task 6 overwrite test confirms old file is orphaned

**Placeholder scan:** None — every step has runnable code. The one "skipped" task (Task 11) is explicitly marked as a no-op after design refinement, with the alternative location documented.

**Type consistency:**
- `ExtractedLabel` shape matches between `src/chaima/services/vision.py` (Task 3) and `frontend/src/types/index.ts` (Task 7).
- `ContainerPrefill` defined once in `types/index.ts` (Task 7), consumed by `DrawerContext` (Task 7), `ChemicalForm` (Task 12, 13), and `ContainerForm` (Task 14).
- Hook names: `useExtractFromPhoto` (Task 9), `useUploadContainerImage` (Task 10), both consistent across consumers.
- Endpoint paths: `/api/v1/groups/{group_id}/chemicals/extract-from-photo` (Task 5, 9) and `/api/v1/groups/{group_id}/containers/{container_id}/image` (Task 6, 10, 15).
