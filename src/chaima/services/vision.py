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
