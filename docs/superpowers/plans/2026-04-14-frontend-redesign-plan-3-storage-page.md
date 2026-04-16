# Frontend Redesign — Plan 3: Storage Page

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `/storage` route as a hierarchical browser over the 4-level `building → room → cabinet → shelf` tree. Non-superusers never see the building level — their breadcrumb starts at Room. The deepest level (shelf) renders container cards instead of child nodes, reusing the `ContainerCard` grid from Plan 2. Admins get inline add / edit / archive for rooms, cabinets and shelves; superusers additionally get building CRUD (the full buildings manager lives in Plan 4 / Settings, but the Storage page must still let an SU create a building so the tree is usable).

**Architecture:** Keep React 19 + MUI 9 + React Query + React Router. Reuse every Plan 2 primitive: `Layout`, `EditDrawer` + `DrawerContext`, `RoleGate`, `ContainerCard`, theme tokens. The route becomes `/storage/*` with a catch-all param so deep-linking to a specific node works (`/storage/<locationId>`). Replace the existing `StoragePage.tsx` (dialog-based, no kind discrimination) with a composition of `StorageBreadcrumbs`, `StorageChildList` and a leaf-shelf `ContainerGrid`. Add a new `StorageForm` body that plugs into `EditDrawer`.

**Tech Stack:** React 19, MUI 9 `@emotion/react`, `@tanstack/react-query`, React Router 7, axios. Playwright for E2E. Parent spec: `docs/superpowers/specs/2026-04-14-frontend-redesign-design.md` (section "Page: Storage"). Plan 1 (backend) and Plan 2 (theme / layout / Chemicals page) are merged.

**Dependency notes:** Plan 2 must be merged (`EditDrawer`, `DrawerContext`, `RoleGate`, `ContainerCard`, theme tokens and the top-nav `Layout` are all required). Plan 4 (Settings) is independent and can be written / implemented in parallel — it touches `SettingsPage.tsx` and `src/components/settings/*`, which this plan does not modify. The only shared backend surface is `StorageLocationNode` (see Task 1), so if both plans are in flight the Plan 4 Buildings section should import the updated type rather than redefine it.

---

## File map

**New files:**
- `src/components/StorageBreadcrumbs.tsx`
- `src/components/StorageChildList.tsx`
- `src/components/StorageChildRow.tsx`
- `src/components/drawer/StorageForm.tsx`
- `src/hooks/useStorageNavigation.ts`
- `frontend/e2e/storage.spec.ts`

**Modified files:**
- `src/pages/StoragePage.tsx` — full rewrite. The current implementation is a single-file breadcrumb + dialog CRUD flow with no `kind` handling; it is replaced by a composition of the new components.
- `src/App.tsx` — route change `/storage` → `/storage/*` (or add a nested `/storage/:locationId` route); `StoragePage` reads the current node id from `useParams` and the full tree from the existing `useStorageTree`.
- `src/types/index.ts` — add `kind: StorageKind` to `StorageLocationNode` and `StorageLocationRead`; add `container_count?: number` (optional; populated only if Task 1 ships the backend side). Add `StorageKind` type alias.
- `src/api/hooks/useStorageLocations.ts` — the existing hook file gains: `useShelfContainers(groupId, locationId)` (wraps `GET /groups/:gid/containers?location_id=...`), `useArchiveStorageLocation` and `useUnarchiveStorageLocation` mutations (soft-delete semantics — see Design decisions in Task 5).
- `src/api/hooks/useContainers.ts` — inspect first; this plan only needs the list query by `location_id`. Add the param if not already supported.
- `src/chaima/schemas/storage.py` — add `kind` to `StorageLocationNode` and (optionally, see Task 1) a denormalised `container_count: int` on the node. This is the **only** backend-side change in Plan 3.
- `src/chaima/services/storage_locations.py` — populate the new field when building the tree.

**Deleted files:** None. The existing `StoragePage.tsx` is rewritten in place.

---

## Task 1: Expose `kind` on `StorageLocationNode` (+ optional container count)

**Files:** Modify `src/chaima/schemas/storage.py`, `src/chaima/services/storage_locations.py`, `frontend/src/types/index.ts`.

**Rationale:** The frontend spec requires treating the shelf level differently (show containers instead of children) and hiding the building level from non-superusers. Both decisions need the `kind` field, which the backend model already stores but the `StorageLocationNode` response schema does not surface. Without this fix, the frontend would have to re-fetch each node individually via `GET /storage-locations/:id` just to learn its kind — unacceptable for a tree render.

**Design decisions:**
- **Container count:** the spec shows a "`42`" badge on each child row. We surface it as `container_count: int` on `StorageLocationNode`, computed at query time as the number of non-archived containers whose `location_id` equals that node's id (not transitive — only direct children, see below). The service already walks the tree once; we add a second query that selects `(location_id, count(*))` for all containers in the group and attaches the counts during tree assembly.
- **Transitive vs. direct counts:** the spec is ambiguous. We go with **direct only** (a room row shows containers pinned directly to the room, not the sum of all containers in all cabinets/shelves below). Reason: containers are always placed on a specific kind of leaf in practice (usually a shelf), so transitive counts would mostly duplicate one big number up the tree and hide where things actually are. Document this in the task body so a reviewer can push back if they disagree.
- **Back-compat:** the field is added to the response schema only; no migration. Existing callers tolerate the extra field.

