# GESTIS Deeplinks — Design Spec

**Date:** 2026-07-16
**Status:** Draft — awaiting user review
**Prototype:** `notebooks/test_pubchem_gestis.ipynb` (verified against live APIs 2026-07-06, re-checked 2026-07-09)

## Goal

Give every chemical with a CAS number a direct link to its official GESTIS
substance datasheet (DGUV hazardous-substance database), shown in the
existing "Links" section of `ChemicalInfoBox` next to the PubChem link.
The link must keep working even when the GESTIS API is unreachable or the
server was just restarted.

The GESTIS link **complements** the manually uploaded SDS — it does not
replace it. `sds_path` (vendor/manufacturer safety data sheet, served via
the existing `/{chemical_id}/sds` endpoint) stays untouched; the Links
section simply gains a third independent row: PubChem (`cid`), GESTIS
(`zvg`), SDS (`sds_path`), each rendered only when its field is set.

## Approach (revised from the original brainstorming)

The original design was fully on-demand (no DB field). Revised decision
(user-confirmed 2026-07-16): **resolve the CAS → ZVG mapping once, persist
only the ZVG number on the chemical**, then build the deeplink client-side
from the stored value — zero API calls after first resolution.

Nothing from the GESTIS database itself is stored. The full substance list
(~8,740 entries) is held only transiently in server memory as the
resolution index.

### Why a ZVG number is needed

A GESTIS deeplink requires GESTIS's internal substance id (ZVG), not the
CAS. The GESTIS API has **no server-side CAS search** — its `search`
endpoint ignores the query and always returns the full pure-substance
list, which the official SPA filters locally. We do the same: download
once, index by `cas_nr` in memory, cache with a TTL.

Deeplink format (EN, linking explicitly permitted by GESTIS):

```
https://gestis-database.dguv.de/data?name={zvg}     # zvg zero-padded to 6
```

Verified: ethanol CAS `64-17-5` → ZVG `010420` →
`https://gestis-database.dguv.de/data?name=010420` (HTTP 200).

## Scope

**In scope for v1:**

- Nullable `zvg` column on `Chemical` (+ Alembic migration). Mirrors the
  existing PubChem `cid` enrichment field. Server-authoritative: not
  settable via `ChemicalCreate`/`ChemicalUpdate`.
- `services/gestis.py` — async index service (load, cache, lookup).
- A chemical-scoped resolve-and-store endpoint.
- Index pre-load in the app lifespan (background, non-blocking).
- Config: API base + key via `CHAIMA_`-prefixed settings.
- Frontend: GESTIS link row in `ChemicalInfoBox`, auto-resolve on open
  when CAS is present but `zvg` is not.
- **Bulk backfill as admin action** in Settings → Chemicals, following the
  existing `enrich-pubchem` / `refetch-ghs` SSE pattern (superuser-only).
- **Auto-resolve on write paths:** chemical create/update with a CAS, and
  the PubChem enrich backfill when it resolves a CAS.

**Out of scope — parked:**

- DE-language deeplink variant, per-user language preference.
- Storing or displaying any GESTIS datasheet content (JSON article API).
- Persisting "not found" results (see Design decisions).

## User flow

```
[ Chemicals page ] → click a chemical → ChemicalInfoBox opens
      │
      ├─ chemical.zvg set        → "GESTIS 010420" link rendered
      │                             immediately (no network)
      │
      ├─ zvg null, cas set       → frontend fires resolve call once
      │     ├─ hit               → zvg persisted server-side,
      │     │                       link appears in place
      │     └─ miss / API down   → nothing rendered (no placeholder)
      │
      └─ no cas                  → nothing rendered
```

Clicking the link opens the GESTIS datasheet in a new tab
(`target="_blank" rel="noopener"`), exactly like the PubChem link.

## Design decisions

