# Filter Drawer & Three-Dot Menu Fix — Design Spec

**Date:** 2026-04-16

## Overview

Two changes to the chemicals page:

1. Fix the three-dot overflow menu overlapping content on mobile viewports.
2. Wire up the filter drawer with four working filters: has stock, my secrets, storage location, and groups.

---

## 1. Three-Dot Menu Fix

### Problem

`ChemicalMenu` is positioned `absolute; top: 10; right: 10` inside `ChemicalInfoBox`. On narrow screens the button covers the molar mass value and other properties.

### Fix

Move to `bottom: 10; right: 10`. Same absolute positioning, just anchored to the bottom-right corner of the card. No structural changes to the component tree.

**File:** `frontend/src/components/ChemicalInfoBox.tsx` (line 53)

---

## 2. Filter Drawer

### Filter Order

1. **Has stock + My secrets** — side-by-side toggle switches on one row
2. **Storage location** — tree picker dropdown + "No location assigned" checkbox
3. **Groups** — chip multi-select (only shown when user belongs to multiple groups)

Existing sections (hazard tags, GHS codes, sort/order) are removed from the drawer for now. Sort/order stays at defaults (name, ascending). The "Include archived" toggle is removed from the drawer since it's already in FilterBar as a chip — or it can stay; user preference.

### FilterState Changes

```typescript
export interface FilterState {
  includeArchived: boolean;
  hasContainers: boolean | undefined;
  mySecrets: boolean;
  locationId: string | undefined;
  noLocation: boolean;
  selectedGroupIds: string[];
  sort: string;
  order: "asc" | "desc";
}
```

Dropped: `hazardTagId`, `ghsCodeId` (not needed yet).
Added: `mySecrets`, `locationId`, `noLocation`.

### FilterDrawer UI

- **Has stock** — `Switch`, label "Has stock", subtitle "Only chemicals with active containers"
- **My secrets** — `Switch`, label "My secrets", subtitle "Show only my secret chemicals"
- Both on the same row, equal width.
- **Storage location** — label "Storage location". A select/picker that opens the existing `LocationPicker` tree component. Below it, a checkbox "No location assigned" that filters to chemicals whose containers have no `location_id`.
- **Groups** — label "Groups". Chip row with each group the user belongs to. Tapping toggles selection. At least one group must remain selected. Only shown when user belongs to >1 group.
- **Apply** button at the bottom closes the drawer and applies filters.

### FilterBar Chips

Active filters render as removable chips in the `FilterBar`:
- "In stock" when `hasContainers === true`
- "My secrets" when `mySecrets === true`
- "Location: {name}" when `locationId` is set
- "No location" when `noLocation === true`
- "Including archived" when `includeArchived === true`
- Group names are not shown as chips (the multi-select is the primary UI).

### Backend Changes

**Router:** `src/chaima/routers/chemicals.py` — add query parameters:

```python
my_secrets: bool = Query(False)
location_id: UUID | None = Query(None)
no_location: bool = Query(False)
```

**Service:** `src/chaima/services/chemicals.py` — `list_chemicals()`:

- `my_secrets=True`: filter to `Chemical.is_secret == True` AND `Chemical.created_by == viewer.id`. This bypasses the normal `apply_secret_filter` which hides other users' secrets — here we explicitly want only the viewer's own secrets.
- `location_id`: join through `Container` and filter `Container.location_id == location_id` (only chemicals that have at least one container at this location).
- `no_location=True`: join through `Container` and filter `Container.location_id.is_(None)` (chemicals with at least one container that has no assigned location).

**Frontend types:** `frontend/src/types/index.ts` — add `my_secrets`, `location_id`, `no_location` to `ChemicalSearchParams`.

**Frontend hook:** `frontend/src/api/hooks/useChemicals.ts` — pass new params through to the API call.

### Multi-Group View

When multiple groups are selected in the filter, use the existing `useMultiGroupChemicals` hook which fetches from each group in parallel and merges results. When only one group is selected, use the standard `useChemicals` hook.

`ChemicalsPage` switches between the two based on `filters.selectedGroupIds.length`.

---

## Files Affected

| File | Change |
|------|--------|
| `frontend/src/components/ChemicalInfoBox.tsx` | Move menu to bottom-right |
| `frontend/src/components/FilterDrawer.tsx` | Rewrite filter sections |
| `frontend/src/components/FilterBar.tsx` | Add chip types for new filters |
| `frontend/src/pages/ChemicalsPage.tsx` | Wire filter state to hooks, multi-group switching |
| `frontend/src/api/hooks/useChemicals.ts` | Pass new filter params |
| `frontend/src/types/index.ts` | Update `ChemicalSearchParams` |
| `src/chaima/routers/chemicals.py` | Add `my_secrets`, `location_id`, `no_location` params |
| `src/chaima/services/chemicals.py` | Implement new filters in `list_chemicals` |

## Out of Scope

- Hazard tag and GHS code filters (deferred)
- Sort/order UI (keep defaults)
- Storage location CRUD (already exists)