- [ ] **Step 1: Update `StorageLocationNode` in `src/chaima/schemas/storage.py`:**

```python
class StorageLocationNode(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    kind: StorageKind
    description: str | None
    parent_id: UUID | None
    container_count: int = 0
    children: list["StorageLocationNode"] = []
```

`parent_id` is added so the frontend can reconstruct ancestry without re-walking the tree.

- [ ] **Step 2: Update the service** (`src/chaima/services/storage_locations.py`). Find the function that builds the tree (likely `build_tree` or `get_tree`) and:
  - Select all locations for the group in one query.
  - Select `location_id, count(*)` from containers where `group_id = :gid and is_archived = false` grouped by `location_id`, build a dict.
  - When constructing each `StorageLocationNode`, pass `kind=loc.kind`, `parent_id=loc.parent_id` and `container_count=counts.get(loc.id, 0)`.

- [ ] **Step 3: Add / extend backend tests** in `tests/routers/test_storage_locations.py`:
  - One test that creates a room, a shelf under it, a container on the shelf, and asserts the tree response contains `kind="shelf"` on the shelf node and `container_count=1` on the shelf and `container_count=0` on the room.

- [ ] **Step 4: Mirror in TS types** — `frontend/src/types/index.ts`:

```ts
export type StorageKind = "building" | "room" | "cabinet" | "shelf";

export interface StorageLocationRead {
  id: string;
  name: string;
  kind: StorageKind;
  description: string | null;
  parent_id: string | null;
  created_at: string;
}

export interface StorageLocationNode {
  id: string;
  name: string;
  kind: StorageKind;
  description: string | null;
  parent_id: string | null;
  container_count: number;
  children: StorageLocationNode[];
}

export interface StorageLocationCreate {
  name: string;
  kind: StorageKind;
  description?: string | null;
  parent_id?: string | null;
}

export interface StorageLocationUpdate {
  name?: string | null;
  description?: string | null;
  parent_id?: string | null;
}
```

- [ ] **Step 5: Run `pytest tests/routers/test_storage_locations.py` and `npm run build`.** Both green.

- [ ] **Step 6: Commit.**

```bash
git add src/chaima/schemas/storage.py src/chaima/services/storage_locations.py tests/routers/test_storage_locations.py frontend/src/types/index.ts
git commit -m "feat(storage): expose kind, parent_id and container_count on tree nodes"
```

**Acceptance criteria:**
- `GET /groups/:gid/storage-locations` returns a tree whose every node has `kind`, `parent_id` and `container_count` fields.
- Frontend `tsc -b` passes with the extended types.
- Existing Chemicals E2E from Plan 2 still passes (no regression in Container create which uses `location_id`).

---

## Task 2: `useStorageNavigation` hook

**Files:** Create `src/hooks/useStorageNavigation.ts`.

**Rationale:** Two concerns get mixed in the current `StoragePage`: "walk the tree to find the currently-selected node" and "decide which level a non-superuser should start at". Pulling both into a hook keeps the page component declarative and makes the superuser/user split testable in isolation.

- [ ] **Step 1: Create the hook:**

```ts
import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { useStorageTree } from "../api/hooks/useStorageLocations";
import { useCurrentUser } from "../api/hooks/useAuth";
import { useGroup } from "../components/GroupContext";
import type { StorageLocationNode } from "../types";

export interface StorageNavigation {
  loading: boolean;
  /** Roots the user is allowed to see. SU → buildings. User → rooms (flattened from all buildings). */
  visibleRoots: StorageLocationNode[];
  /** Full ancestor chain from a visible root to the current node (inclusive). Empty at the root view. */
  path: StorageLocationNode[];
  /** Currently-selected node, or null at root. */
  current: StorageLocationNode | null;
  /** Children to render in the child list. Equal to current.children when a node is selected, else visibleRoots. */
  children: StorageLocationNode[];
  /** Containers live here — render the ContainerGrid instead of StorageChildList. */
  isLeaf: boolean;
  /** The kind of child that should be added by the "+ Add ..." button below the list, or null if the user can't add here. */
  nextChildKind: "building" | "room" | "cabinet" | "shelf" | null;
}

function findPath(
  nodes: StorageLocationNode[],
  targetId: string,
  acc: StorageLocationNode[] = [],
): StorageLocationNode[] | null {
  for (const n of nodes) {
    const next = [...acc, n];
    if (n.id === targetId) return next;
    const found = findPath(n.children, targetId, next);
    if (found) return found;
  }
  return null;
}

const CHILD_KIND: Record<string, StorageNavigation["nextChildKind"]> = {
  building: "room",
  room: "cabinet",
  cabinet: "shelf",
  shelf: null, // shelves hold containers, not sub-locations
};

export function useStorageNavigation(): StorageNavigation {
  const { groupId } = useGroup();
  const { data: user } = useCurrentUser();
  const { locationId } = useParams<{ locationId?: string }>();
  const tree = useStorageTree(groupId);

  return useMemo<StorageNavigation>(() => {
    const all = tree.data ?? [];
    const isSuperuser = !!user?.is_superuser;

    // Non-SU: skip the building layer, present rooms as the visible roots.
    const visibleRoots: StorageLocationNode[] = isSuperuser
      ? all
      : all.flatMap((building) =>
          building.kind === "building" ? building.children : [building],
        );

    const path = locationId ? findPath(visibleRoots, locationId) ?? [] : [];
    const current = path.length ? path[path.length - 1] : null;
    const children = current ? current.children : visibleRoots;
    const isLeaf = current?.kind === "shelf";

    let nextChildKind: StorageNavigation["nextChildKind"];
    if (!current) {
      nextChildKind = isSuperuser ? "building" : "room";
    } else {
      nextChildKind = CHILD_KIND[current.kind] ?? null;
    }

    return {
      loading: tree.isLoading,
      visibleRoots,
      path,
      current,
      children,
      isLeaf,
      nextChildKind,
    };
  }, [tree.data, tree.isLoading, user?.is_superuser, locationId]);
}
```

