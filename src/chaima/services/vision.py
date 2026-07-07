from __future__ import annotations

import datetime
import json
import os
import re
from typing import Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

DEFAULT_MODEL = "gemini-2.5-flash"

# Model output is derived from photographed labels — i.e. attacker-controllable
# text. Bound it before it reaches chemical creation and exports.
_MAX_FIELD_LEN = 200
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_STRING_FIELDS = ("cas", "name", "unit", "supplier_name", "identifier", "purity")

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


def _clean_field(value: str | None) -> str | None:
    """Strip control characters, trim whitespace, cap length."""
    if value is None:
        return None
    cleaned = _CONTROL_CHARS_RE.sub("", value).strip()
    if not cleaned:
        return None
    return cleaned[:_MAX_FIELD_LEN]


def _sanitize_label(label: ExtractedLabel) -> ExtractedLabel:
    for field in _STRING_FIELDS:
        setattr(label, field, _clean_field(getattr(label, field)))
    return label


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
        return _sanitize_label(ExtractedLabel.model_validate(data))
    except (json.JSONDecodeError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="vision_service_unavailable",
        ) from None
