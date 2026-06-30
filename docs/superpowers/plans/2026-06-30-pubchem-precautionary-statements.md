# PubChem Precautionary (P) Statements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch GHS Precautionary Statement codes (P-codes) from PubChem and surface them on chemicals as their own list, end-to-end (catalog → DB → parser → API → frontend), mirroring the existing H-code (`GHSCode`) stack.

**Architecture:** P-codes get a dedicated catalog table `PStatement` (code + English text, seeded from a static `data/p_statements.json` like `ghs_codes.json`) and a `ChemicalPStatement` join table. PubChem's "GHS Classification" body already contains a "Precautionary Statement Codes" item per source bucket — a single comma-separated string (e.g. `"P210, P233, ..., and P501"`) including combination codes (`P305+P351+P338`). We parse that string with majority voting across buckets (same rule as H-codes), resolve codes to catalog rows (unknown codes warned + skipped), and persist via a join table. The expensive PUG-View GHS body is fetched once and cached so adding P-parsing costs no extra network round-trip.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy (async), Alembic, httpx, pytest (asyncio_mode=auto), React + TypeScript + MUI + react-query.

**Key existing anchors (read these first):**
- Catalog pattern: `src/chaima/data/ghs_codes.json`, `src/chaima/models/ghs.py`, `src/chaima/services/seed.py`
- Parser: `src/chaima/services/pubchem.py` (`parse_ghs_classification`, `_iter_ghs_sections`, `_fetch_ghs`, `lookup_ghs`)
- Schema: `src/chaima/schemas/pubchem.py`, `src/chaima/schemas/chemical.py` (`GHSCodeReadNested`, `ChemicalDetail`)
- Service: `src/chaima/services/chemicals.py` (`_resolve_ghs_codes_by_code`, `replace_ghs_codes`, `get_chemical_detail`)
- Enrich/refetch: `src/chaima/services/enrich.py` (`refetch_ghs_one`)
- Router: `src/chaima/routers/chemicals.py:294` (`get_chemical` detail assembly)
- Migration head: `f608356fe048` (file `alembic/versions/f608356fe048_add_analytics_tables_and_user_login_.py`)
- Frontend: `frontend/src/types/index.ts`, `frontend/src/components/ChemicalInfoBox.tsx`, `frontend/src/components/ChemicalList.tsx:29`
- Parser test fixture (already contains 3 buckets with P-codes): `tests/test_services/fixtures/pubchem_acetone_ghs.json`

**Commands:**
- Backend tests: `./.venv/Scripts/python.exe -m pytest <path> -v`
- Alembic: `./.venv/Scripts/alembic.exe revision -m "..."` / `./.venv/Scripts/alembic.exe upgrade head` / `downgrade -1`
- Frontend build/typecheck: `cd frontend && npm run build`

> **Conventions to honor (from project memory):**
> - No real domains/IPs/emails in source — none needed here.
> - After frontend edits in bundled mode, `npm run build` is required (backend serves `src/chaima/static/`). Final task covers this.
> - Commit frequently; the user reviews uncommitted changes before any push. Do **not** push.

---

## File Structure

**Create:**
- `src/chaima/data/p_statements.json` — static P-statement catalog (code + English text)
- `src/chaima/models/pstatement.py` — `PStatement`, `ChemicalPStatement`
- `alembic/versions/<rev>_add_precautionary_statements.py` — two new tables
- `tests/test_services/test_pstatements.py` — parser + catalog tests
- `frontend/src/components/PStatementList.tsx` — renders P-code chips with tooltips

**Modify:**
- `src/chaima/models/__init__.py` — export new models
- `src/chaima/models/chemical.py` — add `pstatement_links` relationship
- `src/chaima/services/seed.py` — seed `p_statements.json`
- `src/chaima/services/pubchem.py` — raw GHS-body cache + `parse_precautionary_codes` + `lookup_precautionary`
- `src/chaima/schemas/pubchem.py` — `PubChemLookupResult.precautionary_codes`
- `src/chaima/schemas/chemical.py` — `PStatementReadNested`, `ChemicalDetail.precautionary_codes`
- `src/chaima/services/chemicals.py` — `_resolve_p_codes_by_code`, `replace_p_codes`, eager-load in `get_chemical_detail`
- `src/chaima/services/enrich.py` — P-merge in `refetch_ghs_one`
- `src/chaima/routers/chemicals.py` — assemble `precautionary_codes` in `get_chemical`
- `frontend/src/types/index.ts` — `PStatementRead`, extend `ChemicalDetail`, `PubChemLookupResult`
- `frontend/src/components/ChemicalInfoBox.tsx` — render P-statements under Hazards
- `frontend/src/components/ChemicalList.tsx` — thread `pStatements` prop

---

## Task 1: P-statement catalog data file

**Files:**
- Create: `src/chaima/data/p_statements.json`
- Test: `tests/test_services/test_pstatements.py`

The catalog is a JSON array of `{"code": "...", "description": "..."}` objects (no pictogram/signal_word — P-codes have neither). It must include all standard single P-codes (P1xx general, P2xx prevention, P3xx response, P4xx storage, P5xx disposal) **and** the combination codes. At minimum it MUST contain every code present in the acetone fixture so downstream resolution tests pass:
`P210, P233, P240, P241, P242, P243, P261, P264, P265, P264+P265, P271, P280, P303, P361, P353, P303+P361+P353, P304, P340, P304+P340, P305, P351, P338, P305+P351+P338, P319, P337, P317, P337+P317, P370, P378, P370+P378, P403, P233, P403+P233, P235, P403+P235, P405, P501`.