**Design decisions:**
- When a non-SU lands at `/storage` with no selected node, the visible roots are "all rooms across all buildings the group is in". That means the spec's breadcrumb "`Storage › Lab 201 › ...`" effectively starts at the first crumb being a room. We also do **not** render a synthetic "Building" crumb in the middle — the building level is invisible.
- When a non-SU is at the root and presses "Add room", we need a `parent_id` (a building). For v1 we use the **first building the group is assigned to**; if there is none, the "Add room" button is disabled with a tooltip "Ask an admin to create a building first". This keeps the Storage page usable even for groups with a single building (the common case) without forcing a building picker into the UI. Larger multi-building groups can be handled when / if they appear (YAGNI).

- [ ] **Step 2: Commit.**

```bash
git add frontend/src/hooks/useStorageNavigation.ts
git commit -m "feat(storage): useStorageNavigation hook with SU/user split and leaf detection"
```

**Acceptance criteria:**
- Hook returns `isLeaf: true` only when the selected node has `kind: "shelf"`.
- For a non-SU, `visibleRoots` never contains a node with `kind: "building"`.
- For the SU, `visibleRoots` equals the full tree.
- `nextChildKind` cycles building → room → cabinet → shelf → null.

---

## Task 3: Extend `useStorageLocations` hook with shelf-container queries and archive mutations

**Files:** Modify `src/api/hooks/useStorageLocations.ts`, `src/api/hooks/useContainers.ts`.

**Rationale:** The leaf (shelf) view needs to list containers by `location_id`. The Chemicals page already creates containers at a location, so the backend endpoint `GET /groups/:gid/containers?location_id=...` exists from Plan 1 — we just need a hook that binds it to a React Query key. Archive mutations are added here to centralise storage-location writes in the same file as the existing create/update/delete.

- [ ] **Step 1: Inspect `useContainers.ts`.** Confirm the list hook already accepts `location_id`. If not, add it:

```ts
export function useContainers(groupId: string, params: ContainerSearchParams = {}) {
  return useQuery({
    queryKey: ["containers", groupId, params],
    queryFn: () =>
      client
        .get(`/groups/${groupId}/containers`, { params })
        .then((r) => r.data as PaginatedResponse<ContainerRead>),
    enabled: !!groupId,
  });
}
```

- [ ] **Step 2: Add a thin wrapper in `useStorageLocations.ts`** so the Storage page doesn't need to know about the containers hook file:

```ts
import { useContainers } from "./useContainers";

export function useShelfContainers(groupId: string, locationId: string | null) {
  return useContainers(groupId, locationId ? { location_id: locationId, is_archived: false, limit: 200 } : {});
  // React Query's `enabled` flag is not set here because useContainers enables on groupId alone;
  // the empty-params branch returns the unfiltered list which we discard when !locationId.
}
```

If that feels awkward, just use `useContainers` directly from the page and delete this wrapper. Either is fine.

- [ ] **Step 3: Add archive mutations.** Storage locations are soft-deleted per the parent spec (nothing is hard-deleted). The backend currently exposes `DELETE /storage-locations/:id`; in Plan 1 this was implemented as a soft delete that sets `is_archived = true`. Verify by reading `src/chaima/services/storage_locations.py` — if it hard-deletes, open a small follow-up (out of scope for Plan 3) and for now wire `useArchiveStorageLocation` to the `DELETE` endpoint. Rename the existing `useDeleteStorageLocation` export as `useArchiveStorageLocation` (leave a `useDeleteStorageLocation` alias for one release cycle if anything else imports it — grep first).

