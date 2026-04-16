# Filter Drawer & Three-Dot Menu Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the three-dot menu mobile overlap, and wire up four working filters in the filter drawer (has stock, my secrets, storage location, groups).

**Architecture:** Backend gets three new query params on `list_chemicals` (`my_secrets`, `location_id`, `no_location`). Frontend `FilterDrawer` is rewritten with the four filters, `FilterState` updated, and `ChemicalsPage` wires filter state through to the API hooks. Multi-group view uses the existing `useMultiGroupChemicals` hook.

**Tech Stack:** FastAPI, SQLModel, React, MUI v9, TanStack Query

**Spec:** `docs/superpowers/specs/2026-04-16-filter-drawer-and-menu-fix-design.md`

---

### Task 1: Three-dot menu — move to bottom-right

**Files:**
- Modify: `frontend/src/components/ChemicalInfoBox.tsx:53`

- [ ] **Step 1: Move the menu position**

In `frontend/src/components/ChemicalInfoBox.tsx`, change line 53 from:

```tsx
<Box sx={{ position: "absolute", top: 10, right: 10, zIndex: 2 }}>
```

to:

```tsx
<Box sx={{ position: "absolute", bottom: 10, right: 10, zIndex: 2 }}>
```

- [ ] **Step 2: Verify in browser**

Open a chemical's expanded view on a narrow viewport (< 600px). Confirm the three-dot menu sits at the bottom-right corner and does not overlap the molar mass or other property values.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ChemicalInfoBox.tsx
git commit -m "fix(ui): move three-dot menu to bottom-right to prevent mobile overlap"
```

---

### Task 2: Backend — add `my_secrets`, `location_id`, `no_location` filters

**Files:**
- Modify: `src/chaima/services/chemicals.py:216-317` (the `list_chemicals` function)
- Modify: `src/chaima/routers/chemicals.py:51-118` (the `list_chemicals` endpoint)
- Test: `tests/test_services/test_chemicals.py`
- Test: `tests/test_api/test_chemicals.py`

- [ ] **Step 1: Write failing service-layer tests**

Add to `tests/test_services/test_chemicals.py`:

```python
async def test_list_chemicals_my_secrets(session, group, user, other_user, membership):
    """my_secrets=True returns only the viewer's own secret chemicals."""
    await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Secret A", is_secret=True,
    )
    await chemical_service.create_chemical(
        session, group_id=group.id, created_by=other_user.id, name="Secret B", is_secret=True,
    )
    await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Public C",
    )
    await session.commit()

    items, total = await chemical_service.list_chemicals(
        session, group_id=group.id, viewer=user, my_secrets=True,
    )
    assert total == 1
    assert items[0].name == "Secret A"


async def test_list_chemicals_location_filter(session, group, user, membership):
    """location_id filters to chemicals with a container at that location."""
    from chaima.models.container import Container
    from chaima.models.storage import StorageLocation

    loc = StorageLocation(name="Shelf A", kind="shelf")
    session.add(loc)
    await session.flush()

    chem_a = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol",
    )
    chem_b = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Acetone",
    )
    session.add(Container(
        chemical_id=chem_a.id, group_id=group.id, created_by=user.id,
        location_id=loc.id, identifier="E-001", amount=1.0, unit="L",
    ))
    session.add(Container(
        chemical_id=chem_b.id, group_id=group.id, created_by=user.id,
        location_id=loc.id, identifier="A-001", amount=0.5, unit="L",
    ))
    await session.commit()

    items, total = await chemical_service.list_chemicals(
        session, group_id=group.id, viewer=user, location_id=loc.id,
    )
    assert total == 2
    names = {i.name for i in items}
    assert names == {"Ethanol", "Acetone"}


