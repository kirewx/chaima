"""Tests for the SPA catch-all and root-level static file serving."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from chaima.app import app

_STATIC_DIR = Path(__file__).resolve().parents[2] / "src" / "chaima" / "static"
_FRONTEND_BUILT = (_STATIC_DIR / "index.html").is_file()

pytestmark = pytest.mark.skipif(
    not _FRONTEND_BUILT,
    reason="Frontend must be built (src/chaima/static/index.html) for SPA tests.",
)


@pytest.mark.asyncio
async def test_favicon_svg_is_served_as_svg() -> None:
    """GET /favicon.svg returns the real SVG file, not the SPA index.html."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/favicon.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert len(resp.content) > 0
    assert not resp.content.lstrip().startswith(b"<!doctype html")


@pytest.mark.asyncio
async def test_icons_svg_is_served_as_svg() -> None:
    """GET /icons.svg returns the real SVG file, not the SPA index.html."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/icons.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert len(resp.content) > 0
    assert not resp.content.lstrip().startswith(b"<!doctype html")


@pytest.mark.asyncio
async def test_unknown_path_falls_back_to_spa_index() -> None:
    """Unknown non-file paths still return index.html so the SPA router works."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/some/spa/route/that/doesnt/exist")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