```ts
export function useArchiveStorageLocation(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (locationId: string) =>
      client.delete(`/groups/${groupId}/storage-locations/${locationId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["storageLocations", groupId] });
      queryClient.invalidateQueries({ queryKey: ["containers", groupId] });
    },
  });
}
```

(An `unarchive` endpoint is nice to have but **not** required for Plan 3 — archived storage locations simply vanish from the tree; restoring them can be done via Swagger or a later polish pass. State this in the acceptance criteria below.)

- [ ] **Step 4: Commit.**

```bash
git add frontend/src/api/hooks/useStorageLocations.ts frontend/src/api/hooks/useContainers.ts
git commit -m "feat(hooks): shelf container query + archive mutation for storage locations"
```

**Acceptance criteria:**
- `useShelfContainers(groupId, shelfId)` returns a paginated list filtered to the given shelf, with `is_archived=false`.
- `useArchiveStorageLocation` invalidates both the storage tree and the containers list (the tree cache must refresh because `container_count` depends on container state).
- Unarchive is intentionally out of scope; note it in the "Plan 3 complete" section.

---

## Task 4: `StorageBreadcrumbs` component

**Files:** Create `src/components/StorageBreadcrumbs.tsx`.

**Rationale:** Keep breadcrumb rendering small and reusable. It takes a `path` from `useStorageNavigation` and a click handler; the building-hiding logic is entirely in the hook, so the component is dumb.

- [ ] **Step 1: Create the component:**

```tsx
import { Breadcrumbs, Link, Typography, Box } from "@mui/material";
import { useNavigate } from "react-router-dom";
import type { StorageLocationNode } from "../types";

export interface StorageBreadcrumbsProps {
  path: StorageLocationNode[];
}

export function StorageBreadcrumbs({ path }: StorageBreadcrumbsProps) {
  const navigate = useNavigate();
  return (
    <Box sx={{ mb: 2 }}>
      <Breadcrumbs
        separator="›"
        sx={{
          fontSize: 13,
          "& .MuiBreadcrumbs-separator": { color: "text.secondary", mx: 0.75 },
        }}
      >
        <Link
          component="button"
          underline="hover"
          onClick={() => navigate("/storage")}
          sx={{ color: "text.secondary", fontSize: 13 }}
        >
          Storage
        </Link>
        {path.map((node, i) => {
          const isLast = i === path.length - 1;
          return isLast ? (
            <Typography key={node.id} sx={{ color: "text.primary", fontSize: 13, fontWeight: 500 }}>
              {node.name}
            </Typography>
          ) : (
            <Link
              key={node.id}
              component="button"
              underline="hover"
              onClick={() => navigate(`/storage/${node.id}`)}
              sx={{ color: "text.secondary", fontSize: 13 }}
            >
              {node.name}
            </Link>
          );
        })}
      </Breadcrumbs>
    </Box>
  );
}
```

- [ ] **Step 2: Commit.**

```bash
git add frontend/src/components/StorageBreadcrumbs.tsx
git commit -m "feat(components): StorageBreadcrumbs"
```

**Acceptance criteria:**
- Root breadcrumb (`Storage`) is always shown and navigates to `/storage`.
- Intermediate crumbs are clickable links; the last crumb is rendered as plain text.
- No building is ever rendered for non-SU users (enforced by the caller via `path` content).

---

## Task 5: `StorageChildRow` and `StorageChildList`

**Files:** Create `src/components/StorageChildRow.tsx` and `src/components/StorageChildList.tsx`.

**Rationale:** The child list is the main body of every non-leaf storage level. Each row: name + optional description + container-count badge + (admin-only) edit pencil. The row is clickable to drill down. Factoring `Row` separately keeps the per-row state (hover → reveal pencil) simple.

- [ ] **Step 1: `StorageChildRow.tsx`:**

```tsx
import { Box, Typography, IconButton, Tooltip } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import { useNavigate } from "react-router-dom";
import type { StorageLocationNode } from "../types";
import { RoleGate } from "./RoleGate";
import { useDrawer } from "./drawer/DrawerContext";

