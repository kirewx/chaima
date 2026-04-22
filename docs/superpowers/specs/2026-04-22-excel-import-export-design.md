# Excel/CSV import + export — design

**Date:** 2026-04-22
**Status:** approved, ready for implementation plan

## Motivation

Labs joining chaima arrive with existing inventories maintained in Excel. Each lab's spreadsheet uses its own column layout and conventions — there is no canonical schema to assume. The app needs a one-time onboarding path that accepts an arbitrary Excel or CSV, maps its columns to chaima fields interactively, and commits the result atomically. The reverse direction — exporting the current chemical list as CSV or Excel — is simpler and is bundled into the same spec.

Reference for general shape: the legacy `PythonFZ/ChemData` project.

## Scope

In scope:
1. **Import wizard** in `Settings → Admin → Import data`, admin-only, 5 steps (upload → column mapping → location mapping → chemical review → commit).
2. **Export** button on the Chemicals page, CSV or XLSX, respecting current filter state.
3. **PubChem enrichment** as a separate admin action that fills missing SMILES / CID / GHS / synonyms on chemicals that lack them. Works on imported and manually-added chemicals alike.

Out of scope:
- Saved/named import templates (this is one-time onboarding per `A` in brainstorming).
- Background job queue for enrichment (runs synchronously with a streaming progress response).
- Export formats beyond CSV/XLSX (no JSON, no PDF).

## Decisions recap

| # | Decision |
|---|---|
| 1 | Usage pattern is **one-time onboarding** — no saved templates. |
| 2 | **Location-mapping step** in the wizard; user maps each distinct source-text string to an existing `StorageLocation` or creates a new one. |
| 3 | **Chemical matching** by CAS if present, else normalized name. Dedup-review step lets the user merge groups before commit. |
| 4 | Add nullable **`Container.ordered_by_name`** column. The Excel's "label" column maps to the existing `Container.identifier` (auto-generated if absent). |
| 5 | Import wizard lives in **`Settings → Admin → Import data`**, gated on `GroupAdminDep`. |

## Architecture

### Wizard flow (client-side state, stateless server)

1. **Upload.** User drops `.xlsx` or `.csv`. Client POSTs to `/import/preview`; server parses once with `openpyxl` or stdlib `csv`, returns the grid as JSON (`columns`, up to 20 preview rows, total row count, sheet list if multi-sheet, `detected_mapping` heuristic guess). No server state persists between steps — the client holds the parsed grid through the remaining steps.
2. **Column mapping.** Each source column gets mapped to one of: `name`, `cas`, `location_text`, `quantity`, `unit`, `quantity_unit_combined`, `purity`, `purchased_at`, `ordered_by`, `identifier`, `created_by_name`, `comment`, `ignore`. The server's heuristic pre-fills common German/English headers (`"Name"`, `"CAS-Nr."`, `"Menge"`, `"Behälter"`, etc.) so the user mostly confirms. Required targets: `name` + (`quantity` OR `quantity_unit_combined`).
3. **Location mapping.** The wizard lists every distinct `location_text` value. For each, the user picks an existing `StorageLocation` from the tree picker OR clicks "Create new" (name + optional parent). Same tree picker the filter drawer uses today.
4. **Chemical review.** Rows are grouped by (normalized name, CAS) and the wizard shows each group with a count, e.g. `"Ethanol × 12 containers"`. The user can merge groups manually (e.g. `"Ethanol"` + `"Ethanol 99%"` → one chemical, two sub-groups of containers). Per-row warnings also surface here: unparseable quantity, unknown unit, empty required field.
5. **Commit.** Client POSTs the fully-resolved payload to `/import/commit`. Server validates and writes in a single DB transaction. Returns a summary (`created_chemicals`, `created_containers`, `created_locations`, `skipped_rows`). On any validation error, nothing commits.

### Server endpoints