Use the official CLP/GHS English wording (consistent with `ghs_codes.json`, which is English). Example entries (exact style to follow):

```json
[
  {"code": "P210", "description": "Keep away from heat, hot surfaces, sparks, open flames and other ignition sources. No smoking."},
  {"code": "P233", "description": "Keep container tightly closed."},
  {"code": "P280", "description": "Wear protective gloves/protective clothing/eye protection/face protection."},
  {"code": "P305+P351+P338", "description": "IF IN EYES: Rinse cautiously with water for several minutes. Remove contact lenses, if present and easy to do. Continue rinsing."},
  {"code": "P501", "description": "Dispose of contents/container in accordance with local/regional/national/international regulations."}
]
```

- [ ] **Step 1: Write the failing test (catalog completeness + shape)**

```python
# tests/test_services/test_pstatements.py
import json
from pathlib import Path

_CATALOG = (
    Path(__file__).resolve().parents[1]
    / ".." / "src" / "chaima" / "data" / "p_statements.json"
).resolve()


def test_catalog_is_well_formed():
    entries = json.loads(_CATALOG.read_text(encoding="utf-8"))
    assert isinstance(entries, list) and entries
    codes = [e["code"] for e in entries]
    assert len(codes) == len(set(codes)), "duplicate codes in catalog"
    for e in entries:
        assert e["code"].startswith("P")
        assert e["description"].strip()


def test_catalog_covers_acetone_fixture_codes():
    entries = json.loads(_CATALOG.read_text(encoding="utf-8"))
    codes = {e["code"] for e in entries}
    required = {
        "P210", "P233", "P240", "P241", "P242", "P243", "P261",
        "P264+P265", "P271", "P280", "P303+P361+P353", "P304+P340",
        "P305+P351+P338", "P319", "P337+P317", "P370+P378",
        "P403+P233", "P403+P235", "P405", "P501",
    }
    missing = required - codes
    assert not missing, f"catalog missing required P-codes: {sorted(missing)}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_services/test_pstatements.py -v`
Expected: FAIL — `FileNotFoundError` (catalog not created yet).

- [ ] **Step 3: Create the catalog file**

Create `src/chaima/data/p_statements.json` with the full standard P-statement set (single + combination codes) using official CLP/GHS English wording. Ensure every code listed above is present. UTF-8, no BOM.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_services/test_pstatements.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/chaima/data/p_statements.json tests/test_services/test_pstatements.py
git commit -m "feat(ghs): add precautionary (P) statement catalog"
```

---

## Task 2: P-statement models

**Files:**
- Create: `src/chaima/models/pstatement.py`
- Modify: `src/chaima/models/__init__.py`, `src/chaima/models/chemical.py:47`

- [ ] **Step 1: Write the model module**

```python
# src/chaima/models/pstatement.py
import uuid as uuid_pkg

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class PStatement(SQLModel, table=True):
    __tablename__ = "p_statement"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    code: str = Field(unique=True, index=True)
    description: str

    chemical_links: list["ChemicalPStatement"] = Relationship(
        back_populates="p_statement"
    )


class ChemicalPStatement(SQLModel, table=True):
    __tablename__ = "chemical_p_statement"
    __table_args__ = (UniqueConstraint("chemical_id", "p_statement_id"),)

    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", primary_key=True)
    p_statement_id: uuid_pkg.UUID = Field(
        foreign_key="p_statement.id", primary_key=True
    )

    chemical: "Chemical" = Relationship(back_populates="pstatement_links")
    p_statement: "PStatement" = Relationship(back_populates="chemical_links")
```

- [ ] **Step 2: Add the relationship on `Chemical`**

In `src/chaima/models/chemical.py`, after line 47 (`ghs_links: list["ChemicalGHS"] = Relationship(back_populates="chemical")`), add:

```python
    pstatement_links: list["ChemicalPStatement"] = Relationship(back_populates="chemical")
```

- [ ] **Step 3: Register the models in the package**

In `src/chaima/models/__init__.py`, add the import (after the `ghs` import line):

```python
from chaima.models.pstatement import ChemicalPStatement, PStatement
```

And add `"ChemicalPStatement"` and `"PStatement"` to `__all__` (keep alphabetical-ish order, matching the file's style).

- [ ] **Step 4: Verify models import cleanly**

Run: `./.venv/Scripts/python.exe -c "from chaima.models import PStatement, ChemicalPStatement, Chemical; print('ok')"`
Expected: prints `ok` with no SQLAlchemy mapper errors.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/pstatement.py src/chaima/models/__init__.py src/chaima/models/chemical.py
git commit -m "feat(ghs): add PStatement + ChemicalPStatement models"
```

---

## Task 3: Alembic migration for the two new tables

**Files:**
- Create: `alembic/versions/<rev>_add_precautionary_statements.py`

Current head is `f608356fe048`. Mirror the structure of the analytics migration's `upgrade`/`downgrade`.

- [ ] **Step 1: Generate an empty revision**

Run: `./.venv/Scripts/alembic.exe revision -m "add precautionary statements"`
Expected: creates a new file under `alembic/versions/` with `down_revision = "f608356fe048"`. Note the generated revision id.

- [ ] **Step 2: Fill in `upgrade`/`downgrade`**

