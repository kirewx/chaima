# PubChem Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user fetch chemical metadata from PubChem by name or CAS from inside the chemical form (create + edit), and auto-fill name, CAS, molar mass, synonyms, CID, SMILES, and GHS hazard codes.

**Architecture:** New FastAPI endpoint `GET /pubchem/lookup` wraps PubChem PUG REST in an async service. Result populates both visible form fields and hidden form state that rides along in the existing `POST/PATCH /chemicals` payload. GHS codes are pre-seeded globally via a new idempotent seed mechanism run from the FastAPI lifespan, so chemicals only need to link to existing rows. No DB migration required — every persisted field already exists on the `Chemical` model.

**Tech Stack:** FastAPI + SQLModel + httpx (backend), React + MUI + TanStack Query + Axios (frontend), pytest-asyncio (auto mode), Playwright (e2e).

**Spec:** `docs/superpowers/specs/2026-04-15-pubchem-integration-design.md`

---

## File map

**Create:**
- `src/chaima/data/ghs_codes.json`
- `src/chaima/services/seed.py`
- `src/chaima/services/pubchem.py`
- `src/chaima/schemas/pubchem.py`
- `src/chaima/routers/pubchem.py`
- `tests/test_services/test_seed.py`
- `tests/test_services/test_pubchem.py`
- `tests/test_services/fixtures/pubchem_acetone_cid.json`
- `tests/test_services/fixtures/pubchem_acetone_properties.json`
- `tests/test_services/fixtures/pubchem_acetone_synonyms.json`
- `tests/test_services/fixtures/pubchem_acetone_ghs.json`
- `tests/test_routers/test_pubchem.py`
- `frontend/src/api/hooks/usePubChem.ts`
- `frontend/e2e/chemical-pubchem.spec.ts`

**Modify:**
- `pyproject.toml` — promote `httpx` to runtime deps.
- `src/chaima/app.py` — register pubchem router, call `run_seeds` in lifespan.
- `src/chaima/schemas/chemical.py` — add optional `synonyms`, `ghs_codes` to `ChemicalCreate` and `ChemicalUpdate`.
- `src/chaima/services/chemicals.py` — handle `synonyms`/`ghs_codes` in `create_chemical`/`update_chemical`.
- `src/chaima/routers/chemicals.py` — pass the new fields through to the service.
- `tests/test_services/test_chemicals.py` — new test cases for the extended service.
- `frontend/src/types/index.ts` — add `PubChemLookupResult`, `PubChemGHSHit`, extend `ChemicalCreate`/`ChemicalUpdate` if typed.
- `frontend/src/components/drawer/ChemicalForm.tsx` — lookup bar, molar mass field, hidden extras state, fetch handler, updated save payload.

---

## Task 1: Promote httpx to runtime dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Edit `pyproject.toml`**

  Under `[project].dependencies`, add `"httpx>=0.28.1",` (keep alphabetical placement between `fastapi-users` and `pydantic-settings`). Remove `"httpx>=0.28.1",` from `[dependency-groups].dev`.

  Final `[project].dependencies`:

  ```toml
  dependencies = [
      "aiosqlite>=0.22.1",
      "alembic>=1.18.4",
      "fastapi>=0.135.3",
      "fastapi-users[sqlalchemy]>=15.0.5",
      "httpx>=0.28.1",
      "pydantic-settings>=2.13.1",
      "sqlmodel>=0.0.38",
      "typer>=0.21.1",
      "uvicorn>=0.40.0",
  ]
  ```

  Final `[dependency-groups]`:

  ```toml
  [dependency-groups]
  dev = [
      "pytest>=9.0.3",
      "pytest-asyncio>=1.3.0",
  ]
  ```

- [ ] **Step 2: Sync dependencies**

  Run: `uv sync`
  Expected: completes without error. `uv.lock` may update.

- [ ] **Step 3: Commit**

  ```bash
  git add pyproject.toml uv.lock
  git commit -m "build: promote httpx to runtime dependency"
  ```

---

## Task 2: GHS catalog data file

**Files:**
- Create: `src/chaima/data/ghs_codes.json`

This is a pure data task — no tests, no imports. The seed logic (which consumes this file) lands in Task 3.

