# SDS Link (`sds_url`) with Fetch-and-Archive

## Problem

Chemicals can only carry a safety data sheet as an uploaded PDF (`sds_path`). External chemical lists often already contain SDS *links* (Dropbox share links, vendor SDS pages). Today those links cannot be stored, and the import wizard silently drops SDS columns. Relying on the links alone is fragile: share links belong to third-party accounts and rot, and most external hosts cannot be embedded for in-app viewing.

## Solution

Add an `sds_url` field alongside `sds_path` — the URL is the *source reference*, the stored PDF is what the app *displays*. A server-side fetch action downloads the PDF from the URL once and archives it into the existing upload storage (`sds_path`), so viewing works in-app through the existing authenticated stream endpoint regardless of the external host. A group-level batch action fetches all missing PDFs after an import. The import wizard gains an `sds_url` column target.

The upload feature stays unchanged. Nothing is removed.

## Scope

- `sds_url` is a plain reference field; no live proxying of external URLs.
- The import does NOT trigger PDF fetching; that is a separate admin batch action.
- No re-fetch/refresh of already archived PDFs: once `sds_path` is set, the fetch action skips the chemical (409 / batch-skip). Replacing an archived PDF is done via the existing manual upload ("Replace").

## Data Model

`Chemical` gains one column:

| Column  | Type              | Notes                        |
|---------|-------------------|------------------------------|
| sds_url | str \| None (2000) | Source URL of the SDS PDF   |

Additive Alembic migration (add column, nullable, no default). `sds_path` is untouched.

## Backend Changes

### Schemas (`schemas/chemical.py`)

`sds_url` added to `ChemicalCreate`, `ChemicalUpdate`, `ChemicalRead` (and the container-detail read model, mirroring `sds_path`). Validation on create/update: if set and non-empty, must start with `http://` or `https://` after stripping, max length 2000 → otherwise 422. Empty string normalizes to `None`.

### Fetch endpoint (single)

`POST /api/v1/groups/{group_id}/chemicals/{chemical_id}/sds-fetch` — `GroupAdminDep` (same gate as the SDS upload).

Behavior:
1. 409 if the chemical has no `sds_url`; 409 if `sds_path` is already set (fill-only — replace by uploading manually).
2. Download the URL server-side and store the result via `files_service.save_upload` into `sds_path`, exactly like the upload endpoint.
3. Return the updated chemical.

Fetch rules (shared helper, e.g. `services/sds_fetch.py`):
- Scheme must be http/https.
- SSRF guard: resolve the hostname and reject private, loopback, link-local, and reserved addresses; re-validate every redirect hop; max 5 redirects.
- Timeout ~15 s, size cap 20 MB (streamed, aborted when exceeded).
- Dropbox rewrite: for `dropbox.com` share URLs, force `dl=1` at fetch time (stored `sds_url` stays as entered).
- Accept the body only if `Content-Type` is `application/pdf` **or** the body starts with `%PDF-`.
- Failures map to 502 with a human-readable reason (blocked host, not a PDF, too large, timeout, upstream error). The URL stays usable as a plain external link.

### Batch fetch (group)

`POST /api/v1/groups/{group_id}/chemicals/fetch-sds` — `GroupAdminDep`, SSE stream following the PubChem enrichment pattern (`routers/chemicals.py` enrich/refetch endpoints).

- Selects chemicals in the group with `sds_url` set and `sds_path IS NULL`.
- Processes sequentially; one progress event per chemical (fetched / failed + reason); failures do not abort the run.
- Final summary event: fetched / failed / skipped counts.

### Import wizard

- New target `sds_url` in `_HEADER_PATTERNS` (`services/import_.py`) and `IMPORT_TARGETS` (frontend types). Patterns, inserted above the generic entries: `sicherheitsdatenblatt`, `datenblatt`, `sds`.
- Commit: cell values are stripped; `""` and `"-"` count as empty (silently ignored). Non-empty values not starting with http(s) produce a row *warning* (not an error) and are ignored. Valid URLs are set on newly created chemicals; for existing chemicals (name-dedup path) the URL is backfilled only when `sds_url` is empty — never overwritten.
- Export: add `sds_url` to `EXPORT_COLUMNS` (`services/export.py`) so export → import round-trips (the `sds_url` header matches the `sds` pattern).

## Frontend Changes

### ChemicalInfoBox

Display states:
1. `sds_path` set → "Safety data sheet" stream link as today; if `sds_url` is also set, a small source row (external-link icon, opens in new tab, `rel="noopener noreferrer"`).
2. Only `sds_url` → external link row + admin button "Fetch PDF" calling the single-fetch endpoint (spinner while pending, inline error on failure); on success the stored-PDF link appears.
3. Neither → unchanged today's behavior (research links + upload button). The research-links condition extends from `!sds_path` to `!sds_path && !sds_url`.

### ChemicalForm (drawer)

Text field "SDS-Link (URL)" on create and edit, with lightweight client validation (http/https), mapped to `sds_url`.

### ChemicalsAdminSection

New streaming action button "Fetch missing SDS PDFs" next to the enrichment buttons, wired to the batch SSE endpoint with the same progress UI pattern.

### Types / hooks

`sds_url` on the `Chemical` type; `useFetchSds` mutation hook; batch-stream hook following the existing enrichment stream helpers.

## Files to Change

| File | Change |
|------|--------|
| `src/chaima/models/chemical.py` | Add `sds_url` column |
| Alembic migration | Add column |
| `src/chaima/schemas/chemical.py` | Add + validate `sds_url` in create/update/read |
| `src/chaima/services/chemicals.py` | Persist `sds_url` on create/update |
| `src/chaima/services/sds_fetch.py` | New: guarded download helper (SSRF, size, type, Dropbox rewrite) |
| `src/chaima/routers/chemicals.py` | `sds-fetch` (single) + `fetch-sds` (batch SSE) endpoints |
| `src/chaima/services/import_.py` | `sds_url` header patterns + commit handling (fill-only, `-` handling) |
| `src/chaima/services/export.py` | Add `sds_url` to `EXPORT_COLUMNS` |
| `frontend/src/types/index.ts` | `sds_url` on `Chemical`, new import target |
| `frontend/src/api/hooks/useChemicals.ts` | `useFetchSds` + batch stream hook |
| `frontend/src/components/ChemicalInfoBox.tsx` | Display states, fetch button, research-link condition |
| `frontend/src/components/drawer/ChemicalForm.tsx` | URL text field |
| `frontend/src/components/settings/ChemicalsAdminSection.tsx` | Batch button |
| Tests | See below |

## Testing

- Schema: valid http/https accepted, `javascript:`/garbage → 422, empty → None.
- Import service: header detection (the long German SDS header matches), commit sets `sds_url`, `-`/empty ignored silently, junk value → warning, fill-only on existing chemicals; export column present.
- Fetch helper (mocked transport): success stores PDF; non-PDF rejected; over-size aborted; private/loopback host blocked; redirect to private host blocked; Dropbox `dl=0` → `dl=1` rewrite.
- API: single fetch happy path + 409s + admin gate; batch SSE emits per-item and summary events, failures don't abort.
- E2E: info box shows external link and fetch button when only `sds_url` is set; stored-PDF link after fetch (mocked); form field round-trip. (The 9 pre-existing red e2e tests on main are unrelated and stay untouched.)