export function StorageChildRow({ node }: { node: StorageLocationNode }) {
  const navigate = useNavigate();
  const { open } = useDrawer();
  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={() => navigate(`/storage/${node.id}`)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") navigate(`/storage/${node.id}`);
      }}
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        px: 1.5,
        py: 1.25,
        minHeight: 44,
        borderBottom: "1px solid",
        borderColor: "divider",
        cursor: "pointer",
        transition: "background-color 120ms",
        "&:hover": { bgcolor: "action.hover", "& .edit-btn": { opacity: 1 } },
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="body2" sx={{ fontWeight: 500, color: "text.primary", lineHeight: 1.3 }} noWrap>
          {node.name}
        </Typography>
        {node.description && (
          <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block" }}>
            {node.description}
          </Typography>
        )}
      </Box>
      <RoleGate allow={["admin", "superuser"]}>
        <Tooltip title="Edit">
          <IconButton
            size="small"
            className="edit-btn"
            onClick={(e) => {
              e.stopPropagation();
              open({ kind: "storage-edit", locationId: node.id });
            }}
            sx={{ opacity: 0, "&:focus": { opacity: 1 } }}
          >
            <EditIcon fontSize="inherit" sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
      </RoleGate>
      <Box
        sx={{
          minWidth: 32,
          textAlign: "right",
          fontVariantNumeric: "tabular-nums",
          fontSize: 12,
          color: "text.secondary",
          fontWeight: 500,
        }}
      >
        {node.container_count}
      </Box>
    </Box>
  );
}
```

- [ ] **Step 2: `StorageChildList.tsx`:**

```tsx
import { Box, Button, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import type { StorageLocationNode, StorageKind } from "../types";
import { StorageChildRow } from "./StorageChildRow";
import { RoleGate } from "./RoleGate";
import { useDrawer } from "./drawer/DrawerContext";

const KIND_LABEL: Record<StorageKind, string> = {
  building: "building",
  room: "room",
  cabinet: "cabinet",
  shelf: "shelf",
};

export interface StorageChildListProps {
  children: StorageLocationNode[];
  parentId: string | null;
  nextChildKind: StorageKind | null;
  /** Passed through when the add button is clicked — the drawer pre-fills `parent_id`. */
  parentHintForNewChild?: string | null;
}

export function StorageChildList({
  children,
  parentId,
  nextChildKind,
  parentHintForNewChild,
}: StorageChildListProps) {
  const { open } = useDrawer();
  const hasChildren = children.length > 0;

  return (
    <Box>
      {hasChildren ? (
        <Box sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1, overflow: "hidden" }}>
          {children.map((c) => (
            <StorageChildRow key={c.id} node={c} />
          ))}
        </Box>
      ) : (
        <Typography color="text.secondary" sx={{ py: 3, textAlign: "center", fontSize: 13 }}>
          {nextChildKind ? `No ${KIND_LABEL[nextChildKind]}s yet.` : "Nothing here."}
        </Typography>
      )}

      {nextChildKind && (
        <RoleGate allow={nextChildKind === "building" ? ["superuser"] : ["admin", "superuser"]}>
          <Box sx={{ mt: 1.5 }}>
            <Button
              size="small"
              startIcon={<AddIcon />}
              onClick={() =>
                open({
                  kind: "storage-new",
                  childKind: nextChildKind,
                  parentId: parentHintForNewChild ?? parentId,
                })
              }
              sx={{ color: "text.secondary" }}
            >
              Add {KIND_LABEL[nextChildKind]}
            </Button>
          </Box>
        </RoleGate>
      )}
    </Box>
  );
}
```

**Design decisions:**
- Row borders are on the container box, not each row — gives the list a crisp "table frame" look consistent with the high-density spec.
- The edit pencil is opacity-0 until hover/focus to keep the row quiet. Keyboard users still get it on focus.
- Building creation is gated to `["superuser"]`, everything else to `["admin", "superuser"]`, matching the spec's permission table.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/StorageChildRow.tsx frontend/src/components/StorageChildList.tsx
git commit -m "feat(components): StorageChildList and StorageChildRow"
```

**Acceptance criteria:**
- Clicking a row navigates to `/storage/<childId>`.
- Edit pencil only visible to admins and superusers.
- `+ Add building` only visible to superusers; `+ Add room/cabinet/shelf` visible to admins and superusers.
- Container count renders on the right with tabular numerals.

---

## Task 6: `StorageForm` drawer body

**Files:** Create `src/components/drawer/StorageForm.tsx`. Modify `src/components/drawer/DrawerContext.tsx` to accept the new request shapes.

**Rationale:** Creating / editing a storage unit is a small form (name, description) that plugs into the shared `EditDrawer`, matching how `ChemicalForm` and `ContainerForm` are already structured in Plan 2.

- [ ] **Step 1: Extend `DrawerContext` request union.** Open `src/components/drawer/DrawerContext.tsx` — the `DrawerRequest` (or similarly named) discriminated union currently lists chemical/container variants. Add:

```ts
| { kind: "storage-new"; childKind: StorageKind; parentId: string | null }
| { kind: "storage-edit"; locationId: string }
```

and import `StorageKind` from `../../types`. Update the dispatcher switch in `EditDrawer` to render `<StorageForm mode="create" childKind={req.childKind} parentId={req.parentId} />` / `<StorageForm mode="edit" locationId={req.locationId} />`.

- [ ] **Step 2: Create `StorageForm.tsx`:**