async def test_list_chemicals_no_location(session, group, user, membership):
    """no_location=True returns chemicals with at least one unlocated container."""
    from chaima.models.container import Container
    from chaima.models.storage import StorageLocation

    loc = StorageLocation(name="Shelf B", kind="shelf")
    session.add(loc)
    await session.flush()

    chem_a = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Ethanol",
    )
    chem_b = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Acetone",
    )
    # chem_a has a container WITH a location
    session.add(Container(
        chemical_id=chem_a.id, group_id=group.id, created_by=user.id,
        location_id=loc.id, identifier="E-001", amount=1.0, unit="L",
    ))
    # chem_b has a container WITHOUT a location
    session.add(Container(
        chemical_id=chem_b.id, group_id=group.id, created_by=user.id,
        location_id=None, identifier="A-001", amount=0.5, unit="L",
    ))
    await session.commit()

    items, total = await chemical_service.list_chemicals(
        session, group_id=group.id, viewer=user, no_location=True,
    )
    assert total == 1
    assert items[0].name == "Acetone"
```

Note: `other_user` fixture already exists in `conftest.py`. The `Container` model requires `location_id` — check if it's nullable. If not, skip the `no_location` container test for now and handle in step 3.

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_services/test_chemicals.py::test_list_chemicals_my_secrets tests/test_services/test_chemicals.py::test_list_chemicals_location_filter tests/test_services/test_chemicals.py::test_list_chemicals_no_location -v
```

Expected: FAIL — `list_chemicals()` does not accept `my_secrets`, `location_id`, or `no_location` params yet.

- [ ] **Step 3: Implement service-layer filters**

In `src/chaima/services/chemicals.py`, update the `list_chemicals` function signature to add three new parameters:

```python
async def list_chemicals(
    session: AsyncSession,
    group_id: UUID,
    viewer: User,
    *,
    search: str | None = None,
    hazard_tag_id: UUID | None = None,
    ghs_code_id: UUID | None = None,
    has_containers: bool | None = None,
    my_secrets: bool = False,
    location_id: UUID | None = None,
    no_location: bool = False,
    include_archived: bool = False,
    sort: str = "name",
    order: str = "asc",
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Chemical], int]:
```

Add the filter logic after the existing `has_containers` block (around line 302) and before `apply_secret_filter`:

```python
    if my_secrets:
        query = query.where(Chemical.is_secret.is_(True), Chemical.created_by == viewer.id)

    if location_id is not None:
        loc_exists = (
            select(Container.id)
            .where(
                Container.chemical_id == Chemical.id,
                Container.location_id == location_id,
            )
            .correlate(Chemical)
            .exists()
        )
        query = query.where(loc_exists)

    if no_location:
        no_loc_exists = (
            select(Container.id)
            .where(
                Container.chemical_id == Chemical.id,
                Container.location_id.is_(None),  # type: ignore[union-attr]
            )
            .correlate(Chemical)
            .exists()
        )
        query = query.where(no_loc_exists)
```

If `location_id` is non-nullable on `Container`, you'll need to make it nullable first with an alembic migration — but based on the model it's `uuid_pkg.UUID = Field(...)` without `| None`, so check whether containers can exist without a location. If the field is required, the `no_location` filter won't match any rows — skip that filter for now and note it as a follow-up.

- [ ] **Step 4: Run service tests to verify they pass**

```bash
pytest tests/test_services/test_chemicals.py -v
```

Expected: All pass including the three new tests.

- [ ] **Step 5: Write failing API-layer test**

Add to `tests/test_api/test_chemicals.py`:

```python
async def test_list_chemicals_my_secrets_filter(client, session, group, membership, user):
    session.add(Chemical(group_id=group.id, name="My Secret", created_by=user.id, is_secret=True))
    session.add(Chemical(group_id=group.id, name="Public", created_by=user.id))
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/chemicals?my_secrets=true")
    assert resp.status_code == 200
    page = PaginatedResponse[ChemicalRead].model_validate(resp.json())
    assert page.total == 1
    assert page.items[0].name == "My Secret"
```

- [ ] **Step 6: Update the router to pass new params**

In `src/chaima/routers/chemicals.py`, add the three query parameters to `list_chemicals`:

```python
async def list_chemicals(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    user: CurrentUserDep,
    search: str | None = Query(None),
    hazard_tag_id: UUID | None = Query(None),
    ghs_code_id: UUID | None = Query(None),
    has_containers: bool | None = Query(None),
    my_secrets: bool = Query(False),
    location_id: UUID | None = Query(None),
    no_location: bool = Query(False),
    include_archived: bool = Query(False),
    sort: str = Query("name"),
    order: str = Query("asc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ChemicalRead]:
```

