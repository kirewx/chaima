# Import Duplicate File Warning

## Problem

Users can accidentally import the same file twice, flooding the database with duplicate chemicals and containers. There is no feedback that a file was already imported.

## Solution

Add a lightweight import log that tracks which files have been imported per group. When a user uploads a file that was previously imported into the same group, show a warning with the previous import date and who did it. The user can confirm to proceed or cancel.

## Scope

- Import always targets the user's current `main_group_id` (no group selector in the wizard). To import into a different group, switch main group first.
- No undo/batch tracking — just a duplicate filename warning.

## Data Model

New table `import_log`:

| Column        | Type         | Notes                          |
|---------------|--------------|--------------------------------|
| id            | UUID (PK)    | Default uuid4                  |
| group_id      | UUID (FK)    | References `group.id`, indexed |
| file_name     | str          | Original upload filename       |
| imported_by   | UUID (FK)    | References `user.id`           |
| row_count     | int          | Number of rows imported        |
| created_at    | datetime(tz) | server_default=now()           |

SQLModel model: `ImportLog` in `src/chaima/models/import_log.py`.

Alembic migration to create the table.

## Backend Changes

### Preview endpoint (`POST /groups/{group_id}/import/preview`)

After parsing the file, query `import_log` for `(group_id, file_name)` ordered by `created_at DESC`, limit 1.

Add to `PreviewResponse`:
```python
previous_import: PreviousImport | None  # null if no match
```

Where `PreviousImport` is:
```python
class PreviousImport(BaseModel):
    imported_at: datetime
    imported_by_name: str
    row_count: int
```

### Commit endpoint (`POST /groups/{group_id}/import/commit`)

On successful commit (after `session.commit()`), insert an `ImportLog` row with the file name, group, user, and row count. The file name must be passed in the commit body.

Add `file_name: str` to `CommitBody`.

## Frontend Changes

### ImportSection.tsx

- Pass `file.name` through to the commit call (add to `CommitBody` type).
- After preview returns, if `previous_import` is not null, show a warning dialog before proceeding to column mapping:

  > **"reagents.xlsx" was already imported**
  > This file was imported on Apr 20, 2026 by erik@... (42 rows).
  > Importing again may create duplicate chemicals and containers.
  > [Cancel] [Import anyway]

- If user confirms, proceed normally. If cancel, reset to upload step.

### Types

Add `PreviousImport` and update `PreviewResponse` in `types/index.ts`.

## Files to Change

| File | Change |
|------|--------|
| `src/chaima/models/import_log.py` | New model |
| `src/chaima/models/__init__.py` | Register model (if needed for alembic) |
| `src/chaima/services/import_.py` | Query import_log in preview, insert on commit |
| `src/chaima/routers/import_.py` | Add `previous_import` to preview response, `file_name` to commit body |
| `frontend/src/types/index.ts` | Add `PreviousImport`, update `PreviewResponse` and `CommitBody` |
| `frontend/src/components/settings/ImportSection.tsx` | Warning dialog, pass file_name to commit |
| Alembic migration | New `import_log` table |
| Tests | Update import service/API tests |