- **(a) Endpoint shape:**
  `POST /api/v1/groups/{group_id}/chemicals/{chemical_id}/gestis-resolve`.
  Chemical-scoped (not the earlier top-level `GET /gestis/link?cas=`)
  because the call now *mutates* the chemical row, so it must go through
  the existing group-membership authorization and fits the established
  action-endpoint pattern (`/{chemical_id}/archive` etc.). The frontend
  never writes `zvg` itself.
- **(b) EN deeplink only** (`gestis-database.dguv.de`).
- **(c) No hit → render nothing.** No "No GESTIS entry" placeholder row.
- **(d) API key from settings** (`CHAIMA_GESTIS_API_KEY`), with the
  public GESTIS web-client key as shipped default. That key is served in
  cleartext by GESTIS's own SPA (`env-config.js`) — public by design, not
  a secret — but stays overridable via env like every other setting.
- **(e) Index lifecycle:** background load at startup from the app
  lifespan (non-blocking — startup never waits on GESTIS), 24 h TTL,
  lazy re-fetch on first lookup after expiry. If the index is
  unavailable, resolution degrades gracefully to "no result".
- **(f) No "not found" persistence.** Once the index is warm, a repeat
  miss costs one dict lookup — not worth a `gestis_checked_at` column.
  Bonus: substances newly added to GESTIS are picked up automatically on
  the next info-box open.
- **(g) `zvg` is stored zero-padded to 6 chars** (`"010420"`), exactly as
  the deeplink needs it. Column name `zvg` for consistency with the
  terse existing `cid`.
- **(h) Resolve endpoint never 5xxs on GESTIS failure.** Upstream
  problems return `{zvg: null, url: null}`; only auth/ownership errors
  produce 4xx.
- **(i) Auto-resolve on write paths is warm-index only.** Creating or
  updating a chemical must never wait on a GESTIS list download (up to
  30 s) or fail because GESTIS is down. The service exposes a
  non-blocking variant (`get_zvg_if_warm`) that consults only an
  already-loaded index and never touches the network. Cold index →
  `zvg` stays null and the info-box on-demand resolve (or the admin
  backfill) catches up later. Since the index is pre-loaded at startup,
  the warm path is the overwhelmingly common case.
- **(j) CAS change invalidates `zvg`.** When an update changes the CAS,
  the stored `zvg` is cleared and re-resolved (warm-index attempt) so a
  stale deeplink can never point at the wrong substance.
- **(k) Backfill iterates without throttling.** Unlike the PubChem
  backfills (one upstream call per chemical, 0.25 s sleep), GESTIS
  resolution is a local dict lookup after a single list download — the
  loop needs no rate-limit delay.

## Backend

### New files

- `src/chaima/services/gestis.py` — index service.
- `src/chaima/schemas/gestis.py` — `GestisResolveResult`.
- `tests/services/test_gestis.py`, router tests (see Testing).
- Alembic migration: add nullable `zvg` column to `chemical`.

### Modified files

- `src/chaima/models/chemical.py` — `zvg: str | None = Field(default=None)`.
- `src/chaima/schemas/chemical.py` — add `zvg` to `ChemicalRead` /
  `ChemicalDetail` (read-only; **not** added to Create/Update).
- `src/chaima/routers/chemicals.py` — the resolve endpoint + the
  `backfill-gestis` bulk endpoint.
- `src/chaima/services/chemicals.py` — auto-resolve hook in
  create/update (decisions (i)/(j)).
- `src/chaima/services/enrich.py` — GESTIS attempt inside `enrich_one`
  after a CAS is resolved; new `backfill_group_gestis` generator.
- `src/chaima/config.py` — `gestis_api_base`, `gestis_api_key` settings.
- `src/chaima/app.py` — schedule background index pre-load in lifespan.

### Service (`services/gestis.py`)

```python
async def get_zvg(cas: str) -> str | None: ...        # loads index if needed
def get_zvg_if_warm(cas: str) -> str | None: ...      # never awaits network
def gestis_url(zvg: str) -> str: ...
async def preload_index() -> None: ...   # fired from lifespan, swallows errors
```