And pass them through to the service call:

```python
    items, total = await chemical_service.list_chemicals(
        session,
        group_id,
        viewer=user,
        search=search,
        hazard_tag_id=hazard_tag_id,
        ghs_code_id=ghs_code_id,
        has_containers=has_containers,
        my_secrets=my_secrets,
        location_id=location_id,
        no_location=no_location,
        include_archived=include_archived,
        sort=sort,
        order=order,
        offset=offset,
        limit=limit,
    )
```

- [ ] **Step 7: Run all tests**

```bash
pytest tests/test_services/test_chemicals.py tests/test_api/test_chemicals.py -v
```

Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add src/chaima/services/chemicals.py src/chaima/routers/chemicals.py tests/test_services/test_chemicals.py tests/test_api/test_chemicals.py
git commit -m "feat(chemicals): add my_secrets, location_id, no_location filter params"
```

---

### Task 3: Frontend types and hook — pass new filter params

**Files:**
- Modify: `frontend/src/types/index.ts:265-273`
- Modify: `frontend/src/api/hooks/useChemicals.ts:7-19`

- [ ] **Step 1: Update ChemicalSearchParams**

In `frontend/src/types/index.ts`, replace the `ChemicalSearchParams` interface:

```typescript
export interface ChemicalSearchParams {
  search?: string;
  hazard_tag_id?: string;
  ghs_code_id?: string;
  has_containers?: boolean;
  my_secrets?: boolean;
  location_id?: string;
  no_location?: boolean;
  sort?: "name" | "created_at" | "updated_at" | "cas";
  order?: "asc" | "desc";
  limit?: number;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add my_secrets, location_id, no_location to ChemicalSearchParams"
```

---

### Task 4: Rewrite FilterDrawer

**Files:**
- Modify: `frontend/src/components/FilterDrawer.tsx`
- Modify: `frontend/src/components/FilterBar.tsx`

- [ ] **Step 1: Update FilterState and FilterDrawer props**

Rewrite `frontend/src/components/FilterDrawer.tsx` with the new filter layout. The complete replacement:

```tsx
import { useState } from "react";
import {
  SwipeableDrawer, Drawer, Box, Typography, Switch, FormControlLabel,
  Chip, Stack, Button, Divider, Checkbox, TextField, MenuItem,
  useMediaQuery, useTheme,
} from "@mui/material";
import type { GroupRead, StorageLocationNode } from "../types";
import LocationPicker from "./LocationPicker";

export interface FilterState {
  includeArchived: boolean;
  hasContainers: boolean | undefined;
  mySecrets: boolean;
  locationId: string | undefined;
  locationName: string | undefined;
  noLocation: boolean;
  selectedGroupIds: string[];
  sort: string;
  order: "asc" | "desc";
}

interface FilterDrawerProps {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  filters: FilterState;
  onApply: (filters: FilterState) => void;
  groups: GroupRead[];
  storageTree: StorageLocationNode[];
}

export default function FilterDrawer({
  open, onOpen, onClose, filters, onApply, groups, storageTree,
}: FilterDrawerProps) {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const [pickerOpen, setPickerOpen] = useState(false);

  const handleChange = (patch: Partial<FilterState>) => {
    onApply({ ...filters, ...patch });
  };

  const toggleGroup = (groupId: string) => {
    const current = filters.selectedGroupIds;
    const updated = current.includes(groupId)
      ? current.filter((id) => id !== groupId)
      : [...current, groupId];
    if (updated.length > 0) {
      handleChange({ selectedGroupIds: updated });
    }
  };

  const content = (
    <Box sx={{ px: isDesktop ? 2 : 3, py: 2, width: isDesktop ? 320 : "auto" }}>
      {!isDesktop && (
        <Box sx={{ width: 40, height: 4, bgcolor: "#444", borderRadius: 2, mx: "auto", mb: 2 }} />
      )}
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>Filters</Typography>

      {/* Has stock + My secrets — side by side */}
      <Stack direction="row" spacing={2} sx={{ mb: 1 }}>
        <FormControlLabel
          control={
            <Switch
              checked={filters.hasContainers === true}
              onChange={(_, checked) =>
                handleChange({ hasContainers: checked ? true : undefined })
              }
            />
          }
          label={<Typography variant="body2">Has stock</Typography>}
          sx={{ flex: 1, m: 0 }}
        />
        <FormControlLabel
          control={
            <Switch
              checked={filters.mySecrets}
              onChange={(_, checked) => handleChange({ mySecrets: checked })}
            />
          }
          label={<Typography variant="body2">My secrets</Typography>}
          sx={{ flex: 1, m: 0 }}
        />
      </Stack>

      <Divider sx={{ my: 2 }} />

      {/* Storage location */}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Storage location
      </Typography>
      <Button
        variant="outlined"
        size="small"
        fullWidth
        onClick={() => setPickerOpen(true)}
        sx={{ justifyContent: "flex-start", textTransform: "none", mb: 1 }}
      >
        {filters.locationName ?? "Select location..."}
      </Button>
      {filters.locationId && (
        <Button
          size="small"
          onClick={() => handleChange({ locationId: undefined, locationName: undefined })}
          sx={{ textTransform: "none", mb: 0.5 }}
        >
          Clear location
        </Button>
      )}
      <FormControlLabel
        control={
          <Checkbox
            checked={filters.noLocation}
            onChange={(_, checked) => handleChange({ noLocation: checked })}
            size="small"
          />
        }
        label={<Typography variant="body2">No location assigned</Typography>}
        sx={{ m: 0 }}
      />

      <LocationPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(id, path) => handleChange({ locationId: id, locationName: path, noLocation: false })}
        tree={storageTree}
      />

      {groups.length > 1 && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Groups
          </Typography>
          <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5 }}>
            {groups.map((g) => (
              <Chip
                key={g.id}
                label={g.name}
                size="small"
                color={filters.selectedGroupIds.includes(g.id) ? "primary" : "default"}
                variant={filters.selectedGroupIds.includes(g.id) ? "filled" : "outlined"}
                onClick={() => toggleGroup(g.id)}
              />
            ))}
          </Stack>
        </>
      )}

      <Divider sx={{ my: 2 }} />

      {/* Sort & Order */}
      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <TextField
          select label="Sort by" value={filters.sort}
          onChange={(e) => handleChange({ sort: e.target.value })}
          size="small" sx={{ flex: 1 }}
        >
          <MenuItem value="name">Name</MenuItem>
          <MenuItem value="cas">CAS</MenuItem>
          <MenuItem value="created_at">Created</MenuItem>
          <MenuItem value="updated_at">Updated</MenuItem>
        </TextField>
        <TextField
          select label="Order" value={filters.order}
          onChange={(e) => handleChange({ order: e.target.value as "asc" | "desc" })}
          size="small" sx={{ flex: 1 }}
        >
          <MenuItem value="asc">Ascending</MenuItem>
          <MenuItem value="desc">Descending</MenuItem>
        </TextField>
      </Stack>

      <Button variant="contained" fullWidth onClick={onClose}>Apply</Button>
    </Box>
  );

  if (isDesktop) {
    return (
      <Drawer anchor="right" open={open} onClose={onClose}
        slotProps={{ paper: { sx: { borderTopLeftRadius: 8, borderBottomLeftRadius: 8, bgcolor: "background.default" } } }}>
        {content}
      </Drawer>
    );
  }

  return (
    <SwipeableDrawer anchor="bottom" open={open} onOpen={onOpen} onClose={onClose}
      slotProps={{ paper: { sx: { borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: "70vh" } } }}>
      {content}
    </SwipeableDrawer>
  );
}
```

- [ ] **Step 2: Update FilterBar to show new active filter chips**

Replace `frontend/src/components/FilterBar.tsx` — no changes to the component itself, but the caller (`ChemicalsPage`) will now build more `ActiveFilter` entries. The component is already generic enough.

No code change needed to `FilterBar.tsx` — it renders whatever `ActiveFilter[]` it receives.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: Errors in `ChemicalsPage.tsx` because it still passes old props to `FilterDrawer`. That's expected — fixed in Task 5.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/FilterDrawer.tsx
git commit -m "feat(ui): rewrite FilterDrawer with has-stock, my-secrets, location, groups filters"
```

