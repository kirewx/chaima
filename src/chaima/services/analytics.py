"""Read-side aggregations for the admin analytics dashboard.

All functions accept an explicit ``now`` for deterministic testing; in
production the routers pass ``datetime.now(timezone.utc)``.

Percentiles are computed in Python after fetching the matching rows —
SQLite has no ``percentile_cont``, and slow-request volumes are small
enough (capped at 30-day retention) that this stays cheap.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.analytics import Event, SlowRequest
from chaima.models.user import User

_RANGE_TO_DELTA = {
    "24h": dt.timedelta(hours=24),
    "7d": dt.timedelta(days=7),
    "30d": dt.timedelta(days=30),
    "90d": dt.timedelta(days=90),
}

_CREATE_TYPES = (
    "chemical_created", "container_created", "order_created", "wishlist_added",
)


def range_to_window(range_: str, *, now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    """Return (start, end) for a named range. Unknown ranges default to 7d."""
    delta = _RANGE_TO_DELTA.get(range_, _RANGE_TO_DELTA["7d"])
    return (now - delta, now)


async def summary(
    session: AsyncSession, *, range_: str, now: dt.datetime,
) -> dict[str, Any]:
    """Top-line KPI counters for the given range."""
    start, end = range_to_window(range_, now=now)

    distinct_users = await session.exec(
        select(func.count(func.distinct(Event.user_id))).where(
            Event.created_at >= start, Event.created_at <= end,
            Event.user_id.is_not(None),
        )
    )
    counts_by_type = await session.exec(
        select(Event.type, func.count(Event.id)).where(
            Event.created_at >= start, Event.created_at <= end,
        ).group_by(Event.type)
    )
    counts = dict(counts_by_type.all())

    return {
        "active_users": distinct_users.one() or 0,
        "total_logins": counts.get("login_success", 0),
        "total_searches": counts.get("search_executed", 0),
        "total_creates": sum(counts.get(t, 0) for t in _CREATE_TYPES),
        "total_photo_extracts": counts.get("photo_extract", 0),
        "total_pubchem_fetches": counts.get("pubchem_fetch", 0),
        "range_start": start,
        "range_end": end,
    }


async def user_stats(
    session: AsyncSession, *, range_: str, now: dt.datetime,
) -> list[dict[str, Any]]:
    """One row per user, with last_login_at and per-type counts in range."""
    start, end = range_to_window(range_, now=now)

    users = (await session.exec(select(User))).all()

    counts_rows = (await session.exec(
        select(Event.user_id, Event.type, func.count(Event.id)).where(
            Event.created_at >= start, Event.created_at <= end,
            Event.user_id.is_not(None),
        ).group_by(Event.user_id, Event.type)
    )).all()

    per_user: dict = defaultdict(lambda: defaultdict(int))
    for uid, type_, cnt in counts_rows:
        per_user[uid][type_] = cnt

    out: list[dict[str, Any]] = []
    for u in users:
        c = per_user.get(u.id, {})
        out.append({
            "user_id": u.id,
            "email": u.email,
            "last_login_at": u.last_login_at,
            "logins_in_range": c.get("login_success", 0),
            "searches": c.get("search_executed", 0),
            "chemicals_created": c.get("chemical_created", 0),
            "containers_created": c.get("container_created", 0),
            "orders_created": c.get("order_created", 0),
            "wishlist_added": c.get("wishlist_added", 0),
            "photo_extracts": c.get("photo_extract", 0),
        })
    # Sort: last_login DESC NULLS LAST.
    out.sort(key=lambda r: (r["last_login_at"] is None, -(r["last_login_at"].timestamp() if r["last_login_at"] else 0)))
    return out


async def top_searches(
    session: AsyncSession, *, range_: str, limit: int, now: dt.datetime,
) -> list[dict[str, Any]]:
    """Top search queries by count, with avg result count and empty-result count."""
    start, end = range_to_window(range_, now=now)
    rows = (await session.exec(
        select(Event.payload).where(
            Event.type == "search_executed",
            Event.created_at >= start, Event.created_at <= end,
        )
    )).all()

    counts: dict[str, dict[str, Any]] = {}
    for payload in rows:
        if not payload:
            continue
        q = payload.get("query")
        rc = payload.get("result_count", 0)
        if q is None:
            continue
        entry = counts.setdefault(q, {"count": 0, "sum": 0, "empty": 0})
        entry["count"] += 1
        entry["sum"] += rc
        if rc == 0:
            entry["empty"] += 1

    items = [
        {
            "query": q, "count": e["count"],
            "avg_result_count": (e["sum"] / e["count"]) if e["count"] else 0.0,
            "empty_count": e["empty"],
        }
        for q, e in counts.items()
    ]
    items.sort(key=lambda r: r["count"], reverse=True)
    return items[:limit]


def _percentile(values: list[int], pct: float) -> int:
    """Linear-interpolation percentile. ``values`` must be non-empty."""
    if not values:
        return 0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return int(s[lo] + (s[hi] - s[lo]) * frac)


async def slow_endpoints(
    session: AsyncSession, *, range_: str, limit: int, now: dt.datetime,
) -> list[dict[str, Any]]:
    """Per-endpoint percentile latencies + counts within the range."""
    start, end = range_to_window(range_, now=now)
    rows = (await session.exec(
        select(SlowRequest.method, SlowRequest.path, SlowRequest.status, SlowRequest.duration_ms).where(
            SlowRequest.created_at >= start, SlowRequest.created_at <= end,
        )
    )).all()

    grouped: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for method, path, status, dur in rows:
        grouped[(method, path)].append((status, dur))

    out: list[dict[str, Any]] = []
    for (method, path), entries in grouped.items():
        durations = [d for _s, d in entries]
        errors = sum(1 for s, _d in entries if s >= 500)
        out.append({
            "method": method, "path": path,
            "p50_ms": _percentile(durations, 0.50),
            "p95_ms": _percentile(durations, 0.95),
            "p99_ms": _percentile(durations, 0.99),
            "count": len(entries),
            "error_count": errors,
        })
    out.sort(key=lambda r: r["p95_ms"], reverse=True)
    return out[:limit]


async def compact(
    session: AsyncSession, *, now: dt.datetime,
) -> dict[str, int]:
    """Roll events older than 30 days into ``event_daily`` and prune.

    Steps (each in its own commit):
    1. For each ``(day, user_id, type)`` in ``event`` with ``created_at < now - 30d``,
       upsert ``event_daily`` with count and group_id. Then DELETE those events.
    2. DELETE ``event_daily`` rows with ``day < (now - 365d).date()``.
    3. DELETE ``slow_request`` rows with ``created_at < now - 30d``.

    Returns counts for each step.
    """
    from sqlalchemy import delete
    from chaima.models.analytics import EventDaily

    cutoff_30d = now - dt.timedelta(days=30)
    cutoff_365d = (now - dt.timedelta(days=365)).date()

    # --- Step 1: aggregate then delete ---
    agg_rows = (await session.exec(
        select(
            func.date(Event.created_at).label("day"),
            Event.user_id, Event.type, Event.group_id,
            func.count(Event.id).label("count"),
        ).where(
            Event.created_at < cutoff_30d,
            Event.user_id.is_not(None),
        ).group_by(
            func.date(Event.created_at), Event.user_id, Event.type, Event.group_id,
        )
    )).all()

    events_aggregated = 0
    for day_s, user_id, type_, group_id, count in agg_rows:
        if isinstance(day_s, str):
            day_v = dt.date.fromisoformat(day_s)
        else:
            day_v = day_s
        existing = await session.get(EventDaily, (day_v, user_id, type_))
        if existing is None:
            session.add(EventDaily(
                day=day_v, user_id=user_id, type=type_,
                group_id=group_id, count=count,
            ))
        else:
            existing.count += count
            session.add(existing)
        events_aggregated += count

    events_deleted_result = await session.exec(
        delete(Event).where(Event.created_at < cutoff_30d)
    )
    events_deleted = events_deleted_result.rowcount or 0

    # --- Step 2: prune ancient daily rows ---
    daily_deleted_result = await session.exec(
        delete(EventDaily).where(EventDaily.day < cutoff_365d)
    )
    daily_deleted = daily_deleted_result.rowcount or 0

    # --- Step 3: prune old slow_requests ---
    slow_deleted_result = await session.exec(
        delete(SlowRequest).where(SlowRequest.created_at < cutoff_30d)
    )
    slow_deleted = slow_deleted_result.rowcount or 0

    await session.commit()

    return {
        "events_aggregated": events_aggregated,
        "events_deleted": events_deleted,
        "event_daily_deleted": daily_deleted,
        "slow_requests_deleted": slow_deleted,
    }