- [ ] **Step 1: Create the data file**

  Create `src/chaima/data/ghs_codes.json` with the canonical UN GHS hazard-statement catalog. Each entry has `code`, `description`, `signal_word`, `pictogram`. Signal word is `"Danger"`, `"Warning"`, or `null`. Pictogram is one of `GHS01`–`GHS09` or `null` (EUH statements have no pictogram). Descriptions match UN GHS Rev. 9 Annex 3.

  ```json
  [
    {"code": "H200", "description": "Unstable explosive", "signal_word": "Danger", "pictogram": "GHS01"},
    {"code": "H201", "description": "Explosive; mass explosion hazard", "signal_word": "Danger", "pictogram": "GHS01"},
    {"code": "H202", "description": "Explosive; severe projection hazard", "signal_word": "Danger", "pictogram": "GHS01"},
    {"code": "H203", "description": "Explosive; fire, blast or projection hazard", "signal_word": "Danger", "pictogram": "GHS01"},
    {"code": "H204", "description": "Fire or projection hazard", "signal_word": "Warning", "pictogram": "GHS01"},
    {"code": "H205", "description": "May mass explode in fire", "signal_word": "Danger", "pictogram": "GHS01"},
    {"code": "H206", "description": "Fire, blast or projection hazard; increased risk of explosion if desensitising agent is reduced", "signal_word": "Danger", "pictogram": "GHS01"},
    {"code": "H207", "description": "Fire or projection hazard; increased risk of explosion if desensitising agent is reduced", "signal_word": "Danger", "pictogram": "GHS01"},
    {"code": "H208", "description": "Fire hazard; increased risk of explosion if desensitising agent is reduced", "signal_word": "Warning", "pictogram": "GHS02"},
    {"code": "H220", "description": "Extremely flammable gas", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H221", "description": "Flammable gas", "signal_word": "Warning", "pictogram": "GHS02"},
    {"code": "H222", "description": "Extremely flammable aerosol", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H223", "description": "Flammable aerosol", "signal_word": "Warning", "pictogram": "GHS02"},
    {"code": "H224", "description": "Extremely flammable liquid and vapour", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H225", "description": "Highly flammable liquid and vapour", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H226", "description": "Flammable liquid and vapour", "signal_word": "Warning", "pictogram": "GHS02"},
    {"code": "H227", "description": "Combustible liquid", "signal_word": "Warning", "pictogram": "GHS02"},
    {"code": "H228", "description": "Flammable solid", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H229", "description": "Pressurised container: may burst if heated", "signal_word": "Warning", "pictogram": null},
    {"code": "H230", "description": "May react explosively even in the absence of air", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H231", "description": "May react explosively even in the absence of air at elevated pressure and/or temperature", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H232", "description": "May ignite spontaneously if exposed to air", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H240", "description": "Heating may cause an explosion", "signal_word": "Danger", "pictogram": "GHS01"},
    {"code": "H241", "description": "Heating may cause a fire or explosion", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H242", "description": "Heating may cause a fire", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H250", "description": "Catches fire spontaneously if exposed to air", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H251", "description": "Self-heating; may catch fire", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H252", "description": "Self-heating in large quantities; may catch fire", "signal_word": "Warning", "pictogram": "GHS02"},
    {"code": "H260", "description": "In contact with water releases flammable gases which may ignite spontaneously", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H261", "description": "In contact with water releases flammable gases", "signal_word": "Danger", "pictogram": "GHS02"},
    {"code": "H270", "description": "May cause or intensify fire; oxidiser", "signal_word": "Danger", "pictogram": "GHS03"},
    {"code": "H271", "description": "May cause fire or explosion; strong oxidiser", "signal_word": "Danger", "pictogram": "GHS03"},
    {"code": "H272", "description": "May intensify fire; oxidiser", "signal_word": "Warning", "pictogram": "GHS03"},
    {"code": "H280", "description": "Contains gas under pressure; may explode if heated", "signal_word": "Warning", "pictogram": "GHS04"},
    {"code": "H281", "description": "Contains refrigerated gas; may cause cryogenic burns or injury", "signal_word": "Warning", "pictogram": "GHS04"},
    {"code": "H290", "description": "May be corrosive to metals", "signal_word": "Warning", "pictogram": "GHS05"},
    {"code": "H300", "description": "Fatal if swallowed", "signal_word": "Danger", "pictogram": "GHS06"},
    {"code": "H301", "description": "Toxic if swallowed", "signal_word": "Danger", "pictogram": "GHS06"},
    {"code": "H302", "description": "Harmful if swallowed", "signal_word": "Warning", "pictogram": "GHS07"},
    {"code": "H303", "description": "May be harmful if swallowed", "signal_word": null, "pictogram": null},
    {"code": "H304", "description": "May be fatal if swallowed and enters airways", "signal_word": "Danger", "pictogram": "GHS08"},
    {"code": "H305", "description": "May be harmful if swallowed and enters airways", "signal_word": "Warning", "pictogram": "GHS08"},
    {"code": "H310", "description": "Fatal in contact with skin", "signal_word": "Danger", "pictogram": "GHS06"},
    {"code": "H311", "description": "Toxic in contact with skin", "signal_word": "Danger", "pictogram": "GHS06"},
    {"code": "H312", "description": "Harmful in contact with skin", "signal_word": "Warning", "pictogram": "GHS07"},
    {"code": "H313", "description": "May be harmful in contact with skin", "signal_word": null, "pictogram": null},
    {"code": "H314", "description": "Causes severe skin burns and eye damage", "signal_word": "Danger", "pictogram": "GHS05"},
    {"code": "H315", "description": "Causes skin irritation", "signal_word": "Warning", "pictogram": "GHS07"},
    {"code": "H316", "description": "Causes mild skin irritation", "signal_word": null, "pictogram": null},
    {"code": "H317", "description": "May cause an allergic skin reaction", "signal_word": "Warning", "pictogram": "GHS07"},
    {"code": "H318", "description": "Causes serious eye damage", "signal_word": "Danger", "pictogram": "GHS05"},
    {"code": "H319", "description": "Causes serious eye irritation", "signal_word": "Warning", "pictogram": "GHS07"},
    {"code": "H320", "description": "Causes eye irritation", "signal_word": null, "pictogram": null},
    {"code": "H330", "description": "Fatal if inhaled", "signal_word": "Danger", "pictogram": "GHS06"},
    {"code": "H331", "description": "Toxic if inhaled", "signal_word": "Danger", "pictogram": "GHS06"},
    {"code": "H332", "description": "Harmful if inhaled", "signal_word": "Warning", "pictogram": "GHS07"},
    {"code": "H333", "description": "May be harmful if inhaled", "signal_word": null, "pictogram": null},
    {"code": "H334", "description": "May cause allergy or asthma symptoms or breathing difficulties if inhaled", "signal_word": "Danger", "pictogram": "GHS08"},
    {"code": "H335", "description": "May cause respiratory irritation", "signal_word": "Warning", "pictogram": "GHS07"},
    {"code": "H336", "description": "May cause drowsiness or dizziness", "signal_word": "Warning", "pictogram": "GHS07"},
    {"code": "H340", "description": "May cause genetic defects", "signal_word": "Danger", "pictogram": "GHS08"},
    {"code": "H341", "description": "Suspected of causing genetic defects", "signal_word": "Warning", "pictogram": "GHS08"},
    {"code": "H350", "description": "May cause cancer", "signal_word": "Danger", "pictogram": "GHS08"},
    {"code": "H351", "description": "Suspected of causing cancer", "signal_word": "Warning", "pictogram": "GHS08"},
    {"code": "H360", "description": "May damage fertility or the unborn child", "signal_word": "Danger", "pictogram": "GHS08"},
    {"code": "H361", "description": "Suspected of damaging fertility or the unborn child", "signal_word": "Warning", "pictogram": "GHS08"},
    {"code": "H362", "description": "May cause harm to breast-fed children", "signal_word": null, "pictogram": "GHS08"},
    {"code": "H370", "description": "Causes damage to organs", "signal_word": "Danger", "pictogram": "GHS08"},
    {"code": "H371", "description": "May cause damage to organs", "signal_word": "Warning", "pictogram": "GHS08"},
    {"code": "H372", "description": "Causes damage to organs through prolonged or repeated exposure", "signal_word": "Danger", "pictogram": "GHS08"},
    {"code": "H373", "description": "May cause damage to organs through prolonged or repeated exposure", "signal_word": "Warning", "pictogram": "GHS08"},
    {"code": "H400", "description": "Very toxic to aquatic life", "signal_word": "Warning", "pictogram": "GHS09"},
    {"code": "H401", "description": "Toxic to aquatic life", "signal_word": null, "pictogram": null},
    {"code": "H402", "description": "Harmful to aquatic life", "signal_word": null, "pictogram": null},
    {"code": "H410", "description": "Very toxic to aquatic life with long lasting effects", "signal_word": "Warning", "pictogram": "GHS09"},
    {"code": "H411", "description": "Toxic to aquatic life with long lasting effects", "signal_word": null, "pictogram": "GHS09"},
    {"code": "H412", "description": "Harmful to aquatic life with long lasting effects", "signal_word": null, "pictogram": null},
    {"code": "H413", "description": "May cause long lasting harmful effects to aquatic life", "signal_word": null, "pictogram": null},
    {"code": "H420", "description": "Harms public health and the environment by destroying ozone in the upper atmosphere", "signal_word": "Warning", "pictogram": null},
    {"code": "EUH014", "description": "Reacts violently with water", "signal_word": null, "pictogram": null},
    {"code": "EUH018", "description": "In use may form flammable/explosive vapour-air mixture", "signal_word": null, "pictogram": null},
    {"code": "EUH019", "description": "May form explosive peroxides", "signal_word": null, "pictogram": null},
    {"code": "EUH029", "description": "Contact with water liberates toxic gas", "signal_word": null, "pictogram": null},
    {"code": "EUH031", "description": "Contact with acids liberates toxic gas", "signal_word": null, "pictogram": null},
    {"code": "EUH032", "description": "Contact with acids liberates very toxic gas", "signal_word": null, "pictogram": null},
    {"code": "EUH044", "description": "Risk of explosion if heated under confinement", "signal_word": null, "pictogram": null},
    {"code": "EUH066", "description": "Repeated exposure may cause skin dryness or cracking", "signal_word": null, "pictogram": null},
    {"code": "EUH070", "description": "Toxic by eye contact", "signal_word": null, "pictogram": null},
    {"code": "EUH071", "description": "Corrosive to the respiratory tract", "signal_word": null, "pictogram": null}
  ]
  ```

- [ ] **Step 2: Validate JSON parses**

  Run: `python -c "import json, pathlib; data = json.loads(pathlib.Path('src/chaima/data/ghs_codes.json').read_text()); print(f'OK: {len(data)} entries'); assert all('code' in d and 'description' in d for d in data)"`
  Expected: `OK: 88 entries` (or similar count).

- [ ] **Step 3: Commit**

  ```bash
  git add src/chaima/data/ghs_codes.json
  git commit -m "feat(ghs): add canonical GHS hazard-statement catalog data"
  ```

---

## Task 3: Seed mechanism + GHS seed + lifespan wiring

**Files:**
- Create: `src/chaima/services/seed.py`
- Create: `tests/test_services/test_seed.py`
- Modify: `src/chaima/app.py`

- [ ] **Step 1: Write the failing seed test**

  Create `tests/test_services/test_seed.py`:

  ```python
  # tests/test_services/test_seed.py
  import json
  from pathlib import Path

  from sqlmodel import select

  from chaima.models.ghs import GHSCode
  from chaima.services.seed import run_seeds, seed_ghs_catalog

  CATALOG_PATH = Path("src/chaima/data/ghs_codes.json")


  async def test_seed_ghs_catalog_inserts_all(session):
      expected = json.loads(CATALOG_PATH.read_text())

      await seed_ghs_catalog(session)
      await session.commit()

      result = await session.exec(select(GHSCode))
      rows = result.all()
      assert len(rows) == len(expected)
      codes = {r.code for r in rows}
      assert "H225" in codes
      assert "H319" in codes
      assert "EUH066" in codes


  async def test_seed_ghs_catalog_idempotent(session):
      await seed_ghs_catalog(session)
      await session.commit()
      first_count = len((await session.exec(select(GHSCode))).all())

      await seed_ghs_catalog(session)
      await session.commit()
      second_count = len((await session.exec(select(GHSCode))).all())

      assert first_count == second_count


  async def test_seed_preserves_edited_descriptions(session):
      await seed_ghs_catalog(session)
      await session.commit()

      # Hand-edit an existing row
      row = (
          await session.exec(select(GHSCode).where(GHSCode.code == "H225"))
      ).first()
      assert row is not None
      row.description = "HAND EDITED"
      session.add(row)
      await session.commit()

      # Re-run seed
      await seed_ghs_catalog(session)
      await session.commit()

      row = (
          await session.exec(select(GHSCode).where(GHSCode.code == "H225"))
      ).first()
      assert row is not None
      assert row.description == "HAND EDITED"


  async def test_run_seeds_runs_ghs_catalog(session):
      await run_seeds(session)
      await session.commit()
      result = await session.exec(select(GHSCode))
      assert len(result.all()) > 0
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `uv run pytest tests/test_services/test_seed.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'chaima.services.seed'`.

- [ ] **Step 3: Implement `src/chaima/services/seed.py`**

  ```python
  # src/chaima/services/seed.py
  """Idempotent data seeds run from the FastAPI lifespan.

  Each seed function must be safe to run on every startup: it may insert
  missing rows but must never overwrite existing ones. Add new seeds by
  writing an async function and calling it from ``run_seeds``.
  """
  import json
  import logging
  from pathlib import Path

  from sqlmodel import select
  from sqlmodel.ext.asyncio.session import AsyncSession

  from chaima.models.ghs import GHSCode

  logger = logging.getLogger(__name__)

  _DATA_DIR = Path(__file__).resolve().parents[1] / "data"
  _GHS_CATALOG_PATH = _DATA_DIR / "ghs_codes.json"


  async def seed_ghs_catalog(session: AsyncSession) -> None:
      """Insert missing rows from the GHS catalog.

      Existing rows are left untouched (hand-edited descriptions survive).
      """
      entries = json.loads(_GHS_CATALOG_PATH.read_text())

      existing_codes: set[str] = set()
      result = await session.exec(select(GHSCode.code))
      for code in result.all():
          existing_codes.add(code)

      inserted = 0
      for entry in entries:
          code = entry["code"]
          if code in existing_codes:
              continue
          session.add(
              GHSCode(
                  code=code,
                  description=entry["description"],
                  signal_word=entry.get("signal_word"),
                  pictogram=entry.get("pictogram"),
              )
          )
          inserted += 1

      await session.flush()
      logger.info(
          "seeded GHS: %d inserted, %d already present",
          inserted,
          len(entries) - inserted,
      )


  async def run_seeds(session: AsyncSession) -> None:
      """Run every registered seed in order.

      Called from the FastAPI lifespan after ``create_db_and_tables``.
      """
      await seed_ghs_catalog(session)
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `uv run pytest tests/test_services/test_seed.py -v`
  Expected: all 4 tests PASS.

