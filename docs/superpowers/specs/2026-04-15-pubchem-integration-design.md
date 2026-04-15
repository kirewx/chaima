# PubChem Integration — Design Spec

**Date:** 2026-04-15
**Status:** Approved — ready for implementation plan

## Goal

Let a user fetch chemical metadata from PubChem by name or CAS and pre-fill
the chemical form, so creating a new chemical (or enriching an existing one)
takes seconds instead of manual data entry.

## Scope

**In scope for v1:**

- A `GET /pubchem/lookup?q=<name-or-cas>` backend endpoint that hits
  PubChem PUG REST and returns a normalized payload.
- A "Lookup from PubChem" bar at the top of the `ChemicalForm` drawer,
  available in both create and edit modes.
- Fetched data populates name, CAS, molar mass (visible) plus cid, smiles,
  synonyms, GHS hazard codes, and `structure_source = PUBCHEM` (hidden).
- A one-time seed of the global `GHSCode` catalog from a bundled JSON file,
  run idempotently from the FastAPI lifespan.
- A generic seed mechanism (`services/seed.py` with `run_seeds`) that future
  seeds can slot into.

**Out of scope — parked for future features:**

- Vendor / supplier rebuy flow (cheapest + fastest shipping).
- Storage condition modeling (freezer / fridge / RT / inert).
- Rendering of GHS pictograms as images (v1 stores pictogram code strings
  only; rendering can land with the chemical detail redesign).
- A PubChem hit list for ambiguous name searches — v1 takes the top CID.
- Real PubChem hits in CI.

## User flow

```
[ Chemicals page ]
      │  click "New chemical"  (or "Edit" on an existing one)
      ▼
┌────────────── New chemical ──────────────┐
│  🔍 Lookup from PubChem                  │
│  [ acetone       ]  [ Fetch ]            │
│  Fills name, CAS, molar mass and hazards │
│  from PubChem.                            │
│  ─────────────────────────────────       │
│  Name*      [ Acetone           ]        │
│  CAS        [ 67-64-1           ]        │
│  Molar mass [ 58.08       ] g/mol        │
│  Comment    [                   ]        │
│  ☐ Secret                                 │
│                              [ Save ]    │
└───────────────────────────────────────────┘
```

1. User types a name or CAS into the lookup bar, presses Enter or clicks
   Fetch.
2. Frontend calls `GET /pubchem/lookup?q=<query>` and stores the result.
3. **Visible fields are overwritten** with fetched values — name, CAS, molar
   mass. Rationale: if the user pressed Fetch, they want the authoritative
   data.
4. **Hidden extras** (cid, smiles, synonyms, ghs_codes, structure_source)
   are attached to the form's local state and sent on save.
5. A small caption under the lookup bar confirms success:
   `✓ Fetched from PubChem (CID 180)`.
6. A "×" clear affordance on the lookup bar resets the fetched extras back
   to defaults but leaves the visible fields alone (so the user can keep
   whatever they typed).
7. On save, the usual `POST /chemicals` or `PATCH /chemicals/{id}` call
   carries the visible fields plus the hidden extras. Synonyms and GHS
   codes are replaced via the existing bulk-update services.

**Edit mode detail:** when the form loads for an existing chemical, the
hidden extras are seeded from the loaded `ChemicalDetail` so saving
without pressing Fetch preserves existing synonyms / GHS links. Pressing
Fetch in edit mode replaces everything (visible and hidden) — the whole
point of refetching.

## Backend

### New files

- `src/chaima/services/pubchem.py` — PUG REST client + parser.
- `src/chaima/schemas/pubchem.py` — `PubChemLookupResult`, `PubChemGHSHit`.
- `src/chaima/routers/pubchem.py` — single `GET /pubchem/lookup` endpoint.
- `src/chaima/services/seed.py` — `run_seeds`, `seed_ghs_catalog`.
- `src/chaima/data/ghs_codes.json` — static GHS catalog (≈90 rows).

### Modified files

- `src/chaima/app.py` — include the new router; call `run_seeds` from the
  lifespan after `create_all`.
- `src/chaima/schemas/chemical.py` — add optional `synonyms: list[str]`
  and `ghs_codes: list[str]` to `ChemicalCreate` and `ChemicalUpdate`.
- `src/chaima/services/chemicals.py` — on create/update, if `synonyms` or
  `ghs_codes` present, call the existing `replace_synonyms` /
  `replace_ghs_codes` services. Unknown GHS codes (not in catalog) are
  logged and skipped, not upserted, not an error.
