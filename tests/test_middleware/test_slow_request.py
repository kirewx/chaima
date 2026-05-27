"""Tests for the slow-request logging middleware."""
import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from chaima.middleware.slow_request import SlowRequestMiddleware
from chaima.models.analytics import SlowRequest


def _make_app(threshold_ms: int):
    app = FastAPI()
    app.add_middleware(SlowRequestMiddleware, threshold_ms=threshold_ms)

    @app.get("/fast")
    async def fast():
        return {"ok": True}

    @app.get("/slow")
    async def slow():
        await asyncio.sleep(0.15)
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="bang")

    @app.get("/items/{item_id}")
    async def get_item(item_id: str):
        await asyncio.sleep(0.15)
        return {"id": item_id}

    return app


@pytest.mark.asyncio
async def test_fast_request_is_not_logged(session, patch_events_session_maker):
    app = _make_app(threshold_ms=100)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/fast")
        assert r.status_code == 200
    rows = (await session.exec(select(SlowRequest))).all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_slow_request_is_logged(session, patch_events_session_maker):
    app = _make_app(threshold_ms=100)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/slow")
        assert r.status_code == 200
    rows = (await session.exec(select(SlowRequest))).all()
    assert len(rows) == 1
    assert rows[0].method == "GET"
    assert rows[0].path == "/slow"
    assert rows[0].status == 200
    assert rows[0].duration_ms >= 100


@pytest.mark.asyncio
async def test_5xx_is_logged_even_when_fast(session, patch_events_session_maker):
    app = _make_app(threshold_ms=100)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/boom")
        assert r.status_code == 500
    rows = (await session.exec(select(SlowRequest))).all()
    assert len(rows) == 1
    assert rows[0].status == 500
    assert rows[0].path == "/boom"


@pytest.mark.asyncio
async def test_path_is_normalized_to_matched_route(session, patch_events_session_maker):
    """Path params like /items/{item_id} should not blow up the path cardinality."""
    app = _make_app(threshold_ms=100)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/items/abc")
        assert r.status_code == 200
    rows = (await session.exec(select(SlowRequest))).all()
    assert len(rows) == 1
    assert rows[0].path == "/items/{item_id}"