- **Index:** `GET {gestis_api_base}/search/x` with
  `Authorization: Bearer {gestis_api_key}`, 30 s timeout. Build
  `{cas_nr: zvg_nr.zfill(6)}` from entries that have a `cas_nr`.
  Module-level cache `(index, expiry)` with 24 h TTL, same pattern as
  `services/pubchem.py`. A single in-flight load guarded by an
  `asyncio.Lock` so concurrent first requests don't fetch twice.
- **Input validation:** normalize/strip the CAS; validate pattern
  `^\d{2,7}-\d{2}-\d$` **and** the CAS check digit (ported from the
  notebook's `cas_check_digit_ok`) before touching the index. Invalid
  CAS → `None` without any upstream call.
- **Failure semantics:** any upstream failure (non-2xx, timeout, network)
  logs a warning and yields `None` from `get_zvg`; a stale-but-present
  index keeps serving during a failed refresh (serve-stale-on-error).

### Endpoint

```python
@router.post("/{chemical_id}/gestis-resolve", response_model=GestisResolveResult)
async def resolve_gestis(group_id: UUID, chemical_id: UUID, ...):
```

Behavior:

1. Load chemical, enforce group membership (existing dependency chain) —
   404/403 identical to other chemical endpoints.
2. Already has `zvg` → return it immediately, **no upstream call**
   (idempotent).
3. No CAS on the chemical → `{zvg: null, url: null}`.
4. `get_zvg(cas)` hit → persist `zvg` on the chemical, return
   `{zvg, url}`.
5. Miss or GESTIS unavailable → `{zvg: null, url: null}` (nothing
   persisted, per decision (f)/(h)).

### Auto-resolve on write paths

All three hooks use `get_zvg_if_warm` (decision (i)) and set `zvg` only
when it is currently null (except the CAS-change invalidation, decision
(j)). No hook ever raises or delays the write.

1. **Create** (`services/chemicals.py`): after a chemical is created with
   a CAS, attempt warm resolution and set `zvg` on the same flush.
2. **Update** (`services/chemicals.py`): if the update changes the CAS →
   clear `zvg`, then attempt warm resolution against the new CAS. If the
   update merely adds a CAS where none was → attempt warm resolution.
3. **PubChem enrich** (`services/enrich.py::enrich_one`): when the
   PubChem lookup yields/confirms a CAS, attempt warm resolution before
   the flush. This covers the interactive "Fetch from PubChem → Save"
   flow (which lands in create/update anyway) and the bulk PubChem
   backfill.

### Bulk backfill (admin action)

`POST /api/v1/groups/{group_id}/chemicals/backfill-gestis` — mirrors
`enrich-pubchem` / `refetch-ghs` exactly: superuser-only
(`SuperuserDep`), body `{chemical_ids: [...] | null}`, SSE
`StreamingResponse` with one event per chemical plus a final summary.

- Default selection (`chemical_ids: null`): all chemicals in the group
  with a CAS and `zvg IS NULL`.
- Generator `backfill_group_gestis` in `services/enrich.py`, statuses:
  `resolved` / `skipped` (no CAS or `zvg` already set) / `not_found` /
  `error` (index unavailable).
- Uses the full `get_zvg` (may trigger the one index download), then
  iterates without throttling (decision (k)) — one commit per chemical
  like the existing generators, so progress survives interruption.

### Schema

```python
class GestisResolveResult(BaseModel):
    zvg: str | None    # "010420"
    url: str | None    # https://gestis-database.dguv.de/data?name=010420
```

### Config

```python
gestis_api_base: str = "https://gestis-api.dguv.de/api"
gestis_api_key: str = "<public web-client key>"   # override: CHAIMA_GESTIS_API_KEY
```

## Frontend

### New files

- `frontend/src/api/hooks/useGestis.ts` — `useGestisResolve()` mutation
  hook (`POST .../gestis-resolve`).

### Modified files

- `frontend/src/types/index.ts` — `zvg: string | null` on the chemical
  types (`ChemicalRead`/`ChemicalDetail` mirror).
- `frontend/src/components/ChemicalInfoBox.tsx` — link row + auto-resolve.
- `frontend/src/components/settings/ChemicalsAdminSection.tsx` — third
  admin control "Resolve GESTIS links", superuser-only, cloning the
  existing SSE fetch-and-dialog pattern of the PubChem enrich control
  (progress counter, final summary line
  `Resolved N, skipped N, not found N, errors N`).

### ChemicalInfoBox behavior

In the "Links" section, directly under the PubChem row:

- `chemical.zvg` set → render
  `GESTIS {zvg}` → `https://gestis-database.dguv.de/data?name={zvg}`
  (base URL as a frontend constant; same `LinkIcon` + `MuiLink` styling
  as the PubChem row).
- `zvg` null but `cas` set → fire `useGestisResolve` **once per opened
  chemical** (effect keyed on `chemical.id`, guarded against re-fire).
  On a hit, update the chemical in the React Query cache (or invalidate
  the detail query) so the link appears without a manual refresh.
- Miss, error, or no CAS → render nothing (decision (c)); errors are
  silent (no toast — this is background enrichment, not a user action).

## Testing

TDD; all GESTIS HTTP mocked (no live network in CI).

**Service tests** (`tests/services/test_gestis.py`):

- index built correctly from a canned list fixture (entries without
  `cas_nr` skipped, `zvg` zero-padded).
- `get_zvg` hit / miss.
- invalid CAS pattern and bad check digit → `None`, no HTTP call.
- upstream 500 / timeout on first load → `None`, warning logged.
- TTL expiry triggers re-fetch; failed refresh serves the stale index.
- concurrent first lookups fetch the list only once.

**Router tests** (extend `tests/routers/test_chemicals.py` or new file):

- unauthenticated → 401; foreign group → 403/404 (match existing suite).
- hit → 200 `{zvg, url}` **and** `zvg` persisted on the chemical.
- chemical already has `zvg` → returns stored value, upstream not called.
- chemical without CAS → nulls, nothing persisted.
- GESTIS down → 200 with nulls (never 5xx), nothing persisted.
- `backfill-gestis`: non-superuser → 403; SSE events + summary correct;
  default selection only touches `cas IS NOT NULL AND zvg IS NULL`.

**Write-path tests** (extend `tests/services/test_chemicals.py` /
`test_enrich.py`):

- create with CAS + warm index → `zvg` set; cold index → `zvg` null,
  create still succeeds.
- update changing CAS → old `zvg` cleared, new one resolved (warm).
- update leaving CAS untouched → `zvg` untouched.
- `enrich_one` resolving a CAS also sets `zvg` (warm index).

**Frontend e2e** (`frontend/e2e/` alongside existing specs):

- chemical with stored `zvg` → link rendered with correct href, no
  resolve call fired.
- chemical with CAS, no `zvg` → resolve intercepted with a hit fixture →
  link appears.
- resolve miss → no GESTIS row rendered.

## Error handling summary

| Scenario                          | Backend response      | Frontend surface            |
|-----------------------------------|-----------------------|-----------------------------|
| CAS resolves in GESTIS            | 200 `{zvg, url}`      | Link appears / persists     |
| CAS not in GESTIS (~expected)     | 200 `{null, null}`    | Nothing rendered            |
| Chemical has no CAS               | 200 `{null, null}`    | No resolve call fired       |
| GESTIS API down / index cold      | 200 `{null, null}`    | Nothing (retried next open) |
| Invalid CAS (pattern/check digit) | 200 `{null, null}`    | Nothing rendered            |
| Unauthenticated / foreign group   | 401 / 403–404         | Existing auth handling      |

## Open questions

None — the two points left open after brainstorming are resolved above:
endpoint shape (decision (a): chemical-scoped resolve-and-store) and
"not found" memory (decision (f): none, misses are cheap once the index
is warm).