- [ ] **Step 5: Wire into the FastAPI lifespan**

  Modify `src/chaima/app.py`. Add the import and extend the lifespan.

  Add import near the other `chaima.*` imports:

  ```python
  from chaima.services.seed import run_seeds
  ```

  Update the `lifespan` function:

  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      await create_db_and_tables()
      async with async_session_maker() as session:
          await seed_admin(session)
          await run_seeds(session)
      yield
  ```

- [ ] **Step 6: Smoke test the app startup**

  Run: `uv run python -c "import asyncio; from chaima.app import lifespan; from fastapi import FastAPI; asyncio.run(lifespan(FastAPI()).__aenter__())"`
  Expected: no exceptions. The log line `seeded GHS: N inserted, M already present` appears.

- [ ] **Step 7: Commit**

  ```bash
  git add src/chaima/services/seed.py tests/test_services/test_seed.py src/chaima/app.py
  git commit -m "feat(seed): idempotent GHS catalog seed run from lifespan"
  ```

---

## Task 4: PubChem schemas + service + tests

**Files:**
- Create: `src/chaima/schemas/pubchem.py`
- Create: `src/chaima/services/pubchem.py`
- Create: `tests/test_services/test_pubchem.py`
- Create: `tests/test_services/fixtures/pubchem_acetone_cid.json`
- Create: `tests/test_services/fixtures/pubchem_acetone_properties.json`
- Create: `tests/test_services/fixtures/pubchem_acetone_synonyms.json`
- Create: `tests/test_services/fixtures/pubchem_acetone_ghs.json`

- [ ] **Step 1: Create the fixture files**

  Create `tests/test_services/fixtures/pubchem_acetone_cid.json`:

  ```json
  {"IdentifierList": {"CID": [180]}}
  ```

  Create `tests/test_services/fixtures/pubchem_acetone_properties.json`:

  ```json
  {
    "PropertyTable": {
      "Properties": [
        {
          "CID": 180,
          "MolecularWeight": "58.08",
          "CanonicalSMILES": "CC(=O)C",
          "IUPACName": "propan-2-one"
        }
      ]
    }
  }
  ```

  Create `tests/test_services/fixtures/pubchem_acetone_synonyms.json`:

  ```json
  {
    "InformationList": {
      "Information": [
        {
          "CID": 180,
          "Synonym": [
            "propan-2-one",
            "Acetone",
            "67-64-1",
            "2-Propanone",
            "Dimethyl ketone",
            "Propanone",
            "Dimethylformaldehyde",
            "beta-Ketopropane",
            "Pyroacetic ether",
            "Ketone propane"
          ]
        }
      ]
    }
  }
  ```

  Create `tests/test_services/fixtures/pubchem_acetone_ghs.json`:

  ```json
  {
    "Hierarchies": {
      "Hierarchy": [
        {
          "SourceName": "European Chemicals Agency (ECHA)",
          "SourceID": "GHS Classification",
          "Node": [
            {
              "Information": {
                "Name": "Pictogram",
                "Description": "GHS02"
              }
            },
            {
              "Information": {
                "Name": "Signal",
                "Description": "Danger"
              }
            },
            {
              "Information": {
                "Name": "GHS Hazard Statements",
                "Description": "H225: Highly flammable liquid and vapour [Danger Flammable liquids - Category 2]"
              }
            },
            {
              "Information": {
                "Name": "GHS Hazard Statements",
                "Description": "H319: Causes serious eye irritation [Warning Serious eye damage/eye irritation - Category 2A]"
              }
            },
            {
              "Information": {
                "Name": "GHS Hazard Statements",
                "Description": "H336: May cause drowsiness or dizziness [Warning Specific target organ toxicity, single exposure; Narcotic effects - Category 3]"
              }
            }
          ]
        }
      ]
    }
  }
  ```

- [ ] **Step 2: Write the failing service tests**

  Create `tests/test_services/test_pubchem.py`:

  ```python
  # tests/test_services/test_pubchem.py
  import json
  from pathlib import Path
  from unittest.mock import AsyncMock, patch

  import httpx
  import pytest

  from chaima.services import pubchem as pubchem_service
  from chaima.services.pubchem import (
      PubChemNotFound,
      PubChemUpstreamError,
      parse_ghs_classification,
  )

  FIXTURES = Path(__file__).parent / "fixtures"


  def _load(name: str) -> dict:
      return json.loads((FIXTURES / name).read_text())


  def _mock_response(data: dict, status: int = 200) -> httpx.Response:
      return httpx.Response(
          status_code=status,
          json=data,
          request=httpx.Request("GET", "https://pubchem.ncbi.nlm.nih.gov/"),
      )


  def _build_client_mock(responses: list[httpx.Response]) -> AsyncMock:
      client = AsyncMock(spec=httpx.AsyncClient)
      client.__aenter__.return_value = client
      client.__aexit__.return_value = None
      client.get = AsyncMock(side_effect=responses)
      return client


  async def test_lookup_by_name_happy_path():
      responses = [
          _mock_response(_load("pubchem_acetone_cid.json")),
          _mock_response(_load("pubchem_acetone_properties.json")),
          _mock_response(_load("pubchem_acetone_synonyms.json")),
          _mock_response(_load("pubchem_acetone_ghs.json")),
      ]
      client = _build_client_mock(responses)

      with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
          result = await pubchem_service.lookup("acetone")

      assert result.cid == "180"
      assert result.name == "propan-2-one"
      assert result.cas == "67-64-1"
      assert result.molar_mass == pytest.approx(58.08)
      assert result.smiles == "CC(=O)C"
      assert "Acetone" in result.synonyms
      assert len(result.synonyms) <= 20
      codes = [g.code for g in result.ghs_codes]
      assert "H225" in codes
      assert "H319" in codes
      assert "H336" in codes
      h225 = next(g for g in result.ghs_codes if g.code == "H225")
      assert h225.description.startswith("Highly flammable")
      assert h225.signal_word == "Danger"
      assert h225.pictogram == "GHS02"


  async def test_lookup_by_cas_happy_path():
      # CAS is passed to the same name namespace — PUG REST resolves it.
      responses = [
          _mock_response(_load("pubchem_acetone_cid.json")),
          _mock_response(_load("pubchem_acetone_properties.json")),
          _mock_response(_load("pubchem_acetone_synonyms.json")),
          _mock_response(_load("pubchem_acetone_ghs.json")),
      ]
      client = _build_client_mock(responses)

      with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
          result = await pubchem_service.lookup("67-64-1")

      assert result.cid == "180"
      assert result.cas == "67-64-1"


  async def test_lookup_not_found():
      responses = [_mock_response({}, status=404)]
      client = _build_client_mock(responses)

      with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
          with pytest.raises(PubChemNotFound):
              await pubchem_service.lookup("nonexistent-compound-xyz")


  async def test_lookup_upstream_error_500():
      responses = [_mock_response({}, status=500)]
      client = _build_client_mock(responses)

      with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
          with pytest.raises(PubChemUpstreamError):
              await pubchem_service.lookup("acetone")


  async def test_lookup_upstream_error_timeout():
      client = AsyncMock(spec=httpx.AsyncClient)
      client.__aenter__.return_value = client
      client.__aexit__.return_value = None
      client.get = AsyncMock(
          side_effect=httpx.TimeoutException("timeout", request=None)
      )

      with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
          with pytest.raises(PubChemUpstreamError):
              await pubchem_service.lookup("acetone")


  def test_parse_ghs_classification_extracts_codes():
      data = json.loads((FIXTURES / "pubchem_acetone_ghs.json").read_text())
      hits = parse_ghs_classification(data)
      codes = [h.code for h in hits]
      assert codes == ["H225", "H319", "H336"]
      assert all(h.signal_word in {"Danger", "Warning"} for h in hits)
      h225 = next(h for h in hits if h.code == "H225")
      assert "flammable" in h225.description.lower()


  def test_parse_ghs_classification_empty():
      assert parse_ghs_classification({}) == []
      assert parse_ghs_classification({"Hierarchies": {}}) == []


  async def test_lookup_synonym_cap():
      long_synonyms = {
          "InformationList": {
              "Information": [
                  {
                      "CID": 180,
                      "Synonym": ["67-64-1"] + [f"syn-{i}" for i in range(500)],
                  }
              ]
          }
      }
      responses = [
          _mock_response(_load("pubchem_acetone_cid.json")),
          _mock_response(_load("pubchem_acetone_properties.json")),
          _mock_response(long_synonyms),
          _mock_response(_load("pubchem_acetone_ghs.json")),
      ]
      client = _build_client_mock(responses)

      with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
          result = await pubchem_service.lookup("acetone")

      assert len(result.synonyms) == 20
  ```

- [ ] **Step 3: Run tests to verify they fail**

  Run: `uv run pytest tests/test_services/test_pubchem.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'chaima.services.pubchem'`.

- [ ] **Step 4: Create `src/chaima/schemas/pubchem.py`**

  ```python
  # src/chaima/schemas/pubchem.py
  """Schemas for the PubChem lookup endpoint response."""
  from pydantic import BaseModel


  class PubChemGHSHit(BaseModel):
      """One GHS hazard statement parsed from a PubChem classification.

      Parameters
      ----------
      code : str
          GHS hazard statement code, e.g. ``"H225"``.
      description : str
          Human-readable description of the hazard.
      signal_word : str or None
          ``"Danger"``, ``"Warning"``, or ``None``.
      pictogram : str or None
          Pictogram identifier (``GHS01``–``GHS09``) or ``None``.
      """

      code: str
      description: str
      signal_word: str | None = None
      pictogram: str | None = None


  class PubChemLookupResult(BaseModel):
      """Normalized PubChem lookup result returned to the frontend.

      Parameters
      ----------
      cid : str
          PubChem compound ID as a string.
      name : str
          IUPAC name of the compound (preferred display name).
      cas : str or None
          First CAS-pattern synonym found in the synonym list, if any.
      molar_mass : float or None
          Molecular weight in g/mol.
      smiles : str or None
          Canonical SMILES notation.
      synonyms : list[str]
          Up to 20 synonyms (common names, trade names, CAS).
      ghs_codes : list[PubChemGHSHit]
          GHS hazard statements parsed from the PubChem classification.
      """

      cid: str
      name: str
      cas: str | None = None
      molar_mass: float | None = None
      smiles: str | None = None
      synonyms: list[str]
      ghs_codes: list[PubChemGHSHit]
  ```

- [ ] **Step 5: Create `src/chaima/services/pubchem.py`**

  ```python
  # src/chaima/services/pubchem.py
  """Async client for PubChem PUG REST.

  Exposes a single public ``lookup`` coroutine that resolves a name or CAS
  to a normalized ``PubChemLookupResult``. Errors are mapped to two domain
  exceptions — ``PubChemNotFound`` for 404 CID lookups and
  ``PubChemUpstreamError`` for everything else (non-2xx, timeouts, network).
  """
  from __future__ import annotations

  import logging
  import re
  from typing import Any
  from urllib.parse import quote

  import httpx

  from chaima.schemas.pubchem import PubChemGHSHit, PubChemLookupResult

  logger = logging.getLogger(__name__)

  _BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
  _PER_REQUEST_TIMEOUT = 8.0
  _TOTAL_TIMEOUT = 15.0
  _SYNONYM_CAP = 20
  _CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
  _HAZARD_CODE_RE = re.compile(r"^(H\d{3}|EUH\d{3})\b")


  class PubChemNotFound(Exception):
      """Raised when the initial CID lookup returns 404."""


  class PubChemUpstreamError(Exception):
      """Raised for non-404 PubChem failures (5xx, timeouts, network)."""


  async def lookup(query: str) -> PubChemLookupResult:
      """Resolve a name or CAS to a normalized PubChem result.

      Parameters
      ----------
      query : str
          Chemical name, synonym, or CAS number.

      Returns
      -------
      PubChemLookupResult
          Normalized result payload.

      Raises
      ------
      PubChemNotFound
          If PubChem does not recognize the query.
      PubChemUpstreamError
          For any other upstream failure (5xx, timeout, network).
      """
      q = query.strip()
      timeout = httpx.Timeout(_TOTAL_TIMEOUT, connect=_PER_REQUEST_TIMEOUT)

      async with httpx.AsyncClient(base_url=_BASE_URL, timeout=timeout) as client:
          cid = await _resolve_cid(client, q)
          props = await _fetch_properties(client, cid)
          synonyms = await _fetch_synonyms(client, cid)
          ghs_raw = await _fetch_ghs(client, cid)

      cas = _pick_cas(synonyms)
      return PubChemLookupResult(
          cid=str(cid),
          name=props.get("IUPACName") or q,
          cas=cas,
          molar_mass=_to_float(props.get("MolecularWeight")),
          smiles=props.get("CanonicalSMILES"),
          synonyms=synonyms[:_SYNONYM_CAP],
          ghs_codes=parse_ghs_classification(ghs_raw),
      )


  async def _resolve_cid(client: httpx.AsyncClient, query: str) -> int:
      path = f"/compound/name/{quote(query, safe='')}/cids/JSON"
      try:
          resp = await client.get(path)
      except (httpx.TimeoutException, httpx.TransportError) as exc:
          raise PubChemUpstreamError(str(exc)) from exc
      if resp.status_code == 404:
          raise PubChemNotFound(query)
      if resp.status_code >= 400:
          raise PubChemUpstreamError(f"CID lookup {resp.status_code}")
      data = resp.json()
      cids = (data.get("IdentifierList") or {}).get("CID") or []
      if not cids:
          raise PubChemNotFound(query)
      return int(cids[0])


  async def _fetch_properties(
      client: httpx.AsyncClient, cid: int
  ) -> dict[str, Any]:
      path = (
          f"/compound/cid/{cid}/property/"
          f"MolecularWeight,CanonicalSMILES,IUPACName/JSON"
      )
      try:
          resp = await client.get(path)
      except (httpx.TimeoutException, httpx.TransportError) as exc:
          raise PubChemUpstreamError(str(exc)) from exc
      if resp.status_code >= 400:
          raise PubChemUpstreamError(f"properties {resp.status_code}")
      data = resp.json()
      props_list = (data.get("PropertyTable") or {}).get("Properties") or []
      return props_list[0] if props_list else {}


  async def _fetch_synonyms(client: httpx.AsyncClient, cid: int) -> list[str]:
      path = f"/compound/cid/{cid}/synonyms/JSON"
      try:
          resp = await client.get(path)
      except (httpx.TimeoutException, httpx.TransportError) as exc:
          raise PubChemUpstreamError(str(exc)) from exc
      if resp.status_code >= 400:
          raise PubChemUpstreamError(f"synonyms {resp.status_code}")
      data = resp.json()
      info_list = (data.get("InformationList") or {}).get("Information") or []
      if not info_list:
          return []
      return list(info_list[0].get("Synonym") or [])


  async def _fetch_ghs(client: httpx.AsyncClient, cid: int) -> dict[str, Any]:
      path = f"/compound/cid/{cid}/classification/JSON"
      try:
          resp = await client.get(
              path, params={"classification_type": "ghs"}
          )
      except (httpx.TimeoutException, httpx.TransportError) as exc:
          raise PubChemUpstreamError(str(exc)) from exc
      # 404 here just means "no GHS data" — not fatal.
      if resp.status_code == 404:
          return {}
      if resp.status_code >= 400:
          raise PubChemUpstreamError(f"ghs {resp.status_code}")
      return resp.json()


  def _pick_cas(synonyms: list[str]) -> str | None:
      for syn in synonyms:
          if _CAS_RE.match(syn.strip()):
              return syn.strip()
      return None


  def _to_float(value: Any) -> float | None:
      if value is None:
          return None
      try:
          return float(value)
      except (TypeError, ValueError):
          return None


  def parse_ghs_classification(data: dict[str, Any]) -> list[PubChemGHSHit]:
      """Extract H-code hits from a PubChem GHS classification response.

      PubChem serializes GHS data as a flat ``Hierarchy.Node[]`` list where
      each node has an ``Information`` dict. Signal word and pictogram
      apply to the whole compound; hazard-statement nodes carry the code
      and description in one ``Description`` string shaped like
      ``"H225: Highly flammable liquid and vapour [Danger ...]"``.

      Parameters
      ----------
      data : dict
          The parsed JSON body from ``/classification/JSON``.

      Returns
      -------
      list[PubChemGHSHit]
          One hit per hazard statement. Empty list if the shape is
          missing, malformed, or has no hazard statements.
      """
      hierarchies = (data.get("Hierarchies") or {}).get("Hierarchy") or []
      if not hierarchies:
          return []

      signal_word: str | None = None
      pictogram: str | None = None
      hits: list[PubChemGHSHit] = []

      # A compound usually has one hierarchy; walk all to be safe.
      for hierarchy in hierarchies:
          nodes = hierarchy.get("Node") or []
          for node in nodes:
              info = node.get("Information") or {}
              name = info.get("Name")
              desc = info.get("Description") or ""
              if name == "Signal":
                  signal_word = desc.strip() or signal_word
              elif name == "Pictogram" and pictogram is None:
                  # Prefer the first pictogram code encountered.
                  match = re.search(r"GHS\d{2}", desc)
                  if match:
                      pictogram = match.group(0)
              elif name == "GHS Hazard Statements":
                  hits.append(_parse_hazard_statement(desc))

      # Back-fill per-statement signal word / pictogram from the compound
      # defaults when the hazard statement didn't carry its own.
      for h in hits:
          if h.signal_word is None:
              h.signal_word = signal_word
          if h.pictogram is None:
              h.pictogram = pictogram

      # Drop any entries where we couldn't parse a code.
      return [h for h in hits if h.code]


  def _parse_hazard_statement(text: str) -> PubChemGHSHit:
      """Parse one ``H-code: description [Signal ...]`` line."""
      code = ""
      description = text
      local_signal: str | None = None

      match = _HAZARD_CODE_RE.match(text)
      if match:
          code = match.group(1)
          remainder = text[match.end():].lstrip(": ").strip()
          # Split off a trailing "[Danger ...]" annotation if present.
          if "[" in remainder and remainder.endswith("]"):
              description, _, annotation = remainder.rpartition(" [")
              annotation = annotation.rstrip("]")
              if annotation.startswith("Danger"):
                  local_signal = "Danger"
              elif annotation.startswith("Warning"):
                  local_signal = "Warning"
          else:
              description = remainder

      return PubChemGHSHit(
          code=code,
          description=description,
          signal_word=local_signal,
          pictogram=None,
      )
  ```

- [ ] **Step 6: Run tests to verify they pass**

  Run: `uv run pytest tests/test_services/test_pubchem.py -v`
  Expected: all 8 tests PASS.

- [ ] **Step 7: Commit**

  ```bash
  git add src/chaima/schemas/pubchem.py src/chaima/services/pubchem.py tests/test_services/test_pubchem.py tests/test_services/fixtures/
  git commit -m "feat(pubchem): async PUG REST client + GHS parser"
  ```

---

## Task 5: PubChem router + wire into app

**Files:**
- Create: `src/chaima/routers/pubchem.py`
- Create: `tests/test_routers/test_pubchem.py`
- Modify: `src/chaima/app.py`

- [ ] **Step 1: Write the failing router test**

  Create `tests/test_routers/test_pubchem.py`:

  ```python
  # tests/test_routers/test_pubchem.py
  from unittest.mock import AsyncMock, patch

  from chaima.schemas.pubchem import PubChemGHSHit, PubChemLookupResult
  from chaima.services.pubchem import PubChemNotFound, PubChemUpstreamError


  _FAKE_RESULT = PubChemLookupResult(
      cid="180",
      name="propan-2-one",
      cas="67-64-1",
      molar_mass=58.08,
      smiles="CC(=O)C",
      synonyms=["Acetone", "67-64-1", "Dimethyl ketone"],
      ghs_codes=[
          PubChemGHSHit(
              code="H225",
              description="Highly flammable liquid and vapour",
              signal_word="Danger",
              pictogram="GHS02",
          )
      ],
  )


  async def test_lookup_endpoint_requires_auth(client):
      resp = await client.get("/api/v1/pubchem/lookup", params={"q": "acetone"})
      assert resp.status_code == 401


  async def test_lookup_endpoint_success(authed_client):
      with patch(
          "chaima.routers.pubchem.pubchem_service.lookup",
          new=AsyncMock(return_value=_FAKE_RESULT),
      ):
          resp = await authed_client.get(
              "/api/v1/pubchem/lookup", params={"q": "acetone"}
          )
      assert resp.status_code == 200
      body = resp.json()
      assert body["cid"] == "180"
      assert body["cas"] == "67-64-1"
      assert body["ghs_codes"][0]["code"] == "H225"


  async def test_lookup_endpoint_not_found(authed_client):
      with patch(
          "chaima.routers.pubchem.pubchem_service.lookup",
          new=AsyncMock(side_effect=PubChemNotFound("nope")),
      ):
          resp = await authed_client.get(
              "/api/v1/pubchem/lookup", params={"q": "nope"}
          )
      assert resp.status_code == 404


  async def test_lookup_endpoint_upstream_error(authed_client):
      with patch(
          "chaima.routers.pubchem.pubchem_service.lookup",
          new=AsyncMock(side_effect=PubChemUpstreamError("boom")),
      ):
          resp = await authed_client.get(
              "/api/v1/pubchem/lookup", params={"q": "acetone"}
          )
      assert resp.status_code == 502
  ```

  **Note:** this test assumes the existing `tests/conftest.py` provides `client` (unauthenticated) and `authed_client` (logged-in) fixtures matching the pattern used in other router tests. If the fixture names differ, adapt to match — check one existing router test (e.g. `tests/test_routers/test_chemicals.py`) for the actual names before committing.

- [ ] **Step 2: Run tests to verify they fail**

  Run: `uv run pytest tests/test_routers/test_pubchem.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'chaima.routers.pubchem'`.

- [ ] **Step 3: Create `src/chaima/routers/pubchem.py`**

  ```python
  # src/chaima/routers/pubchem.py
  """PubChem lookup endpoint.

  Wraps ``chaima.services.pubchem.lookup`` behind a simple authenticated
  GET. The response is public external data, so auth is only required to
  keep the endpoint from being used as an open proxy to PubChem.
  """
  from fastapi import APIRouter, Depends, HTTPException, Query

  from chaima.auth import fastapi_users
  from chaima.models.user import User
  from chaima.schemas.pubchem import PubChemLookupResult
  from chaima.services import pubchem as pubchem_service
  from chaima.services.pubchem import PubChemNotFound, PubChemUpstreamError

  router = APIRouter(prefix="/api/v1/pubchem", tags=["pubchem"])

  current_active_user = fastapi_users.current_user(active=True)


  @router.get("/lookup", response_model=PubChemLookupResult)
  async def lookup_pubchem(
      q: str = Query(..., min_length=1, max_length=200),
      user: User = Depends(current_active_user),
  ) -> PubChemLookupResult:
      """Resolve a chemical name or CAS number via PubChem PUG REST."""
      try:
          return await pubchem_service.lookup(q)
      except PubChemNotFound as exc:
          raise HTTPException(status_code=404, detail="No PubChem match") from exc
      except PubChemUpstreamError as exc:
          raise HTTPException(
              status_code=502, detail="PubChem unavailable"
          ) from exc
  ```

  **Note:** the exact import path for `current_active_user` / `fastapi_users` must match what other routers do. Open `src/chaima/routers/chemicals.py` and mirror that router's auth-dependency import style — adjust the two lines above if chemicals uses a different helper.

- [ ] **Step 4: Register the router in `src/chaima/app.py`**

  Add the import:

  ```python
  from chaima.routers.pubchem import router as pubchem_router
  ```

  Add the include call below `containers_router`:

  ```python
  app.include_router(pubchem_router)
  ```

- [ ] **Step 5: Run tests to verify they pass**

  Run: `uv run pytest tests/test_routers/test_pubchem.py -v`
  Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add src/chaima/routers/pubchem.py tests/test_routers/test_pubchem.py src/chaima/app.py
  git commit -m "feat(pubchem): GET /api/v1/pubchem/lookup endpoint"
  ```