```
POST /api/v1/groups/{group_id}/import/preview          (GroupAdminDep, multipart upload)
  Body:    file (xlsx or csv, max 5 MB), optional sheet_name
  Returns: { columns: [str], rows: [[cell, ...]], row_count: int,
             sheets: [str] | null, detected_mapping: {column_name: target_field} }

POST /api/v1/groups/{group_id}/import/commit           (GroupAdminDep, json)
  Body: {
    column_mapping: {source_column: target_field},
    quantity_unit_combined_column: str | null,
    location_mapping: [{source_text: str,
                        location_id: UUID | null,
                        new_location: {name: str, parent_id: UUID | null} | null}],
    chemical_groups: [{canonical_name: str, canonical_cas: str | null,
                       row_indices: [int]}],
    rows: [[cell, ...]],   // client sends back the grid it parsed
  }
  Returns 200: { created_chemicals: int, created_containers: int,
                 created_locations: int, skipped_rows: [{index, reason}] }
  Returns 400: validation errors; nothing is written.
```

### Service layer

Pure, composable functions in `src/chaima/services/import_.py` (trailing underscore — `import` is a reserved word):

- `parse_upload(file, format, sheet_name=None) -> Grid`
- `apply_column_mapping(grid, mapping, qu_combined_column) -> list[ParsedRow]`
- `split_quantity_unit(s: str) -> tuple[float | None, str | None]`
- `group_chemicals_by_identity(rows) -> list[ChemicalGroup]`
- `detect_header_mapping(columns: list[str]) -> dict[str, str]`
- `commit_import(session, group_id, payload) -> Summary`

Each is testable standalone with fixtures. The router is thin — it delegates everything to these functions.

### Parsing details

- **File format:** `.xlsx` via `openpyxl` (new dep — add to `pyproject.toml`), `.csv` via stdlib. Max file size 5 MB, enforced in the router before parsing.
- **Quantity+unit regex:** `^\s*(-?\d+(?:[.,]\d+)?)\s*([a-zA-ZµμÅ%°]+)?\s*$` — comma-or-dot decimal, optional unit token. Unparseable cells leave amount / unit null and the row is added to `skipped_rows` with an explanation.
- **Identifier auto-gen:** missing `identifier` → call the existing container-creation service, which already auto-generates via `services/containers.py` logic (exercised by `tests/test_services/test_containers_identifier.py`).
- **Transaction scope:** the whole commit runs inside a single `async with session.begin()`. If row 412 of 500 fails validation, nothing commits.

## Data model changes

**One new column.** Alembic migration `<new rev>_add_container_ordered_by_name.py`:

- `Container.ordered_by_name: str | None` — nullable, indexed (users may filter by it later).

No other schema changes. The Excel's "label" column maps to the existing `Container.identifier`. `created_by` from Excel goes into `Container.comment` (rare field, not worth a column).

## Export

**Trigger.** Button on the Chemicals page header next to "New" → dropdown with "CSV" and "Excel". No separate Settings page.

**Endpoint:**
```
GET /api/v1/groups/{group_id}/chemicals/export?format=csv|xlsx
  Accepts the same query params as GET /chemicals (search, hazard_tag_id, ghs_code_id,
  has_containers, my_secrets, location_id, include_archived).
  Returns the file with Content-Disposition: attachment; filename="chaima-<group>-<date>.<ext>".
```

**Row format.** One row per container (symmetric with import). Chemicals with zero containers appear as one row with empty container fields, so they're still present.

**Columns (fixed order):** `name`, `cas`, `smiles`, `location`, `identifier`, `quantity`, `unit`, `purity`, `ordered_by`, `supplier`, `purchased_at`, `comment`, `ghs_codes` (semicolon-joined), `hazard_tags` (semicolon-joined), `is_archived`. Column names match import targets so an exported file is re-importable after trivial cleanup.

**Access.** Any group member — read-only, covers data the user can already see.

**Implementation.** Service `services/export.py` with `export_chemicals(session, group_id, filters, format) -> bytes`. `openpyxl` for xlsx, stdlib `csv` for csv. Buffer in memory (no streaming). Hard cap: 10 000 rows → 413 with a message asking the user to narrow filters.

## PubChem enrichment (follow-on feature)

Separate from the import pipeline so it also benefits manually-added chemicals.

**Trigger.** Button in `Settings → Admin → Chemicals` titled "Enrich missing data from PubChem". Also a row-level "Enrich" icon in the chemical detail panel. Admin-only.