---

### Task 5: Wire ChemicalsPage to use new filters

**Files:**
- Modify: `frontend/src/pages/ChemicalsPage.tsx`

- [ ] **Step 1: Rewrite ChemicalsPage**

Replace the full contents of `frontend/src/pages/ChemicalsPage.tsx`:

```tsx
import { Box, TextField, InputAdornment, IconButton, Stack, Badge, Button } from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import TuneIcon from "@mui/icons-material/Tune";
import AddIcon from "@mui/icons-material/Add";
import { useState } from "react";
import { useChemicals, useMultiGroupChemicals } from "../api/hooks/useChemicals";
import { useCurrentUser } from "../api/hooks/useAuth";
import { useGroups } from "../api/hooks/useGroups";
import { useStorageTree } from "../api/hooks/useStorageLocations";
import { ChemicalList } from "../components/ChemicalList";
import { FilterBar, type ActiveFilter } from "../components/FilterBar";
import { useDrawer } from "../components/drawer/DrawerContext";
import FilterDrawer, { type FilterState } from "../components/FilterDrawer";
import type { ChemicalSearchParams } from "../types";

export default function ChemicalsPage() {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? undefined;
  const drawer = useDrawer();
  const [search, setSearch] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<FilterState>({
    includeArchived: false,
    hasContainers: undefined,
    mySecrets: false,
    locationId: undefined,
    locationName: undefined,
    noLocation: false,
    selectedGroupIds: groupId ? [groupId] : [],
    sort: "name",
    order: "asc",
  });

  // Keep selectedGroupIds in sync when groupId first resolves
  const groups = useGroups();
  const storageTree = useStorageTree(groupId ?? "");

  const searchParams: ChemicalSearchParams = {
    search: search || undefined,
    has_containers: filters.hasContainers,
    my_secrets: filters.mySecrets || undefined,
    location_id: filters.locationId,
    no_location: filters.noLocation || undefined,
    sort: filters.sort as ChemicalSearchParams["sort"],
    order: filters.order,
  };

  const isMultiGroup =
    filters.selectedGroupIds.length > 1 ||
    (filters.selectedGroupIds.length === 1 && filters.selectedGroupIds[0] !== groupId);

  // Single-group fetch (with infinite scroll)
  const singleGroup = useChemicals(
    filters.selectedGroupIds[0] ?? groupId ?? "",
    searchParams,
    filters.includeArchived,
  );

  // Multi-group fetch (parallel, no infinite scroll)
  const multiGroup = useMultiGroupChemicals(
    isMultiGroup ? filters.selectedGroupIds : [],
    searchParams,
  );

  const singleItems = singleGroup.data?.pages.flatMap((p) => p.items) ?? [];
  const multiItems = multiGroup
    .flatMap((q) => q.data?.items ?? []);
  const items = isMultiGroup ? multiItems : singleItems;
  const isLoading = isMultiGroup
    ? multiGroup.some((q) => q.isLoading)
    : singleGroup.isLoading;

  // Build active filter chips
  const activeFilters: ActiveFilter[] = [];
  if (filters.includeArchived) {
    activeFilters.push({
      key: "archived",
      label: "Including archived",
      onRemove: () => setFilters((f) => ({ ...f, includeArchived: false })),
    });
  }
  if (filters.hasContainers === true) {
    activeFilters.push({
      key: "stock",
      label: "In stock",
      onRemove: () => setFilters((f) => ({ ...f, hasContainers: undefined })),
    });
  }
  if (filters.mySecrets) {
    activeFilters.push({
      key: "secrets",
      label: "My secrets",
      onRemove: () => setFilters((f) => ({ ...f, mySecrets: false })),
    });
  }
  if (filters.locationId) {
    activeFilters.push({
      key: "location",
      label: `Location: ${filters.locationName ?? "selected"}`,
      onRemove: () => setFilters((f) => ({ ...f, locationId: undefined, locationName: undefined })),
    });
  }
  if (filters.noLocation) {
    activeFilters.push({
      key: "noLocation",
      label: "No location",
      onRemove: () => setFilters((f) => ({ ...f, noLocation: false })),
    });
  }

  if (!groupId) {
    return <Box sx={{ color: "text.secondary" }}>No group selected.</Box>;
  }

  return (
    <Stack>
      <Stack
        direction="row"
        spacing={1}
        sx={{ alignItems: "center", px: 2, py: 1.5 }}
      >
        <TextField
          size="small"
          fullWidth
          placeholder="Search chemical, CAS or container ID…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={() => drawer.open({ kind: "chemical-new" })}
          sx={{ whiteSpace: "nowrap", minWidth: 0 }}
        >
          <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
            New
          </Box>
        </Button>
        <Badge
          color="primary"
          variant="dot"
          invisible={activeFilters.length === 0}
          overlap="circular"
        >
          <IconButton
            aria-label="Filters"
            sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1 }}
            onClick={() => setFiltersOpen(true)}
          >
            <TuneIcon fontSize="small" />
          </IconButton>
        </Badge>
      </Stack>
      <FilterBar filters={activeFilters} />
      <ChemicalList items={items} loading={isLoading} groupId={groupId} />
      <FilterDrawer
        open={filtersOpen}
        onOpen={() => setFiltersOpen(true)}
        onClose={() => setFiltersOpen(false)}
        filters={filters}
        onApply={setFilters}
        groups={groups.data ?? []}
        storageTree={storageTree.data ?? []}
      />
    </Stack>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Test in browser**

1. Open the chemicals page.
2. Click the filter (tune) icon — confirm drawer opens with the four filter sections.
3. Toggle "Has stock" — verify the list updates and a chip appears.
4. Toggle "My secrets" — verify filtering works.
5. Open the location picker — select a location, confirm chip and list update.
6. Check "No location assigned" — confirm chip appears.
7. If multiple groups exist, toggle group chips — confirm list switches data source.
8. Remove filter chips — verify each filter clears correctly.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ChemicalsPage.tsx
git commit -m "feat(ui): wire filter drawer to chemicals page with all four filters"
```