```tsx
import { useState, useEffect } from "react";
import { Stack, TextField, Button, Box, Typography, Alert } from "@mui/material";
import {
  useCreateStorageLocation,
  useUpdateStorageLocation,
  useArchiveStorageLocation,
  useStorageLocation,
} from "../../api/hooks/useStorageLocations";
import { useGroup } from "../GroupContext";
import { useDrawer } from "./DrawerContext";
import type { StorageKind } from "../../types";

const KIND_LABEL: Record<StorageKind, string> = {
  building: "Building",
  room: "Room",
  cabinet: "Cabinet",
  shelf: "Shelf",
};

type Props =
  | { mode: "create"; childKind: StorageKind; parentId: string | null }
  | { mode: "edit"; locationId: string };

export function StorageForm(props: Props) {
  const { groupId } = useGroup();
  const { close } = useDrawer();

  const editQuery = useStorageLocation(
    groupId,
    props.mode === "edit" ? props.locationId : "",
  );
  const existing = props.mode === "edit" ? editQuery.data : undefined;

  const createMut = useCreateStorageLocation(groupId);
  const updateMut = useUpdateStorageLocation(
    groupId,
    props.mode === "edit" ? props.locationId : "",
  );
  const archiveMut = useArchiveStorageLocation(groupId);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (existing) {
      setName(existing.name);
      setDescription(existing.description ?? "");
    }
  }, [existing?.id]);

  const kind: StorageKind =
    props.mode === "create" ? props.childKind : existing?.kind ?? "shelf";
  const title =
    props.mode === "create" ? `New ${KIND_LABEL[kind].toLowerCase()}` : `Edit ${KIND_LABEL[kind].toLowerCase()}`;

  const submitting = createMut.isPending || updateMut.isPending || archiveMut.isPending;

  const onSubmit = async () => {
    setError(null);
    try {
      if (props.mode === "create") {
        await createMut.mutateAsync({
          name: name.trim(),
          kind,
          description: description.trim() || null,
          parent_id: props.parentId ?? null,
        });
      } else {
        await updateMut.mutateAsync({
          name: name.trim(),
          description: description.trim() || null,
        });
      }
      close();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Could not save.");
    }
  };

  const onArchive = async () => {
    if (props.mode !== "edit") return;
    if (!window.confirm(`Archive this ${KIND_LABEL[kind].toLowerCase()}? Containers inside it keep their data but the location will no longer appear in the tree.`)) return;
    try {
      await archiveMut.mutateAsync(props.locationId);
      close();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Could not archive.");
    }
  };

  return (
    <Box sx={{ p: 2.5 }}>
      <Typography variant="h3" sx={{ mb: 2 }}>
        {title}
      </Typography>
      <Stack spacing={2}>
        <TextField
          label="Name"
          size="small"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          inputProps={{ name: "name" }}
        />
        <TextField
          label="Description"
          size="small"
          multiline
          minRows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          helperText="Optional — e.g. a shelf note, cabinet contents summary."
        />
        {error && <Alert severity="error">{error}</Alert>}
      </Stack>

      <Stack direction="row" justifyContent="space-between" sx={{ mt: 3 }}>
        {props.mode === "edit" ? (
          <Button color="error" size="small" onClick={onArchive} disabled={submitting}>
            Archive
          </Button>
        ) : (
          <span />
        )}
        <Stack direction="row" spacing={1}>
          <Button size="small" onClick={close} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant="contained"
            size="small"
            onClick={onSubmit}
            disabled={!name.trim() || submitting}
          >
            {props.mode === "create" ? "Create" : "Save"}
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}
```

- [ ] **Step 3: Manual verify.** Start `npm run dev`. As a superuser, `+ Add building` → drawer opens → create "Main Building". Descend, `+ Add room` → drawer opens with `parentId` prefilled → create "Lab 201". Repeat cabinet and shelf. Edit the shelf → rename → save. Archive it → disappears from the tree.

- [ ] **Step 4: Commit.**

```bash
git add frontend/src/components/drawer/StorageForm.tsx frontend/src/components/drawer/DrawerContext.tsx frontend/src/components/drawer/EditDrawer.tsx
git commit -m "feat(drawer): StorageForm for create/edit/archive of storage locations"
```

**Acceptance criteria:**
- Drawer opens with the right title for each kind (Room / Cabinet / Shelf / Building).
- `parent_id` is pre-populated from the drawer request — the user never picks a parent.
- Archive button present in edit mode only, with a `window.confirm` guard.
- 400 errors (e.g. duplicate name under a parent) surface in the Alert.

---

## Task 7: Rewrite `StoragePage.tsx`

**Files:** Replace `src/pages/StoragePage.tsx`. Modify `src/App.tsx`.

**Rationale:** The page is now a thin composition. All state lives in `useStorageNavigation`; all writes go through `DrawerContext` → `StorageForm`; leaf rendering reuses `ContainerCard` from Plan 2.

- [ ] **Step 1: Update the route in `App.tsx`.** Replace the `/storage` route (and any `/storage/:id`) with:

```tsx
<Route path="/storage" element={<StoragePage />} />
<Route path="/storage/:locationId" element={<StoragePage />} />
```

Both hit the same component — the presence of `locationId` in `useParams` is what drives the drill-down.

- [ ] **Step 2: Rewrite `StoragePage.tsx`:**