---

## Task 6: Chemicals schema + service extension for synonyms and GHS codes

**Files:**
- Modify: `src/chaima/schemas/chemical.py`
- Modify: `src/chaima/services/chemicals.py`
- Modify: `src/chaima/routers/chemicals.py`
- Modify: `tests/test_services/test_chemicals.py`

- [ ] **Step 1: Write the failing service tests**

  Append to `tests/test_services/test_chemicals.py`:

  ```python
  from sqlalchemy.orm import selectinload
  from sqlmodel import select

  from chaima.models.chemical import Chemical
  from chaima.models.ghs import ChemicalGHS, GHSCode
  from chaima.services.seed import seed_ghs_catalog


  async def test_create_chemical_with_pubchem_payload(session, group, user):
      await seed_ghs_catalog(session)
      await session.commit()

      chem = await chemical_service.create_chemical(
          session,
          group_id=group.id,
          created_by=user.id,
          name="Acetone",
          cas="67-64-1",
          cid="180",
          smiles="CC(=O)C",
          molar_mass=58.08,
          structure_source="PUBCHEM",
          synonyms=["Propan-2-one", "Dimethyl ketone"],
          ghs_codes=["H225", "H319"],
      )
      await session.commit()

      loaded = (
          await session.exec(
              select(Chemical)
              .where(Chemical.id == chem.id)
              .options(
                  selectinload(Chemical.synonyms),
                  selectinload(Chemical.ghs_links).selectinload(
                      ChemicalGHS.ghs_code
                  ),
              )
          )
      ).first()
      assert loaded is not None
      assert loaded.cid == "180"
      assert loaded.molar_mass == 58.08
      names = {s.name for s in loaded.synonyms}
      assert "Propan-2-one" in names
      assert "Dimethyl ketone" in names
      linked_codes = {link.ghs_code.code for link in loaded.ghs_links}
      assert linked_codes == {"H225", "H319"}


  async def test_create_chemical_with_unknown_ghs_code_is_skipped(
      session, group, user, caplog
  ):
      await seed_ghs_catalog(session)
      await session.commit()

      with caplog.at_level("WARNING"):
          chem = await chemical_service.create_chemical(
              session,
              group_id=group.id,
              created_by=user.id,
              name="Mystery compound",
              ghs_codes=["H225", "H999"],
          )
          await session.commit()

      loaded = (
          await session.exec(
              select(Chemical)
              .where(Chemical.id == chem.id)
              .options(
                  selectinload(Chemical.ghs_links).selectinload(
                      ChemicalGHS.ghs_code
                  )
              )
          )
      ).first()
      assert loaded is not None
      linked = {link.ghs_code.code for link in loaded.ghs_links}
      assert linked == {"H225"}
      assert any("H999" in record.getMessage() for record in caplog.records)


  async def test_update_chemical_replaces_synonyms_and_ghs(session, group, user):
      await seed_ghs_catalog(session)
      await session.commit()

      chem = await chemical_service.create_chemical(
          session,
          group_id=group.id,
          created_by=user.id,
          name="Acetone",
          synonyms=["old-synonym"],
          ghs_codes=["H225"],
      )
      await session.commit()

      await chemical_service.update_chemical(
          session,
          chem,
          synonyms=["new-synonym-1", "new-synonym-2"],
          ghs_codes=["H319", "H336"],
      )
      await session.commit()

      loaded = (
          await session.exec(
              select(Chemical)
              .where(Chemical.id == chem.id)
              .options(
                  selectinload(Chemical.synonyms),
                  selectinload(Chemical.ghs_links).selectinload(
                      ChemicalGHS.ghs_code
                  ),
              )
          )
      ).first()
      assert loaded is not None
      assert {s.name for s in loaded.synonyms} == {
          "new-synonym-1",
          "new-synonym-2",
      }
      assert {link.ghs_code.code for link in loaded.ghs_links} == {
          "H319",
          "H336",
      }
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `uv run pytest tests/test_services/test_chemicals.py::test_create_chemical_with_pubchem_payload -v`
  Expected: FAIL with `TypeError: create_chemical() got an unexpected keyword argument 'synonyms'`.

- [ ] **Step 3: Extend `src/chaima/schemas/chemical.py`**

  Add `synonyms` and `ghs_codes` to both `ChemicalCreate` and `ChemicalUpdate` (just append these two fields to each class body):

  ```python
  synonyms: list[str] | None = None
  ghs_codes: list[str] | None = None
  ```

- [ ] **Step 4: Extend `src/chaima/services/chemicals.py`**

  Add near the top, next to the existing logger (or create one):

  ```python
  import logging

  logger = logging.getLogger(__name__)
  ```

  Add a private helper above `create_chemical`:

  ```python
  async def _resolve_ghs_codes_by_code(
      session: AsyncSession, codes: list[str]
  ) -> list[UUID]:
      """Map GHS code strings to existing GHSCode row IDs.

      Codes that aren't in the catalog are logged at WARNING level and
      skipped — they never trigger an upsert or an error.
      """
      if not codes:
          return []
      result = await session.exec(
          select(GHSCode).where(GHSCode.code.in_(codes))  # type: ignore[union-attr]
      )
      found = {row.code: row.id for row in result.all()}
      resolved: list[UUID] = []
      for code in codes:
          ghs_id = found.get(code)
          if ghs_id is None:
              logger.warning("unknown GHS code from upstream: %s", code)
              continue
          resolved.append(ghs_id)
      return resolved
  ```

  Extend `create_chemical`'s signature and body. Add two kwargs after `sds_path`:

  ```python
      synonyms: list[str] | None = None,
      ghs_codes: list[str] | None = None,
  ```

  At the bottom of `create_chemical`, **replace** the final `return chem` with:

  ```python
      if synonyms:
          await replace_synonyms(
              session, chem.id, [{"name": s, "category": None} for s in synonyms]
          )
      if ghs_codes:
          ghs_ids = await _resolve_ghs_codes_by_code(session, ghs_codes)
          if ghs_ids:
              await replace_ghs_codes(session, chem.id, ghs_ids)
      return chem
  ```

  Extend `update_chemical` the same way. Current signature is `update_chemical(session, chemical, **kwargs)`; change it so synonyms/ghs_codes are extracted from kwargs before the scalar-assignment loop:

  ```python
  async def update_chemical(
      session: AsyncSession,
      chemical: Chemical,
      **kwargs: object,
  ) -> Chemical:
      """Update chemical scalar fields and optionally replace synonyms / GHS codes.

      Parameters
      ----------
      session : AsyncSession
          The database session.
      chemical : Chemical
          The chemical instance to update.
      **kwargs : object
          Field name/value pairs to update. ``None`` values for scalar
          fields are skipped. The ``synonyms`` and ``ghs_codes`` keys are
          treated specially and trigger full-replace on the relation
          tables when present.
      """
      synonyms = kwargs.pop("synonyms", None)
      ghs_codes = kwargs.pop("ghs_codes", None)

      for key, value in kwargs.items():
          if value is not None:
              setattr(chemical, key, value)
      session.add(chemical)
      await session.flush()

      if synonyms is not None:
          await replace_synonyms(
              session,
              chemical.id,
              [{"name": s, "category": None} for s in synonyms],
          )
      if ghs_codes is not None:
          ghs_ids = await _resolve_ghs_codes_by_code(session, ghs_codes)
          await replace_ghs_codes(session, chemical.id, ghs_ids)

      return chemical
  ```

- [ ] **Step 5: Update the chemicals router to pass the new fields through**

  Open `src/chaima/routers/chemicals.py`. Find the POST handler that calls `chemical_service.create_chemical` and the PATCH handler that calls `chemical_service.update_chemical`. The existing handlers will look something like `create_chemical(session, ..., **payload.model_dump(exclude_unset=True))` or they may destructure fields explicitly.

  If the handler already uses `**payload.model_dump(exclude_unset=True)` style, **no code change is needed** — the new fields flow through automatically.

  If the handler destructures explicit kwargs, add `synonyms=payload.synonyms` and `ghs_codes=payload.ghs_codes` to the call site for both POST and PATCH.

  **Verification:** after editing, run `uv run pytest tests/test_routers/test_chemicals.py -v` and confirm nothing regressed.

- [ ] **Step 6: Run the new service tests**

  Run: `uv run pytest tests/test_services/test_chemicals.py -v`
  Expected: all tests PASS (the three new ones plus pre-existing tests).

- [ ] **Step 7: Run the full backend test suite**

  Run: `uv run pytest -v`
  Expected: every backend test passes.

- [ ] **Step 8: Commit**

  ```bash
  git add src/chaima/schemas/chemical.py src/chaima/services/chemicals.py src/chaima/routers/chemicals.py tests/test_services/test_chemicals.py
  git commit -m "feat(chemicals): accept synonyms and GHS codes on create/update"
  ```

---

## Task 7: Frontend types + `usePubChem` hook

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/api/hooks/usePubChem.ts`

