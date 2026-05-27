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