```tsx
import { Box, Typography, Stack, CircularProgress } from "@mui/material";
import { useStorageNavigation } from "../hooks/useStorageNavigation";
import { StorageBreadcrumbs } from "../components/StorageBreadcrumbs";
import { StorageChildList } from "../components/StorageChildList";
import { ContainerCard } from "../components/ContainerCard";
import { useShelfContainers } from "../api/hooks/useStorageLocations";
import { useGroup } from "../components/GroupContext";
import { RoleGate } from "../components/RoleGate";
import { useDrawer } from "../components/drawer/DrawerContext";
import { Button } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";

export default function StoragePage() {
  const { groupId } = useGroup();
  const nav = useStorageNavigation();
  const { open } = useDrawer();

  // Leaf-only container fetch.
  const containers = useShelfContainers(
    groupId,
    nav.isLeaf && nav.current ? nav.current.id : null,
  );

  if (nav.loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress size={22} />
      </Box>
    );
  }

  return (
    <Box>
      <StorageBreadcrumbs path={nav.path} />

      <Stack direction="row" alignItems="baseline" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h1">
          {nav.current?.name ?? "Storage"}
        </Typography>
        {nav.current && (
          <RoleGate allow={["admin", "superuser"]}>
            <Button
              size="small"
              onClick={() => open({ kind: "storage-edit", locationId: nav.current!.id })}
              sx={{ color: "text.secondary" }}
            >
              Edit {nav.current.kind}
            </Button>
          </RoleGate>
        )}
      </Stack>

      {nav.current?.description && (
        <Typography color="text.secondary" sx={{ mb: 2, fontSize: 13 }}>
          {nav.current.description}
        </Typography>
      )}

      {nav.isLeaf ? (
        <Box>
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
            <Typography variant="h5">
              Containers ({containers.data?.total ?? 0})
            </Typography>
          </Stack>
          {containers.isLoading ? (
            <CircularProgress size={18} />
          ) : (containers.data?.items.length ?? 0) === 0 ? (
            <Typography color="text.secondary" sx={{ py: 3, textAlign: "center", fontSize: 13 }}>
              No containers on this shelf yet. Create one from the Chemicals page.
            </Typography>
          ) : (
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", sm: "repeat(auto-fill, minmax(210px, 1fr))" },
                gap: 1.5,
              }}
            >
              {containers.data!.items.map((c) => (
                <ContainerCard key={c.id} container={c} linkToChemical />
              ))}
            </Box>
          )}
        </Box>
      ) : (
        <StorageChildList
          children={nav.children}
          parentId={nav.current?.id ?? null}
          nextChildKind={nav.nextChildKind}
          parentHintForNewChild={nav.current?.id ?? null}
        />
      )}
    </Box>
  );
}
```

- [ ] **Step 3: `ContainerCard` — add `linkToChemical` prop.** `ContainerCard` from Plan 2 doesn't know about the Storage page. Extend it with an optional `linkToChemical?: boolean` prop; when true, wrap the card body in a `RouterLink` to `/?expand=<chemicalId>`. `ChemicalsPage` already supports the `expand` query param (Plan 2 Task 11 — verify). If not, add a tiny effect that reads `?expand=` from the location and pre-expands that row on mount.

- [ ] **Step 4: Manual verify.**
  - As a non-SU: `/storage` → see rooms directly, no building layer, `Storage ›` is the only root crumb.
  - Drill down room → cabinet → shelf.
  - On a shelf, see a container grid if any containers live there, clicking a card jumps to the Chemicals page with that row expanded.
  - As a superuser: same, but the first level is buildings.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/pages/StoragePage.tsx frontend/src/App.tsx frontend/src/components/ContainerCard.tsx
git commit -m "feat(storage): rewrite StoragePage as a tree browser with leaf container grid"
```

**Acceptance criteria:**
- The page composes only `StorageBreadcrumbs`, `StorageChildList` / `ContainerGrid`, and the Edit button — all data lives in hooks.
- Non-SU never sees building-kind rows or crumbs.
- Leaf shelf view reuses `ContainerCard`; each card links back to the Chemicals page.
- Deep-linking to `/storage/<locationId>` restores the exact view after refresh.

---

## Task 8: Responsive polish

**Files:** Various.

**Rationale:** The spec's responsive table lists container cards as 1-column on mobile, breadcrumbs wrapping, and row headings truncating. Reuse what Plan 2 Task 16 established.

- [ ] **Step 1: At 375 px:**
  - Breadcrumbs wrap rather than overflow (MUI `Breadcrumbs` already does this; confirm).
  - `StorageChildRow` name `noWrap` truncates cleanly.
  - Container grid collapses to one column.
  - Drawer is full-width.

- [ ] **Step 2: Fix any issues** — usual suspect is `minWidth: 0` on flex children.

- [ ] **Step 3: Commit.**

```bash
git add -u frontend/src/components/ frontend/src/pages/StoragePage.tsx
git commit -m "fix(responsive): polish Storage page at mobile breakpoints"
```

**Acceptance criteria:**
- No horizontal scroll at 375 px on any level.
- Drawer opens full-width on mobile.

---

## Task 9: Playwright E2E for Storage

**Files:** Create `frontend/e2e/storage.spec.ts`.

**Rationale:** Mirror the shape of `frontend/e2e/chemicals.spec.ts` from Plan 2. Cover the core superuser flow (create building → room → cabinet → shelf → archive), the non-SU view (no building level visible), and the leaf-container linkback.

- [ ] **Step 1: Write the spec.** Check `playwright.config.ts` for the base URL and existing login helpers before copy-pasting selectors.

```ts
import { test, expect } from "@playwright/test";