- [ ] **Step 1: Add frontend types**

  Append to `frontend/src/types/index.ts`:

  ```ts
  export interface PubChemGHSHit {
    code: string;
    description: string;
    signal_word: string | null;
    pictogram: string | null;
  }

  export interface PubChemLookupResult {
    cid: string;
    name: string;
    cas: string | null;
    molar_mass: number | null;
    smiles: string | null;
    synonyms: string[];
    ghs_codes: PubChemGHSHit[];
  }
  ```

  Also extend whichever `ChemicalCreate` / `ChemicalUpdate` interface lives in this file to include the two optional fields:

  ```ts
  synonyms?: string[];
  ghs_codes?: string[];
  cid?: string | null;
  smiles?: string | null;
  molar_mass?: number | null;
  structure_source?: "NONE" | "PUBCHEM" | "UPLOADED";
  ```

  If any of those fields already exist in the current `ChemicalCreate`/`ChemicalUpdate`, don't duplicate them — just add the missing ones.

- [ ] **Step 2: Create the hook**

  Create `frontend/src/api/hooks/usePubChem.ts`:

  ```ts
  import { useMutation } from "@tanstack/react-query";
  import type { AxiosError } from "axios";
  import client from "../client";
  import type { PubChemLookupResult } from "../../types";

  export function usePubChemLookup() {
    return useMutation<PubChemLookupResult, AxiosError, string>({
      mutationFn: (q) =>
        client
          .get<PubChemLookupResult>("/pubchem/lookup", { params: { q } })
          .then((r) => r.data),
    });
  }
  ```

  **Note:** confirm the existing `client` import path matches other hooks in `frontend/src/api/hooks/` — if hooks use `"../client"` vs `"../../api/client"`, mirror what the majority use.