- `pyproject.toml` — promote `httpx>=0.28.1` from `[dependency-groups].dev`
  to `[project].dependencies`.

### PubChem service

```python
async def lookup(query: str) -> PubChemLookupResult:
    ...
```

**Input normalization:** strip whitespace. No CAS-vs-name branching — both
go to the `name` namespace; PUG REST resolves CAS through it.

**PUG REST calls** (sequential, async, shared `httpx.AsyncClient`, 8 s
per-request timeout, 15 s total):

1. `GET /rest/pug/compound/name/{query}/cids/JSON` → first CID from
   `IdentifierList.CID[0]`. 404 → `PubChemNotFound`.
2. `GET /rest/pug/compound/cid/{cid}/property/MolecularWeight,CanonicalSMILES,IUPACName/JSON`
   → molar mass, SMILES, IUPAC name.
3. `GET /rest/pug/compound/cid/{cid}/synonyms/JSON` → full list, capped at
   the first **20**. CAS is extracted as the first synonym matching
   `^\d{2,7}-\d{2}-\d$`.
4. `GET /rest/pug/compound/cid/{cid}/classification/JSON?classification_type=ghs`
   → parse `Hierarchies.Hierarchy` tree for H-codes, signal word, pictogram.

**Error classes:**

- `PubChemNotFound` — initial CID lookup returns 404.
- `PubChemUpstreamError` — any other non-200, timeout, connect error.
  The router maps this to **502**.

**Caching:** none in v1.

### Schemas

```python
class PubChemGHSHit(BaseModel):
    code: str                      # "H225"
    description: str               # "Highly flammable liquid and vapour"
    signal_word: str | None        # "Danger" | "Warning" | None
    pictogram: str | None          # "GHS02" | None

class PubChemLookupResult(BaseModel):
    cid: str
    name: str                      # IUPAC name
    cas: str | None                # first CAS-pattern synonym
    molar_mass: float | None
    smiles: str | None
    synonyms: list[str]            # capped at 20
    ghs_codes: list[PubChemGHSHit]
```

`ChemicalCreate` / `ChemicalUpdate` gain:

```python
synonyms: list[str] | None = None
ghs_codes: list[str] | None = None  # just the code strings
```

`cid`, `smiles`, `molar_mass`, `structure_source` already exist on these
schemas and are used as-is.

### Router

```python
@router.get("/pubchem/lookup", response_model=PubChemLookupResult)
async def lookup_pubchem(
    q: str = Query(..., min_length=1, max_length=200),
    user: User = Depends(current_active_user),
) -> PubChemLookupResult:
    try:
        return await pubchem_service.lookup(q)
    except PubChemNotFound:
        raise HTTPException(404, "No PubChem match")
    except PubChemUpstreamError:
        raise HTTPException(502, "PubChem unavailable")
```

Auth: any authenticated user. No group scoping — the response is public
external data.

### Seed mechanism

`src/chaima/services/seed.py`:

```python
async def seed_ghs_catalog(session: AsyncSession) -> None: ...
async def run_seeds(session: AsyncSession) -> None:
    await seed_ghs_catalog(session)
```

`seed_ghs_catalog` loads `src/chaima/data/ghs_codes.json`, iterates rows,
`SELECT` by code, inserts if missing, leaves existing rows untouched (so
hand-edited descriptions survive). Logs one line:
`seeded GHS: N inserted, M already present`.

Called from the FastAPI lifespan in `app.py` after `create_all`. Future
seeds add another function and one line in `run_seeds`. No registry, no
DSL.

**GHS catalog contents:** physical H200–H290, health H300–H373,
environmental H400–H422, plus EUH001, EUH014, EUH029, EUH031, EUH032,
EUH066, EUH070, EUH071, EUH201–EUH210. Pictogram codes GHS01–GHS09, null
for EUH. Signal word "Danger", "Warning", or null per the UN mapping.
Roughly 90 rows, ≈8 KB file.

## Frontend

### New files

- `frontend/src/api/hooks/usePubChem.ts` — `useMutation`-based hook.

### Modified files

- `frontend/src/types/index.ts` — add `PubChemLookupResult` and
  `PubChemGHSHit` mirroring the backend schema.
- `frontend/src/components/drawer/ChemicalForm.tsx` — add the lookup bar,
  the molar mass field, the hidden extras state, the fetch handler, and
  the updated save payload.

### Hook

```ts
export function usePubChemLookup() {
  return useMutation<PubChemLookupResult, AxiosError, string>({
    mutationFn: (q) =>
      client.get("/pubchem/lookup", { params: { q } }).then((r) => r.data),
  });
}
```