**Endpoint:**
```
POST /api/v1/groups/{group_id}/chemicals/enrich-pubchem           (GroupAdminDep)
  Body: { chemical_ids: [UUID] | null }     // null = all in group missing cid
  Returns a text/event-stream: one event per chemical with { id, status, ... }
  Final event: { summary: { enriched, not_found, errors: [...] } }
```

**Behavior per chemical:**
1. Skip if `cid` is already set (already enriched).
2. Look up by `cas` if present, else by `name`, via `services/pubchem.py:lookup`.
3. On match: fill only the fields currently `NULL` — never overwrites user data. Fields touched: `cid`, `smiles`, `molar_mass`, `synonyms` (append missing), `ghs_codes` (append missing).
4. On 404 / upstream error: record in `errors`, continue.

**Rate limiting.** PubChem PUG REST tolerates ~5 req/sec. Service iterates with `await asyncio.sleep(0.25)` between calls. 500-chemical enrichment takes ≈ 2 minutes; the streaming response drives a progress bar in the UI.

**UI.** Modal dialog with progress bar + running counts ("312 / 500 — found 287, not found 25"). Final state shows the errors list if any. The modal blocks while running; cancel-button aborts further calls but keeps already-persisted changes.

## Testing

### Backend unit tests — `tests/test_services/test_import.py`

- `split_quantity_unit`: `"250 mL"`, `"1,5 L"`, `"5"`, `"some text"`, `""`, `"0.1 µmol"`.
- `apply_column_mapping`: ignore columns, missing required target, conflicting targets on two columns.
- `group_chemicals_by_identity`: merges by CAS when present, falls back to normalized name, treats whitespace + case as equal.
- `detect_header_mapping`: common German/English headers pre-fill correctly (`"Name"`, `"Menge"`, `"Behälter"`, `"CAS-Nr."`, `"Standort"`, `"Lieferant"`, etc.).

### Backend API tests — `tests/test_api/test_import.py`

- `preview`: xlsx happy path, csv happy path, multi-sheet `.xlsx` with `sheet_name` selection, oversized-file (>5 MB) rejection with 413, non-admin rejection with 403.
- `commit`: full happy path against `tests/fixtures/import_sample.xlsx` (~20 rows covering every edge case). Partial-failure rollback: inject a bad row, assert zero rows in DB afterward. Missing required column mapping → 400.

### Backend API tests — `tests/test_api/test_export.py`

- csv and xlsx happy paths (parse returned bytes to verify columns + rows).
- Filter params flow through: `?has_containers=true&location_id=...` produces the right subset.
- Oversized-group → 413.
- Filename header correct: `attachment; filename="chaima-<group>-<YYYY-MM-DD>.xlsx"`.

### Backend API tests — `tests/test_api/test_pubchem_enrich.py`

- Uses existing PubChem test doubles from `test_services/test_pubchem.py`.
- Only-null-fields overwritten: chemical with existing `smiles` keeps it untouched.
- `not_found` surfaces in the final summary event.
- Empty `chemical_ids` selects all group chemicals missing `cid`.

### Frontend

- `tsc --noEmit` clean.
- One Playwright e2e: `frontend/e2e/import-wizard.spec.ts` — upload fixture → map columns → map locations → review → commit → verify rows on `/chemicals`.
- No component unit tests. Wizard state is thin; e2e covers the happy path end-to-end.

### Fixtures

- `tests/fixtures/import_sample.xlsx` — committed. Covers:
  - mixed qty+unit cell ("250 mL" in one column, separate qty/unit in another)
  - same chemical across rows, CAS in one row missing in another
  - two spellings of the same location (`"fridge 0.728"`, `"Fridge 0.728"`)
  - row with no identifier (tests auto-gen)
  - row missing optional columns
  - one unparseable quantity (tests `skipped_rows` reporting)

## Open questions (for implementation plan, not blockers)

- Should the commit endpoint accept streaming progress, too? Probably not needed for a 5 MB file cap — commit is fast once validated. Keep it as a single blocking request.
- Cancel/abort during import? Since commit is atomic, "cancel" pre-commit is just "close the wizard". No server-side abort needed.
- Re-import / dedup across imports? v1 treats each import as fresh: same-named chemical in a second import creates a duplicate. Accepting that because onboarding is one-time. If it becomes a pain, the chemical-review step already has the merge UX — can extend to merge against existing DB rows in a future iteration.