- [ ] **Step 3: Typecheck**

  Run: `cd frontend && npx tsc --noEmit`
  Expected: no errors.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/types/index.ts frontend/src/api/hooks/usePubChem.ts
  git commit -m "feat(frontend): PubChem lookup types and TanStack hook"
  ```

---

## Task 8: ChemicalForm — lookup bar, molar mass field, hidden extras

**Files:**
- Modify: `frontend/src/components/drawer/ChemicalForm.tsx`

- [ ] **Step 1: Rewrite `ChemicalForm.tsx`**

  Replace the full contents of `frontend/src/components/drawer/ChemicalForm.tsx`:

  ```tsx
  import {
    Button,
    Stack,
    TextField,
    FormControlLabel,
    Switch,
    Alert,
    Typography,
    CircularProgress,
    Box,
    IconButton,
    InputAdornment,
  } from "@mui/material";
  import CloseIcon from "@mui/icons-material/Close";
  import { useState, useEffect, type KeyboardEvent } from "react";
  import {
    useCreateChemical,
    useUpdateChemical,
    useChemicalDetail,
  } from "../../api/hooks/useChemicals";
  import { useCurrentUser } from "../../api/hooks/useAuth";
  import { usePubChemLookup } from "../../api/hooks/usePubChem";

  interface Props {
    chemicalId?: string;
    onDone: () => void;
  }

  interface FetchedExtras {
    cid: string | null;
    smiles: string | null;
    synonyms: string[];
    ghs_codes: string[];
    structure_source: "PUBCHEM" | "NONE";
  }

  const EMPTY_EXTRAS: FetchedExtras = {
    cid: null,
    smiles: null,
    synonyms: [],
    ghs_codes: [],
    structure_source: "NONE",
  };

  export function ChemicalForm({ chemicalId, onDone }: Props) {
    const { data: user } = useCurrentUser();
    const groupId = user?.main_group_id ?? "";
    const existing = useChemicalDetail(groupId, chemicalId ?? "");
    const create = useCreateChemical(groupId);
    const update = useUpdateChemical(groupId, chemicalId ?? "");
    const lookup = usePubChemLookup();

    const [name, setName] = useState("");
    const [cas, setCas] = useState("");
    const [molarMass, setMolarMass] = useState<string>("");
    const [comment, setComment] = useState("");
    const [isSecret, setIsSecret] = useState(false);

    const [query, setQuery] = useState("");
    const [extras, setExtras] = useState<FetchedExtras>(EMPTY_EXTRAS);
    const [lookupError, setLookupError] = useState<string | null>(null);

    useEffect(() => {
      if (existing.data) {
        const e = existing.data;
        setName(e.name);
        setCas(e.cas ?? "");
        setMolarMass(e.molar_mass != null ? String(e.molar_mass) : "");
        setComment(e.comment ?? "");
        setIsSecret(e.is_secret);
        setExtras({
          cid: e.cid ?? null,
          smiles: e.smiles ?? null,
          synonyms: (e.synonyms ?? []).map((s) => s.name),
          ghs_codes: (e.ghs_codes ?? []).map((g) => g.code),
          structure_source:
            e.structure_source === "PUBCHEM" ? "PUBCHEM" : "NONE",
        });
      }
    }, [existing.data]);

    if (chemicalId && existing.isLoading) {
      return (
        <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
          <CircularProgress size={20} />
        </Box>
      );
    }

    const saving = create.isPending || update.isPending;
    const err = create.error || update.error;

    const onFetch = async () => {
      const q = query.trim();
      if (!q) return;
      setLookupError(null);
      try {
        const result = await lookup.mutateAsync(q);
        setName(result.name);
        setCas(result.cas ?? "");
        setMolarMass(
          result.molar_mass != null ? String(result.molar_mass) : "",
        );
        setExtras({
          cid: result.cid,
          smiles: result.smiles,
          synonyms: result.synonyms,
          ghs_codes: result.ghs_codes.map((g) => g.code),
          structure_source: "PUBCHEM",
        });
      } catch (e) {
        const status =
          (e as { response?: { status?: number } })?.response?.status ?? 0;
        if (status === 404) {
          setLookupError("No PubChem match");
        } else {
          setLookupError("PubChem unavailable");
        }
      }
    };

    const onQueryKey = (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        void onFetch();
      }
    };

    const onClearLookup = () => {
      setQuery("");
      setExtras(EMPTY_EXTRAS);
      setLookupError(null);
    };

    const onSubmit = async () => {
      const parsedMolarMass = molarMass.trim() === "" ? null : Number(molarMass);
      const payload = {
        name: name.trim(),
        cas: cas.trim() || null,
        comment: comment.trim() || null,
        is_secret: isSecret,
        molar_mass: Number.isFinite(parsedMolarMass as number)
          ? (parsedMolarMass as number)
          : null,
        cid: extras.cid,
        smiles: extras.smiles,
        structure_source: extras.structure_source,
        synonyms: extras.synonyms,
        ghs_codes: extras.ghs_codes,
      };
      if (chemicalId) {
        await update.mutateAsync(payload);
      } else {
        await create.mutateAsync(payload);
      }
      onDone();
    };

    const fetched = extras.cid !== null;

    return (
      <Stack spacing={2}>
        {err instanceof Error && <Alert severity="error">{err.message}</Alert>}
        {lookupError && <Alert severity="warning">{lookupError}</Alert>}

        <Box
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            p: 1.5,
          }}
        >
          <Stack direction="row" spacing={1} alignItems="center">
            <TextField
              label="Lookup from PubChem"
              placeholder="Name or CAS"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onQueryKey}
              size="small"
              fullWidth
              InputProps={{
                endAdornment: fetched ? (
                  <InputAdornment position="end">
                    <IconButton
                      size="small"
                      onClick={onClearLookup}
                      aria-label="Clear PubChem lookup"
                    >
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ) : null,
              }}
            />
            <Button
              variant="outlined"
              onClick={() => void onFetch()}
              disabled={lookup.isPending || query.trim() === ""}
            >
              {lookup.isPending ? (
                <CircularProgress size={16} />
              ) : (
                "Fetch"
              )}
            </Button>
          </Stack>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ mt: 0.5, display: "block" }}
          >
            Fills name, CAS, molar mass and hazards from PubChem.
          </Typography>
          {fetched && (
            <Typography
              variant="caption"
              color="success.main"
              sx={{ mt: 0.5, display: "block" }}
            >
              ✓ Fetched from PubChem (CID {extras.cid})
            </Typography>
          )}
        </Box>

        <TextField
          label="Name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          size="small"
        />
        <TextField
          label="CAS number"
          value={cas}
          onChange={(e) => setCas(e.target.value)}
          size="small"
          helperText="Optional. Leave blank for internal materials."
        />
        <TextField
          label="Molar mass"
          value={molarMass}
          onChange={(e) => setMolarMass(e.target.value)}
          size="small"
          type="number"
          inputProps={{ step: "0.01", min: "0" }}
          InputProps={{
            endAdornment: <InputAdornment position="end">g/mol</InputAdornment>,
          }}
        />
        <TextField
          label="Comment"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          multiline
          minRows={2}
          size="small"
        />
        <FormControlLabel
          control={
            <Switch
              checked={isSecret}
              onChange={(_, v) => setIsSecret(v)}
            />
          }
          label={
            <Stack>
              <Typography variant="body2">Mark as secret</Typography>
              <Typography variant="caption" color="text.secondary">
                Only you and system admins will see this chemical.
              </Typography>
            </Stack>
          }
          sx={{ alignItems: "flex-start", m: 0 }}
        />

        <Stack
          direction="row"
          spacing={1}
          sx={{ justifyContent: "flex-end", mt: 2 }}
        >
          <Button onClick={onDone} disabled={saving}>
            Cancel
          </Button>
          <Button
            variant="contained"
            disabled={saving || !name.trim()}
            onClick={onSubmit}
          >
            {chemicalId ? "Save" : "Create"}
          </Button>
        </Stack>
      </Stack>
    );
  }
  ```

- [ ] **Step 2: Typecheck**

  Run: `cd frontend && npx tsc --noEmit`
  Expected: no errors.

- [ ] **Step 3: Smoke test in the browser**

  Start both servers (backend: `uv run uvicorn chaima.app:app --reload --port 8000`; frontend: `cd frontend && npm run dev`). Open the app, click **New chemical**, type `acetone` in the lookup bar, click **Fetch**. Verify:

  - Name becomes `propan-2-one`
  - CAS becomes `67-64-1`
  - Molar mass becomes `58.08`
  - The green `✓ Fetched from PubChem (CID 180)` caption appears
  - Clicking **Create** saves the chemical and the row appears in the list
  - Expanding the new chemical's row shows the synonyms and GHS codes that came from PubChem

  Also test: open an existing manually-created chemical → Edit → type a CAS in the lookup bar → Fetch → Save → expanded row shows the newly-attached synonyms and GHS.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/components/drawer/ChemicalForm.tsx
  git commit -m "feat(chemicals): PubChem lookup bar in ChemicalForm"
  ```

