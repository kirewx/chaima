# Excel/CSV Import + Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a 5-step import wizard (admin-only) that ingests arbitrary Excel/CSV inventories into chaima, a symmetric CSV/XLSX export on the Chemicals page, and a PubChem enrichment admin action.

**Architecture:** Three phases that each leave main in a shippable state. Phase 1 adds `openpyxl`, the `Container.ordered_by_name` column, and the export flow. Phase 2 adds the import wizard — all state on the client, two stateless server endpoints (`/import/preview` and `/import/commit`). Phase 3 adds the PubChem enrichment action (streaming progress via `text/event-stream`).

**Tech Stack:** FastAPI + SQLModel + alembic (backend), pytest + pytest-asyncio (tests), React + MUI + TanStack Query + axios (frontend), openpyxl (xlsx parsing), Playwright (e2e).

**Spec:** `docs/superpowers/specs/2026-04-22-excel-import-export-design.md`

---

## Phase 1 — Groundwork + export

Adds the xlsx dependency, the one schema change, and the simpler of the two features (export). After Phase 1 you can download the chemical list as CSV or Excel.

### Task 1.1: Add `openpyxl` dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` (auto)

- [ ] **Step 1: Add openpyxl to dependencies**

Edit `pyproject.toml`, add to the `dependencies` array:

```toml
    "openpyxl>=3.1.5",
```

- [ ] **Step 2: Lock and install**

```bash
uv lock
uv sync
```

Expected: `uv.lock` updated; no errors.

- [ ] **Step 3: Smoke-import in REPL**

```bash
uv run python -c "import openpyxl; print(openpyxl.__version__)"
```

