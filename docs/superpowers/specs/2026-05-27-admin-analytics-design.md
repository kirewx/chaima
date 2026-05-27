# Admin Analytics — Design Spec

**Date:** 2026-05-27
**Status:** Approved (brainstorming)
**Scope:** Single Settings section under `SUPERUSER` showing per-user activity, top searches, and slow endpoints. Backed by a new event log, login counters on `user`, and a slow-request log.

---

## Goals

- Superuser sees who is using the app, how often, and for what.
- Superuser can spot performance hotspots (slow endpoints, error spikes).
- Telemetry collection must never measurably slow down user-facing requests.
- Storage must stay bounded over months/years without manual intervention.

## Non-Goals (v1)

- No per-group-admin scope. Only superusers see analytics.
- No charts/visualizations beyond KPI counters + sortable tables + ordered lists.
- No real-time push — page is reload-driven.
- No CSV/PDF export of analytics data.
- No request-body inspection or any PII logging beyond what is already in payloads (e.g., search query strings).
- No multi-tenancy / per-instance segmentation.

---

## Architecture Overview

Three storage surfaces serve distinct read patterns:

1. **`event` (raw, hot)** — append-only log of semantic events. Holds last 30 days; older rows are aggregated nightly into `event_daily` and deleted.
2. **`event_daily` (aggregated, cold)** — one row per `(day, user_id, type)` with `count`. Holds last 365 days; older rows deleted nightly.
3. **`slow_request` (raw, hot)** — append-only log of requests above a latency or error threshold. Holds last 30 days; older rows deleted nightly. **Not aggregated** — only the last 30 days are interesting for tuning.

Two additional fields on the existing `user` table provide a fast "active users" answer without scanning `event`:

- `last_login_at: datetime | None`
- `login_count: int default 0`

All event and slow-request writes are deferred via `fastapi.BackgroundTasks` so the user-facing response returns before the telemetry write executes. Writes are wrapped in `try/except` — a telemetry failure must never propagate to the request.

---

## Data Model

### Add to `models/user.py`

```python
last_login_at: Mapped[datetime.datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True, default=None
)
login_count: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
```

### New: `models/analytics.py`

```python
class Event(SQLModel, table=True):
    __tablename__ = "event"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID | None = Field(default=None, foreign_key="user.id", index=True)
    group_id: UUID | None = Field(default=None, foreign_key="group.id", index=True)
    type: str = Field(index=True)        # see EventType below
    payload: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(),
                         nullable=False, index=True)
    )

    __table_args__ = (
        Index("ix_event_user_created", "user_id", "created_at"),
        Index("ix_event_type_created", "type", "created_at"),
    )


class EventDaily(SQLModel, table=True):
    __tablename__ = "event_daily"

    day: date = Field(primary_key=True)
    user_id: UUID = Field(primary_key=True, foreign_key="user.id")
    type: str = Field(primary_key=True)
    group_id: UUID | None = Field(default=None, foreign_key="group.id")
    count: int


class SlowRequest(SQLModel, table=True):
    __tablename__ = "slow_request"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID | None = Field(default=None, foreign_key="user.id")
    method: str
    path: str = Field(index=True)        # normalized: /chemicals/{chemical_id}/containers
    status: int
    duration_ms: int
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(),
                         nullable=False, index=True)
    )

    __table_args__ = (
        Index("ix_slow_path_created", "path", "created_at"),
    )
```

### EventType enum (string constants)

```
login_success     payload: {}
login_failure     payload: {email_attempted: str}     user_id = NULL
search_executed   payload: {query: str, result_count: int}
chemical_created  payload: {chemical_id: str}
container_created payload: {container_id: str}
order_created     payload: {order_id: str}
wishlist_added    payload: {wishlist_item_id: str}
photo_extract     payload: {success: bool, confidence: "high"|"medium"|"low"|null}
pubchem_fetch     payload: {success: bool, cas_resolved: bool}
```

### Migration

Single Alembic migration creates the three tables, adds the two `user` columns, and creates all indices in one revision.