---

## Task 9: Playwright e2e test

**Files:**
- Create: `frontend/e2e/chemical-pubchem.spec.ts`

- [ ] **Step 1: Create the spec**

  Create `frontend/e2e/chemical-pubchem.spec.ts`:

  ```ts
  import { test, expect, type Page } from "@playwright/test";

  async function login(page: Page) {
    await page.goto("/login");
    await page.getByLabel("Email").fill("admin@chaima.dev");
    await page.getByLabel("Password").fill("changeme");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL("/", { timeout: 15_000 });
  }

  const FAKE_LOOKUP = {
    cid: "180",
    name: "propan-2-one",
    cas: "67-64-1",
    molar_mass: 58.08,
    smiles: "CC(=O)C",
    synonyms: ["Acetone", "67-64-1", "Dimethyl ketone"],
    ghs_codes: [
      {
        code: "H225",
        description: "Highly flammable liquid and vapour",
        signal_word: "Danger",
        pictogram: "GHS02",
      },
      {
        code: "H319",
        description: "Causes serious eye irritation",
        signal_word: "Warning",
        pictogram: "GHS07",
      },
    ],
  };

  test.describe("PubChem lookup", () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await page.goto("/");
    });

    test("happy path: fetch, fill, save", async ({ page }) => {
      await page.route("**/api/v1/pubchem/lookup*", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(FAKE_LOOKUP),
        });
      });

      await page.getByRole("button", { name: /new chemical/i }).click();
      const drawer = page.getByRole("dialog");
      await expect(drawer).toBeVisible();

      await drawer
        .getByLabel(/lookup from pubchem/i)
        .fill("e2e-fetch-acetone-" + Date.now());
      await drawer.getByRole("button", { name: /^fetch$/i }).click();

      await expect(drawer.getByLabel(/^name$/i)).toHaveValue("propan-2-one");
      await expect(drawer.getByLabel(/cas number/i)).toHaveValue("67-64-1");
      await expect(drawer.getByLabel(/molar mass/i)).toHaveValue("58.08");
      await expect(drawer.getByText(/fetched from pubchem/i)).toBeVisible();

      // Uniquify the saved name so the test is re-runnable against the same DB.
      const unique = "propan-2-one-e2e-" + Date.now();
      await drawer.getByLabel(/^name$/i).fill(unique);

      await drawer.getByRole("button", { name: /^create$/i }).click();
      await expect(drawer).toHaveCount(0);

      // The new chemical appears in the list.
      await expect(page.getByText(unique)).toBeVisible({ timeout: 10_000 });
    });

    test("upstream error: toast appears, fields untouched", async ({ page }) => {
      await page.route("**/api/v1/pubchem/lookup*", async (route) => {
        await route.fulfill({
          status: 502,
          contentType: "application/json",
          body: JSON.stringify({ detail: "PubChem unavailable" }),
        });
      });

      await page.getByRole("button", { name: /new chemical/i }).click();
      const drawer = page.getByRole("dialog");
      await expect(drawer).toBeVisible();

      await drawer.getByLabel(/^name$/i).fill("preserved-manual-name");
      await drawer.getByLabel(/lookup from pubchem/i).fill("acetone");
      await drawer.getByRole("button", { name: /^fetch$/i }).click();

      await expect(
        drawer.getByText(/pubchem unavailable/i),
      ).toBeVisible({ timeout: 5_000 });
      // Visible name field was not overwritten.
      await expect(drawer.getByLabel(/^name$/i)).toHaveValue(
        "preserved-manual-name",
      );

      // Close drawer to leave DB state clean (nothing was saved).
      await drawer.getByRole("button", { name: /cancel/i }).click();
      await expect(drawer).toHaveCount(0);
    });
  });
  ```

  **Note:** the "New chemical" button label and the drawer role may differ in the actual UI. Open `frontend/e2e/settings.spec.ts` and the chemicals list component to confirm exact selectors before running the test, and adjust `getByRole("button", { name: /new chemical/i })` / `getByRole("dialog")` as needed.