Expected: prints a version like `3.1.5`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add openpyxl for Excel import/export"
```

---

### Task 1.2: Add `Container.ordered_by_name` column (model + schemas)

**Files:**
- Modify: `src/chaima/models/container.py:15`
- Modify: `src/chaima/schemas/container.py`
- Test: `tests/test_models/test_container.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_models/test_container.py`:

```python
async def test_container_ordered_by_name_nullable(session, storage_location, chemical, user):
    from chaima.models.container import Container
    c = Container(
        chemical_id=chemical.id,
        location_id=storage_location.id,
        identifier="TEST-001",
        amount=1.0,
        unit="L",
        created_by=user.id,
        ordered_by_name="M. Schmidt",
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.ordered_by_name == "M. Schmidt"

    c2 = Container(
        chemical_id=chemical.id,
        location_id=storage_location.id,
        identifier="TEST-002",
        amount=1.0,
        unit="L",
        created_by=user.id,
    )
    session.add(c2)
    await session.commit()
    await session.refresh(c2)
    assert c2.ordered_by_name is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_models/test_container.py::test_container_ordered_by_name_nullable -v
```

Expected: FAIL — `ordered_by_name` is not a valid Container field.

- [ ] **Step 3: Add column to the model**

In `src/chaima/models/container.py`, after the `supplier_id` field (around line 15), add:

```python
    ordered_by_name: str | None = Field(default=None, index=True)
```

- [ ] **Step 4: Add field to schemas**

In `src/chaima/schemas/container.py`:

`ContainerCreate`: add after `purchased_at`:

```python
    ordered_by_name: str | None = None
```

`ContainerUpdate`: add after `purchased_at`:

```python
    ordered_by_name: str | None = None
```

`ContainerRead`: add after `purchased_at`:

```python
    ordered_by_name: str | None
```

Update the docstrings to mention the field.

- [ ] **Step 5: Run test**

```bash
uv run pytest tests/test_models/test_container.py::test_container_ordered_by_name_nullable -v
```

Expected: PASS.

- [ ] **Step 6: Run full test suite for regressions**

```bash
uv run pytest tests/ -q
```

Expected: all pass (number increases by 1).

- [ ] **Step 7: Commit**

```bash
git add src/chaima/models/container.py src/chaima/schemas/container.py tests/test_models/test_container.py
git commit -m "feat(container): add nullable ordered_by_name column"
```

---

### Task 1.3: Alembic migration for `ordered_by_name`

**Files:**
- Create: `alembic/versions/<rev>_add_container_ordered_by_name.py`

- [ ] **Step 1: Generate the migration**

```bash
uv run alembic revision --autogenerate -m "add container ordered_by_name"
```

Expected: a new file in `alembic/versions/`. Note the revision id in the filename.

- [ ] **Step 2: Inspect the migration**

Open the generated file. `upgrade()` should contain:

```python
op.add_column('container',
    sa.Column('ordered_by_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
op.create_index(op.f('ix_container_ordered_by_name'), 'container', ['ordered_by_name'], unique=False)
```

`downgrade()` should drop the index and column. If autogenerate missed anything, fill it in by hand (match the style of `49c7178e33a9_initial_schema.py`).

- [ ] **Step 3: Apply the migration locally**

```bash
uv run alembic upgrade head
```

Expected: no errors; `chaima.db` now has the new column.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/ -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/*_add_container_ordered_by_name.py
git commit -m "chore(alembic): add container.ordered_by_name column migration"
```

---

### Task 1.4: `services/export.py` — row building + CSV writer

**Files:**
- Create: `src/chaima/services/export.py`
- Create: `tests/test_services/test_export.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_export.py`:

```python
from io import StringIO, BytesIO
import csv

from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.storage import StorageLocation
from chaima.models.supplier import Supplier
from chaima.services import export as export_service


async def test_export_csv_one_row_per_container(session, group, user):
    loc = StorageLocation(name="Shelf A", kind="shelf")
    session.add(loc)
    sup = Supplier(name="Sigma", group_id=group.id)
    session.add(sup)
    chem = Chemical(name="Ethanol", cas="64-17-5", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.flush()
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id, supplier_id=sup.id,
        created_by=user.id, identifier="E-001", amount=1.0, unit="L",
        ordered_by_name="M. Schmidt",
    ))
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id,
        created_by=user.id, identifier="E-002", amount=0.5, unit="L",
    ))
    await session.commit()

    data = await export_service.export_chemicals(session, group.id, filters={}, fmt="csv")
    reader = csv.reader(StringIO(data.decode("utf-8")))
    rows = list(reader)
    header = rows[0]
    body = rows[1:]

    assert header[:7] == ["name", "cas", "smiles", "location", "identifier", "quantity", "unit"]
    assert len(body) == 2
    e001 = next(r for r in body if r[4] == "E-001")
    assert e001[0] == "Ethanol"
    assert e001[1] == "64-17-5"
    assert e001[3] == "Shelf A"
    assert e001[5] == "1.0"
    assert e001[6] == "L"
    assert "M. Schmidt" in e001  # ordered_by column
    assert "Sigma" in e001        # supplier column


async def test_export_includes_chemical_without_containers(session, group, user):
    chem = Chemical(name="Isolated", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()

    data = await export_service.export_chemicals(session, group.id, filters={}, fmt="csv")
    reader = csv.reader(StringIO(data.decode("utf-8")))
    rows = list(reader)
    body = rows[1:]
    assert len(body) == 1
    assert body[0][0] == "Isolated"
    assert body[0][4] == ""  # identifier empty
    assert body[0][5] == ""  # quantity empty
```

- [ ] **Step 2: Run to see it fail**

```bash
uv run pytest tests/test_services/test_export.py -v
```

Expected: FAIL — `chaima.services.export` module does not exist.

- [ ] **Step 3: Implement `export_chemicals` (csv path)**

Create `src/chaima/services/export.py`:

```python
# src/chaima/services/export.py
import csv
from io import BytesIO, StringIO
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical
from chaima.models.chemical_ghs import ChemicalGHS
from chaima.models.chemical_hazard_tag import ChemicalHazardTag
from chaima.models.container import Container


EXPORT_COLUMNS = [
    "name", "cas", "smiles", "location", "identifier", "quantity", "unit",
    "purity", "ordered_by", "supplier", "purchased_at", "comment",
    "ghs_codes", "hazard_tags", "is_archived",
]

EXPORT_ROW_CAP = 10_000


class ExportTooLargeError(Exception):
    """Raised when the filtered export would exceed EXPORT_ROW_CAP."""


async def _load_chemicals_with_containers(
    session: AsyncSession, group_id: UUID, filters: dict[str, Any]
) -> list[Chemical]:
    stmt = (
        select(Chemical)
        .where(Chemical.group_id == group_id)
        .options(
            selectinload(Chemical.containers).selectinload(Container.location),
            selectinload(Chemical.containers).selectinload(Container.supplier),
            selectinload(Chemical.ghs_links).selectinload(ChemicalGHS.ghs_code),
            selectinload(Chemical.hazard_tag_links).selectinload(ChemicalHazardTag.hazard_tag),
        )
        .order_by(Chemical.name)
    )
    # TODO: apply filters (has_containers, location_id, my_secrets, ...) in a later task
    result = await session.exec(stmt)
    return list(result.all())


def _row_for_container(chem: Chemical, container: Container | None) -> list[str]:
    ghs = ";".join(sorted(link.ghs_code.code for link in chem.ghs_links))
    tags = ";".join(sorted(link.hazard_tag.name for link in chem.hazard_tag_links))
    if container is None:
        return [
            chem.name, chem.cas or "", chem.smiles or "",
            "", "", "", "", "", "", "", "", chem.comment or "",
            ghs, tags, str(chem.is_archived),
        ]
    return [
        chem.name, chem.cas or "", chem.smiles or "",
        container.location.name if container.location else "",
        container.identifier,
        str(container.amount),
        container.unit,
        container.purity or "",
        container.ordered_by_name or "",
        container.supplier.name if container.supplier else "",
        container.purchased_at.isoformat() if container.purchased_at else "",
        chem.comment or "",
        ghs, tags, str(container.is_archived),
    ]


def _build_rows(chemicals: list[Chemical]) -> list[list[str]]:
    rows: list[list[str]] = []
    for chem in chemicals:
        if not chem.containers:
            rows.append(_row_for_container(chem, None))
        else:
            for container in chem.containers:
                rows.append(_row_for_container(chem, container))
    return rows


async def export_chemicals(
    session: AsyncSession,
    group_id: UUID,
    *,
    filters: dict[str, Any],
    fmt: Literal["csv", "xlsx"],
) -> bytes:
    chemicals = await _load_chemicals_with_containers(session, group_id, filters)
    rows = _build_rows(chemicals)
    if len(rows) > EXPORT_ROW_CAP:
        raise ExportTooLargeError(
            f"Export would produce {len(rows)} rows (cap: {EXPORT_ROW_CAP}). Narrow the filter."
        )

    if fmt == "csv":
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(EXPORT_COLUMNS)
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    if fmt == "xlsx":
        return _to_xlsx(rows)

    raise ValueError(f"Unsupported format: {fmt}")


def _to_xlsx(rows: list[list[str]]) -> bytes:
    # Implemented in Task 1.5
    raise NotImplementedError
```

- [ ] **Step 4: Run the csv tests**

```bash
uv run pytest tests/test_services/test_export.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/export.py tests/test_services/test_export.py
git commit -m "feat(export): chemicals CSV export service with one row per container"
```

---

### Task 1.5: XLSX writer + filter support

**Files:**
- Modify: `src/chaima/services/export.py`
- Modify: `tests/test_services/test_export.py`

- [ ] **Step 1: Add filter + xlsx tests**

Append to `tests/test_services/test_export.py`:

```python
from openpyxl import load_workbook


async def test_export_xlsx_round_trip(session, group, user):
    loc = StorageLocation(name="Shelf A", kind="shelf")
    session.add(loc)
    chem = Chemical(name="Ethanol", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.flush()
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id, created_by=user.id,
        identifier="E-001", amount=1.0, unit="L",
    ))
    await session.commit()

    data = await export_service.export_chemicals(session, group.id, filters={}, fmt="xlsx")
    wb = load_workbook(BytesIO(data))
    ws = wb.active
    header = [cell.value for cell in ws[1]]
    assert header[:5] == ["name", "cas", "smiles", "location", "identifier"]
    assert ws.cell(row=2, column=1).value == "Ethanol"


async def test_export_respects_location_filter(session, group, user):
    loc_a = StorageLocation(name="Shelf A", kind="shelf")
    loc_b = StorageLocation(name="Shelf B", kind="shelf")
    session.add(loc_a)
    session.add(loc_b)
    chem_a = Chemical(name="OnA", group_id=group.id, created_by=user.id)
    chem_b = Chemical(name="OnB", group_id=group.id, created_by=user.id)
    session.add(chem_a)
    session.add(chem_b)
    await session.flush()
    session.add(Container(chemical_id=chem_a.id, location_id=loc_a.id,
                          created_by=user.id, identifier="A-1", amount=1, unit="L"))
    session.add(Container(chemical_id=chem_b.id, location_id=loc_b.id,
                          created_by=user.id, identifier="B-1", amount=1, unit="L"))
    await session.commit()

    data = await export_service.export_chemicals(
        session, group.id, filters={"location_id": loc_a.id}, fmt="csv"
    )
    reader = csv.reader(StringIO(data.decode("utf-8")))
    body = list(reader)[1:]
    names = {r[0] for r in body}
    assert names == {"OnA"}


async def test_export_too_large_raises(session, group, user, monkeypatch):
    monkeypatch.setattr(export_service, "EXPORT_ROW_CAP", 1)
    chem = Chemical(name="A", group_id=group.id, created_by=user.id)
    chem2 = Chemical(name="B", group_id=group.id, created_by=user.id)
    session.add(chem)
    session.add(chem2)
    await session.commit()
    import pytest
    with pytest.raises(export_service.ExportTooLargeError):
        await export_service.export_chemicals(session, group.id, filters={}, fmt="csv")
```

- [ ] **Step 2: Run to see failure**

```bash
uv run pytest tests/test_services/test_export.py -v
```

Expected: xlsx test fails with `NotImplementedError`, filter test passes or fails depending on implementation (likely passes since filter is missing and returns everything, but `OnB` appears when only `OnA` should). Too-large test passes.

- [ ] **Step 3: Implement `_to_xlsx`**

Replace the `_to_xlsx` stub in `src/chaima/services/export.py`:

```python
def _to_xlsx(rows: list[list[str]]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Chemicals"
    ws.append(EXPORT_COLUMNS)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: Implement filter support**

Replace `_load_chemicals_with_containers` body — apply the same filters as `services/chemicals.list_chemicals`, reusing its logic. In `src/chaima/services/export.py`:

```python
from chaima.services.chemicals import list_chemicals as list_chemicals_service
```

Then:

```python
async def _load_chemicals_with_containers(
    session: AsyncSession, group_id: UUID, filters: dict[str, Any], viewer_id: UUID
) -> list[Chemical]:
    # Delegate filtering to the canonical list endpoint with limit high enough
    # to hit the row cap before anything else. Then eager-load relationships.
    from chaima.models.user import User
    viewer = await session.get(User, viewer_id)
    items, _ = await list_chemicals_service(
        session,
        group_id,
        viewer=viewer,
        search=filters.get("search"),
        hazard_tag_id=filters.get("hazard_tag_id"),
        ghs_code_id=filters.get("ghs_code_id"),
        has_containers=filters.get("has_containers"),
        my_secrets=filters.get("my_secrets", False),
        location_id=filters.get("location_id"),
        include_archived=filters.get("include_archived", False),
        sort="name",
        order="asc",
        offset=0,
        limit=EXPORT_ROW_CAP + 1,
    )
    # Re-fetch with eager loading (list_chemicals returns bare Chemical rows)
    ids = [c.id for c in items]
    if not ids:
        return []
    stmt = (
        select(Chemical)
        .where(Chemical.id.in_(ids))
        .options(
            selectinload(Chemical.containers).selectinload(Container.location),
            selectinload(Chemical.containers).selectinload(Container.supplier),
            selectinload(Chemical.ghs_links).selectinload(ChemicalGHS.ghs_code),
            selectinload(Chemical.hazard_tag_links).selectinload(ChemicalHazardTag.hazard_tag),
        )
        .order_by(Chemical.name)
    )
    result = await session.exec(stmt)
    return list(result.all())
```

Update `export_chemicals` signature to accept `viewer_id`:

```python
async def export_chemicals(
    session: AsyncSession,
    group_id: UUID,
    *,
    viewer_id: UUID,
    filters: dict[str, Any],
    fmt: Literal["csv", "xlsx"],
) -> bytes:
```

Pass `viewer_id` down and fix all existing tests to pass `viewer_id=user.id`.

- [ ] **Step 5: Run all export tests**

```bash
uv run pytest tests/test_services/test_export.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/chaima/services/export.py tests/test_services/test_export.py
git commit -m "feat(export): xlsx output + filter parity with list endpoint"
```

---

### Task 1.6: Export router endpoint

**Files:**
- Modify: `src/chaima/routers/chemicals.py`
- Create: `tests/test_api/test_export.py`

- [ ] **Step 1: Write the failing API test**

Create `tests/test_api/test_export.py`:

```python
from io import BytesIO, StringIO
import csv
from openpyxl import load_workbook

from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.storage import StorageLocation


async def test_export_csv_happy_path(client, session, group, user, membership):
    loc = StorageLocation(name="Shelf A", kind="shelf")
    session.add(loc)
    chem = Chemical(name="Ethanol", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.flush()
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id, created_by=user.id,
        identifier="E-001", amount=1.0, unit="L",
    ))
    await session.commit()

    resp = await client.get(
        f"/api/v1/groups/{group.id}/chemicals/export?format=csv"
    )
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["content-disposition"].endswith(".csv\"")
    rows = list(csv.reader(StringIO(resp.text)))
    assert rows[0][0] == "name"
    assert rows[1][0] == "Ethanol"


async def test_export_xlsx_happy_path(client, session, group, user, membership):
    chem = Chemical(name="Ethanol", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()

    resp = await client.get(
        f"/api/v1/groups/{group.id}/chemicals/export?format=xlsx"
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    wb = load_workbook(BytesIO(resp.content))
    ws = wb.active
    assert ws.cell(row=1, column=1).value == "name"
    assert ws.cell(row=2, column=1).value == "Ethanol"


async def test_export_unknown_format_400(client, group, membership):
    resp = await client.get(
        f"/api/v1/groups/{group.id}/chemicals/export?format=pdf"
    )
    assert resp.status_code == 422  # pydantic Literal validator


async def test_export_respects_has_containers_filter(client, session, group, user, membership):
    loc = StorageLocation(name="Shelf A", kind="shelf")
    session.add(loc)
    chem_empty = Chemical(name="Empty", group_id=group.id, created_by=user.id)
    chem_full = Chemical(name="Full", group_id=group.id, created_by=user.id)
    session.add(chem_empty)
    session.add(chem_full)
    await session.flush()
    session.add(Container(
        chemical_id=chem_full.id, location_id=loc.id, created_by=user.id,
        identifier="F-1", amount=1, unit="L",
    ))
    await session.commit()

    resp = await client.get(
        f"/api/v1/groups/{group.id}/chemicals/export?format=csv&has_containers=true"
    )
    rows = list(csv.reader(StringIO(resp.text)))
    names = {r[0] for r in rows[1:]}
    assert names == {"Full"}


async def test_export_not_member_403(client, group):
    resp = await client.get(
        f"/api/v1/groups/{group.id}/chemicals/export?format=csv"
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_api/test_export.py -v
```

Expected: all fail (endpoint doesn't exist → 404).

- [ ] **Step 3: Add the endpoint to `routers/chemicals.py`**

In `src/chaima/routers/chemicals.py`, imports — add:

```python
from datetime import date
from typing import Literal
from fastapi.responses import Response
from chaima.services import export as export_service
```

Add a new route near the top (above the catch-all `/{chemical_id}` path routes). **Placement matters**: `@router.get("/export")` must be declared before `@router.get("/{chemical_id}")` in the file, otherwise FastAPI will match `export` as a `chemical_id` UUID (it'll then fail parsing, but better to avoid even trying).

```python
@router.get("/export")
async def export_chemicals_endpoint(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    user: CurrentUserDep,
    format: Literal["csv", "xlsx"] = Query("csv"),
    search: str | None = Query(None),
    hazard_tag_id: UUID | None = Query(None),
    ghs_code_id: UUID | None = Query(None),
    has_containers: bool | None = Query(None),
    my_secrets: bool = Query(False),
    location_id: UUID | None = Query(None),
    include_archived: bool = Query(False),
) -> Response:
    _group, _link = member
    try:
        data = await export_service.export_chemicals(
            session,
            group_id,
            viewer_id=user.id,
            filters={
                "search": search,
                "hazard_tag_id": hazard_tag_id,
                "ghs_code_id": ghs_code_id,
                "has_containers": has_containers,
                "my_secrets": my_secrets,
                "location_id": location_id,
                "include_archived": include_archived,
            },
            fmt=format,
        )
    except export_service.ExportTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        )

    media_type = (
        "text/csv"
        if format == "csv"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    group_slug = _group.name.lower().replace(" ", "-") or "group"
    filename = f"chaima-{group_slug}-{date.today().isoformat()}.{format}"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: Run API tests**

```bash
uv run pytest tests/test_api/test_export.py -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Run full suite for regressions**

```bash
uv run pytest tests/ -q
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/chaima/routers/chemicals.py tests/test_api/test_export.py
git commit -m "feat(chemicals): GET /export endpoint (CSV + XLSX)"
```

---

### Task 1.7: Frontend — `ExportButton` component

**Files:**
- Create: `frontend/src/components/chemicals/ExportButton.tsx`
- Modify: `frontend/src/pages/ChemicalsPage.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/chemicals/ExportButton.tsx`:

```tsx
import { useState } from "react";
import { Button, Menu, MenuItem } from "@mui/material";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import client from "../../api/client";
import type { ChemicalSearchParams } from "../../types";

interface Props {
  groupId: string;
  params: ChemicalSearchParams;
  includeArchived: boolean;
}

export function ExportButton({ groupId, params, includeArchived }: Props) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [busy, setBusy] = useState(false);

  const download = async (fmt: "csv" | "xlsx") => {
    setAnchor(null);
    setBusy(true);
    try {
      const resp = await client.get(
        `/groups/${groupId}/chemicals/export`,
        {
          params: { ...params, include_archived: includeArchived, format: fmt },
          responseType: "blob",
        },
      );
      const cd = resp.headers["content-disposition"] as string | undefined;
      const match = cd?.match(/filename="([^"]+)"/);
      const filename = match?.[1] ?? `chaima-export.${fmt}`;
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button
        variant="outlined"
        size="small"
        startIcon={<FileDownloadIcon />}
        disabled={busy}
        onClick={(e) => setAnchor(e.currentTarget)}
      >
        Export
      </Button>
      <Menu
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
      >
        <MenuItem onClick={() => download("csv")}>CSV</MenuItem>
        <MenuItem onClick={() => download("xlsx")}>Excel</MenuItem>
      </Menu>
    </>
  );
}
```

- [ ] **Step 2: Wire the button into `ChemicalsPage`**

In `frontend/src/pages/ChemicalsPage.tsx`, add the import near the top:

```tsx
import { ExportButton } from "../components/chemicals/ExportButton";
```

In the header `Stack` (right next to the "New" button — around the existing `<Button ... onClick={() => drawer.open({ kind: "chemical-new" })}>`), add:

```tsx
<ExportButton
  groupId={groupId}
  params={searchParams}
  includeArchived={filters.includeArchived}
/>
```

Place it after the "New" button but before the filter `IconButton`.

- [ ] **Step 3: Typecheck**

```bash
cd frontend
npx tsc --noEmit
```

Expected: EXIT 0.

- [ ] **Step 4: Manual test**

Start backend + frontend, log in, open the Chemicals page, click Export → CSV. Verify: a `chaima-<group>-<date>.csv` downloads and contains your chemicals. Repeat for Excel.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chemicals/ExportButton.tsx frontend/src/pages/ChemicalsPage.tsx
git commit -m "feat(ui): export button on chemicals page (CSV + Excel)"
```

---

## Phase 2 — Import wizard

This is the bulk of the work. Backend first (service functions → router), then frontend wizard (one step per component), then e2e.

### Task 2.1: `split_quantity_unit` helper

**Files:**
- Create: `src/chaima/services/import_.py`
- Create: `tests/test_services/test_import.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_services/test_import.py`:

```python
import pytest

from chaima.services import import_ as import_service


@pytest.mark.parametrize("input_str,expected", [
    ("250 mL", (250.0, "mL")),
    ("1,5 L", (1.5, "L")),
    ("1.5 L", (1.5, "L")),
    ("5", (5.0, None)),
    ("0.1 µmol", (0.1, "µmol")),
    ("100g", (100.0, "g")),
    ("", (None, None)),
    ("some text", (None, None)),
    ("abc 5 def", (None, None)),
])
def test_split_quantity_unit(input_str, expected):
    assert import_service.split_quantity_unit(input_str) == expected
```

- [ ] **Step 2: Run — confirm failure**

```bash
uv run pytest tests/test_services/test_import.py -v
```

Expected: module not found.

- [ ] **Step 3: Create `services/import_.py` with the helper**

Create `src/chaima/services/import_.py`:

```python
# src/chaima/services/import_.py
# trailing underscore: `import` is a reserved word
import re

_QU_RE = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*([a-zA-ZµμÅ%°]+)?\s*$")


def split_quantity_unit(s: str) -> tuple[float | None, str | None]:
    """Split a cell like '250 mL' into (250.0, 'mL').

    Returns (None, None) if the input does not parse cleanly.
    Accepts either ',' or '.' as decimal separator. Unit is optional.
    """
    if not s:
        return (None, None)
    m = _QU_RE.match(s)
    if m is None:
        return (None, None)
    qty_str = m.group(1).replace(",", ".")
    try:
        qty = float(qty_str)
    except ValueError:
        return (None, None)
    unit = m.group(2)
    return (qty, unit)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_services/test_import.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/import_.py tests/test_services/test_import.py
git commit -m "feat(import): split_quantity_unit helper"
```

---

### Task 2.2: Header detection heuristic

**Files:**
- Modify: `src/chaima/services/import_.py`
- Modify: `tests/test_services/test_import.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_services/test_import.py`:

```python
def test_detect_header_mapping_english():
    cols = ["Name", "CAS", "Location", "Quantity", "Unit", "Supplier"]
    m = import_service.detect_header_mapping(cols)
    assert m == {
        "Name": "name",
        "CAS": "cas",
        "Location": "location_text",
        "Quantity": "quantity",
        "Unit": "unit",
        "Supplier": "ordered_by",  # NOTE: map "Supplier" column → ordered_by? No — see step 3
    }


def test_detect_header_mapping_german():
    cols = ["Name", "CAS-Nr.", "Standort", "Menge", "Einheit", "Lieferant", "Bestellt von"]
    m = import_service.detect_header_mapping(cols)
    assert m["Name"] == "name"
    assert m["CAS-Nr."] == "cas"
    assert m["Standort"] == "location_text"
    assert m["Menge"] == "quantity"
    assert m["Einheit"] == "unit"
    assert m["Bestellt von"] == "ordered_by"


def test_detect_header_mapping_unknown_column():
    cols = ["Flibbertigibbet"]
    assert import_service.detect_header_mapping(cols) == {"Flibbertigibbet": "ignore"}


def test_detect_header_mapping_combined_qu():
    cols = ["Name", "Menge (mit Einheit)"]
    m = import_service.detect_header_mapping(cols)
    assert m["Menge (mit Einheit)"] == "quantity_unit_combined"
```

**Correction for test_detect_header_mapping_english:** "Supplier" isn't `ordered_by`; remove that expectation. Replace the first test with:

```python
def test_detect_header_mapping_english():
    cols = ["Name", "CAS", "Location", "Quantity", "Unit", "Purity"]
    m = import_service.detect_header_mapping(cols)
    assert m == {
        "Name": "name",
        "CAS": "cas",
        "Location": "location_text",
        "Quantity": "quantity",
        "Unit": "unit",
        "Purity": "purity",
    }
```

- [ ] **Step 2: Run to see failure**

```bash
uv run pytest tests/test_services/test_import.py -v -k detect_header
```

Expected: FAIL — function not defined.

- [ ] **Step 3: Implement `detect_header_mapping`**

Append to `src/chaima/services/import_.py`:

```python
# Known header patterns: lowercase substring → target field.
# Order matters (first match wins). More specific patterns go first.
_HEADER_PATTERNS: list[tuple[str, str]] = [
    ("cas", "cas"),
    ("mit einheit", "quantity_unit_combined"),
    ("with unit", "quantity_unit_combined"),
    ("menge", "quantity"),
    ("quantity", "quantity"),
    ("amount", "quantity"),
    ("einheit", "unit"),
    ("unit", "unit"),
    ("standort", "location_text"),
    ("location", "location_text"),
    ("lagerort", "location_text"),
    ("reinheit", "purity"),
    ("purity", "purity"),
    ("bestellt von", "ordered_by"),
    ("ordered by", "ordered_by"),
    ("besteller", "ordered_by"),
    ("erstellt von", "created_by_name"),
    ("created by", "created_by_name"),
    ("label", "identifier"),
    ("behälter", "identifier"),
    ("identifier", "identifier"),
    ("bemerkung", "comment"),
    ("kommentar", "comment"),
    ("comment", "comment"),
    ("notes", "comment"),
    ("kaufdatum", "purchased_at"),
    ("gekauft", "purchased_at"),
    ("purchased", "purchased_at"),
    ("bought", "purchased_at"),
    ("name", "name"),
]


def detect_header_mapping(columns: list[str]) -> dict[str, str]:
    """Guess a target field for each source column header. Unknown → 'ignore'."""
    result: dict[str, str] = {}
    for col in columns:
        lower = col.strip().lower()
        chosen: str | None = None
        for pattern, target in _HEADER_PATTERNS:
            if pattern in lower:
                chosen = target
                break
        result[col] = chosen or "ignore"
    return result
```

- [ ] **Step 4: Run header tests**

```bash
uv run pytest tests/test_services/test_import.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/import_.py tests/test_services/test_import.py
git commit -m "feat(import): detect_header_mapping heuristic (EN+DE)"
```

---

### Task 2.3: File parsing — xlsx + csv → Grid

**Files:**
- Modify: `src/chaima/services/import_.py`
- Modify: `tests/test_services/test_import.py`
- Create: `tests/fixtures/import_sample.xlsx`
- Create: `tests/fixtures/import_sample.csv`

- [ ] **Step 1: Create fixtures**

Run this one-time script (save as `scripts/make_import_fixture.py`, run it, then delete the script — only the fixtures are committed):

```python
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = "Inventory"
ws.append(["Name", "CAS-Nr.", "Standort", "Menge (mit Einheit)", "Behälter", "Bestellt von"])
ws.append(["Ethanol", "64-17-5", "fridge 0.728", "1 L", "E-001", "M. Schmidt"])
ws.append(["Ethanol", "64-17-5", "Fridge 0.728", "500 mL", "", "A. Müller"])  # dup location spelling, missing id
ws.append(["Acetone", "67-64-1", "cabinet XA", "2.5 L", "AC-01", ""])
ws.append(["Toluene", "", "argon glovebox", "junk text", "T-1", ""])  # unparseable qty
wb.save("tests/fixtures/import_sample.xlsx")

with open("tests/fixtures/import_sample.csv", "w", encoding="utf-8") as f:
    f.write("Name,CAS,Location,Quantity,Unit\n")
    f.write("Ethanol,64-17-5,Shelf A,1,L\n")
    f.write("Acetone,67-64-1,Shelf B,500,mL\n")
```

```bash
uv run python scripts/make_import_fixture.py
rm scripts/make_import_fixture.py  # do not commit
```

Verify the files exist:
```bash
ls tests/fixtures/import_sample.*
```

- [ ] **Step 2: Write parsing tests**

Append to `tests/test_services/test_import.py`:

```python
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def test_parse_xlsx():
    with (FIXTURE_DIR / "import_sample.xlsx").open("rb") as f:
        grid = import_service.parse_upload(f.read(), "xlsx")
    assert grid.columns[:3] == ["Name", "CAS-Nr.", "Standort"]
    assert grid.row_count == 4
    # Header row not in rows; rows[0] is first data row
    assert grid.rows[0][0] == "Ethanol"
    assert grid.sheets == ["Inventory"]


def test_parse_csv():
    with (FIXTURE_DIR / "import_sample.csv").open("rb") as f:
        grid = import_service.parse_upload(f.read(), "csv")
    assert grid.columns == ["Name", "CAS", "Location", "Quantity", "Unit"]
    assert grid.row_count == 2
    assert grid.rows[0][0] == "Ethanol"
    assert grid.sheets is None


def test_parse_xlsx_pick_sheet():
    # Single-sheet fixture; verify sheet_name argument works
    with (FIXTURE_DIR / "import_sample.xlsx").open("rb") as f:
        grid = import_service.parse_upload(f.read(), "xlsx", sheet_name="Inventory")
    assert grid.row_count == 4


def test_parse_xlsx_missing_sheet_raises():
    with (FIXTURE_DIR / "import_sample.xlsx").open("rb") as f:
        import pytest
        with pytest.raises(ValueError, match="Sheet 'NoSuchSheet' not found"):
            import_service.parse_upload(f.read(), "xlsx", sheet_name="NoSuchSheet")
```

- [ ] **Step 3: Run — fail**

```bash
uv run pytest tests/test_services/test_import.py -v -k parse
```

Expected: FAIL — `parse_upload` and `Grid` not defined.

- [ ] **Step 4: Implement parsing**

Append to `src/chaima/services/import_.py`:

```python
import csv as csv_module
from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import Literal


@dataclass
class Grid:
    columns: list[str]
    rows: list[list[str]]     # all rows (not just preview)
    row_count: int
    sheets: list[str] | None  # None for csv; list of sheet names for xlsx


def parse_upload(
    data: bytes, fmt: Literal["xlsx", "csv"], sheet_name: str | None = None
) -> Grid:
    if fmt == "xlsx":
        return _parse_xlsx(data, sheet_name)
    if fmt == "csv":
        return _parse_csv(data)
    raise ValueError(f"Unsupported format: {fmt}")


def _parse_xlsx(data: bytes, sheet_name: str | None) -> Grid:
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    sheet_names = wb.sheetnames
    if sheet_name is None:
        ws = wb.active
    else:
        if sheet_name not in sheet_names:
            raise ValueError(f"Sheet '{sheet_name}' not found. Available: {sheet_names}")
        ws = wb[sheet_name]

    all_rows = [
        [("" if cell is None else str(cell)) for cell in row]
        for row in ws.iter_rows(values_only=True)
    ]
    if not all_rows:
        return Grid(columns=[], rows=[], row_count=0, sheets=sheet_names)

    columns = [str(c).strip() for c in all_rows[0]]
    rows = all_rows[1:]
    # drop trailing fully-empty rows
    while rows and all(cell == "" for cell in rows[-1]):
        rows.pop()
    return Grid(columns=columns, rows=rows, row_count=len(rows), sheets=sheet_names)


def _parse_csv(data: bytes) -> Grid:
    text = data.decode("utf-8-sig")
    reader = csv_module.reader(StringIO(text))
    all_rows = list(reader)
    if not all_rows:
        return Grid(columns=[], rows=[], row_count=0, sheets=None)
    columns = [c.strip() for c in all_rows[0]]
    rows = all_rows[1:]
    while rows and all(cell == "" for cell in rows[-1]):
        rows.pop()
    return Grid(columns=columns, rows=rows, row_count=len(rows), sheets=None)
```

- [ ] **Step 5: Run parsing tests**

```bash
uv run pytest tests/test_services/test_import.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/chaima/services/import_.py tests/test_services/test_import.py tests/fixtures/import_sample.xlsx tests/fixtures/import_sample.csv
git commit -m "feat(import): parse_upload (xlsx + csv) and test fixtures"
```

---

### Task 2.4: `apply_column_mapping` + `group_chemicals_by_identity`

**Files:**
- Modify: `src/chaima/services/import_.py`
- Modify: `tests/test_services/test_import.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_services/test_import.py`:

```python
def test_apply_column_mapping_basic():
    grid = import_service.Grid(
        columns=["Name", "CAS", "Qty", "Unit", "Notes"],
        rows=[["Ethanol", "64-17-5", "1", "L", "ignore this"]],
        row_count=1,
        sheets=None,
    )
    mapping = {
        "Name": "name",
        "CAS": "cas",
        "Qty": "quantity",
        "Unit": "unit",
        "Notes": "ignore",
    }
    parsed = import_service.apply_column_mapping(grid, mapping, qu_combined_column=None)
    assert len(parsed) == 1
    row = parsed[0]
    assert row.index == 0
    assert row.name == "Ethanol"
    assert row.cas == "64-17-5"
    assert row.quantity == 1.0
    assert row.unit == "L"
    assert row.errors == []


def test_apply_column_mapping_combined_qu():
    grid = import_service.Grid(
        columns=["Name", "Menge"],
        rows=[["Acetone", "250 mL"], ["Bad", "junk"]],
        row_count=2,
        sheets=None,
    )
    mapping = {"Name": "name", "Menge": "quantity_unit_combined"}
    parsed = import_service.apply_column_mapping(grid, mapping, qu_combined_column="Menge")
    assert parsed[0].quantity == 250.0
    assert parsed[0].unit == "mL"
    assert parsed[0].errors == []
    assert parsed[1].quantity is None
    assert "unparseable" in parsed[1].errors[0].lower()


def test_apply_column_mapping_missing_required_name():
    grid = import_service.Grid(
        columns=["CAS"],
        rows=[["64-17-5"]],
        row_count=1,
        sheets=None,
    )
    mapping = {"CAS": "cas"}
    import pytest
    with pytest.raises(import_service.MappingValidationError, match="name"):
        import_service.apply_column_mapping(grid, mapping, qu_combined_column=None)


def test_group_chemicals_by_cas():
    rows = [
        _parsed(0, name="Ethanol 99%", cas="64-17-5"),
        _parsed(1, name="ethanol", cas="64-17-5"),
        _parsed(2, name="Acetone", cas="67-64-1"),
    ]
    groups = import_service.group_chemicals_by_identity(rows)
    assert len(groups) == 2
    ethanol_group = next(g for g in groups if g.canonical_cas == "64-17-5")
    assert sorted(ethanol_group.row_indices) == [0, 1]


def test_group_chemicals_by_name_when_no_cas():
    rows = [
        _parsed(0, name="Water", cas=None),
        _parsed(1, name="  water ", cas=None),
        _parsed(2, name="WATER", cas=None),
    ]
    groups = import_service.group_chemicals_by_identity(rows)
    assert len(groups) == 1
    assert groups[0].row_indices == [0, 1, 2]


def _parsed(index, **kw):
    return import_service.ParsedRow(
        index=index,
        name=kw.get("name"),
        cas=kw.get("cas"),
        location_text=kw.get("location_text"),
        quantity=kw.get("quantity"),
        unit=kw.get("unit"),
        purity=kw.get("purity"),
        purchased_at=kw.get("purchased_at"),
        ordered_by=kw.get("ordered_by"),
        identifier=kw.get("identifier"),
        created_by_name=kw.get("created_by_name"),
        comment=kw.get("comment"),
        errors=[],
    )
```

- [ ] **Step 2: Run — fail**

```bash
uv run pytest tests/test_services/test_import.py -v -k "column_mapping or group_chemicals"
```

Expected: classes not defined.

- [ ] **Step 3: Implement**

Append to `src/chaima/services/import_.py`:

```python
@dataclass
class ParsedRow:
    index: int
    name: str | None
    cas: str | None
    location_text: str | None
    quantity: float | None
    unit: str | None
    purity: str | None
    purchased_at: str | None
    ordered_by: str | None
    identifier: str | None
    created_by_name: str | None
    comment: str | None
    errors: list[str]


class MappingValidationError(ValueError):
    pass


_REQUIRED_TARGETS = {"name"}  # plus quantity OR quantity_unit_combined, handled separately


def apply_column_mapping(
    grid: Grid,
    mapping: dict[str, str],
    qu_combined_column: str | None,
) -> list[ParsedRow]:
    targets_in_use = set(mapping.values())
    missing = _REQUIRED_TARGETS - targets_in_use
    if missing:
        raise MappingValidationError(f"Missing required columns: {sorted(missing)}")
    has_qty = "quantity" in targets_in_use
    has_qu = qu_combined_column is not None
    if not (has_qty or has_qu):
        raise MappingValidationError(
            "Need either a 'quantity' column or a 'quantity_unit_combined' column"
        )

    col_index = {col: i for i, col in enumerate(grid.columns)}
    parsed: list[ParsedRow] = []
    for i, row in enumerate(grid.rows):
        errors: list[str] = []
        values: dict[str, str | None] = {t: None for t in [
            "name", "cas", "location_text", "quantity", "unit", "purity",
            "purchased_at", "ordered_by", "identifier", "created_by_name", "comment",
        ]}
        qty: float | None = None
        unit: str | None = None
        for source_col, target in mapping.items():
            if target == "ignore":
                continue
            cell = row[col_index[source_col]] if col_index[source_col] < len(row) else ""
            cell = cell.strip() if cell else ""
            if target == "quantity_unit_combined":
                q, u = split_quantity_unit(cell)
                if cell and q is None:
                    errors.append(f"Unparseable quantity+unit cell: {cell!r}")
                qty = q if q is not None else qty
                unit = u if u is not None else unit
            elif target == "quantity":
                if cell:
                    try:
                        qty = float(cell.replace(",", "."))
                    except ValueError:
                        errors.append(f"Unparseable quantity: {cell!r}")
            elif target == "unit":
                unit = cell or None
            else:
                values[target] = cell or None

        if not values.get("name"):
            errors.append("Missing chemical name")

        parsed.append(ParsedRow(
            index=i,
            name=values["name"],
            cas=values["cas"],
            location_text=values["location_text"],
            quantity=qty,
            unit=unit,
            purity=values["purity"],
            purchased_at=values["purchased_at"],
            ordered_by=values["ordered_by"],
            identifier=values["identifier"],
            created_by_name=values["created_by_name"],
            comment=values["comment"],
            errors=errors,
        ))
    return parsed


@dataclass
class ChemicalGroup:
    canonical_name: str
    canonical_cas: str | None
    row_indices: list[int]


def _normalize_name(s: str | None) -> str:
    return (s or "").strip().lower()


def group_chemicals_by_identity(rows: list[ParsedRow]) -> list[ChemicalGroup]:
    # Key: CAS if present, else normalized name
    buckets: dict[str, list[ParsedRow]] = {}
    for r in rows:
        if r.cas:
            key = f"cas:{r.cas}"
        else:
            key = f"name:{_normalize_name(r.name)}"
        buckets.setdefault(key, []).append(r)

    groups: list[ChemicalGroup] = []
    for key, rs in buckets.items():
        # canonical name = first non-empty name in the bucket
        canonical = next((r.name for r in rs if r.name), rs[0].name or "")
        canonical_cas = next((r.cas for r in rs if r.cas), None)
        groups.append(ChemicalGroup(
            canonical_name=canonical,
            canonical_cas=canonical_cas,
            row_indices=[r.index for r in rs],
        ))
    return groups
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_services/test_import.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/import_.py tests/test_services/test_import.py
git commit -m "feat(import): apply_column_mapping + group_chemicals_by_identity"
```

---

### Task 2.5: `commit_import` — write everything in one transaction

**Files:**
- Modify: `src/chaima/services/import_.py`
- Modify: `tests/test_services/test_import.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_services/test_import.py`:

```python
from uuid import UUID

from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.storage import StorageLocation


async def test_commit_import_happy_path(session, group, user):
    payload = import_service.CommitPayload(
        column_mapping={
            "Name": "name", "CAS": "cas", "Location": "location_text",
            "Qty": "quantity", "Unit": "unit", "Id": "identifier",
        },
        quantity_unit_combined_column=None,
        rows=[
            ["Ethanol", "64-17-5", "Shelf A", "1", "L", "E-001"],
            ["Ethanol", "64-17-5", "Shelf A", "0.5", "L", "E-002"],
            ["Acetone", "67-64-1", "Shelf B", "250", "mL", "A-001"],
        ],
        columns=["Name", "CAS", "Location", "Qty", "Unit", "Id"],
        location_mapping=[
            import_service.LocationMapping(source_text="Shelf A", location_id=None,
                                            new_location={"name": "Shelf A", "parent_id": None}),
            import_service.LocationMapping(source_text="Shelf B", location_id=None,
                                            new_location={"name": "Shelf B", "parent_id": None}),
        ],
        chemical_groups=[
            import_service.ChemicalGroupPayload(
                canonical_name="Ethanol", canonical_cas="64-17-5", row_indices=[0, 1]
            ),
            import_service.ChemicalGroupPayload(
                canonical_name="Acetone", canonical_cas="67-64-1", row_indices=[2]
            ),
        ],
    )

    summary = await import_service.commit_import(
        session, group_id=group.id, viewer_id=user.id, payload=payload,
    )
    await session.commit()

    assert summary.created_chemicals == 2
    assert summary.created_containers == 3
    assert summary.created_locations == 2
    assert summary.skipped_rows == []

    from sqlmodel import select
    chems = (await session.exec(select(Chemical).where(Chemical.group_id == group.id))).all()
    assert {c.name for c in chems} == {"Ethanol", "Acetone"}


async def test_commit_import_rollback_on_error(session, group, user):
    # A bad row: missing chemical name entirely
    payload = import_service.CommitPayload(
        column_mapping={"Name": "name", "Qty": "quantity", "Unit": "unit"},
        quantity_unit_combined_column=None,
        rows=[
            ["Ethanol", "1", "L"],
            ["", "1", "L"],  # invalid: no name
        ],
        columns=["Name", "Qty", "Unit"],
        location_mapping=[],
        chemical_groups=[
            import_service.ChemicalGroupPayload(canonical_name="Ethanol", canonical_cas=None, row_indices=[0, 1]),
        ],
    )
    import pytest
    with pytest.raises(import_service.ImportValidationError):
        await import_service.commit_import(
            session, group_id=group.id, viewer_id=user.id, payload=payload,
        )
    # Rollback: no chemicals created
    from sqlmodel import select
    chems = (await session.exec(select(Chemical).where(Chemical.group_id == group.id))).all()
    assert chems == []


async def test_commit_import_uses_existing_location(session, group, user):
    existing = StorageLocation(name="Existing Shelf", kind="shelf")
    session.add(existing)
    await session.commit()

    payload = import_service.CommitPayload(
        column_mapping={"Name": "name", "Loc": "location_text", "Q": "quantity", "U": "unit"},
        quantity_unit_combined_column=None,
        rows=[["Ethanol", "Existing", "1", "L"]],
        columns=["Name", "Loc", "Q", "U"],
        location_mapping=[
            import_service.LocationMapping(source_text="Existing", location_id=existing.id, new_location=None),
        ],
        chemical_groups=[
            import_service.ChemicalGroupPayload(canonical_name="Ethanol", canonical_cas=None, row_indices=[0]),
        ],
    )
    summary = await import_service.commit_import(
        session, group_id=group.id, viewer_id=user.id, payload=payload,
    )
    await session.commit()
    assert summary.created_locations == 0
    assert summary.created_containers == 1
```

- [ ] **Step 2: Run — fail**

```bash
uv run pytest tests/test_services/test_import.py -v -k commit_import
```

Expected: payload classes don't exist.

- [ ] **Step 3: Implement**

Append to `src/chaima/services/import_.py`:

```python
import uuid as uuid_pkg
from dataclasses import field as dc_field


@dataclass
class LocationMapping:
    source_text: str
    location_id: uuid_pkg.UUID | None
    new_location: dict | None  # {"name": str, "parent_id": UUID | None}


@dataclass
class ChemicalGroupPayload:
    canonical_name: str
    canonical_cas: str | None
    row_indices: list[int]


@dataclass
class CommitPayload:
    column_mapping: dict[str, str]
    quantity_unit_combined_column: str | None
    columns: list[str]
    rows: list[list[str]]
    location_mapping: list[LocationMapping]
    chemical_groups: list[ChemicalGroupPayload]


@dataclass
class ImportSummary:
    created_chemicals: int
    created_containers: int
    created_locations: int
    skipped_rows: list[dict]  # [{"index": int, "reason": str}]


class ImportValidationError(ValueError):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(f"Import validation failed: {len(errors)} error(s)")


async def commit_import(
    session,
    *,
    group_id: uuid_pkg.UUID,
    viewer_id: uuid_pkg.UUID,
    payload: CommitPayload,
) -> ImportSummary:
    from chaima.models.chemical import Chemical
    from chaima.models.container import Container
    from chaima.models.storage import StorageLocation

    # 1. Parse rows up front; fail early on any validation error
    parsed = apply_column_mapping(
        Grid(columns=payload.columns, rows=payload.rows, row_count=len(payload.rows), sheets=None),
        payload.column_mapping,
        payload.quantity_unit_combined_column,
    )
    errors = [{"index": r.index, "reason": "; ".join(r.errors)} for r in parsed if r.errors]
    if errors:
        raise ImportValidationError(errors)

    # 2. Resolve locations (create missing ones)
    location_text_to_id: dict[str, uuid_pkg.UUID] = {}
    created_locations = 0
    for lm in payload.location_mapping:
        if lm.location_id is not None:
            location_text_to_id[lm.source_text] = lm.location_id
        elif lm.new_location is not None:
            new_loc = StorageLocation(
                name=lm.new_location["name"],
                kind="cabinet",  # default kind for imported flat locations
                parent_id=lm.new_location.get("parent_id"),
            )
            session.add(new_loc)
            await session.flush()
            location_text_to_id[lm.source_text] = new_loc.id
            created_locations += 1
        else:
            raise ImportValidationError(
                [{"index": -1, "reason": f"Location '{lm.source_text}' has no mapping"}]
            )

    # 3. Resolve chemicals (one Chemical per ChemicalGroupPayload)
    row_to_chemical: dict[int, uuid_pkg.UUID] = {}
    created_chemicals = 0
    for cg in payload.chemical_groups:
        chem = Chemical(
            name=cg.canonical_name,
            cas=cg.canonical_cas,
            group_id=group_id,
            created_by=viewer_id,
        )
        session.add(chem)
        await session.flush()
        created_chemicals += 1
        for idx in cg.row_indices:
            row_to_chemical[idx] = chem.id

    # 4. Create one Container per parsed row
    from chaima.services import containers as container_service
    created_containers = 0
    for row in parsed:
        chem_id = row_to_chemical.get(row.index)
        if chem_id is None:
            raise ImportValidationError(
                [{"index": row.index, "reason": "Row not assigned to any chemical group"}]
            )
        loc_id = location_text_to_id.get(row.location_text or "")
        if loc_id is None and row.location_text:
            raise ImportValidationError(
                [{"index": row.index, "reason": f"Unmapped location: {row.location_text!r}"}]
            )
        if loc_id is None:
            raise ImportValidationError(
                [{"index": row.index, "reason": "Row has no location"}]
            )
        identifier = row.identifier or _next_identifier(cg.canonical_name)
        try:
            await container_service.create_container(
                session,
                chemical_id=chem_id,
                location_id=loc_id,
                identifier=identifier,
                amount=row.quantity if row.quantity is not None else 0.0,
                unit=row.unit or "",
                created_by=viewer_id,
                purchased_at=None,
            )
        except container_service.DuplicateIdentifier:
            identifier = f"{identifier}-{row.index}"
            await container_service.create_container(
                session,
                chemical_id=chem_id,
                location_id=loc_id,
                identifier=identifier,
                amount=row.quantity if row.quantity is not None else 0.0,
                unit=row.unit or "",
                created_by=viewer_id,
                purchased_at=None,
            )
        # Set optional fields that create_container doesn't accept via kwargs
        # (ordered_by_name, purity, comment, ordered_by_name) — set directly on the ORM object
        # The last added container is the session's pending one; we find it by identifier.
        # Simpler: fetch and update.
        from sqlmodel import select
        fetched = (await session.exec(
            select(Container).where(Container.identifier == identifier)
        )).first()
        if fetched:
            fetched.ordered_by_name = row.ordered_by
            fetched.purity = row.purity
            if row.comment or row.created_by_name:
                pieces = []
                if row.comment:
                    pieces.append(row.comment)
                if row.created_by_name:
                    pieces.append(f"created by: {row.created_by_name}")
                # Concatenate into chemical's comment (rarely used)
                chem = await session.get(Chemical, chem_id)
                existing_comment = chem.comment or ""
                chem.comment = ("; ".join([existing_comment] + pieces)).strip("; ")
        created_containers += 1

    await session.flush()
    return ImportSummary(
        created_chemicals=created_chemicals,
        created_containers=created_containers,
        created_locations=created_locations,
        skipped_rows=[],
    )


_identifier_counters: dict[str, int] = {}


def _next_identifier(chem_name: str) -> str:
    # Fallback auto-identifier: uppercase first letter + numeric counter, in-memory dedup.
    # The final uniqueness check is enforced by check_identifier_unique_in_group; this is just
    # a reasonable starting guess. The caller handles DuplicateIdentifier by suffixing.
    key = chem_name[:1].upper() if chem_name else "X"
    _identifier_counters[key] = _identifier_counters.get(key, 0) + 1
    return f"{key}-IMP-{_identifier_counters[key]:04d}"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_services/test_import.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/import_.py tests/test_services/test_import.py
git commit -m "feat(import): commit_import transactional writer"
```

---

### Task 2.6: Router — `/import/preview` and `/import/commit`

**Files:**
- Create: `src/chaima/routers/import_.py`
- Modify: `src/chaima/app.py`
- Create: `tests/test_api/test_import.py`

- [ ] **Step 1: Register the router in the app**

In `src/chaima/app.py`, find the list of `app.include_router(...)` calls and add:

```python
from chaima.routers import import_ as import_router
app.include_router(import_router.router)
```

- [ ] **Step 2: Write API tests**

Create `tests/test_api/test_import.py`:

```python
from pathlib import Path

FIXTURE = Path(__file__).parent.parent / "fixtures" / "import_sample.xlsx"


async def test_preview_xlsx(client, group, admin_membership):
    with FIXTURE.open("rb") as f:
        resp = await client.post(
            f"/api/v1/groups/{group.id}/import/preview",
            files={"file": ("import_sample.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["columns"][:3] == ["Name", "CAS-Nr.", "Standort"]
    assert body["row_count"] == 4
    assert body["detected_mapping"]["Name"] == "name"
    assert body["detected_mapping"]["CAS-Nr."] == "cas"


async def test_preview_requires_admin(client, group, membership):
    # non-admin member
    with FIXTURE.open("rb") as f:
        resp = await client.post(
            f"/api/v1/groups/{group.id}/import/preview",
            files={"file": ("s.xlsx", f, "application/octet-stream")},
        )
    assert resp.status_code == 403


async def test_commit_happy_path(client, session, group, user, admin_membership):
    body = {
        "column_mapping": {"Name": "name", "Loc": "location_text", "Q": "quantity", "U": "unit"},
        "quantity_unit_combined_column": None,
        "columns": ["Name", "Loc", "Q", "U"],
        "rows": [["Ethanol", "Shelf A", "1", "L"]],
        "location_mapping": [
            {"source_text": "Shelf A", "location_id": None,
             "new_location": {"name": "Shelf A", "parent_id": None}},
        ],
        "chemical_groups": [
            {"canonical_name": "Ethanol", "canonical_cas": None, "row_indices": [0]},
        ],
    }
    resp = await client.post(
        f"/api/v1/groups/{group.id}/import/commit", json=body,
    )
    assert resp.status_code == 200, resp.text
    summary = resp.json()
    assert summary["created_chemicals"] == 1
    assert summary["created_containers"] == 1
    assert summary["created_locations"] == 1


async def test_commit_validation_error_400(client, group, admin_membership):
    body = {
        "column_mapping": {"Name": "name", "Q": "quantity", "U": "unit"},
        "quantity_unit_combined_column": None,
        "columns": ["Name", "Q", "U"],
        "rows": [["", "1", "L"]],  # missing name
        "location_mapping": [],
        "chemical_groups": [{"canonical_name": "x", "canonical_cas": None, "row_indices": [0]}],
    }
    resp = await client.post(
        f"/api/v1/groups/{group.id}/import/commit", json=body,
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert any("name" in e["reason"].lower() for e in detail["errors"])
```

- [ ] **Step 3: Run — fail**

```bash
uv run pytest tests/test_api/test_import.py -v
```

Expected: 404 (router not registered).

- [ ] **Step 4: Implement the router**

Create `src/chaima/routers/import_.py`:

```python
# src/chaima/routers/import_.py
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from chaima.dependencies import CurrentUserDep, GroupAdminDep, SessionDep
from chaima.services import import_ as import_service

router = APIRouter(prefix="/api/v1/groups/{group_id}/import", tags=["import"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


class PreviewResponse(BaseModel):
    columns: list[str]
    rows: list[list[str]]
    row_count: int
    sheets: list[str] | None
    detected_mapping: dict[str, str]


class LocationMappingBody(BaseModel):
    source_text: str
    location_id: UUID | None = None
    new_location: dict | None = None


class ChemicalGroupBody(BaseModel):
    canonical_name: str
    canonical_cas: str | None = None
    row_indices: list[int]


class CommitBody(BaseModel):
    column_mapping: dict[str, str]
    quantity_unit_combined_column: str | None = None
    columns: list[str]
    rows: list[list[str]]
    location_mapping: list[LocationMappingBody]
    chemical_groups: list[ChemicalGroupBody]


class CommitResponse(BaseModel):
    created_chemicals: int
    created_containers: int
    created_locations: int
    skipped_rows: list[dict] = []


@router.post("/preview", response_model=PreviewResponse)
async def preview(
    group_id: UUID,
    session: SessionDep,
    admin: GroupAdminDep,
    file: UploadFile = File(...),
    sheet_name: str | None = None,
) -> PreviewResponse:
    _ = group_id  # only used for auth via admin dep
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(data)} bytes, max {MAX_UPLOAD_BYTES}).",
        )
    lower = (file.filename or "").lower()
    if lower.endswith(".xlsx"):
        fmt = "xlsx"
    elif lower.endswith(".csv"):
        fmt = "csv"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx and .csv are supported.",
        )
    try:
        grid = import_service.parse_upload(data, fmt, sheet_name=sheet_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return PreviewResponse(
        columns=grid.columns,
        rows=grid.rows,
        row_count=grid.row_count,
        sheets=grid.sheets,
        detected_mapping=import_service.detect_header_mapping(grid.columns),
    )


@router.post("/commit", response_model=CommitResponse)
async def commit(
    group_id: UUID,
    body: CommitBody,
    session: SessionDep,
    admin: GroupAdminDep,
    user: CurrentUserDep,
) -> CommitResponse:
    payload = import_service.CommitPayload(
        column_mapping=body.column_mapping,
        quantity_unit_combined_column=body.quantity_unit_combined_column,
        columns=body.columns,
        rows=body.rows,
        location_mapping=[
            import_service.LocationMapping(
                source_text=lm.source_text,
                location_id=lm.location_id,
                new_location=lm.new_location,
            )
            for lm in body.location_mapping
        ],
        chemical_groups=[
            import_service.ChemicalGroupPayload(
                canonical_name=cg.canonical_name,
                canonical_cas=cg.canonical_cas,
                row_indices=cg.row_indices,
            )
            for cg in body.chemical_groups
        ],
    )
    try:
        summary = await import_service.commit_import(
            session, group_id=group_id, viewer_id=user.id, payload=payload,
        )
        await session.commit()
    except import_service.ImportValidationError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Validation failed", "errors": exc.errors},
        )
    return CommitResponse(
        created_chemicals=summary.created_chemicals,
        created_containers=summary.created_containers,
        created_locations=summary.created_locations,
        skipped_rows=summary.skipped_rows,
    )
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_api/test_import.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/chaima/routers/import_.py src/chaima/app.py tests/test_api/test_import.py
git commit -m "feat(import): /preview and /commit endpoints (admin-only)"
```

---

### Task 2.7: Frontend types + API hooks

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/api/hooks/useImport.ts`

- [ ] **Step 1: Add types**

Append to `frontend/src/types/index.ts`:

```ts
export interface ImportPreviewResponse {
  columns: string[];
  rows: string[][];
  row_count: number;
  sheets: string[] | null;
  detected_mapping: Record<string, string>;
}

export interface ImportLocationMapping {
  source_text: string;
  location_id: string | null;
  new_location: { name: string; parent_id: string | null } | null;
}

export interface ImportChemicalGroup {
  canonical_name: string;
  canonical_cas: string | null;
  row_indices: number[];
}

export interface ImportCommitBody {
  column_mapping: Record<string, string>;
  quantity_unit_combined_column: string | null;
  columns: string[];
  rows: string[][];
  location_mapping: ImportLocationMapping[];
  chemical_groups: ImportChemicalGroup[];
}

export interface ImportCommitResponse {
  created_chemicals: number;
  created_containers: number;
  created_locations: number;
  skipped_rows: { index: number; reason: string }[];
}

export type ImportTarget =
  | "name" | "cas" | "location_text" | "quantity" | "unit"
  | "quantity_unit_combined" | "purity" | "purchased_at"
  | "ordered_by" | "identifier" | "created_by_name" | "comment" | "ignore";

export const IMPORT_TARGETS: ImportTarget[] = [
  "name", "cas", "location_text", "quantity", "unit", "quantity_unit_combined",
  "purity", "purchased_at", "ordered_by", "identifier", "created_by_name",
  "comment", "ignore",
];
```

- [ ] **Step 2: Create hooks**

Create `frontend/src/api/hooks/useImport.ts`:

```ts
import { useMutation } from "@tanstack/react-query";
import client from "../client";
import type {
  ImportPreviewResponse,
  ImportCommitBody,
  ImportCommitResponse,
} from "../../types";

export function useImportPreview(groupId: string) {
  return useMutation<ImportPreviewResponse, unknown, { file: File; sheetName?: string }>({
    mutationFn: async ({ file, sheetName }) => {
      const form = new FormData();
      form.append("file", file);
      if (sheetName) form.append("sheet_name", sheetName);
      const resp = await client.post(
        `/groups/${groupId}/import/preview`, form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      return resp.data;
    },
  });
}

export function useImportCommit(groupId: string) {
  return useMutation<ImportCommitResponse, unknown, ImportCommitBody>({
    mutationFn: (body) =>
      client.post(`/groups/${groupId}/import/commit`, body).then((r) => r.data),
  });
}
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend
npx tsc --noEmit
```

Expected: EXIT 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/hooks/useImport.ts
git commit -m "feat(ui): types + hooks for import wizard"
```

---

### Task 2.8: `ImportSection` — wizard shell + step 1 (Upload)

**Files:**
- Create: `frontend/src/components/settings/ImportSection.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/components/settings/SettingsNav.tsx`

- [ ] **Step 1: Add "import" to nav types**

In `frontend/src/components/settings/SettingsNav.tsx`, edit `SettingsSectionKey`:

```ts
export type SettingsSectionKey =
  | "account" | "group" | "members" | "hazard-tags" | "suppliers"
  | "import" | "buildings" | "system";
```

- [ ] **Step 2: Register the route in SettingsPage**

In `frontend/src/pages/SettingsPage.tsx`, add to the `items` array (under `"GROUP ADMIN"`):

```tsx
{ key: "import", label: "Import data", group: "GROUP ADMIN", visible: isMember },
```

And in the body, add the render branch:

```tsx
{active === "import" && isMember && user?.main_group_id && (
  <ImportSection groupId={user.main_group_id} />
)}
```

Import it at top:

```tsx
import { ImportSection } from "../components/settings/ImportSection";
```

- [ ] **Step 3: Create the shell**

Create `frontend/src/components/settings/ImportSection.tsx`:

```tsx
import { useState } from "react";
import { Alert, Box, Button, Stack, Stepper, Step, StepLabel, Typography } from "@mui/material";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { SectionHeader } from "./SectionHeader";
import { useImportPreview } from "../../api/hooks/useImport";
import type { ImportPreviewResponse } from "../../types";

type WizardState =
  | { step: "upload" }
  | { step: "columns"; preview: ImportPreviewResponse; file: File }
  | { step: "locations"; preview: ImportPreviewResponse; columnMapping: Record<string, string>; quCombined: string | null }
  | { step: "review"; /* ... */ }
  | { step: "done"; summary: unknown };

interface Props {
  groupId: string;
}

export function ImportSection({ groupId }: Props) {
  const [state, setState] = useState<WizardState>({ step: "upload" });
  const preview = useImportPreview(groupId);

  const steps = ["Upload", "Columns", "Locations", "Review", "Done"];
  const activeStep = { upload: 0, columns: 1, locations: 2, review: 3, done: 4 }[state.step];

  return (
    <Box>
      <SectionHeader
        title="Import data"
        subtitle="Ingest a lab inventory from Excel or CSV. One-time setup — import once, then use chaima going forward."
      />

      <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
        {steps.map((s) => <Step key={s}><StepLabel>{s}</StepLabel></Step>)}
      </Stepper>

      {state.step === "upload" && (
        <UploadStep
          onPicked={async (file) => {
            const res = await preview.mutateAsync({ file });
            setState({ step: "columns", preview: res, file });
          }}
          loading={preview.isPending}
          error={preview.error}
        />
      )}

      {state.step === "columns" && (
        <Alert severity="info">Column mapping — coming in Task 2.9.</Alert>
      )}
    </Box>
  );
}

function UploadStep({
  onPicked, loading, error,
}: {
  onPicked: (file: File) => void;
  loading: boolean;
  error: unknown;
}) {
  return (
    <Stack spacing={2} sx={{ maxWidth: 500 }}>
      <Typography variant="body2" color="text.secondary">
        Accepted formats: <b>.xlsx</b>, <b>.csv</b>. Max size: 5 MB.
      </Typography>
      <Button
        variant="contained"
        component="label"
        startIcon={<UploadFileIcon />}
        disabled={loading}
      >
        {loading ? "Reading…" : "Choose file"}
        <input
          type="file"
          hidden
          accept=".xlsx,.csv"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onPicked(f);
          }}
        />
      </Button>
      {error instanceof Error && (
        <Alert severity="error">{error.message}</Alert>
      )}
    </Stack>
  );
}
```

- [ ] **Step 4: Typecheck**

```bash
cd frontend
npx tsc --noEmit
```

Expected: EXIT 0.

- [ ] **Step 5: Manual check**

Run backend + frontend. Log in as admin, go to Settings → Import data. Upload `tests/fixtures/import_sample.xlsx`. Wizard advances to step 2 (shows "Column mapping — coming..." placeholder).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/settings/ImportSection.tsx frontend/src/pages/SettingsPage.tsx frontend/src/components/settings/SettingsNav.tsx
git commit -m "feat(ui): import wizard shell + upload step"
```

---

### Task 2.9: Column-mapping step

**Files:**
- Modify: `frontend/src/components/settings/ImportSection.tsx`

- [ ] **Step 1: Extract `ColumnMappingStep` component**

Replace the `{state.step === "columns" && ...}` block and add a component below `UploadStep`:

```tsx
{state.step === "columns" && (
  <ColumnMappingStep
    preview={state.preview}
    onBack={() => setState({ step: "upload" })}
    onNext={(mapping, qu) => {
      setState({
        step: "locations",
        preview: state.preview,
        columnMapping: mapping,
        quCombined: qu,
      });
    }}
  />
)}
{state.step === "locations" && (
  <Alert severity="info">Location mapping — coming in Task 2.10.</Alert>
)}
```

Add the component (import `IMPORT_TARGETS`, `MenuItem`, `Paper`, `Stack`, `Table*`, `TextField`):

```tsx
import { IMPORT_TARGETS } from "../../types";
import type { ImportTarget } from "../../types";
import {
  MenuItem, Paper, Table, TableBody, TableCell, TableHead, TableRow, TextField,
} from "@mui/material";

function ColumnMappingStep({
  preview,
  onBack,
  onNext,
}: {
  preview: ImportPreviewResponse;
  onBack: () => void;
  onNext: (mapping: Record<string, string>, qu: string | null) => void;
}) {
  const [mapping, setMapping] = useState<Record<string, string>>(preview.detected_mapping);

  const quCombined = Object.entries(mapping).find(([, t]) => t === "quantity_unit_combined")?.[0] ?? null;

  const hasName = Object.values(mapping).includes("name");
  const hasQty = Object.values(mapping).includes("quantity") || quCombined !== null;
  const canProceed = hasName && hasQty;

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Map each column to a chaima field. Columns not needed: choose <b>ignore</b>.
        Required: at least one <b>name</b> and either <b>quantity</b> or <b>quantity_unit_combined</b>.
      </Typography>

      <Paper variant="outlined" sx={{ overflow: "hidden" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Source column</TableCell>
              <TableCell>Chaima field</TableCell>
              <TableCell>Sample values</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {preview.columns.map((col, colIdx) => (
              <TableRow key={col}>
                <TableCell sx={{ fontWeight: 500 }}>{col}</TableCell>
                <TableCell>
                  <TextField
                    select size="small" value={mapping[col] ?? "ignore"}
                    onChange={(e) =>
                      setMapping((m) => ({ ...m, [col]: e.target.value as ImportTarget }))
                    }
                    sx={{ minWidth: 200 }}
                  >
                    {IMPORT_TARGETS.map((t) => (
                      <MenuItem key={t} value={t}>{t}</MenuItem>
                    ))}
                  </TextField>
                </TableCell>
                <TableCell sx={{ color: "text.secondary", fontSize: 12 }}>
                  {preview.rows.slice(0, 3).map((r) => r[colIdx]).filter(Boolean).join(", ")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      {!canProceed && (
        <Alert severity="warning">
          At least one column must be mapped to <b>name</b>, and one to either <b>quantity</b> or <b>quantity_unit_combined</b>.
        </Alert>
      )}

      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
        <Button onClick={onBack}>Back</Button>
        <Button variant="contained" disabled={!canProceed} onClick={() => onNext(mapping, quCombined)}>
          Next
        </Button>
      </Stack>
    </Stack>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend
npx tsc --noEmit
```

Expected: EXIT 0.

- [ ] **Step 3: Manual check**

Upload the fixture. Verify mapping table renders with pre-filled guesses, "Next" disabled until `name` + `quantity`/`quantity_unit_combined` are present.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/settings/ImportSection.tsx
git commit -m "feat(ui): import wizard column-mapping step"
```

---

### Task 2.10: Location-mapping step

**Files:**
- Modify: `frontend/src/components/settings/ImportSection.tsx`

- [ ] **Step 1: Extract distinct location strings from rows**

Add a helper inside `ImportSection.tsx`:

```tsx
function distinctLocations(rows: string[][], columns: string[], mapping: Record<string, string>): string[] {
  const colIdx = columns.findIndex((c) => mapping[c] === "location_text");
  if (colIdx < 0) return [];
  const set = new Set<string>();
  for (const r of rows) {
    const v = (r[colIdx] ?? "").trim();
    if (v) set.add(v);
  }
  return Array.from(set).sort();
}
```

- [ ] **Step 2: Replace placeholder with `LocationMappingStep`**

Swap the `{state.step === "locations" && ...}` block:

```tsx
{state.step === "locations" && (
  <LocationMappingStep
    groupId={groupId}
    distinct={distinctLocations(state.preview.rows, state.preview.columns, state.columnMapping)}
    onBack={() =>
      setState({ step: "columns", preview: state.preview, file: (state as any).file })
    }
    onNext={(mappings) => {
      setState({ step: "review", /* ... */ } as any);  // stub, next task
    }}
  />
)}
```

Add the component (uses existing `useStorageTree` + `LocationPicker`):

```tsx
import { useStorageTree } from "../../api/hooks/useStorageLocations";
import LocationPicker from "../LocationPicker";
import type { ImportLocationMapping } from "../../types";

function LocationMappingStep({
  groupId,
  distinct,
  onBack,
  onNext,
}: {
  groupId: string;
  distinct: string[];
  onBack: () => void;
  onNext: (mappings: ImportLocationMapping[]) => void;
}) {
  const { data: tree = [] } = useStorageTree(groupId);
  const [rows, setRows] = useState<Record<string, { mode: "existing" | "new"; location_id?: string; new_name?: string; parent_id?: string | null }>>(() => {
    const init: Record<string, { mode: "new"; new_name: string }> = {};
    for (const d of distinct) init[d] = { mode: "new", new_name: d };
    return init;
  });
  const [pickerFor, setPickerFor] = useState<string | null>(null);

  const allMapped = distinct.every((d) => {
    const r = rows[d];
    if (!r) return false;
    if (r.mode === "existing") return !!r.location_id;
    return (r.new_name ?? "").trim() !== "";
  });

  const submit = () => {
    const out: ImportLocationMapping[] = distinct.map((d) => {
      const r = rows[d];
      if (r.mode === "existing") {
        return { source_text: d, location_id: r.location_id ?? null, new_location: null };
      }
      return {
        source_text: d,
        location_id: null,
        new_location: { name: (r.new_name ?? "").trim(), parent_id: r.parent_id ?? null },
      };
    });
    onNext(out);
  };

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Map each distinct location string to an existing storage location or create a new one.
        Newly created ones are flat (no parent) by default.
      </Typography>

      <Paper variant="outlined" sx={{ overflow: "hidden" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Source text</TableCell>
              <TableCell>Mode</TableCell>
              <TableCell>Target</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {distinct.map((d) => {
              const r = rows[d];
              return (
                <TableRow key={d}>
                  <TableCell sx={{ fontWeight: 500 }}>{d}</TableCell>
                  <TableCell>
                    <TextField
                      select size="small" value={r.mode}
                      onChange={(e) => {
                        const mode = e.target.value as "existing" | "new";
                        setRows((s) => ({ ...s, [d]: mode === "existing"
                          ? { mode: "existing" }
                          : { mode: "new", new_name: d } }));
                      }}
                    >
                      <MenuItem value="existing">Pick existing</MenuItem>
                      <MenuItem value="new">Create new</MenuItem>
                    </TextField>
                  </TableCell>
                  <TableCell>
                    {r.mode === "existing" ? (
                      <Button size="small" variant="outlined" onClick={() => setPickerFor(d)}>
                        {r.location_id ? "Change…" : "Pick location"}
                      </Button>
                    ) : (
                      <TextField
                        size="small"
                        value={r.new_name ?? ""}
                        onChange={(e) =>
                          setRows((s) => ({ ...s, [d]: { ...s[d], new_name: e.target.value } }))
                        }
                      />
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Paper>

      <LocationPicker
        open={pickerFor !== null}
        onClose={() => setPickerFor(null)}
        onSelect={(id) => {
          if (pickerFor) {
            setRows((s) => ({ ...s, [pickerFor]: { mode: "existing", location_id: id } }));
          }
          setPickerFor(null);
        }}
        tree={tree}
      />

      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
        <Button onClick={onBack}>Back</Button>
        <Button variant="contained" disabled={!allMapped} onClick={submit}>
          Next
        </Button>
      </Stack>
    </Stack>
  );
}
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend
npx tsc --noEmit
```

Expected: EXIT 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/settings/ImportSection.tsx
git commit -m "feat(ui): import wizard location-mapping step"
```

---

### Task 2.11: Chemical-review step + commit step

**Files:**
- Modify: `frontend/src/components/settings/ImportSection.tsx`

- [ ] **Step 1: Wire state for review + commit**

Update the `WizardState` type and state transitions. Replace the earlier `WizardState` with:

```tsx
type WizardState =
  | { step: "upload" }
  | { step: "columns"; preview: ImportPreviewResponse; file: File }
  | { step: "locations"; preview: ImportPreviewResponse; file: File;
      columnMapping: Record<string, string>; quCombined: string | null }
  | { step: "review"; preview: ImportPreviewResponse; file: File;
      columnMapping: Record<string, string>; quCombined: string | null;
      locations: ImportLocationMapping[] }
  | { step: "done"; summary: import("../../types").ImportCommitResponse };
```

Update the location-step `onNext` to set:

```tsx
onNext={(mappings) =>
  setState({
    step: "review",
    preview: state.preview, file: state.file,
    columnMapping: state.columnMapping, quCombined: state.quCombined,
    locations: mappings,
  })}
```

Also fix the columns `onNext` to carry `file` into locations state.

- [ ] **Step 2: Add `ChemicalReviewStep` (client-side grouping)**

```tsx
import { useImportCommit } from "../../api/hooks/useImport";
import type { ImportChemicalGroup, ImportCommitBody } from "../../types";

{state.step === "review" && (
  <ChemicalReviewStep
    groupId={groupId}
    preview={state.preview}
    columnMapping={state.columnMapping}
    quCombined={state.quCombined}
    locations={state.locations}
    onBack={() =>
      setState({
        step: "locations",
        preview: state.preview, file: state.file,
        columnMapping: state.columnMapping, quCombined: state.quCombined,
      })}
    onDone={(summary) => setState({ step: "done", summary })}
  />
)}

{state.step === "done" && (
  <Alert severity="success">
    Created {state.summary.created_chemicals} chemicals, {state.summary.created_containers} containers,
    {state.summary.created_locations} new locations.
    <Button sx={{ ml: 2 }} onClick={() => setState({ step: "upload" })}>Import another</Button>
  </Alert>
)}

function ChemicalReviewStep({
  groupId, preview, columnMapping, quCombined, locations, onBack, onDone,
}: {
  groupId: string;
  preview: ImportPreviewResponse;
  columnMapping: Record<string, string>;
  quCombined: string | null;
  locations: ImportLocationMapping[];
  onBack: () => void;
  onDone: (r: import("../../types").ImportCommitResponse) => void;
}) {
  const commit = useImportCommit(groupId);

  // Client-side grouping by (CAS if present, else normalized name)
  const groups = groupOnClient(preview, columnMapping);

  const submit = async () => {
    const body: ImportCommitBody = {
      column_mapping: columnMapping,
      quantity_unit_combined_column: quCombined,
      columns: preview.columns,
      rows: preview.rows,
      location_mapping: locations,
      chemical_groups: groups,
    };
    const r = await commit.mutateAsync(body);
    onDone(r);
  };

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        {groups.length} chemicals will be created, {preview.row_count} containers total.
        Review before committing.
      </Typography>

      <Paper variant="outlined" sx={{ overflow: "hidden" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Chemical</TableCell>
              <TableCell>CAS</TableCell>
              <TableCell>Container count</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {groups.map((g, i) => (
              <TableRow key={i}>
                <TableCell>{g.canonical_name}</TableCell>
                <TableCell>{g.canonical_cas ?? "—"}</TableCell>
                <TableCell>{g.row_indices.length}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      {commit.error instanceof Error && (
        <Alert severity="error">
          {commit.error.message}
        </Alert>
      )}

      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
        <Button onClick={onBack} disabled={commit.isPending}>Back</Button>
        <Button variant="contained" onClick={submit} disabled={commit.isPending}>
          {commit.isPending ? "Importing…" : "Commit import"}
        </Button>
      </Stack>
    </Stack>
  );
}

function groupOnClient(
  preview: ImportPreviewResponse,
  mapping: Record<string, string>,
): ImportChemicalGroup[] {
  const nameIdx = preview.columns.findIndex((c) => mapping[c] === "name");
  const casIdx = preview.columns.findIndex((c) => mapping[c] === "cas");
  const buckets = new Map<string, ImportChemicalGroup>();
  for (let i = 0; i < preview.rows.length; i++) {
    const name = (preview.rows[i][nameIdx] ?? "").trim();
    const cas = casIdx >= 0 ? (preview.rows[i][casIdx] ?? "").trim() : "";
    const key = cas ? `cas:${cas}` : `name:${name.toLowerCase()}`;
    const existing = buckets.get(key);
    if (existing) {
      existing.row_indices.push(i);
    } else {
      buckets.set(key, {
        canonical_name: name,
        canonical_cas: cas || null,
        row_indices: [i],
      });
    }
  }
  return Array.from(buckets.values());
}
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend
npx tsc --noEmit
```

Expected: EXIT 0.

- [ ] **Step 4: Manual full-flow test**

Use the fixture. Walk the wizard end-to-end. Verify success alert; open Chemicals page and confirm rows appear.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/ImportSection.tsx
git commit -m "feat(ui): import wizard review + commit steps"
```

---

### Task 2.12: Playwright e2e happy path

**Files:**
- Create: `frontend/e2e/import-wizard.spec.ts`

- [ ] **Step 1: Write the spec**

```ts
import { test, expect, type Page } from "@playwright/test";
import path from "path";

async function loginAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

test.describe("Import wizard", () => {
  test.beforeEach(async ({ page }) => {
    await loginAdmin(page);
  });

  test("imports a fixture xlsx end-to-end", async ({ page }) => {
    await page.goto("/settings");
    await page.getByRole("button", { name: /import data/i }).click();

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(
      path.resolve(__dirname, "../../tests/fixtures/import_sample.xlsx"),
    );

    // Columns step auto-filled; just click Next
    await page.getByRole("button", { name: /^next$/i }).click();

    // Locations step — all in "Create new" mode by default; just click Next
    await page.getByRole("button", { name: /^next$/i }).click();

    // Review step — commit
    await page.getByRole("button", { name: /commit import/i }).click();

    // Success alert visible
    await expect(page.getByText(/Created \d+ chemicals/i)).toBeVisible({ timeout: 15_000 });

    // Verify on the chemicals page
    await page.goto("/chemicals");
    await expect(page.getByText("Ethanol", { exact: true })).toBeVisible();
    await expect(page.getByText("Acetone", { exact: true })).toBeVisible();
  });
});
```

- [ ] **Step 2: Run the spec (app running locally)**

```bash
cd frontend
npx playwright test e2e/import-wizard.spec.ts
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/import-wizard.spec.ts
git commit -m "test(e2e): import wizard happy-path"
```

---

## Phase 3 — PubChem enrichment

Separate admin action that backfills SMILES/CID/GHS/synonyms on chemicals that lack them.

### Task 3.1: `services/enrich.py` — per-chemical enrich

**Files:**
- Create: `src/chaima/services/enrich.py`
- Create: `tests/test_services/test_enrich.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_enrich.py`:

```python
from unittest.mock import AsyncMock, patch

from chaima.models.chemical import Chemical
from chaima.services import enrich as enrich_service


async def test_enrich_one_fills_only_null_fields(session, group, user):
    chem = Chemical(
        name="Ethanol", cas=None, smiles=None, cid=None, molar_mass=None,
        group_id=group.id, created_by=user.id,
    )
    session.add(chem)
    await session.commit()
    await session.refresh(chem)

    mock_lookup = AsyncMock(return_value={
        "cid": "702",
        "name": "Ethanol",
        "cas": "64-17-5",
        "smiles": "CCO",
        "molar_mass": 46.07,
        "synonyms": ["ethyl alcohol"],
        "ghs_codes": [],
    })
    with patch("chaima.services.enrich.pubchem_lookup", mock_lookup):
        result = await enrich_service.enrich_one(session, chem)
        await session.commit()

    await session.refresh(chem)
    assert result == "enriched"
    assert chem.cid == "702"
    assert chem.smiles == "CCO"
    assert chem.molar_mass == 46.07


async def test_enrich_one_skips_if_cid_set(session, group, user):
    chem = Chemical(
        name="Ethanol", cid="702", group_id=group.id, created_by=user.id,
    )
    session.add(chem)
    await session.commit()
    mock_lookup = AsyncMock()
    with patch("chaima.services.enrich.pubchem_lookup", mock_lookup):
        result = await enrich_service.enrich_one(session, chem)
    assert result == "skipped"
    mock_lookup.assert_not_called()


async def test_enrich_one_not_found(session, group, user):
    chem = Chemical(name="Imaginarium", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()
    from chaima.services.pubchem import PubChemNotFound
    mock_lookup = AsyncMock(side_effect=PubChemNotFound("nope"))
    with patch("chaima.services.enrich.pubchem_lookup", mock_lookup):
        result = await enrich_service.enrich_one(session, chem)
    assert result == "not_found"
```

- [ ] **Step 2: Run — fail**

```bash
uv run pytest tests/test_services/test_enrich.py -v
```

Expected: module not found.

- [ ] **Step 3: Implement**

Create `src/chaima/services/enrich.py`:

```python
# src/chaima/services/enrich.py
from typing import Literal

from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical
from chaima.services.pubchem import PubChemNotFound, lookup as pubchem_lookup

EnrichStatus = Literal["enriched", "skipped", "not_found", "error"]


async def enrich_one(session: AsyncSession, chemical: Chemical) -> EnrichStatus:
    """Fill missing pubchem-sourced fields on `chemical`. Never overwrites non-null."""
    if chemical.cid:
        return "skipped"

    query = chemical.cas or chemical.name
    if not query:
        return "skipped"
    try:
        result = await pubchem_lookup(query)
    except PubChemNotFound:
        return "not_found"
    except Exception:
        return "error"

    if result.get("cid") and not chemical.cid:
        chemical.cid = str(result["cid"])
    if result.get("cas") and not chemical.cas:
        chemical.cas = result["cas"]
    if result.get("smiles") and not chemical.smiles:
        chemical.smiles = result["smiles"]
    if result.get("molar_mass") and chemical.molar_mass is None:
        chemical.molar_mass = result["molar_mass"]
    session.add(chemical)
    await session.flush()
    return "enriched"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_services/test_enrich.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/enrich.py tests/test_services/test_enrich.py
git commit -m "feat(enrich): enrich_one (fills missing PubChem fields, never overwrites)"
```

---

### Task 3.2: Bulk enrich + streaming endpoint

**Files:**
- Modify: `src/chaima/services/enrich.py`
- Modify: `src/chaima/routers/chemicals.py`
- Create: `tests/test_api/test_pubchem_enrich.py`

- [ ] **Step 1: Write the API test**

Create `tests/test_api/test_pubchem_enrich.py`:

```python
import json
from unittest.mock import AsyncMock, patch

from chaima.models.chemical import Chemical


async def test_enrich_endpoint_fills_missing(client, session, group, user, admin_membership):
    chem_a = Chemical(name="Ethanol", group_id=group.id, created_by=user.id)
    chem_b = Chemical(name="Acetone", group_id=group.id, created_by=user.id, cid="180")
    session.add(chem_a)
    session.add(chem_b)
    await session.commit()

    async def fake_lookup(q):
        return {"cid": "702", "smiles": "CCO", "molar_mass": 46.07,
                "cas": "64-17-5", "name": q, "synonyms": [], "ghs_codes": []}

    with patch("chaima.services.enrich.pubchem_lookup", AsyncMock(side_effect=fake_lookup)):
        resp = await client.post(
            f"/api/v1/groups/{group.id}/chemicals/enrich-pubchem",
            json={"chemical_ids": None},
        )
    assert resp.status_code == 200
    # Parse SSE events
    events = [json.loads(line[len("data: "):])
              for line in resp.text.splitlines() if line.startswith("data: ")]
    statuses = [e.get("status") for e in events if "status" in e]
    assert "enriched" in statuses
    assert "skipped" in statuses
    summary_event = next(e for e in events if "summary" in e)
    assert summary_event["summary"]["enriched"] == 1
    assert summary_event["summary"]["skipped"] == 1


async def test_enrich_endpoint_requires_admin(client, group, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/enrich-pubchem",
        json={"chemical_ids": None},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run — fail**

```bash
uv run pytest tests/test_api/test_pubchem_enrich.py -v
```

Expected: 404 (endpoint not defined).

- [ ] **Step 3: Add bulk enrich service**

Append to `src/chaima/services/enrich.py`:

```python
import asyncio
from uuid import UUID

from sqlmodel import select


async def enrich_group_chemicals(
    session: AsyncSession,
    group_id: UUID,
    chemical_ids: list[UUID] | None,
):
    """Async generator yielding per-chemical status events and a final summary."""
    stmt = select(Chemical).where(Chemical.group_id == group_id)
    if chemical_ids is not None:
        stmt = stmt.where(Chemical.id.in_(chemical_ids))
    else:
        stmt = stmt.where(Chemical.cid.is_(None))  # only missing-cid
    result = await session.exec(stmt)
    chemicals = list(result.all())

    counts = {"enriched": 0, "skipped": 0, "not_found": 0, "error": 0}
    for chem in chemicals:
        status = await enrich_one(session, chem)
        counts[status] += 1
        yield {"id": str(chem.id), "name": chem.name, "status": status}
        await session.commit()
        await asyncio.sleep(0.25)  # PubChem rate-limit buffer

    yield {"summary": counts}
```

- [ ] **Step 4: Add the router endpoint**

In `src/chaima/routers/chemicals.py`, add imports:

```python
import json
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from chaima.services import enrich as enrich_service
```

Add:

```python
class EnrichBody(BaseModel):
    chemical_ids: list[UUID] | None = None


@router.post("/enrich-pubchem")
async def enrich_pubchem(
    group_id: UUID,
    body: EnrichBody,
    session: SessionDep,
    admin: GroupAdminDep,
) -> StreamingResponse:
    async def generate():
        async for event in enrich_service.enrich_group_chemicals(
            session, group_id, body.chemical_ids,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_api/test_pubchem_enrich.py -v
```

Expected: all PASS. Note: `admin_membership` fixture needs to exist — it already does (used by supplier tests).

- [ ] **Step 6: Commit**

```bash
git add src/chaima/services/enrich.py src/chaima/routers/chemicals.py tests/test_api/test_pubchem_enrich.py
git commit -m "feat(enrich): bulk enrich endpoint with SSE progress"
```

---

### Task 3.3: Frontend enrichment dialog

**Files:**
- Create: `frontend/src/components/settings/ChemicalsAdminSection.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/components/settings/SettingsNav.tsx`

- [ ] **Step 1: Add nav entry**

In `SettingsNav.tsx`, extend `SettingsSectionKey`:

```ts
| "import" | "chemicals-admin" | "buildings" | "system";
```

In `SettingsPage.tsx`, add to `items`:

```tsx
{ key: "chemicals-admin", label: "Chemicals", group: "GROUP ADMIN", visible: isMember },
```

And in the body:

```tsx
{active === "chemicals-admin" && isMember && user?.main_group_id && (
  <ChemicalsAdminSection groupId={user.main_group_id} />
)}
```

Import:

```tsx
import { ChemicalsAdminSection } from "../components/settings/ChemicalsAdminSection";
```

- [ ] **Step 2: Create the section**

Create `frontend/src/components/settings/ChemicalsAdminSection.tsx`:

```tsx
import { useState } from "react";
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  LinearProgress, Stack, Typography,
} from "@mui/material";
import ScienceIcon from "@mui/icons-material/Science";
import { SectionHeader } from "./SectionHeader";
import client from "../../api/client";

interface Props {
  groupId: string;
}

type EnrichEvent =
  | { id: string; name: string; status: "enriched" | "skipped" | "not_found" | "error" }
  | { summary: { enriched: number; skipped: number; not_found: number; error: number } };

export function ChemicalsAdminSection({ groupId }: Props) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<EnrichEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const start = async () => {
    setRunning(true);
    setEvents([]);
    setErr(null);
    try {
      // fetch with responseType text; parse SSE manually.
      const resp = await client.post(
        `/groups/${groupId}/chemicals/enrich-pubchem`,
        { chemical_ids: null },
        { responseType: "text" },
      );
      for (const line of (resp.data as string).split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const ev = JSON.parse(line.slice(6)) as EnrichEvent;
        setEvents((prev) => [...prev, ev]);
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const summary = events.find((e) => "summary" in e) as
    | { summary: { enriched: number; skipped: number; not_found: number; error: number } }
    | undefined;
  const perChemCount = events.filter((e) => "id" in e).length;

  return (
    <Box>
      <SectionHeader
        title="Chemicals"
        subtitle="Bulk maintenance operations for this group's chemical database."
      />
      <Stack spacing={2} sx={{ maxWidth: 600 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Button
            variant="contained"
            size="small"
            startIcon={<ScienceIcon />}
            onClick={() => setOpen(true)}
          >
            Enrich missing data from PubChem
          </Button>
          <Typography variant="body2" color="text.secondary">
            Fills SMILES, molar mass, CAS, CID for chemicals that lack them.
          </Typography>
        </Stack>
      </Stack>

      <Dialog open={open} onClose={() => !running && setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Enrich chemicals from PubChem</DialogTitle>
        <DialogContent>
          {!running && !summary && (
            <Typography>This fetches missing data from PubChem for every chemical in this group that has no CID yet. Takes ~0.25s per chemical.</Typography>
          )}
          {running && (
            <Stack spacing={2}>
              <LinearProgress />
              <Typography variant="body2">{perChemCount} processed…</Typography>
            </Stack>
          )}
          {summary && (
            <Alert severity="success">
              Enriched {summary.summary.enriched}, skipped {summary.summary.skipped},
              not found {summary.summary.not_found}, errors {summary.summary.error}.
            </Alert>
          )}
          {err && <Alert severity="error">{err}</Alert>}
        </DialogContent>
        <DialogActions>
          {!running && !summary && (
            <>
              <Button onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="contained" onClick={start}>Start</Button>
            </>
          )}
          {(running || summary) && (
            <Button onClick={() => { setOpen(false); setEvents([]); }} disabled={running}>Close</Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
}
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend
npx tsc --noEmit
```

Expected: EXIT 0.

- [ ] **Step 4: Manual test**

Log in as admin. Settings → Chemicals → Enrich. Verify the dialog progresses and shows summary.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/ChemicalsAdminSection.tsx frontend/src/pages/SettingsPage.tsx frontend/src/components/settings/SettingsNav.tsx
git commit -m "feat(ui): PubChem enrichment dialog in Settings → Chemicals"
```

---

## Wrap-up tasks

### Task W.1: Full regression suite + frontend tsc + e2e

- [ ] **Step 1: Backend**

```bash
uv run pytest tests/ -q
```

Expected: all PASS. Total test count should be the prior count + ~25.

- [ ] **Step 2: Frontend**

```bash
cd frontend && npx tsc --noEmit
```

Expected: EXIT 0.

- [ ] **Step 3: E2E**

```bash
cd frontend && npx playwright test
```

Expected: all specs PASS (including `import-wizard.spec.ts` and `container-supplier.spec.ts`).

### Task W.2: Update memory

- [ ] Ask the user whether to add a memory entry about this feature (status, follow-ups). If yes, write a `project_excel_import.md` memory file and link from `MEMORY.md`.

### Task W.3: Push

- [ ] Confirm with the user before `git push origin main`.

---

## Self-review notes (for the implementer)

- **Phase order matters.** Phase 1 adds `openpyxl` which Phase 2 parsing needs — do not skip ahead.
- **Route ordering gotcha** in `routers/chemicals.py`: `/export` and `/enrich-pubchem` are fixed paths and must be declared **before** `/{chemical_id}` so FastAPI doesn't try to parse them as UUIDs.
- **Module name `import_`** (trailing underscore) is intentional — `import` is a Python reserved word. Do not rename.
- **Uvicorn reload gotcha** documented in `feedback_uvicorn_reload.md`: when the router file changes don't seem to take effect, `taskkill //F //IM python.exe && rm -rf __pycache__` and restart from the repo root with `--reload-dir src`.
- **Alembic migration** in Task 1.3 uses autogenerate. If the generated file has extra drift (unrelated columns picked up), strip those out before committing.
- **`commit_import` uses `services.containers.create_container`** which handles identifier uniqueness. The fallback retry on `DuplicateIdentifier` keeps imports robust without special-casing.
- **SSE streaming + axios buffering (Task 3.3).** axios in the browser buffers the full response before returning `resp.data`, so the enrich dialog sees all events at once rather than incrementally. The dialog shows an indeterminate `LinearProgress` during the request, then the per-chemical counts + summary when it completes. If real-time incremental progress becomes a requirement, swap to native `fetch()` + `ReadableStream` reading line-by-line — keep the same SSE format on the server.
- **Between Tasks 2.8 → 2.11 the wizard `WizardState` type accretes fields.** Task 2.10 uses `(state as any).file` as a temporary bridge until Task 2.11 pins down the final shape with explicit `file` + `columnMapping` + `quCombined` + `locations` on the `review` variant. The `as any` cast is intentional and goes away in 2.11 — do not skip 2.11.
