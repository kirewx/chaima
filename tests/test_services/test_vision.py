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