---

### Task 6: Sync selectedGroupIds with initial user group

**Files:**
- Modify: `frontend/src/pages/ChemicalsPage.tsx`

- [ ] **Step 1: Add effect to sync initial group**

The `selectedGroupIds` initializes with `groupId ? [groupId] : []`, but `groupId` may be `undefined` on first render (user query still loading). Add a `useEffect` after the `useState` block:

```tsx
import { useState, useEffect } from "react";

// ... inside ChemicalsPage, after useState for filters:
useEffect(() => {
  if (groupId && filters.selectedGroupIds.length === 0) {
    setFilters((f) => ({ ...f, selectedGroupIds: [groupId] }));
  }
}, [groupId]);
```

- [ ] **Step 2: Verify the page loads correctly on fresh navigation**

Open the app in a fresh tab, navigate to chemicals. The list should load without showing "No group selected" flash.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ChemicalsPage.tsx
git commit -m "fix(ui): sync filter selectedGroupIds when user data loads"
```

---

### Task 7: End-to-end verification

- [ ] **Step 1: Run all backend tests**

```bash
pytest tests/ -v
```

Expected: All pass.

- [ ] **Step 2: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Browser walkthrough**

Test the complete flow:
1. Chemicals page loads with default filters (no chips shown).
2. Open filter drawer → toggle "Has stock" → chip appears, list filters.
3. Open filter drawer → toggle "My secrets" → chip appears, only secret chemicals shown.
4. Open filter drawer → pick a storage location → chip shows "Location: Building > Room > Shelf", list filters.
5. Open filter drawer → check "No location assigned" → chip shows "No location", location picker clears.
6. Open filter drawer → toggle group chips (if multi-group user) → list switches.
7. Remove each chip → filter clears.
8. Expand a chemical → three-dot menu is at bottom-right, no overlap on mobile.

- [ ] **Step 4: Final commit if any cleanup needed**

```bash
git status
# If any uncommitted fixes:
git add -A && git commit -m "chore: filter drawer cleanup"
```
