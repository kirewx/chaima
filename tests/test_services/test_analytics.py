"""Tests for analytics aggregation queries."""
import datetime as dt

import pytest

from chaima.models.analytics import Event, EventDaily, SlowRequest
from chaima.services import analytics as analytics_service


def _utc(year, month, day, hour=12):
    return dt.datetime(year, month, day, hour, 0, 0, tzinfo=dt.timezone.utc)


@pytest.mark.asyncio
async def test_range_to_window_24h_returns_last_day():
    end = _utc(2026, 5, 27)
    start, _ = analytics_service.range_to_window("24h", now=end)
    assert (end - start) == dt.timedelta(hours=24)


@pytest.mark.asyncio
async def test_range_to_window_unknown_falls_back_to_7d():
    end = _utc(2026, 5, 27)
    start, _ = analytics_service.range_to_window("nope", now=end)
    assert (end - start) == dt.timedelta(days=7)


@pytest.mark.asyncio
async def test_summary_counts_only_within_range(session, user, group):
    now = _utc(2026, 5, 27)
    session.add_all([
        Event(user_id=user.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(hours=1)),
        Event(user_id=user.id, group_id=group.id, type="search_executed",
              payload={"query": "x", "result_count": 1},
              created_at=now - dt.timedelta(hours=2)),
        Event(user_id=user.id, group_id=group.id, type="chemical_created",
              payload={"chemical_id": "x"},
              created_at=now - dt.timedelta(hours=3)),
        # Outside the 24h window — must not be counted:
        Event(user_id=user.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(days=8)),
    ])
    await session.flush()

    summary = await analytics_service.summary(session, range_="24h", now=now)
    assert summary["active_users"] == 1
    assert summary["total_logins"] == 1
    assert summary["total_searches"] == 1
    assert summary["total_creates"] == 1
    assert summary["total_photo_extracts"] == 0
    assert summary["total_pubchem_fetches"] == 0


@pytest.mark.asyncio
async def test_user_stats_includes_last_login_and_counts(session, user, group):
    now = _utc(2026, 5, 27)
    user.last_login_at = now - dt.timedelta(minutes=5)
    user.login_count = 14
    session.add(user)
    session.add_all([
        Event(user_id=user.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(hours=1)),
        Event(user_id=user.id, group_id=group.id, type="search_executed",
              payload={"query": "x", "result_count": 1},
              created_at=now - dt.timedelta(hours=2)),
        Event(user_id=user.id, group_id=group.id, type="chemical_created",
              payload={"chemical_id": "x"},
              created_at=now - dt.timedelta(hours=3)),
    ])
    await session.flush()

    rows = await analytics_service.user_stats(session, range_="24h", now=now)
    assert len(rows) >= 1
    me = next(r for r in rows if r["user_id"] == user.id)
    assert me["email"] == user.email
    assert me["last_login_at"] is not None
    assert me["logins_in_range"] == 1
    assert me["searches"] == 1
    assert me["chemicals_created"] == 1


@pytest.mark.asyncio
async def test_top_searches_aggregates_and_sorts(session, user, group):
    now = _utc(2026, 5, 27)
    session.add_all([
        Event(user_id=user.id, group_id=group.id, type="search_executed",
              payload={"query": "acetone", "result_count": 3}, created_at=now - dt.timedelta(hours=1)),
        Event(user_id=user.id, group_id=group.id, type="search_executed",
              payload={"query": "acetone", "result_count": 3}, created_at=now - dt.timedelta(hours=2)),
        Event(user_id=user.id, group_id=group.id, type="search_executed",
              payload={"query": "ethanol", "result_count": 0}, created_at=now - dt.timedelta(hours=3)),
    ])
    await session.flush()

    rows = await analytics_service.top_searches(session, range_="24h", limit=10, now=now)
    assert rows[0]["query"] == "acetone"
    assert rows[0]["count"] == 2
    assert rows[1]["query"] == "ethanol"
    assert rows[1]["empty_count"] == 1


@pytest.mark.asyncio
async def test_slow_endpoints_aggregates_with_percentiles(session, user):
    now = _utc(2026, 5, 27)
    # 10 fast, 1 very slow → p95 ~ p99 ~ slow value
    for ms in [510, 520, 530, 540, 550, 560, 570, 580, 590, 600, 5000]:
        session.add(SlowRequest(
            user_id=user.id, method="POST", path="/api/v1/groups/{group_id}/chemicals/extract-from-photo",
            status=200, duration_ms=ms, created_at=now - dt.timedelta(seconds=ms),
        ))
    await session.flush()

    rows = await analytics_service.slow_endpoints(session, range_="24h", limit=10, now=now)
    assert len(rows) == 1
    row = rows[0]
    assert row["path"] == "/api/v1/groups/{group_id}/chemicals/extract-from-photo"
    assert row["count"] == 11
    assert row["p50_ms"] <= row["p95_ms"] <= row["p99_ms"]
    assert row["p99_ms"] >= 600
