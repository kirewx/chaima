"""API tests for the superuser-only admin analytics endpoints."""
import datetime as dt

import pytest

from chaima.models.analytics import Event, SlowRequest


def _utc(year, month, day, hour=12):
    return dt.datetime(year, month, day, hour, 0, 0, tzinfo=dt.timezone.utc)


@pytest.mark.asyncio
async def test_summary_requires_superuser(client):
    r = await client.get("/api/v1/admin/analytics/summary", params={"range": "7d"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_summary_returns_zeros_when_empty(superuser_client):
    r = await superuser_client.get(
        "/api/v1/admin/analytics/summary", params={"range": "7d"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["active_users"] == 0
    assert body["total_logins"] == 0
    assert body["total_searches"] == 0
    assert body["total_creates"] == 0
    assert body["total_photo_extracts"] == 0
    assert body["total_pubchem_fetches"] == 0


@pytest.mark.asyncio
async def test_summary_counts_seeded_events(superuser_client, session, superuser, group):
    now = dt.datetime.now(dt.timezone.utc)
    session.add_all([
        Event(user_id=superuser.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(hours=1)),
        Event(user_id=superuser.id, group_id=group.id, type="search_executed",
              payload={"query": "acetone", "result_count": 3},
              created_at=now - dt.timedelta(hours=2)),
        Event(user_id=superuser.id, group_id=group.id, type="chemical_created",
              payload={"chemical_id": "x"}, created_at=now - dt.timedelta(hours=3)),
    ])
    await session.flush()

    r = await superuser_client.get(
        "/api/v1/admin/analytics/summary", params={"range": "24h"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["active_users"] == 1
    assert body["total_logins"] == 1
    assert body["total_searches"] == 1
    assert body["total_creates"] == 1


@pytest.mark.asyncio
async def test_users_endpoint_includes_all_users(superuser_client, session, superuser, group):
    from chaima.models.user import User
    bob = User(
        email="bob@example.com", hashed_password="x",
        is_active=True, is_superuser=False, is_verified=True,
        main_group_id=group.id,
    )
    session.add(bob)
    await session.flush()

    r = await superuser_client.get(
        "/api/v1/admin/analytics/users", params={"range": "7d"},
    )
    assert r.status_code == 200
    rows = r.json()
    emails = {row["email"] for row in rows}
    assert "admin@example.com" in emails
    assert "bob@example.com" in emails


@pytest.mark.asyncio
async def test_top_searches_orders_by_count(superuser_client, session, superuser, group):
    now = dt.datetime.now(dt.timezone.utc)
    for q in ["acetone", "acetone", "acetone", "ethanol"]:
        session.add(Event(
            user_id=superuser.id, group_id=group.id, type="search_executed",
            payload={"query": q, "result_count": 0 if q == "ethanol" else 5},
            created_at=now - dt.timedelta(minutes=10),
        ))
    await session.flush()

    r = await superuser_client.get(
        "/api/v1/admin/analytics/top-searches", params={"range": "24h", "limit": 5},
    )
    assert r.status_code == 200
    rows = r.json()
    assert rows[0]["query"] == "acetone"
    assert rows[0]["count"] == 3
    assert rows[1]["query"] == "ethanol"
    assert rows[1]["empty_count"] == 1


@pytest.mark.asyncio
async def test_slow_endpoints_returns_percentiles(superuser_client, session, superuser):
    now = dt.datetime.now(dt.timezone.utc)
    for ms in [510, 520, 530, 540, 550, 560, 570, 580, 590, 600, 5000]:
        session.add(SlowRequest(
            user_id=superuser.id, method="GET", path="/api/v1/groups/{group_id}/chemicals",
            status=200, duration_ms=ms, created_at=now - dt.timedelta(minutes=5),
        ))
    await session.flush()

    r = await superuser_client.get(
        "/api/v1/admin/analytics/slow-endpoints", params={"range": "24h", "limit": 10},
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["count"] == 11
    assert rows[0]["p50_ms"] <= rows[0]["p95_ms"] <= rows[0]["p99_ms"]


@pytest.mark.asyncio
async def test_users_endpoint_requires_superuser(client):
    r = await client.get("/api/v1/admin/analytics/users", params={"range": "7d"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_top_searches_requires_superuser(client):
    r = await client.get("/api/v1/admin/analytics/top-searches", params={"range": "7d"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_slow_endpoints_requires_superuser(client):
    r = await client.get("/api/v1/admin/analytics/slow-endpoints", params={"range": "7d"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_compact_endpoint_requires_superuser(client):
    r = await client.post("/api/v1/admin/analytics/_compact")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_compact_rolls_old_events_into_daily(superuser_client, session, superuser, group):
    """Events older than 30 days move from event → event_daily, then disappear."""
    from chaima.models.analytics import Event, EventDaily
    from sqlmodel import select
    now = dt.datetime.now(dt.timezone.utc)

    session.add_all([
        Event(user_id=superuser.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(days=40)),
        Event(user_id=superuser.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(days=40)),
        Event(user_id=superuser.id, group_id=group.id, type="search_executed",
              payload={"query": "x", "result_count": 1},
              created_at=now - dt.timedelta(days=45)),
        # Fresh — must NOT be compacted:
        Event(user_id=superuser.id, group_id=group.id, type="login_success",
              payload=None, created_at=now - dt.timedelta(hours=1)),
    ])
    await session.flush()

    r = await superuser_client.post("/api/v1/admin/analytics/_compact")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["events_aggregated"] == 3
    assert body["events_deleted"] == 3

    remaining = (await session.exec(select(Event))).all()
    assert len(remaining) == 1  # the fresh one

    daily = (await session.exec(select(EventDaily))).all()
    assert len(daily) == 2  # 2 distinct (day, type) combos
    total = sum(d.count for d in daily)
    assert total == 3


@pytest.mark.asyncio
async def test_compact_prunes_slow_requests_older_than_30d(
    superuser_client, session, superuser,
):
    from chaima.models.analytics import SlowRequest
    from sqlmodel import select
    now = dt.datetime.now(dt.timezone.utc)

    session.add_all([
        SlowRequest(user_id=superuser.id, method="GET", path="/x", status=200,
                    duration_ms=600, created_at=now - dt.timedelta(days=40)),
        SlowRequest(user_id=superuser.id, method="GET", path="/x", status=200,
                    duration_ms=600, created_at=now - dt.timedelta(hours=1)),
    ])
    await session.flush()

    r = await superuser_client.post("/api/v1/admin/analytics/_compact")
    assert r.status_code == 200
    body = r.json()
    assert body["slow_requests_deleted"] == 1

    remaining = (await session.exec(select(SlowRequest))).all()
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_compact_prunes_daily_older_than_365d(superuser_client, session, superuser):
    from chaima.models.analytics import EventDaily
    from sqlmodel import select
    today = dt.date.today()

    session.add_all([
        EventDaily(day=today - dt.timedelta(days=400), user_id=superuser.id,
                   type="login_success", count=5),
        EventDaily(day=today - dt.timedelta(days=10), user_id=superuser.id,
                   type="login_success", count=1),
    ])
    await session.flush()

    r = await superuser_client.post("/api/v1/admin/analytics/_compact")
    assert r.status_code == 200
    body = r.json()
    assert body["event_daily_deleted"] == 1

    remaining = (await session.exec(select(EventDaily))).all()
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_compact_is_idempotent(superuser_client):
    r1 = await superuser_client.post("/api/v1/admin/analytics/_compact")
    r2 = await superuser_client.post("/api/v1/admin/analytics/_compact")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Second call has nothing to do.
    assert r2.json()["events_aggregated"] == 0
    assert r2.json()["events_deleted"] == 0
    assert r2.json()["slow_requests_deleted"] == 0