```python
import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers — keep the generated values
down_revision = "f608356fe048"


def upgrade() -> None:
    op.create_table(
        "p_statement",
        sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_p_statement_code"), "p_statement", ["code"], unique=True)
    op.create_table(
        "chemical_p_statement",
        sa.Column("chemical_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("p_statement_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.ForeignKeyConstraint(["chemical_id"], ["chemical.id"]),
        sa.ForeignKeyConstraint(["p_statement_id"], ["p_statement.id"]),
        sa.PrimaryKeyConstraint("chemical_id", "p_statement_id"),
        sa.UniqueConstraint("chemical_id", "p_statement_id"),
    )


def downgrade() -> None:
    op.drop_table("chemical_p_statement")
    op.drop_index(op.f("ix_p_statement_code"), table_name="p_statement")
    op.drop_table("p_statement")
```

> Verify the GUID/AutoString type references match how `f608356fe048_...py` writes them; copy that file's exact column-type idiom if it differs.

- [ ] **Step 3: Apply and roll back to verify reversibility**

Run: `./.venv/Scripts/alembic.exe upgrade head`
Expected: applies cleanly; `p_statement` and `chemical_p_statement` tables exist.
Run: `./.venv/Scripts/alembic.exe downgrade -1` then `./.venv/Scripts/alembic.exe upgrade head`
Expected: both succeed with no errors.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/
git commit -m "feat(ghs): migration for precautionary statement tables"
```

---

## Task 4: Seed the P-statement catalog at startup

**Files:**
- Modify: `src/chaima/services/seed.py`
- Test: `tests/test_services/test_seed.py` (add a test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_services/test_seed.py` (mirror the existing GHS seed test in that file — match its fixture/session setup):

```python
async def test_seed_p_statements_inserts_catalog(session):
    from sqlmodel import select
    from chaima.models.pstatement import PStatement
    from chaima.services.seed import seed_p_statements

    await seed_p_statements(session)
    codes = set((await session.exec(select(PStatement.code))).all())
    assert {"P210", "P280", "P305+P351+P338"} <= codes

    # Idempotent: a second run inserts nothing new and does not raise.
    await seed_p_statements(session)
    codes2 = set((await session.exec(select(PStatement.code))).all())
    assert codes2 == codes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_services/test_seed.py::test_seed_p_statements_inserts_catalog -v`
Expected: FAIL — `ImportError: cannot import name 'seed_p_statements'`.

- [ ] **Step 3: Implement the seed**

In `src/chaima/services/seed.py`:

Add catalog path next to `_GHS_CATALOG_PATH`:

```python
_P_STATEMENT_CATALOG_PATH = _DATA_DIR / "p_statements.json"
```

Add import next to the GHS model import:

```python
from chaima.models.pstatement import PStatement
```

Add the seed function (mirrors `seed_ghs_catalog`):

```python
async def seed_p_statements(session: AsyncSession) -> None:
    """Insert missing rows from the precautionary-statement catalog.

    Existing rows are left untouched (hand-edited descriptions survive).
    """
    entries = json.loads(_P_STATEMENT_CATALOG_PATH.read_text(encoding="utf-8"))

    existing_codes: set[str] = set()
    result = await session.exec(select(PStatement.code))
    for code in result.all():
        existing_codes.add(code)

    inserted = 0
    for entry in entries:
        code = entry["code"]
        if code in existing_codes:
            continue
        session.add(PStatement(code=code, description=entry["description"]))
        inserted += 1

    await session.flush()
    await session.commit()
    logger.info(
        "seeded P-statements: %d inserted, %d already present",
        inserted,
        len(entries) - inserted,
    )
```

Register it in `run_seeds`:

```python
async def run_seeds(session: AsyncSession) -> None:
    await seed_ghs_catalog(session)
    await seed_p_statements(session)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_services/test_seed.py -v`
Expected: PASS (all seed tests).

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/seed.py tests/test_services/test_seed.py
git commit -m "feat(ghs): seed precautionary statement catalog on startup"
```

---

## Task 5: Parse P-codes from PubChem (+ single-fetch raw-body cache)

**Files:**
- Modify: `src/chaima/services/pubchem.py`
- Test: `tests/test_services/test_pstatements.py`, `tests/test_services/test_pubchem.py`

P-codes live in the same "GHS Classification" body as H-codes. To avoid a second 10–15 s fetch, refactor so the raw body is fetched once and cached, then both `lookup_ghs` and the new `lookup_precautionary` parse from it.

- [ ] **Step 1: Write the failing parser test**

Add to `tests/test_services/test_pstatements.py`:

```python
import json
from pathlib import Path

from chaima.services.pubchem import parse_precautionary_codes

_FIXTURES = Path(__file__).resolve().parents[0] / "fixtures"


def test_parse_precautionary_codes_from_acetone_fixture():
    data = json.loads((_FIXTURES / "pubchem_acetone_ghs.json").read_text())
    codes = parse_precautionary_codes(data)
    # Single + combination codes are extracted; "and " prefix on the last
    # item is stripped; majority voting across the 3 buckets applies.
    assert "P210" in codes
    assert "P280" in codes
    assert "P305+P351+P338" in codes
    assert "P501" in codes
    # No stray "and"-prefixed or empty tokens.
    assert all(c.startswith("P") and "+" not in c.strip("P0123456789+") for c in codes)
    assert "" not in codes


