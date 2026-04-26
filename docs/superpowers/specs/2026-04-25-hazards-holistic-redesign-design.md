# Hazards Holistic Redesign

## Problem

Hazard data exists in the database but is poorly surfaced and not fully editable.

- **GHS pictograms** render at 40px in the right sidebar of the chemical info card, but the entire "Hazards" block is hidden when a chemical has no GHS codes and no tags — so chemicals without PubChem data show no hazard affordance at all. There is no signal-word indication.
- **Hazard tags** can be created, edited, and deleted in Settings (`HazardTagsSection.tsx`), but cannot be attached to a chemical anywhere in the UI. The backend endpoint `PUT /chemicals/{cid}/hazard-tags` exists; nothing calls it.
- **Hazard tag incompatibilities** are modelled (`HazardTagIncompatibility` with `tag_a_id`, `tag_b_id`, `reason`) and have full CRUD endpoints, but Settings has a TODO comment instead of UI.
- **Storage compatibility** between chemicals (e.g., flammable in a cabinet that holds an oxidizer) is unenforced and unsurfaced.

## Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Scope | Throw out the older "GHS-aware features + AI vision" plan; redesign hazards holistically across four surfaces. Vision/structure-dialog/empty-search CTAs become separate specs. |
| 2 | Data model | Keep GHS codes (international, auto-fetched) and hazard tags (group-scoped, manual) as **independent** layers. No unification. |
| 3 | Card display | **Keep the sidebar location** at 40px. Add a Danger/Warning signal-word chip; show an empty-state panel when no hazard data exists. |
| 4 | Tag assignment surface | **Admin-only debug panel** in Settings. Not exposed to regular users. No tag picker in the chemical drawer form. |
| 5 | Storage-warning severity | **Warn-only.** Save remains enabled; the user can override. No hard blocks, no override-reason field. |

## Section 1 — Card display

**File:** `frontend/src/components/ChemicalInfoBox.tsx`

Current state (line 205): the entire "Hazards" sidebar block is gated by `(ghsCodes.length > 0 || hazardTags.length > 0)`.

Changes:

1. **Signal-word chip.** Above the existing `GHSPictogramRow` (line 212), render a small MUI `Chip` derived from the worst signal word across `ghsCodes`:
   - any code with `signal_word === "Danger"` → `<Chip label="Danger" color="error" size="small" />`
   - else any with `"Warning"` → `<Chip label="Warning" color="warning" size="small" />`
   - else no chip.
2. **Empty state.** Replace the current gating with always-render. When both arrays are empty, show:
   - a muted `Typography` saying "No hazard data"
   - for admins, a small `Button` "Manage in Settings" routing to `/settings#chemicals-admin` (anchor to the admin assignment subsection added in Section 2)
   - non-admins see "No hazard data" with no button.

Pictogram size stays at 40px. Tag chips keep their current `HazardTagChips` rendering.

## Section 2 — Admin chemical hazard assignment (debug)

**File:** extend `frontend/src/components/settings/ChemicalsAdminSection.tsx`. Add a new subsection beneath the existing "Enrich from PubChem" block, titled **"Assign hazards (debug)"**.

UI:
- Chemical search field (autocomplete against `GET /groups/{gid}/chemicals?search=`).
- On selection, fetch the chemical detail and render its current GHS codes + hazard tags as removable chips.
- Two MUI `Autocomplete multiple` pickers:
  - **GHS codes** — populated from the existing global `GET /api/v1/ghs-codes` endpoint (new hook `useGHSCodes()` mirroring the pagination pattern in `useHazardTags`).
  - **Hazard tags** — populated from `useHazardTags(groupId)`.
- A single **Save** button.

Save handler:
- Calls existing `PUT /chemicals/{cid}/hazard-tags` with `{ hazard_tag_ids: [...] }`.
- Calls existing `PUT /chemicals/{cid}/ghs-codes` with `{ ghs_ids: [...] }`.
- Both requests in parallel; show one combined success/error.

Visibility: section header only renders when the current user has `is_system_admin` or the group-admin role (match the existing pattern in `ChemicalsAdminSection.tsx`). No backend changes — the section is debug-only by virtue of admin gating.

## Section 3 — Tag incompatibilities UI

**File:** extend `frontend/src/components/settings/HazardTagsSection.tsx`. Remove the TODO from the section subtitle (line 47).

Per-row change in the existing tag list (around line 76): add a third icon button **"Manage incompatibilities"** between Edit and Delete. Click opens a new `IncompatibilityDialog`:

- Title: `Incompatibilities for "{tagName}"`.
- Body:
  - List of current incompatibilities for this tag — each row shows the other tag's name, the optional `reason`, and a "Remove" icon. Backed by `GET /groups/{gid}/hazard-tags/incompatibilities` (filter client-side to those involving this tag).
  - "Add incompatibility" form: an `Autocomplete` of other tags in the group + an optional `reason` `TextField` + Add button.
- Add → `POST /hazard-tags/incompatibilities` with `{ tag_a_id, tag_b_id, reason }`.
- Remove → `DELETE /hazard-tags/incompatibilities/{id}`.

No new backend endpoints. New frontend hook `useHazardTagIncompatibilities(groupId)` mirroring `useHazardTags`.

## Section 4 — Backend compatibility engine

**New file:** `src/chaima/services/hazard_compatibility.py`. Pure functions, no DB writes; takes a `Session` only for the tag-incompatibility query.

Two public functions:

```python
def pair_conflicts(
    session: Session,
    group_id: UUID,
    a_codes: list[GHSCode], a_tags: list[HazardTag], a_name: str,
    b_codes: list[GHSCode], b_tags: list[HazardTag], b_name: str,
) -> list[Conflict]:
    """All reasons chemicals A and B should not share storage."""

def location_conflicts(
    session: Session, group_id: UUID, location_id: UUID,
) -> list[Conflict]:
    """Pairwise conflicts among all chemicals stored under this location subtree."""
```

`Conflict` is a simple dataclass: `chem_a_name, chem_b_name, kind ("ghs" | "tag"), code_or_tag, reason`.

Rule sources:

1. **Hardcoded GHS pairs (v1, conservative):**
   - GHS02 (flammable) ↔ GHS03 (oxidizer) — Fire/explosion risk
   - GHS01 (explosive) ↔ GHS02 / GHS03 — Detonation risk
   - GHS05 (corrosive): split into acid-leaning vs base-leaning by name regex (`acid` / `hydroxide`, `amine`) plus H-code `H290` if available; if undetermined, treat as "corrosive (unspecified)" and warn against any other corrosive.
2. **Tag pairs from DB:** join `HazardTagIncompatibility` for the chemicals' tags. The model's `reason` field flows through to the conflict.

Acid/base discrimination is documented as a known limitation; v2 can add an explicit `acid_base` enum on `Chemical`.

**New endpoints** in a new router file `src/chaima/routers/compatibility.py` mounted at `/groups/{gid}`:

- `GET /locations/{lid}/conflicts` → `list[Conflict]`
- `GET /compatibility/check?chemical_id={cid}&location_id={lid}` → `list[Conflict]` (predicts what would conflict if `cid` were placed under `lid`)

Both reuse `hazard_compatibility.py`. Group-membership dependency is the existing one.

## Section 5 — Storage warning surfaces

**File:** location detail view inside `frontend/src/pages/StoragePage.tsx` (exact JSX path confirmed during implementation).

- New `useLocationConflicts(groupId, locationId)` hook calls `/locations/{lid}/conflicts`.
- Render an MUI `Alert severity="warning"` banner above the location's container list when conflicts is non-empty. One bullet per conflict: `"⚠ {a} ({reason}) and {b} ({reason}) should not share storage"`.
- Hides cleanly when conflicts is empty.

**File:** `frontend/src/components/drawer/ContainerForm.tsx`.

- Watch `location_id`. On change, debounced 250 ms, fire `/compatibility/check?chemical_id=...&location_id=...`.
- Render a thin `Alert severity="warning"` above the Save row when the response is non-empty. Save remains enabled (warn-only per decision 5).
- New hook `useCompatibilityCheck(groupId, chemicalId, locationId)` built with TanStack Query (`useQuery`), with `placeholderData: keepPreviousData` so the warning doesn't flicker while debouncing.

## Files to change

| File | Change |
|---|---|
| `frontend/src/components/ChemicalInfoBox.tsx` | Signal-word chip; empty-state panel; ungate the Hazards block. |
| `frontend/src/components/settings/ChemicalsAdminSection.tsx` | Add "Assign hazards (debug)" subsection. |
| `frontend/src/components/settings/HazardTagsSection.tsx` | Add per-row "Manage incompatibilities" button + dialog; remove TODO. |
| `frontend/src/components/drawer/ContainerForm.tsx` | Inline conflict warning on location change. |
| `frontend/src/pages/StoragePage.tsx` | Conflict banner on location detail view. |
| `frontend/src/api/hooks/useHazardTagIncompatibilities.ts` | **New** — list/create/delete hooks. |
| `frontend/src/api/hooks/useGHSCodes.ts` | **New** — global list hook used by the admin picker. |
| `frontend/src/api/hooks/useCompatibility.ts` | **New** — `useLocationConflicts` and `useCompatibilityCheck`. |
| `frontend/src/types/index.ts` | New `Conflict`, `IncompatibilityRead`, `IncompatibilityCreate` types. |
| `src/chaima/services/hazard_compatibility.py` | **New** — rules engine. |
| `src/chaima/routers/compatibility.py` | **New** — two endpoints, mounted in `main.py`. |
| `src/chaima/main.py` | Register the new router. |

## Out of scope

- Structure-thumbnail click-to-zoom (deferred to a separate spec).
- AI vision label scan with Google Gemini (deferred).
- Empty-search Create + Order CTAs (deferred).
- A user-facing tag picker in `ChemicalForm.tsx` (decision 4: debug-only via Settings).
- An "override reason" field on container conflicts (decision 5: plain warn-only).

## Test plan

**Backend:**
- Unit tests for `hazard_compatibility.py`: flammable+oxidizer, acid+base, explosive+heat, two unrelated chemicals (no conflict), tag-incompatibility-only, mixed GHS+tag.
- Router tests for the two new endpoints: empty result, single conflict, multiple conflicts.

**Frontend (manual):**
- Open a chemical with PubChem GHS data → sidebar shows pictograms + a Danger or Warning chip.
- Open a chemical with no GHS and no tags → sidebar shows "No hazard data" panel. As admin, "Manage in Settings" button is visible and routes to the assignment screen.
- Settings → Chemicals admin → search a chemical, attach two tags + one GHS code, save → reload chemical, sidebar reflects changes.
- Settings → Hazard tags → on a tag, add an incompatibility against another tag with reason → reopen dialog, the row appears.
- Place a flammable container into a cabinet that already holds an oxidizer (via the placement form) → inline warning appears, Save still enabled, container is created.
- Open the cabinet's location detail view → banner lists the conflict.