---

## Performance Guarantees

These are commitments, not suggestions. Each is reflected in the implementation plan.

1. **Deferred writes.** `log_event(...)` is called via `BackgroundTasks.add_task(...)`. The user-facing endpoint awaits its own DB commit, returns the response, then FastAPI runs the telemetry write. A write failure is caught and silently dropped; the request has already succeeded.

2. **Cheap middleware.** The slow-request middleware adds only two `time.monotonic()` calls per request (~µs). It dispatches the response, computes `duration_ms`, and only when `duration_ms > 500` OR `status >= 500` schedules a `SlowRequest` insert via `BackgroundTasks`. No JSON body parsing, no path-parameter walking — uses `request.scope["route"].path` for the normalized path or falls back to `request.url.path` if no matched route.

3. **WAL mode.** `db.py` sets `PRAGMA journal_mode=WAL` on connect. SQLite serializes writes but allows concurrent reads; without WAL, an analytics read could block a user write briefly.

4. **Indices in v1.** All three indices on `event` and the `path` index on `slow_request` are created in the initial migration. No "add later" — adding indices to a large table is itself a write storm.

5. **Read isolation.** Analytics endpoints run only under `/api/v1/admin/analytics/*`, guarded by `is_superuser`. They never run on a user-facing path.

6. **Failure tolerance.** `services/events.py::log_event` is `try/except Exception` around the entire body. The same applies to the slow-request middleware insert. The principle is: telemetry is best-effort, user actions are not.

---

## Write Paths

| Event              | Where                                                                          | Notes                                                                                       |
| ------------------ | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| `login_success`    | fastapi-users `on_after_login` hook                                            | Also bumps `user.last_login_at = now()` and `user.login_count += 1`                         |
| `login_failure`    | Custom authentication-backend wrapper around fastapi-users                     | `user_id` is NULL; payload carries the attempted email                                      |
| `search_executed`  | `routers/chemicals.py::list_chemicals` — when `len(search.strip()) >= 3`        | Payload: `{query, result_count}`. Minimum-length rule avoids spamming the log with one-keystroke incremental searches. |
| `chemical_created` | `routers/chemicals.py::create_chemical`                                        | Payload: `{chemical_id}`                                                                    |
| `container_created`| `routers/containers.py::create_container`                                      | Payload: `{container_id}`                                                                   |
| `order_created`    | `routers/orders.py` create handler                                             | Payload: `{order_id}`                                                                       |
| `wishlist_added`   | `routers/wishlist.py` create handler                                           | Payload: `{wishlist_item_id}`                                                               |
| `photo_extract`    | `routers/chemicals.py::extract_from_photo` (success branch + 502 catch)        | Payload: `{success, confidence}`. `confidence=null` on failure.                              |
| `pubchem_fetch`    | `services/enrich.py` or `services/pubchem.py` at the public entry point         | Payload: `{success, cas_resolved}`                                                          |
| `slow_request`     | ASGI middleware in `app.py`                                                    | Threshold `duration_ms > 500` OR `status >= 500`. Path normalized via matched-route pattern. |

All event writes go through one helper:

```python
# src/chaima/services/events.py
def log_event(
    background_tasks: BackgroundTasks,
    *,
    user_id: UUID | None,
    group_id: UUID | None,
    type: str,
    payload: dict | None = None,
) -> None:
    """Schedule an event write after the current response is sent."""
    background_tasks.add_task(_write_event, user_id, group_id, type, payload)


async def _write_event(user_id, group_id, type, payload):
    try:
        async with async_session_maker() as session:
            session.add(Event(user_id=user_id, group_id=group_id, type=type, payload=payload))
            await session.commit()
    except Exception:
        pass  # telemetry is best-effort
```