- [ ] **Step 2: Run Playwright**

  Make sure both backend and frontend dev servers are running. Then:

  Run: `cd frontend && npx playwright test chemical-pubchem.spec.ts -x`
  Expected: both tests PASS.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/e2e/chemical-pubchem.spec.ts
  git commit -m "test(e2e): PubChem lookup happy path and upstream error"
  ```

---

## Self-review

**Spec coverage — every requirement traces to a task:**

| Spec requirement                                                | Task |
|-----------------------------------------------------------------|------|
| `GET /pubchem/lookup?q=` endpoint                               | 5    |
| Auth: authenticated user, no group scoping                      | 5    |
| PubChem service wraps PUG REST                                  | 4    |
| Input normalization (name + CAS via name namespace)             | 4    |
| Properties fetch (molar mass, SMILES, IUPAC name)               | 4    |
| Synonyms capped at 20 + CAS extraction                          | 4    |
| GHS classification parser                                       | 4    |
| PubChemNotFound → 404, PubChemUpstreamError → 502               | 4, 5 |
| Timeouts (8s/15s)                                                | 4    |
| Idempotent GHS catalog seed                                     | 3    |
| Seed preserves hand-edited descriptions                         | 3    |
| Generic `run_seeds` mechanism called from lifespan              | 3    |
| ChemicalCreate/Update gain `synonyms`, `ghs_codes`              | 6    |
| Unknown GHS codes logged + skipped (not upserted, not fatal)    | 6    |
| httpx promoted to runtime dependency                            | 1    |
| `PubChemLookupResult` + `PubChemGHSHit` frontend types          | 7    |
| `usePubChemLookup` TanStack mutation hook                       | 7    |
| ChemicalForm: lookup bar + Fetch button                         | 8    |
| ChemicalForm: visible molar mass field                          | 8    |
| ChemicalForm: hidden extras state, always overwrite on fetch    | 8    |
| ChemicalForm: edit-mode seed from ChemicalDetail                | 8    |
| ChemicalForm: clear affordance                                  | 8    |
| ChemicalForm: ✓ CID caption                                     | 8    |
| Backend unit tests for service + parser                         | 4    |
| Backend router tests (auth, success, 404, 502)                  | 5    |
| Seed tests (insert all, idempotent, preserve edits)             | 3    |
| Chemicals service tests (pubchem payload, unknown GHS, update)  | 6    |
| Frontend e2e happy path + error path                            | 9    |

**Placeholder scan:** no TBDs, no "add error handling," no bare "similar to task N." Three tasks contain a "confirm the selector/import path matches the codebase" note (Task 5 for `current_active_user`, Task 7 for the axios client import, Task 9 for Playwright selectors) — those are conscious verification steps, not placeholders.

**Type consistency:** `PubChemLookupResult` uses the same field names and nullability on backend and frontend. `FetchedExtras` on the frontend uses `"PUBCHEM" | "NONE"` for `structure_source`, matching the backend `StructureSource` enum. `ghs_codes` is `list[str]` on the service boundary everywhere (the service resolves to UUIDs internally). Synonyms are `list[str]` from the service down; `replace_synonyms` expects `list[dict]`, and the service wraps the strings into `{"name": s, "category": None}` before calling it — consistent.

**No gaps found.**