`useMutation` (not `useQuery`) because refetching the same query should
always hit PubChem fresh — no cache.

### Form state

New visible field: `molar_mass` (numeric, optional, `g/mol` suffix).

Hidden local state:

```ts
const [fetchedExtras, setFetchedExtras] = useState<{
  cid: string | null;
  smiles: string | null;
  synonyms: string[];
  ghs_codes: string[];
  structure_source: "PUBCHEM" | "NONE";
}>({
  cid: null,
  smiles: null,
  synonyms: [],
  ghs_codes: [],
  structure_source: "NONE",
});
```

**On successful fetch:** overwrite name, CAS, molar mass from the result;
replace `fetchedExtras` with `{cid, smiles, synonyms, ghs_codes: result.ghs_codes.map(g => g.code), structure_source: "PUBCHEM"}`.

**On fetch error:** existing snackbar toast. Visible fields untouched.

**Edit mode seed:** on form load, populate `fetchedExtras` from the
loaded `ChemicalDetail` so saving without pressing Fetch preserves
existing data.

**Clear affordance (×):** resets `fetchedExtras` to defaults, clears the
lookup bar, leaves visible fields alone.

**Save payload:** visible fields plus `cid`, `smiles`, `molar_mass`,
`structure_source`, `synonyms`, `ghs_codes` from the merged state.

### Layout

The lookup bar sits in a subtle bordered box at the top of the form,
visually separated from the "real" fields. One line of helper text:
`"Fills name, CAS, molar mass and hazards from PubChem."` A small
caption appears below after a successful fetch:
`✓ Fetched from PubChem (CID 180)`.

## Testing

**Backend unit tests** (`tests/services/test_pubchem.py`):

- `test_lookup_by_name_happy_path` — mock `httpx.AsyncClient` with canned
  responses for acetone; assert every field of the result.
- `test_lookup_by_cas_happy_path` — same, query is `"67-64-1"`.
- `test_lookup_not_found` — CID endpoint 404 → `PubChemNotFound`.
- `test_lookup_upstream_error` — CID endpoint 500 and
  `httpx.TimeoutException` → `PubChemUpstreamError`.
- `test_ghs_parser` — feed the parser a recorded real classification JSON
  fixture, assert H-codes + signal word + pictogram extracted correctly.
- `test_synonym_cap` — canned 500-synonym response, assert 20 returned.

**Backend router tests** (`tests/routers/test_pubchem.py`):

- `test_lookup_endpoint_requires_auth` — unauthenticated → 401.
- `test_lookup_endpoint_success` — monkeypatch service, assert 200.
- `test_lookup_endpoint_not_found` — monkeypatch raises → 404.
- `test_lookup_endpoint_upstream_error` — monkeypatch raises → 502.

**Seed tests** (`tests/services/test_seed.py`):

- `test_seed_ghs_catalog_inserts_all` — empty DB, run seed, assert full
  catalog row count.
- `test_seed_ghs_catalog_idempotent` — run twice, assert stable count, no
  errors.
- `test_seed_preserves_edited_descriptions` — hand-edit a row, run seed,
  assert description unchanged.

**Chemicals service tests** (extending `tests/services/test_chemicals.py`):

- `test_create_chemical_with_pubchem_payload` — create with synonyms,
  ghs_codes, cid, smiles; assert persisted and linked.
- `test_create_chemical_with_unknown_ghs_code` — unknown code → no link,
  no exception, logged.
- `test_update_chemical_replaces_synonyms_and_ghs` — replace semantics.

**Frontend e2e** (`frontend/e2e/chemical-pubchem.spec.ts`):

- Happy path: intercept `GET /pubchem/lookup` with a fixture, open New
  chemical drawer, type "acetone", click Fetch, assert visible fields
  populate, save, assert the chemical appears in the list.
- Error path: intercept with 502, assert the toast appears and visible
  fields are untouched.

No unit tests for the form itself — existing ChemicalForm has none and
this feature doesn't justify bootstrapping a unit-test framework.

## Error handling summary

| Scenario                         | Backend response | Frontend surface              |
|----------------------------------|------------------|-------------------------------|
| No PubChem match                 | 404              | Toast: "No PubChem match"     |
| PubChem upstream error / timeout | 502              | Toast: "PubChem unavailable"  |
| Unauthenticated                  | 401              | Existing auth flow            |
| Unknown GHS code on save         | 200 (link skipped, logged) | Silent — chemical still saved |

## Open questions

None — all design decisions resolved during brainstorming.