The helper uses its own session (not the request's session) because the request's session is closed by the time the background task runs.

---

## Read API

New router `routers/admin_analytics.py`. All endpoints require superuser, return `403` otherwise.

```
GET /api/v1/admin/analytics/summary?range=24h|7d|30d|90d
  → SummaryResponse {
      active_users: int,              # distinct user_ids with any event in range
      total_logins: int,
      total_searches: int,
      total_creates: int,             # sum across chemical/container/order/wishlist
      total_photo_extracts: int,
      total_pubchem_fetches: int,
      range_start: datetime,
      range_end: datetime,
    }

GET /api/v1/admin/analytics/users?range=...
  → list[UserStatsRow] {
      user_id, email, last_login_at,
      logins_in_range, searches, chemicals_created, containers_created,
      orders_created, wishlist_added, photo_extracts,
    }
  Sorted by `last_login_at DESC NULLS LAST` server-side; client may re-sort.

GET /api/v1/admin/analytics/top-searches?range=...&limit=20
  → list[SearchStatsRow] {
      query: str, count: int, avg_result_count: float, empty_count: int,
    }
  ORDER BY count DESC.

GET /api/v1/admin/analytics/slow-endpoints?range=...&limit=20
  → list[SlowEndpointRow] {
      method: str, path: str,
      p50_ms: int, p95_ms: int, p99_ms: int,
      count: int, error_count: int,
    }
  ORDER BY p95_ms DESC.

POST /api/v1/admin/analytics/_compact
  → { ok: true, events_aggregated: int, events_deleted: int,
      event_daily_deleted: int, slow_requests_deleted: int }
  Idempotent; safe to call repeatedly.
```

### Read query strategy

- For `range ≤ 30 days`: query `event` and `slow_request` directly.
- For `range = 90 days`: union `event` (last 30d) + `event_daily` (older). For counts, this is straightforward `SUM(...)`. The per-user table for 90d uses `event_daily` exclusively for the older portion (no per-event detail needed for a count).
- `top-searches` always queries `event` only (no aggregation in `event_daily` preserves query strings).
- `slow-endpoints` always queries `slow_request` only (capped at 30 days by retention).

Endpoints use single SQL statements with `GROUP BY` — no N+1.

---

## Frontend

### Wiring

In `frontend/src/pages/SettingsPage.tsx` add to `items` array:

```ts
{ key: "analytics", label: "Analytics", group: "SUPERUSER", visible: isSuperuser },
```

And render `<AnalyticsSection />` when `active === "analytics"`.

### New file: `frontend/src/components/settings/AnalyticsSection.tsx`

Layout matches the approved mockup:

```
[Zeitraum: 7d v]   [Reload]

+----------+----------+----------+----------+
| 5 aktive | 142 such | 38 cont. | 12 fotos |
| User/7d  | en       | erstellt | extract  |
+----------+----------+----------+----------+

Per User (sortable):
+----------+--------+-------+------+------+-----------+
| User     | Logins | Such. | Cont.| Foto | Last seen |
+----------+--------+-------+------+------+-----------+

Top Suchen           Slow Endpoints
 acetone   23x       POST /extract  1.8s p95
 CAS 67..  11x       GET  /chems    420ms p95
```

- **Range select** is a controlled MUI `Select` with options `24h | 7d | 30d | 90d`. Default: `7d`.
- **KPI cards** are 4 MUI `Card`s in a flex row; wrap on narrow viewports.
- **Per-user table** is plain MUI `<Table>` (no `@mui/x-data-grid`). Manual sort state for each column. Up to ~50 rows expected — no virtualization.
- **Top Searches / Slow Endpoints** are two MUI `<List>` components side-by-side on desktop, stacked on mobile.
- **States**: Skeleton rows while loading, `Alert severity="error"` on failure, "Keine Daten im Zeitraum" empty state.

### Data fetching

One `useQuery` per endpoint, all keyed on the current range:

```ts
useQuery({ queryKey: ["admin-analytics", "summary", range], queryFn: ... })
useQuery({ queryKey: ["admin-analytics", "users", range], queryFn: ... })
useQuery({ queryKey: ["admin-analytics", "top-searches", range], queryFn: ... })
useQuery({ queryKey: ["admin-analytics", "slow-endpoints", range], queryFn: ... })
```

All four queries fire in parallel on mount and on range change.

---

## Retention & Compaction

`POST /api/v1/admin/analytics/_compact` performs all retention work in one transaction-per-step:

1. For each `(day, user_id, type)` in `event` where `created_at < now() - 30d`, upsert a row into `event_daily(day, user_id, type, group_id, count)` with the count. Then `DELETE FROM event WHERE created_at < now() - 30d`.
2. `DELETE FROM event_daily WHERE day < today() - 365d`.
3. `DELETE FROM slow_request WHERE created_at < now() - 30d`.

**Trigger**: external cron (or Windows Task Scheduler on the dev box) calls the endpoint nightly. No APScheduler in-app — easier to reason about under multi-worker setups and matches existing ops pattern (`uvicorn --workers`).

The endpoint is superuser-only and idempotent. A simple shared-secret header is **not** added in v1 — the superuser auth gate is sufficient; if we later want cron to call it without a session, we'd add an API-key header.

---

## Testing

**Backend**

- `tests/test_services/test_events.py` — `log_event` schedules a write; `_write_event` survives a closed/broken session; multiple events serialize correctly.
- `tests/test_api/test_admin_analytics.py` — each of the 5 endpoints: 403 for non-superuser, correct counts for seeded data, correct range filtering, empty-range returns zeros/empty arrays.
- `tests/test_middleware/test_slow_request.py` — middleware adds row only when threshold breached; path is normalized; non-matched paths fall back to raw URL.
- `tests/test_api/test_compact.py` — events older than 30d move to daily; daily older than 365d disappear; slow_requests older than 30d disappear; second call is a no-op.

**Frontend**

- Manual smoke test (no E2E in v1):
  1. Login as superuser → Analytics section visible
  2. Login as regular user → Analytics section hidden
  3. With seeded events, all 4 widgets render expected numbers
  4. Range change re-fetches and updates counts
  5. Network error → error Alert visible

---

## Out of Scope / Future Enhancements

- **Sparkline per user row** (would require `@mui/x-charts` dep)
- **Per-group-admin scope** (currently superuser-only)
- **Real-time updates** via WebSocket / polling
- **Funnel analysis** (e.g., login → search → create conversion)
- **CSV export** of any analytics table
- **Cost tracking** (Gemini token spend, PubChem rate-limit usage)
- **Anomaly alerts** (e.g., 5xx spike notification)

---

## File Map

**Backend — create:**
- `src/chaima/models/analytics.py`
- `src/chaima/services/events.py`
- `src/chaima/middleware/slow_request.py`
- `src/chaima/routers/admin_analytics.py`
- `alembic/versions/<rev>_add_analytics_tables.py`
- `tests/test_services/test_events.py`
- `tests/test_api/test_admin_analytics.py`
- `tests/test_middleware/test_slow_request.py`
- `tests/test_api/test_compact.py`

**Backend — modify:**
- `src/chaima/models/user.py` — add `last_login_at`, `login_count`
- `src/chaima/db.py` — set `PRAGMA journal_mode=WAL` on connect
- `src/chaima/app.py` — mount slow-request middleware, include analytics router
- `src/chaima/auth/...` — wire `on_after_login` hook + login_failure capture
- `src/chaima/routers/chemicals.py` — emit `search_executed`, `chemical_created`, `photo_extract`
- `src/chaima/routers/containers.py` — emit `container_created`
- `src/chaima/routers/orders.py` — emit `order_created`
- `src/chaima/routers/wishlist.py` — emit `wishlist_added`
- `src/chaima/services/pubchem.py` (or `enrich.py`) — emit `pubchem_fetch`

**Frontend — create:**
- `frontend/src/components/settings/AnalyticsSection.tsx`
- `frontend/src/api/hooks/useAdminAnalytics.ts`

**Frontend — modify:**
- `frontend/src/pages/SettingsPage.tsx` — add Analytics nav item + render branch
- `frontend/src/types/index.ts` — add analytics response types