const SU = { email: "su@chaima.dev", password: "changeme" };

async function login(page, creds: { email: string; password: string }) {
  await page.goto("/login");
  await page.fill('input[name="email"]', creds.email);
  await page.fill('input[name="password"]', creds.password);
  await page.click('button[type="submit"]');
  await page.waitForURL("/");
}

test.describe("Storage page", () => {
  test("superuser creates a full building → room → cabinet → shelf path", async ({ page }) => {
    await login(page, SU);
    await page.click("text=Storage");
    await page.waitForURL("/storage");

    // Add building
    await page.click("text=Add building");
    await page.fill('input[name="name"]', "E2E Main Building");
    await page.click("text=Create");
    await expect(page.locator("text=E2E Main Building")).toBeVisible();

    await page.click("text=E2E Main Building");
    await page.click("text=Add room");
    await page.fill('input[name="name"]', "E2E Lab 201");
    await page.click("text=Create");

    await page.click("text=E2E Lab 201");
    await page.click("text=Add cabinet");
    await page.fill('input[name="name"]', "E2E Cabinet A1");
    await page.click("text=Create");

    await page.click("text=E2E Cabinet A1");
    await page.click("text=Add shelf");
    await page.fill('input[name="name"]', "E2E Shelf 2");
    await page.click("text=Create");

    // Drill into shelf and verify the leaf view renders "Containers (0)"
    await page.click("text=E2E Shelf 2");
    await expect(page.locator("text=Containers (0)")).toBeVisible();
    await expect(page.locator("text=No containers on this shelf yet")).toBeVisible();

    // Archive the shelf
    await page.click("text=Edit shelf");
    await page.click("text=Archive");
    // window.confirm — auto-accept via page.on("dialog"):
  });

  test("regular user does not see the building level", async ({ page }) => {
    await login(page, { email: "user@chaima.dev", password: "changeme" });
    await page.click("text=Storage");
    await page.waitForURL("/storage");
    // If a building named "E2E Main Building" exists from the previous test,
    // it should NOT appear as a crumb for this user.
    await expect(page.locator("text=E2E Main Building")).not.toBeVisible();
    // They should see rooms directly as the first level.
  });

  test("leaf container links back to Chemicals page", async ({ page }) => {
    await login(page, SU);
    // Precondition: a container exists on some shelf. If needed, create it via the Chemicals page first.
    // Navigate to that shelf manually by /storage/<id> or by drill-down.
    // Click a container card → expect URL to include /?expand=<chemicalId>.
    //
    // This test may be skipped / marked `test.skip` if the fixtures don't set one up —
    // mark it clearly so it's obvious what's stubbed.
  });
});
```

Dialog auto-accept pattern:

```ts
page.on("dialog", (d) => d.accept());
```

Add it once in a `test.beforeEach` for the archive-path tests.

Selectors (`text=`, `input[name="name"]`) may need tightening — add `aria-label` attributes in components if stable selectors are hard to come by.

- [ ] **Step 2: Run the spec locally.**

```bash
cd frontend
npm run test:e2e -- storage.spec.ts
```

Iterate on selectors until green.

- [ ] **Step 3: Commit.**

```bash
git add frontend/e2e/storage.spec.ts
# + any selector fixups in components
git commit -m "test(e2e): Storage page — tree CRUD, non-SU view, leaf container link"
```

**Acceptance criteria:**
- The SU tree-building test creates a 4-level path end-to-end and archives the shelf.
- The non-SU test fails loudly if the building layer leaks.
- The leaf-link test is either green or explicitly skipped with a note.

---

## Plan 3 complete

After Task 9, `/storage` is fully rebuilt:

- **Live:** Hierarchical browser with 4-level enforcement. Non-superusers see rooms first, superusers see buildings first. Admins can create / edit / archive rooms, cabinets and shelves; superusers additionally get buildings. Leaf shelves render the `ContainerCard` grid reused from the Chemicals page, and each card links back to the Chemicals page with that row expanded. Breadcrumbs deep-link. Drawer chrome, form patterns, role gating and theme all come from Plan 2.
- **Still old / deferred to later:**
  - **Unarchive storage locations** — the tree hides archived nodes, but there is no UI to bring them back; do it via Swagger or a future polish pass.
  - **Transitive container counts** — counts are direct-only by design; if users ask for "total containers in this room including all cabinets", revisit.
  - **Multi-building groups at the "Add room" root level** — v1 always uses the group's first building as the parent when a non-SU adds a room from the root. Groups with more than one building will need a building picker; deferred.
  - **Full Buildings manager** — lives in Plan 4 / Settings › Buildings (address, assigned groups, archival of buildings themselves).
  - **Drag-and-drop re-parenting** — explicitly out of scope per the parent spec's YAGNI list.

**Plan 4 (Settings) is independent of this plan and can be implemented in parallel.** The only shared surface is `StorageLocationNode` / `StorageKind` in `src/types/index.ts` — both plans must import, not redefine.