def test_parse_precautionary_codes_empty_on_no_section():
    assert parse_precautionary_codes({}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_services/test_pstatements.py -k precautionary -v`
Expected: FAIL — `ImportError: cannot import name 'parse_precautionary_codes'`.

- [ ] **Step 3: Implement parser + body cache + lookup**

In `src/chaima/services/pubchem.py`:

Add the P-code regex near `_HAZARD_CODE_RE`:

```python
# A single P-code or a combination like "P305+P351+P338".
_P_CODE_RE = re.compile(r"^P\d{3}(?:\+P\d{3})*$")
```

Add the parser (reuses `_iter_ghs_sections`, `_value_strings`, and the bucket/majority idiom from `parse_ghs_classification`):

```python
def parse_precautionary_codes(data: dict[str, Any]) -> list[str]:
    """Extract P-codes from a PubChem PUG-View GHS Classification body.

    PubChem reports precautionary codes as one comma-separated string per
    source bucket (e.g. ``"P210, P233, ..., and P501"``), including
    combination codes (``P305+P351+P338``). We split that string, normalize
    each token, and keep a code only when it appears in a strict majority of
    source buckets — mirroring ``parse_ghs_classification``. With fewer than
    three buckets every observed code is kept.
    """
    sections = list(_iter_ghs_sections(data))
    if not sections:
        return []

    code_counts: dict[str, int] = defaultdict(int)
    first_seen: dict[str, int] = {}
    order = 0
    bucket_count = 0

    for section in sections:
        buckets: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for info in section.get("Information") or []:
            buckets[info.get("ReferenceNumber")].append(info)

        for items in buckets.values():
            bucket_count += 1
            codes_in_bucket: set[str] = set()
            for info in items:
                if info.get("Name") != "Precautionary Statement Codes":
                    continue
                for raw in _value_strings(info.get("Value") or {}):
                    for token in _split_precautionary_string(raw):
                        if _P_CODE_RE.match(token):
                            codes_in_bucket.add(token)
            for code in codes_in_bucket:
                code_counts[code] += 1
                if code not in first_seen:
                    first_seen[code] = order
                    order += 1

    if bucket_count == 0:
        return []
    threshold = 1 if bucket_count < 3 else bucket_count // 2 + 1
    kept = [c for c, n in code_counts.items() if n >= threshold]
    kept.sort(key=lambda c: (-code_counts[c], first_seen[c]))
    return kept


def _split_precautionary_string(text: str) -> list[str]:
    """Split a 'P210, P233, ..., and P501' string into normalized codes."""
    out: list[str] = []
    for part in text.split(","):
        token = part.strip()
        if token.lower().startswith("and "):
            token = token[4:].strip()
        token = token.rstrip(".")
        if token:
            out.append(token)
    return out
```

Refactor the GHS body fetch so it is fetched once and cached, then add `lookup_precautionary`:

```python
async def _lookup_ghs_body(cid: str) -> dict[str, Any]:
    """Fetch + cache the raw PUG-View GHS Classification body for a CID.

    Cached 24h under ``ghsbody:{cid}``. Returns ``{}`` on any failure so
    callers degrade to empty results without handling errors.
    """
    cache_key = f"ghsbody:{cid}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    timeout = httpx.Timeout(_GHS_TIMEOUT, connect=_PER_REQUEST_TIMEOUT)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            body = await _fetch_ghs(client, int(cid))
    except (PubChemUpstreamError, Exception) as exc:
        logger.warning("GHS body fetch failed for CID %s: %s", cid, exc)
        return {}
    _cache_set(cache_key, body)
    return body


async def lookup_precautionary(cid: str) -> list[str]:
    """Fetch GHS precautionary (P) codes for a CID.

    Reuses the cached raw GHS body, so it adds no network cost when called
    alongside ``lookup_ghs``. Returns an empty list on failure.
    """
    body = await _lookup_ghs_body(cid)
    if not body:
        return []
    return parse_precautionary_codes(body)
```

Update `lookup_ghs` to parse from the cached body instead of fetching directly (keep its `ghs:{cid}` parsed-result cache):

```python
async def lookup_ghs(cid: str) -> list[PubChemGHSHit]:
    cache_key = f"ghs:{cid}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    body = await _lookup_ghs_body(cid)
    result = parse_ghs_classification(body) if body else []
    _cache_set(cache_key, result)
    return result
```

- [ ] **Step 4: Run parser + existing pubchem tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_services/test_pstatements.py tests/test_services/test_pubchem.py -v`
Expected: PASS. The existing `test_lookup_ghs_happy_path` / `test_lookup_ghs_failure_returns_empty` still pass (they mock `httpx.AsyncClient`, which `_lookup_ghs_body` still uses). If a mock-call-count assertion breaks because the body is now cached, adjust only that count, not behavior.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/pubchem.py tests/test_services/test_pstatements.py
git commit -m "feat(pubchem): parse precautionary (P) codes; cache raw GHS body"
```

---

## Task 6: Lookup schema exposes P-codes

**Files:**
- Modify: `src/chaima/schemas/pubchem.py`
- Test: `tests/test_services/test_pubchem.py` (extend lookup-flow coverage if a P-on-lookup test exists; otherwise schema default suffices)

`lookup()` itself does **not** fetch GHS (too slow), so `precautionary_codes` defaults to `[]` on the fast lookup, exactly like `ghs_codes`. The field exists so the refetch/detail paths can populate it and the frontend type is stable.

- [ ] **Step 1: Add the field**

In `src/chaima/schemas/pubchem.py`, in `PubChemLookupResult`, after `ghs_codes`:

```python
    precautionary_codes: list[str] = []
```

Update the class docstring's Parameters to mention `precautionary_codes : list[str]` (P-codes, empty on the fast lookup).

- [ ] **Step 2: Verify `lookup` still constructs**

`lookup()` builds `PubChemLookupResult(... ghs_codes=[])` without passing `precautionary_codes`; the default `[]` covers it.
Run: `./.venv/Scripts/python.exe -m pytest tests/test_services/test_pubchem.py -v`
Expected: PASS (no constructor breakage).

- [ ] **Step 3: Commit**

```bash
git add src/chaima/schemas/pubchem.py
git commit -m "feat(pubchem): add precautionary_codes to lookup schema"
```

---

## Task 7: Persistence helpers — resolve + replace P-codes

**Files:**
- Modify: `src/chaima/services/chemicals.py`
- Test: `tests/test_services/test_chemicals.py` (add tests)

Mirror `_resolve_ghs_codes_by_code` and `replace_ghs_codes` for P-codes.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_services/test_chemicals.py` (reuse the file's existing chemical/session fixtures; seed P-catalog first):

```python
async def test_resolve_p_codes_skips_unknown(session):
    from chaima.services.seed import seed_p_statements
    from chaima.services.chemicals import _resolve_p_codes_by_code

    await seed_p_statements(session)
    ids = await _resolve_p_codes_by_code(session, ["P280", "P999"])
    assert len(ids) == 1  # P280 resolves, P999 is unknown and skipped


async def test_replace_p_codes_round_trips(session, chemical_factory):
    from chaima.services.seed import seed_p_statements
    from chaima.services.chemicals import (
        _resolve_p_codes_by_code,
        replace_p_codes,
    )
    from chaima.models.pstatement import ChemicalPStatement
    from sqlmodel import select

    await seed_p_statements(session)
    chem = await chemical_factory()  # use whatever helper the test module already uses
    ids = await _resolve_p_codes_by_code(session, ["P210", "P280"])
    await replace_p_codes(session, chem.id, ids)
    links = (
        await session.exec(
            select(ChemicalPStatement).where(
                ChemicalPStatement.chemical_id == chem.id
            )
        )
    ).all()
    assert len(links) == 2

    # Replacing with a subset removes the dropped link.
    await replace_p_codes(session, chem.id, ids[:1])
    links2 = (
        await session.exec(
            select(ChemicalPStatement).where(
                ChemicalPStatement.chemical_id == chem.id
            )
        )
    ).all()
    assert len(links2) == 1
```

> If `test_chemicals.py` has no `chemical_factory`, create the chemical inline the same way other tests in that file do (via `chemical_service.create_chemical(...)`); match the existing pattern exactly.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_services/test_chemicals.py -k p_codes -v`
Expected: FAIL — `ImportError` for `_resolve_p_codes_by_code` / `replace_p_codes`.

- [ ] **Step 3: Implement the helpers**

In `src/chaima/services/chemicals.py`, add the model import near the GHS one:

```python
from chaima.models.pstatement import ChemicalPStatement, PStatement
```

Add (mirroring `_resolve_ghs_codes_by_code`):

```python
async def _resolve_p_codes_by_code(
    session: AsyncSession, codes: list[str]
) -> list[UUID]:
    """Map P-code strings to existing PStatement row IDs.

    Codes not in the catalog are logged at WARNING and skipped — they
    never trigger an upsert or an error.
    """
    if not codes:
        return []
    result = await session.exec(
        select(PStatement).where(PStatement.code.in_(codes))  # type: ignore[union-attr]
    )
    found = {row.code: row.id for row in result.all()}
    resolved: list[UUID] = []
    for code in codes:
        pid = found.get(code)
        if pid is None:
            logger.warning("unknown P-code from upstream: %s", code)
            continue
        resolved.append(pid)
    return resolved
```

Add (mirroring `replace_ghs_codes` — copy that function's delete-then-insert body, swapping `ChemicalGHS`→`ChemicalPStatement`, `ghs_id`→`p_statement_id`, return `PStatement` rows):

```python
async def replace_p_codes(
    session: AsyncSession,
    chemical_id: UUID,
    p_statement_ids: list[UUID],
) -> list[PStatement]:
    """Replace all P-statement assignments for a chemical.

    Deletes existing ChemicalPStatement links and creates new ones.
    """
    existing = await session.exec(
        select(ChemicalPStatement).where(
            ChemicalPStatement.chemical_id == chemical_id
        )
    )
    for link in existing.all():
        await session.delete(link)
    await session.flush()

    for pid in p_statement_ids:
        session.add(
            ChemicalPStatement(chemical_id=chemical_id, p_statement_id=pid)
        )
    await session.flush()

    rows = await session.exec(
        select(PStatement).where(PStatement.id.in_(p_statement_ids))  # type: ignore[union-attr]
    )
    return list(rows.all())
```

Add the eager load in `get_chemical_detail` (`src/chaima/services/chemicals.py:418-422`), next to the `ghs_links` option:

```python
            selectinload(Chemical.pstatement_links).selectinload(
                ChemicalPStatement.p_statement
            ),  # type: ignore[arg-type]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_services/test_chemicals.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/chemicals.py tests/test_services/test_chemicals.py
git commit -m "feat(ghs): resolve + replace precautionary codes on chemicals"
```

---

## Task 8: Detail schema + API expose P-codes

**Files:**
- Modify: `src/chaima/schemas/chemical.py`, `src/chaima/routers/chemicals.py:327-338`
- Test: `tests/test_api/test_chemicals.py` (add a detail-shape assertion)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api/test_chemicals.py` (mirror an existing GHS-on-detail test; if none, follow the file's chemical-create + GET `/{id}` pattern). Seed P-catalog, attach a P-code via `replace_p_codes`, then assert the detail payload:

```python
async def test_chemical_detail_includes_precautionary_codes(
    client, session, group, auth_headers, chemical_factory
):
    from chaima.services.seed import seed_p_statements
    from chaima.services.chemicals import _resolve_p_codes_by_code, replace_p_codes

    await seed_p_statements(session)
    chem = await chemical_factory(group_id=group.id)
    ids = await _resolve_p_codes_by_code(session, ["P280"])
    await replace_p_codes(session, chem.id, ids)
    await session.commit()

    resp = await client.get(
        f"/api/v1/groups/{group.id}/chemicals/{chem.id}", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "precautionary_codes" in body
    codes = [p["code"] for p in body["precautionary_codes"]]
    assert "P280" in codes
    assert body["precautionary_codes"][0]["description"].strip()
```

> Match the actual route prefix and fixture names used elsewhere in `test_chemicals.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api/test_chemicals.py -k precautionary -v`
Expected: FAIL — `precautionary_codes` not in response (KeyError / assertion).

- [ ] **Step 3: Add the nested schema + extend `ChemicalDetail`**

In `src/chaima/schemas/chemical.py`, add after `GHSCodeReadNested`:

```python
class PStatementReadNested(BaseModel):
    """Nested precautionary-statement schema used inside ChemicalDetail.

    Parameters
    ----------
    id : UUID
        P-statement catalog ID.
    code : str
        P-code string (e.g. ``"P280"`` or ``"P305+P351+P338"``).
    description : str
        Human-readable precautionary statement.
    """

    model_config = {"from_attributes": True}

    id: UUID
    code: str
    description: str
```

In `ChemicalDetail`, add the field (after `ghs_codes`):

```python
    precautionary_codes: list[PStatementReadNested]
```

Update the `ChemicalDetail` docstring Parameters accordingly.

- [ ] **Step 4: Assemble it in the router**

In `src/chaima/routers/chemicals.py`, import `PStatementReadNested` alongside `GHSCodeReadNested`, and in `get_chemical` (the `return ChemicalDetail(...)` block at line 327) add:

```python
        precautionary_codes=[
            PStatementReadNested.model_validate(link.p_statement, from_attributes=True)
            for link in chem.pstatement_links
        ],
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api/test_chemicals.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/chaima/schemas/chemical.py src/chaima/routers/chemicals.py tests/test_api/test_chemicals.py
git commit -m "feat(api): expose precautionary_codes on chemical detail"
```

---

## Task 9: Refetch merges P-codes alongside GHS

**Files:**
- Modify: `src/chaima/services/enrich.py:113-171`
- Test: `tests/test_services/test_enrich.py` (add a merge test)

`refetch_ghs_one` already pulls GHS + synonyms via `asyncio.gather`. Add P-codes to the gather and merge them like GHS (union with existing, code equality, manual additions preserved).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_services/test_enrich.py` (mirror the existing `refetch_ghs_one` test; seed P-catalog, mock `pubchem.lookup_precautionary` to return `["P210", "P280"]`, give the chemical a `cid`, assert links created and status `"updated"`):

```python
async def test_refetch_merges_precautionary_codes(session, monkeypatch, chemical_factory):
    from chaima.services import enrich as enrich_mod
    from chaima.services.seed import seed_p_statements
    from chaima.models.pstatement import ChemicalPStatement
    from sqlmodel import select

    await seed_p_statements(session)
    chem = await chemical_factory(cid="180")

    async def fake_ghs(cid):
        return []

    async def fake_syn(cid):
        return []

    async def fake_p(cid):
        return ["P210", "P280"]

    monkeypatch.setattr(enrich_mod, "pubchem_lookup_ghs", fake_ghs)
    monkeypatch.setattr(enrich_mod, "pubchem_lookup_synonyms", fake_syn)
    monkeypatch.setattr(enrich_mod, "pubchem_lookup_precautionary", fake_p)

    status = await enrich_mod.refetch_ghs_one(session, chem)
    assert status == "updated"
    links = (
        await session.exec(
            select(ChemicalPStatement).where(
                ChemicalPStatement.chemical_id == chem.id
            )
        )
    ).all()
    assert len(links) == 2
```

> Match the actual fixture/factory names in `test_enrich.py`. If existing refetch tests patch `pubchem_lookup_ghs` differently (e.g. via `patch(...)`), follow that same mechanism.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_services/test_enrich.py -k precautionary -v`
Expected: FAIL — `pubchem_lookup_precautionary` not imported in `enrich`; no P-links created.

- [ ] **Step 3: Implement the merge**

In `src/chaima/services/enrich.py`:

Extend the pubchem import block:

```python
from chaima.services.pubchem import (
    PubChemNotFound,
    lookup as pubchem_lookup,
    lookup_ghs as pubchem_lookup_ghs,
    lookup_precautionary as pubchem_lookup_precautionary,
    lookup_synonyms as pubchem_lookup_synonyms,
)
```

Extend the chemicals-service import:

```python
from chaima.services.chemicals import (
    _resolve_ghs_codes_by_code,
    _resolve_p_codes_by_code,
    replace_ghs_codes,
    replace_p_codes,
    replace_synonyms,
)
from chaima.models.pstatement import ChemicalPStatement, PStatement
```

In `refetch_ghs_one`, extend the gather:

```python
    try:
        hits, new_synonyms, new_p_codes = await asyncio.gather(
            pubchem_lookup_ghs(chemical.cid),
            pubchem_lookup_synonyms(chemical.cid),
            pubchem_lookup_precautionary(chemical.cid),
        )
    except Exception:
        return "error"
```

After the GHS merge block (before the synonym merge), add the P-merge:

```python
    # ---- Precautionary-code merge --------------------------------------
    if new_p_codes:
        existing_p_link_ids = (
            await session.exec(
                select(ChemicalPStatement.p_statement_id).where(
                    ChemicalPStatement.chemical_id == chemical.id
                )
            )
        ).all()
        existing_p_codes_result = await session.exec(
            select(PStatement.code).where(
                PStatement.id.in_(set(existing_p_link_ids))  # type: ignore[union-attr]
            )
        )
        existing_p_codes = set(existing_p_codes_result.all())
        merged_p_codes = existing_p_codes | set(new_p_codes)
        if merged_p_codes != existing_p_codes:
            merged_p_ids = await _resolve_p_codes_by_code(
                session, list(merged_p_codes)
            )
            await replace_p_codes(session, chemical.id, merged_p_ids)
            changed = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_services/test_enrich.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/enrich.py tests/test_services/test_enrich.py
git commit -m "feat(enrich): merge precautionary codes on GHS refetch"
```

---

## Task 10: Frontend — types + H/P statements dialog

**Files:**
- Modify: `frontend/src/types/index.ts`, `frontend/src/components/ChemicalList.tsx:29`, `frontend/src/components/ChemicalInfoBox.tsx`
- Create: `frontend/src/components/hazardSignal.ts`, `frontend/src/components/HazardStatementsDialog.tsx`

> **Design spec:** `docs/superpowers/specs/2026-06-30-hp-statements-display-design.md`.
> H/P **text** is shown in a modal `Dialog` opened from a link in the **Links**
> section (`H + P statements (N·H M·P)`), not inline under Hazards. When there
> are no H and no P codes, a greyed-out `No H/P statements` line shows instead.
> The Hazards section (pictograms/signal/tags) is unchanged.

- [ ] **Step 1: Add the types**

In `frontend/src/types/index.ts`:

Add after `GHSCodeRead`:

```typescript
export interface PStatementRead {
  id: string;
  code: string;
  description: string;
}
```

Extend `ChemicalDetail`:

```typescript
export interface ChemicalDetail extends ChemicalRead {
  synonyms: SynonymRead[];
  ghs_codes: GHSCodeRead[];
  precautionary_codes: PStatementRead[];
  hazard_tags: HazardTagRead[];
}
```

Extend `PubChemLookupResult` (the interface around line 343):

```typescript
  ghs_codes: PubChemGHSHit[];
  precautionary_codes: string[];
```

- [ ] **Step 2: Extract `worstSignalWord` into a shared module**

The dialog and `ChemicalInfoBox` both need the signal-word logic. Lift it out
of `ChemicalInfoBox.tsx` (currently lines 18-25) into a shared file.

Create `frontend/src/components/hazardSignal.ts`:

```typescript
// frontend/src/components/hazardSignal.ts
import type { GHSCodeRead } from "../types";

export function worstSignalWord(
  codes: GHSCodeRead[],
): "Danger" | "Warning" | null {
  let hasWarning = false;
  for (const c of codes) {
    if (c.signal_word === "Danger") return "Danger";
    if (c.signal_word === "Warning") hasWarning = true;
  }
  return hasWarning ? "Warning" : null;
}
```

Then in `frontend/src/components/ChemicalInfoBox.tsx`, **delete** the local
`function worstSignalWord(...)` definition (lines 18-25) and import it instead:

```typescript
import { worstSignalWord } from "./hazardSignal";
```

- [ ] **Step 3: Create `HazardStatementsDialog`**

Create `frontend/src/components/HazardStatementsDialog.tsx`:

```tsx
// frontend/src/components/HazardStatementsDialog.tsx
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Typography,
  Stack,
  Chip,
  Tooltip,
  Box,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import type { GHSCodeRead, PStatementRead } from "../types";
import { GHSPictogramRow } from "./GHSPictogramRow";
import { worstSignalWord } from "./hazardSignal";

interface Props {
  open: boolean;
  onClose: () => void;
  chemicalName: string;
  ghsCodes: GHSCodeRead[];
  pStatements: PStatementRead[];
}

export function HazardStatementsDialog({
  open,
  onClose,
  chemicalName,
  ghsCodes,
  pStatements,
}: Props) {
  const signal = worstSignalWord(ghsCodes);
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pr: 5 }}>
        Hazard &amp; precautionary statements
        <Typography variant="caption" color="text.secondary" display="block">
          {chemicalName}
        </Typography>
        <IconButton
          aria-label="close"
          onClick={onClose}
          sx={{ position: "absolute", right: 8, top: 8 }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {(ghsCodes.length > 0 || signal) && (
          <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 2 }}>
            {ghsCodes.length > 0 && (
              <GHSPictogramRow codes={ghsCodes} size={36} />
            )}
            {signal && (
              <Chip
                label={signal}
                size="small"
                color={signal === "Danger" ? "error" : "warning"}
                sx={{ fontWeight: 600 }}
              />
            )}
          </Stack>
        )}

        {ghsCodes.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              Hazard statements (H)
            </Typography>
            <Stack spacing={0.5}>
              {ghsCodes.map((c) => (
                <Typography key={c.id} variant="body2">
                  <strong>{c.code}</strong> — {c.description}
                </Typography>
              ))}
            </Stack>
          </Box>
        )}

        {pStatements.length > 0 && (
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              Precautionary statements (P)
            </Typography>
            <Stack direction="row" flexWrap="wrap" gap={0.5}>
              {pStatements.map((p) => (
                <Tooltip key={p.id} title={p.description} arrow>
                  <Chip label={p.code} size="small" variant="outlined" />
                </Tooltip>
              ))}
            </Stack>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Wire the trigger + dialog into `ChemicalInfoBox`**

In `frontend/src/components/ChemicalInfoBox.tsx`:

Ensure `useState` is imported from `react` (add it if the file doesn't already
import it):

```typescript
import { useState } from "react";
```

Add these imports:

```typescript
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { HazardStatementsDialog } from "./HazardStatementsDialog";
import type { PStatementRead } from "../types";
```

Add to `Props`:

```typescript
  pStatements?: PStatementRead[];
```

Destructure with a default in the component signature (next to `hazardTags = []`):

```typescript
  pStatements = [],
```

At the top of the component body, add open/close state:

```typescript
  const [hpOpen, setHpOpen] = useState(false);
```

In the **Links** section, immediately after the SDS block (the
`{chemical.sds_path ? (...) : (...)}` expression, ~line 315-331), add the
trigger — a link when codes exist, a greyed-out line when not:

```tsx
        {ghsCodes.length > 0 || pStatements.length > 0 ? (
          <Stack
            direction="row"
            spacing={0.5}
            sx={{ alignItems: "center", mt: 0.5 }}
          >
            <WarningAmberIcon sx={{ fontSize: 12, color: "warning.main" }} />
            <MuiLink
              component="button"
              type="button"
              onClick={() => setHpOpen(true)}
              sx={{ fontSize: 11 }}
            >
              H + P statements ({ghsCodes.length}·H {pStatements.length}·P)
            </MuiLink>
          </Stack>
        ) : (
          <Typography
            variant="caption"
            color="text.disabled"
            sx={{ display: "block", mt: 0.5 }}
          >
            No H/P statements
          </Typography>
        )}
```

Render the dialog once, just before the component's final closing `</Box>`
(the outermost wrapper returned by the component):

```tsx
      <HazardStatementsDialog
        open={hpOpen}
        onClose={() => setHpOpen(false)}
        chemicalName={chemical.name}
        ghsCodes={ghsCodes}
        pStatements={pStatements}
      />
```

> The Hazards section (signal chip + `GHSPictogramRow` + hazard tags) and its
> empty-state guard are **left unchanged** — this task only adds to the Links
> section and appends the dialog.

- [ ] **Step 5: Thread the prop from `ChemicalList`**

In `frontend/src/components/ChemicalList.tsx`, at the `<ChemicalInfoBox ...>`
usage (line 25-29), add next to `ghsCodes={detail?.ghs_codes ?? []}`:

```tsx
        pStatements={detail?.precautionary_codes ?? []}
```

- [ ] **Step 6: Build/typecheck the frontend**

Run: `cd frontend && npm run build`
Expected: `tsc -b` passes with no type errors; `vite build` succeeds (this also
refreshes `src/chaima/static/` for bundled mode). Verify the `worstSignalWord`
extraction didn't leave a dangling reference in `ChemicalInfoBox.tsx`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/components/hazardSignal.ts frontend/src/components/HazardStatementsDialog.tsx frontend/src/components/ChemicalInfoBox.tsx frontend/src/components/ChemicalList.tsx
git commit -m "feat(frontend): H + P statements dialog on chemicals"
```

---

## Task 11: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire backend suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass (previously 423; now higher with the added tests). No failures.

- [ ] **Step 2: Frontend build once more**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 3: Manual smoke (real PubChem)**

Start the app, open a chemical with a `cid` (e.g. acetone, CID 180), run
"refetch GHS", then in the detail panel's **Links** section click
`H + P statements (N·H M·P)`. Confirm the dialog opens showing: pictograms +
signal word in the header, H-codes with descriptions, and P-codes as chips whose
hover tooltips reveal the full text (P210, P280, P305+P351+P338, P501, …).
Confirm a chemical with no GHS/P data shows the greyed-out `No H/P statements`
line (no dialog, no errors).

- [ ] **Step 4: Final commit (if any manual fixups)**

```bash
git add -A
git commit -m "chore(ghs): finalize precautionary statements feature"
```

> Do **not** push — the user reviews uncommitted/committed changes himself before any push.

---

## Self-Review Notes

- **Spec coverage:** Catalog (T1), DB model (T2) + migration (T3) + seed (T4); parser (T5); lookup schema (T6); persistence (T7); detail API (T8); refetch (T9); frontend (T10); verification (T11). "Eigene Liste" honored — `precautionary_codes` is a distinct field/table, never mixed into `ghs_codes`. "Voll durch alle Schichten" honored.
- **No-double-fetch:** T5 caches the raw GHS body under `ghsbody:{cid}`, so `lookup_ghs` + `lookup_precautionary` share one network call.
- **Type consistency:** `PStatement.code/description`, `PStatementReadNested{id,code,description}`, `PStatementRead{id,code,description}`, `precautionary_codes` field name — consistent across backend schema, API, TS types, and component props. Helper names `_resolve_p_codes_by_code` / `replace_p_codes` used identically in T7 and T9.
- **Graceful degradation:** unknown P-codes (not in catalog) are warned + skipped, exactly like unknown H-codes — so an incomplete catalog never errors, it just under-links.
- **Combination codes:** stored as their own catalog entries (`P305+P351+P338`) with official combined wording; `_P_CODE_RE` matches them.
