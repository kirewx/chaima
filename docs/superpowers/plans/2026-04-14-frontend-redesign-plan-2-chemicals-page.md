# Frontend Redesign — Plan 2: Theme, Layout Shell & Chemicals Page

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the frontend visual shell (theme, top-nav layout, role gating, dark mode) and the main Chemicals page with the unified info-box design, container cards, multi-expand, and the shared create/edit drawer.

**Architecture:** Keep React 19 + MUI 9 + React Query + React Router. Rewrite `theme.ts` with a clinical light + dark palette swapped by a `ThemeProvider` that reads `user.dark_mode`. Replace `SearchPage`/`ChemicalCard`/`ChemicalDetail`/`SwipeableRow` with a new `ChemicalsPage` composed of `ChemicalRow`, `ChemicalInfoBox`, `ContainerGrid`, `FilterBar`. One shared `EditDrawer` hosts form bodies (`ChemicalForm`, `ContainerForm`). Forms are a slot pattern so the same drawer chrome is reused everywhere.

**Tech Stack:** React 19, MUI 9 `@emotion/react`, `@tanstack/react-query`, React Router 7, axios. Playwright for E2E. Parent spec: `docs/superpowers/specs/2026-04-14-frontend-redesign-design.md`. Backend from Plan 1 (merged, 182 tests green).

**Dependency notes:** Plan 1 must be merged. Plans 3 (Storage) and 4 (Settings) can be written in parallel once Plan 2 components (`EditDrawer`, `RoleGate`, theme) are in place.

---

## File map

**New files:**
- `src/pages/ChemicalsPage.tsx` (replaces `src/pages/SearchPage.tsx`)
- `src/components/RoleGate.tsx`
- `src/components/ChemicalList.tsx`
- `src/components/ChemicalRow.tsx`
- `src/components/ChemicalInfoBox.tsx`
- `src/components/ContainerCard.tsx`
- `src/components/ContainerGrid.tsx`
- `src/components/FilterBar.tsx`
- `src/components/drawer/EditDrawer.tsx`
- `src/components/drawer/ChemicalForm.tsx`
- `src/components/drawer/ContainerForm.tsx`
- `src/components/drawer/DrawerContext.tsx`
- `src/hooks/useTheme.ts`
- `e2e/chemicals.spec.ts`

**Modified files:**
- `src/theme.ts` (full rewrite — clinical palette + dark variant)
- `src/main.tsx` (`ThemeProvider` wrapper via `useTheme`)
- `src/App.tsx` (route `/` → `ChemicalsPage`)
- `src/components/Layout.tsx` (top nav replacing bottom nav)
- `src/components/FilterDrawer.tsx` (updates for `include_archived` filter)
- `src/types/index.ts` (new fields on `Chemical` type: `is_secret`, `is_archived`, `archived_at`, `structure_source`, `sds_path`)
- `src/api/hooks/useChemicals.ts` (new query params: `include_archived`; mutations for archive/unarchive/SDS-upload/secret-toggle)
- `src/api/hooks/useAuth.ts` or `useCurrentUser.ts` (expose `dark_mode`)

**Deleted files (after migration):**
- `src/components/ChemicalCard.tsx`
- `src/components/ChemicalDetail.tsx`
- `src/components/SwipeableRow.tsx`
- `src/pages/SearchPage.tsx` (moved to `ChemicalsPage.tsx`)

---

## Task 1: Rewrite theme.ts with clinical light + dark palette

**Files:** Modify `src/theme.ts`

- [ ] **Step 1: Replace the file contents with the new theme factory.**

```ts
import { createTheme, type Theme } from "@mui/material/styles";

const light = {
  bg: "#ffffff",
  surface: "#fafbfc",
  ink: "#0f172a",
  muted: "#64748b",
  subtle: "#94a3b8",
  border: "#e2e8f0",
  divider: "#f1f5f9",
  accent: "#4338ca",
  accentSoft: "#eef2ff",
  warn: "#fffbeb",
  warnBorder: "#f59e0b",
  danger: "#b91c1c",
  success: "#059669",
} as const;

const dark = {
  bg: "#0a0a0a",
  surface: "#141414",
  ink: "#e5e5e5",
  muted: "#a3a3a3",
  subtle: "#737373",
  border: "#262626",
  divider: "#1c1c1c",
  accent: "#818cf8",
  accentSoft: "#1e1b4b",
  warn: "#2a2106",
  warnBorder: "#f59e0b",
  danger: "#f87171",
  success: "#4ade80",
} as const;

export const createAppTheme = (mode: "light" | "dark"): Theme => {
  const c = mode === "dark" ? dark : light;
  return createTheme({
    palette: {
      mode,
      primary: { main: c.accent, contrastText: "#ffffff" },
      success: { main: c.success },
      error: { main: c.danger },
      warning: { main: c.warnBorder },
      background: { default: c.bg, paper: c.surface },
      text: { primary: c.ink, secondary: c.muted },
      divider: c.border,
    },
    shape: { borderRadius: 4 },
    typography: {
      fontFamily: "'Geist', -apple-system, system-ui, sans-serif",
      fontSize: 14,
      h1: { fontWeight: 600, fontSize: 26, letterSpacing: "-0.02em", lineHeight: 1.1 },
      h2: { fontWeight: 600, fontSize: 20, letterSpacing: "-0.015em", lineHeight: 1.15 },
      h3: { fontWeight: 600, fontSize: 16, letterSpacing: "-0.01em" },
      h4: { fontWeight: 600, fontSize: 14 },
      h5: { fontWeight: 600, fontSize: 12, letterSpacing: "0.05em", textTransform: "uppercase" },
      body1: { fontSize: 14, lineHeight: 1.5 },
      body2: { fontSize: 12, lineHeight: 1.5 },
      button: { textTransform: "none", fontWeight: 500, letterSpacing: 0 },
      caption: { fontSize: 11, letterSpacing: "0.02em" },
    },
    components: {
      MuiCssBaseline: { styleOverrides: { body: { backgroundColor: c.bg } } },
      MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundColor: c.surface,
            boxShadow: "none",
            border: `1px solid ${c.border}`,
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: { borderRadius: 4 },
          containedPrimary: {
            backgroundColor: c.ink,
            color: mode === "dark" ? c.bg : "#ffffff",
            "&:hover": { backgroundColor: c.accent },
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            backgroundColor: c.surface,
            borderRadius: 4,
            "& fieldset": { borderColor: c.border },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { borderRadius: 3, fontSize: 11, fontWeight: 500 },
        },
      },
      MuiDivider: { styleOverrides: { root: { borderColor: c.divider } } },
    },
  });
};

// Default export kept for backwards compatibility until main.tsx migrates.
export default createAppTheme("light");
```

- [ ] **Step 2: Commit.**

```bash
git add src/theme.ts
git commit -m "feat(theme): clinical light + dark palette factory"
```

---

## Task 2: `useTheme` hook + ThemeProvider integration

**Files:** Create `src/hooks/useTheme.ts`. Modify `src/main.tsx`.

- [ ] **Step 1: Create `src/hooks/useTheme.ts`:**

```ts
import { useMemo } from "react";
import { createAppTheme } from "../theme";
import { useCurrentUser } from "../api/hooks/useAuth";

export function useAppTheme() {
  const { data: user } = useCurrentUser();
  const mode = user?.dark_mode ? "dark" : "light";
  return useMemo(() => createAppTheme(mode), [mode]);
}
```

If the current-user hook is named differently (inspect `src/api/hooks/useAuth.ts` first), adapt the import. The hook must return a user object whose type eventually includes `dark_mode`.

- [ ] **Step 2: Update `src/main.tsx`** so `ThemeProvider` uses the dynamic theme. Wrap the existing `ThemeProvider` usage in a small component that calls `useAppTheme()`. If `main.tsx` currently imports the static default export, switch to the new dynamic version. Keep `CssBaseline`.

Example shape (adapt to the actual existing structure):

```tsx
function ThemedApp({ children }: { children: React.ReactNode }) {
  const theme = useAppTheme();
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}
```

Mount `ThemedApp` inside `QueryClientProvider` so the user query is available when `useAppTheme` reads it.

- [ ] **Step 3: Add `dark_mode` to the TypeScript `User` type** in `src/types/index.ts` (`dark_mode: boolean`). Add it to whatever schema/interface `useCurrentUser` returns.

- [ ] **Step 4: Manual verify.** Start `npm run dev`, log in, check the app renders. Then via Swagger UI: `PATCH /api/v1/users/me {"dark_mode": true}`, refresh the browser — theme should switch to dark (at least palette; full polish comes with individual components).

- [ ] **Step 5: Commit.**

```bash
git add src/hooks/useTheme.ts src/main.tsx src/types/index.ts
git commit -m "feat(theme): apply user.dark_mode preference app-wide"
```

---

## Task 3: Extend `Chemical` type and `useChemicals` hook

**Files:** Modify `src/types/index.ts` and `src/api/hooks/useChemicals.ts`.

- [ ] **Step 1: Update `Chemical` type** to match backend:

```ts
export type StructureSource = "none" | "pubchem" | "uploaded";

export interface Chemical {
  id: string;
  name: string;
  cas: string | null;
  // ... keep all existing fields
  is_secret: boolean;
  is_archived: boolean;
  archived_at: string | null;
  structure_source: StructureSource;
  sds_path: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}
```

Preserve whatever fields already exist — this is additive.

- [ ] **Step 2: Update `useChemicals` hook.** Read the existing hook first. Add support for:
  - Query param: `include_archived?: boolean` (optional, default false, append to query string when true)
  - New mutation: `useArchiveChemical(chemicalId)` → POST `.../chemicals/:id/archive`, invalidates list
  - New mutation: `useUnarchiveChemical(chemicalId)` → POST `.../chemicals/:id/unarchive`, invalidates list
  - New mutation: `useUploadSDS(chemicalId)` → POST `.../chemicals/:id/sds` as `multipart/form-data`, returns updated `Chemical`
  - The `useCreateChemical` mutation payload type must accept `is_secret?: boolean`, `structure_source?: StructureSource`, `sds_path?: string | null`
  - The `useUpdateChemical` mutation payload type must accept `is_secret?: boolean` (for secret-toggle)

Use the existing mutation pattern in the file — don't invent a new one.

- [ ] **Step 3: Manual verify via browser console** that the new mutations are reachable. Or skip and let Task 16 ("..." menu) be the first real user.

- [ ] **Step 4: Commit.**

```bash
git add src/types/index.ts src/api/hooks/useChemicals.ts
git commit -m "feat(api): expose archive/unarchive/sds hooks and new chemical fields"
```

---

## Task 4: `RoleGate` component

**Files:** Create `src/components/RoleGate.tsx`

- [ ] **Step 1: Create the component:**

```tsx
import type { ReactNode } from "react";
import { useCurrentUser } from "../api/hooks/useAuth";

type Role = "admin" | "superuser" | "creator";

interface Props {
  allow: Role[];
  creatorId?: string;
  children: ReactNode;
  fallback?: ReactNode;
}

export function RoleGate({ allow, creatorId, children, fallback = null }: Props) {
  const { data: user } = useCurrentUser();
  if (!user) return <>{fallback}</>;
  if (allow.includes("superuser") && user.is_superuser) return <>{children}</>;
  if (allow.includes("admin") && user.is_admin) return <>{children}</>;
  if (allow.includes("creator") && creatorId && user.id === creatorId) return <>{children}</>;
  return <>{fallback}</>;
}
```

**Note:** The backend does not yet distinguish admin from regular user at the permission layer (Plan 1 deferred that). Treat `is_admin` as equivalent to "is in group" for now — if the `is_admin` field doesn't exist on the user type, use `true` (any group member is an admin in v1) with a TODO comment. When a later mini-plan adds real group roles, this gate will already be in place to hang them on.

- [ ] **Step 2: Commit.**

```bash
git add src/components/RoleGate.tsx
git commit -m "feat(components): RoleGate for admin/superuser/creator visibility"
```

---

## Task 5: Rewrite Layout with top nav

**Files:** Modify `src/components/Layout.tsx`.

- [ ] **Step 1: Read the existing Layout** (currently uses `BottomNavigation`). Replace with a top-nav `AppBar` shell:

```tsx
import { AppBar, Toolbar, Box, Button, IconButton, Avatar, Menu, MenuItem } from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useCurrentUser } from "../api/hooks/useAuth";

const navItems = [
  { to: "/", label: "Chemicals" },
  { to: "/storage", label: "Storage" },
  { to: "/settings", label: "Settings" },
];

export default function Layout() {
  const { data: user } = useCurrentUser();
  const navigate = useNavigate();
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <AppBar
        position="sticky"
        elevation={0}
        color="default"
        sx={{ borderBottom: "1px solid", borderColor: "divider", bgcolor: "background.paper" }}
      >
        <Toolbar sx={{ minHeight: 52, gap: 2 }}>
          <Box sx={{ fontWeight: 700, fontSize: 16, letterSpacing: "-0.01em" }}>
            ChAIMa
          </Box>
          <Box sx={{ display: { xs: "none", sm: "flex" }, gap: 0.5, ml: 2 }}>
            {navItems.map((n) => (
              <Button
                key={n.to}
                component={NavLink}
                to={n.to}
                end={n.to === "/"}
                sx={{
                  color: "text.secondary",
                  px: 1.5,
                  "&.active": { color: "text.primary", fontWeight: 600 },
                }}
              >
                {n.label}
              </Button>
            ))}
          </Box>
          <Box sx={{ flex: 1 }} />
          <IconButton
            sx={{ display: { xs: "inline-flex", sm: "none" } }}
            onClick={() => setMobileOpen(true)}
          >
            <MenuIcon />
          </IconButton>
          <IconButton onClick={(e) => setMenuAnchor(e.currentTarget)}>
            <Avatar sx={{ width: 28, height: 28, fontSize: 12 }}>
              {user?.email?.[0]?.toUpperCase() ?? "?"}
            </Avatar>
          </IconButton>
          <Menu
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={() => setMenuAnchor(null)}
          >
            <MenuItem onClick={() => { setMenuAnchor(null); navigate("/settings"); }}>
              Settings
            </MenuItem>
            <MenuItem
              onClick={async () => {
                setMenuAnchor(null);
                await fetch("/api/v1/auth/jwt/logout", { method: "POST", credentials: "include" });
                navigate("/login");
              }}
            >
              Sign out
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ flex: 1, maxWidth: 1080, width: "100%", mx: "auto", p: { xs: 2, sm: 3 } }}>
        <Outlet />
      </Box>
      {/* TODO mobile drawer body — v1 just routes via avatar menu */}
    </Box>
  );
}
```

Remove the old `BottomNavigation` import and component. Ensure the file compiles. The mobile-drawer `mobileOpen` flag is set up but its body (a slide-in) can be a stub that opens the avatar menu for now; full mobile nav will be polished at the end.

Adapt the logout URL to whatever fastapi-users exposes (inspect the current Layout or LoginPage for the existing logout pattern).

- [ ] **Step 2: Manual verify.** Start dev server, log in, confirm nav items appear and active route is highlighted. Click Settings / Storage and see the existing pages still render.

- [ ] **Step 3: Commit.**

```bash
git add src/components/Layout.tsx
git commit -m "feat(layout): top-nav AppBar with Chemicals/Storage/Settings"
```

---

## Task 6: ChemicalsPage shell

**Files:**
- Create: `src/pages/ChemicalsPage.tsx`
- Modify: `src/App.tsx` (route `/` → `ChemicalsPage`)
- Delete: `src/pages/SearchPage.tsx` (only after the new page works end-to-end — do it in a later task, not now)

- [ ] **Step 1: Create `src/pages/ChemicalsPage.tsx`** with a minimal shell:

```tsx
import { Box, TextField, InputAdornment, IconButton, Stack } from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import TuneIcon from "@mui/icons-material/Tune";
import { useState } from "react";
import { useChemicals } from "../api/hooks/useChemicals";
import { useCurrentUser } from "../api/hooks/useAuth";
import { ChemicalList } from "../components/ChemicalList";

export default function ChemicalsPage() {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id;
  const [search, setSearch] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const { data, isLoading } = useChemicals(groupId, { search });

  if (!groupId) return <Box>No group selected.</Box>;

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={1} alignItems="center">
        <TextField
          size="small"
          fullWidth
          placeholder="Search chemical, CAS or container ID…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
        />
        <IconButton
          onClick={() => setFiltersOpen(true)}
          sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1 }}
        >
          <TuneIcon fontSize="small" />
        </IconButton>
      </Stack>
      {/* FilterBar: Task 7 */}
      <ChemicalList items={data?.items ?? []} loading={isLoading} />
      {/* FilterDrawer: Task 17 */}
    </Stack>
  );
}
```

`ChemicalList` will be stubbed empty in Task 8. For now, create it as a placeholder in the same commit so imports resolve:

```tsx
// src/components/ChemicalList.tsx
import { Box } from "@mui/material";
import type { Chemical } from "../types";

interface Props {
  items: Chemical[];
  loading: boolean;
}

export function ChemicalList({ items, loading }: Props) {
  if (loading) return <Box sx={{ p: 2, color: "text.secondary" }}>Loading…</Box>;
  if (items.length === 0)
    return <Box sx={{ p: 2, color: "text.secondary" }}>No chemicals.</Box>;
  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        overflow: "hidden",
        bgcolor: "background.paper",
      }}
    >
      {items.map((c) => (
        <Box key={c.id} sx={{ p: 1.5, borderBottom: "1px solid", borderColor: "divider" }}>
          {c.name}
        </Box>
      ))}
    </Box>
  );
}
```

- [ ] **Step 2: Update `src/App.tsx`** so the `/` route renders `ChemicalsPage` instead of `SearchPage`. Keep `SearchPage.tsx` on disk for now — delete it in Task 18.

- [ ] **Step 3: Manual verify.** Dev server → log in → see the new header + a simple list of names. No styling yet, just the skeleton.

- [ ] **Step 4: Commit.**

```bash
git add src/pages/ChemicalsPage.tsx src/components/ChemicalList.tsx src/App.tsx
git commit -m "feat(pages): ChemicalsPage shell with search header and list stub"
```

---

## Task 7: `FilterBar` component (active filter chips)

**Files:** Create `src/components/FilterBar.tsx`. Modify `src/pages/ChemicalsPage.tsx`.

- [ ] **Step 1: Create `src/components/FilterBar.tsx`:**

```tsx
import { Box, Chip } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

export interface ActiveFilter {
  key: string;
  label: string;
  onRemove: () => void;
}

export function FilterBar({ filters }: { filters: ActiveFilter[] }) {
  if (filters.length === 0) return null;
  return (
    <Box
      sx={{
        display: "flex",
        flexWrap: "wrap",
        gap: 0.75,
        px: 1,
        py: 1,
        borderBottom: "1px solid",
        borderColor: "divider",
        bgcolor: "background.default",
      }}
    >
      {filters.map((f) => (
        <Chip
          key={f.key}
          label={f.label}
          size="small"
          onDelete={f.onRemove}
          deleteIcon={<CloseIcon />}
          sx={{ bgcolor: "primary.main", color: "primary.contrastText" }}
        />
      ))}
    </Box>
  );
}
```

- [ ] **Step 2: Wire it in `ChemicalsPage`.** Maintain filter state `{ includeArchived: boolean, hazardTagId?: string, ghsCodeId?: string }` (use the existing filter shape of `useChemicals`). Build an `ActiveFilter[]` array from the state. Render `<FilterBar filters={...} />` between the search row and the list.

Include a small dot indicator on the filter `IconButton` when any filter is active (use `Badge` with `variant="dot"`).

- [ ] **Step 3: Manual verify.** With an empty filter state the bar is hidden. Setting a filter programmatically (via React devtools or temporary button) shows a chip; clicking its × removes it.

- [ ] **Step 4: Commit.**

```bash
git add src/components/FilterBar.tsx src/pages/ChemicalsPage.tsx
git commit -m "feat(components): FilterBar active-filter chips"
```

---

## Task 8: `ChemicalRow` collapsed row

**Files:** Create `src/components/ChemicalRow.tsx`. Modify `src/components/ChemicalList.tsx`.

- [ ] **Step 1: Create `ChemicalRow.tsx`:**

```tsx
import { Box, Stack, Typography, Chip } from "@mui/material";
import type { Chemical } from "../types";
import { useContainersForChemical } from "../api/hooks/useContainers";

interface Props {
  chemical: Chemical;
  expanded: boolean;
  onToggle: () => void;
}

export function ChemicalRow({ chemical, expanded, onToggle }: Props) {
  const { data: containers = [] } = useContainersForChemical(chemical.id);
  const active = containers.filter((c) => !c.is_archived);
  const first = active[0];
  const more = active.length - 1;

  return (
    <Box
      onClick={onToggle}
      sx={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        px: 2,
        py: 1.25,
        gap: 2,
        cursor: "pointer",
        bgcolor: expanded ? "background.default" : "transparent",
        "&:hover": { bgcolor: "action.hover" },
      }}
    >
      <Stack sx={{ minWidth: 0, flex: 1 }}>
        <Typography variant="body1" sx={{ fontWeight: 500, lineHeight: 1.2 }}>
          {chemical.name}
        </Typography>
        <Typography
          variant="caption"
          sx={{
            color: chemical.cas ? "text.secondary" : "text.disabled",
            fontStyle: chemical.cas ? "normal" : "italic",
            fontFamily: "'JetBrains Mono', ui-monospace, monospace",
            mt: 0.4,
          }}
        >
          {chemical.cas ?? "no CAS"}
        </Typography>
      </Stack>
      <Stack sx={{ textAlign: "right", pl: 2, flexShrink: 0 }}>
        <Stack direction="row" spacing={0.75} alignItems="center" justifyContent="flex-end">
          <Typography variant="body2" sx={{ fontWeight: 500 }}>
            {first ? `${first.location?.name ?? "—"}` : "—"}
          </Typography>
          {first && (
            <Chip
              label={first.identifier}
              size="small"
              sx={{
                bgcolor: "primary.light",
                color: "primary.dark",
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                fontSize: 10,
                height: 18,
              }}
            />
          )}
        </Stack>
        <Stack direction="row" spacing={0.75} alignItems="center" justifyContent="flex-end" mt={0.4}>
          <Typography variant="caption" color="text.disabled">
            {first ? `${first.amount} ${first.unit}` : "no containers"}
          </Typography>
          {more > 0 && (
            <Chip
              label={`+${more}`}
              size="small"
              sx={{ height: 16, fontSize: 10, bgcolor: "action.selected" }}
            />
          )}
        </Stack>
      </Stack>
    </Box>
  );
}
```

**Check `useContainersForChemical`.** If it doesn't exist in `src/api/hooks/useContainers.ts`, add it as a small hook that reuses the existing container list query filtered by chemical id. If there's already a different pattern (e.g. containers fetched eagerly with chemical detail), adapt — don't introduce a new network pattern.

- [ ] **Step 2: Render in `ChemicalList`.** Replace the placeholder `map` with:

```tsx
import { useState } from "react";
import { ChemicalRow } from "./ChemicalRow";

// ...
const [openIds, setOpenIds] = useState<Set<string>>(new Set());
const toggle = (id: string) => setOpenIds((prev) => {
  const next = new Set(prev);
  if (next.has(id)) next.delete(id); else next.add(id);
  return next;
});

return (
  <Box sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1, bgcolor: "background.paper" }}>
    {items.map((c, i) => (
      <Box key={c.id} sx={{ borderBottom: i < items.length - 1 ? "1px solid" : "none", borderColor: "divider" }}>
        <ChemicalRow
          chemical={c}
          expanded={openIds.has(c.id)}
          onToggle={() => toggle(c.id)}
        />
        {/* Expanded body: Task 10 */}
      </Box>
    ))}
  </Box>
);
```

- [ ] **Step 3: Manual verify.** Create a couple chemicals via Swagger (each with a container) → reload Chemicals page → rows show name/CAS + first container info. Click a row — nothing happens visually yet, but `expanded` state flips. Confirm via React devtools.

- [ ] **Step 4: Commit.**

```bash
git add src/components/ChemicalRow.tsx src/components/ChemicalList.tsx src/api/hooks/useContainers.ts
git commit -m "feat(components): ChemicalRow with location, container id and qty"
```

---

## Task 9: `ChemicalInfoBox` — structure thumb + bullets + sidebar

**Files:** Create `src/components/ChemicalInfoBox.tsx`. Modify `src/components/ChemicalList.tsx` to render it when expanded.

- [ ] **Step 1: Create `ChemicalInfoBox.tsx`:**

```tsx
import { Box, Stack, Typography, Chip, Link as MuiLink } from "@mui/material";
import LinkIcon from "@mui/icons-material/Link";
import DescriptionIcon from "@mui/icons-material/Description";
import type { Chemical } from "../types";
import type { Container } from "../types";

interface Props {
  chemical: Chemical;
  containers: Container[];
}

const propertyBullets = (c: Chemical): { k: string; v: string }[] => {
  const out: { k: string; v: string }[] = [];
  if (c.molar_mass) out.push({ k: "Molar mass", v: `${c.molar_mass} g/mol` });
  if (c.boiling_point != null) out.push({ k: "Boiling point", v: `${c.boiling_point} °C` });
  if (c.melting_point != null) out.push({ k: "Melting point", v: `${c.melting_point} °C` });
  if (c.density != null) out.push({ k: "Density", v: `${c.density} g/cm³` });
  return out;
};

export function ChemicalInfoBox({ chemical, containers }: Props) {
  const totals = containers.reduce<Record<string, number>>((acc, cont) => {
    acc[cont.unit] = (acc[cont.unit] ?? 0) + cont.amount;
    return acc;
  }, {});
  const totalText = Object.entries(totals)
    .map(([u, v]) => `${+v.toFixed(2)} ${u}`)
    .join(" · ");
  const props = propertyBullets(chemical);

  return (
    <Box
      sx={{
        m: 2,
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: "1fr 240px" },
        bgcolor: "background.paper",
        overflow: "hidden",
      }}
    >
      <Box sx={{ p: 2.5, display: "flex", gap: 2 }}>
        <Box sx={{ flexShrink: 0 }}>
          <Box
            sx={{
              width: { xs: 80, md: 100 },
              height: { xs: 80, md: 100 },
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 1,
              bgcolor: "background.default",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              p: 1,
            }}
          >
            {chemical.image_path ? (
              <Box component="img" src={`/uploads/${chemical.image_path}`} sx={{ maxWidth: "100%", maxHeight: "100%" }} />
            ) : (
              <Typography variant="caption" color="text.disabled">no structure</Typography>
            )}
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", textAlign: "center", mt: 0.5, textTransform: "uppercase", letterSpacing: "0.04em" }}>
            {chemical.structure_source === "pubchem" ? "PubChem" : chemical.structure_source === "uploaded" ? "Uploaded" : "—"}
          </Typography>
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Stack component="ul" sx={{ listStyle: "none", p: 0, m: 0 }}>
            {props.map((p) => (
              <Box component="li" key={p.k} sx={{ display: "flex", fontSize: 12, color: "text.primary", py: 0.3 }}>
                <Box sx={{ minWidth: 92, color: "text.secondary" }}>{p.k}</Box>
                <Box>{p.v}</Box>
              </Box>
            ))}
            {chemical.comment && (
              <Box
                component="li"
                sx={{
                  mt: 1,
                  p: 1.25,
                  bgcolor: "warning.light",
                  borderLeft: "2px solid",
                  borderColor: "warning.main",
                  borderRadius: "0 3px 3px 0",
                  fontSize: 12,
                }}
              >
                <Typography variant="caption" sx={{ display: "block", textTransform: "uppercase", letterSpacing: "0.04em", color: "warning.dark", fontWeight: 600, mb: 0.25 }}>
                  Comment
                </Typography>
                {chemical.comment}
              </Box>
            )}
          </Stack>
        </Box>
      </Box>
      <Box sx={{ p: 2, borderLeft: { md: "1px solid" }, borderTop: { xs: "1px solid", md: "none" }, borderColor: "divider", bgcolor: "background.default" }}>
        <Box sx={{ pb: 1.5, mb: 1.5, borderBottom: "1px solid", borderColor: "divider" }}>
          <Typography sx={{ fontSize: 20, fontWeight: 600, lineHeight: 1, color: "text.primary" }}>
            {totalText || "—"}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.4 }}>
            <b>{containers.length} containers</b>
          </Typography>
        </Box>
        <Typography variant="h5" sx={{ mb: 0.5 }}>Links</Typography>
        {chemical.cid && (
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mb: 0.5 }}>
            <LinkIcon sx={{ fontSize: 12, color: "primary.main" }} />
            <MuiLink href={`https://pubchem.ncbi.nlm.nih.gov/compound/${chemical.cid}`} target="_blank" rel="noopener" sx={{ fontSize: 11 }}>
              PubChem {chemical.cid}
            </MuiLink>
          </Stack>
        )}
        {chemical.sds_path && (
          <Stack direction="row" spacing={0.5} alignItems="center">
            <DescriptionIcon sx={{ fontSize: 12, color: "primary.main" }} />
            <MuiLink href={`/uploads/${chemical.sds_path}`} target="_blank" rel="noopener" sx={{ fontSize: 11 }}>
              Safety data sheet
            </MuiLink>
          </Stack>
        )}
      </Box>
    </Box>
  );
}
```

- [ ] **Step 2: Wire into `ChemicalList`.** When a row is expanded, render `<ChemicalInfoBox chemical={c} containers={containersFor(c.id)} />` under it. Fetch containers via the hook from Task 8. Add a temporary placeholder for the container grid (Task 11 will fill it). Use a collapse transition for smoothness — MUI `Collapse` component.

- [ ] **Step 3: Manual verify.** Expand a row with containers. Verify structure placeholder, property bullets, hero stat, and any links.

- [ ] **Step 4: Commit.**

```bash
git add src/components/ChemicalInfoBox.tsx src/components/ChemicalList.tsx
git commit -m "feat(components): ChemicalInfoBox unified structure/properties/sidebar"
```

---

## Task 10: `ContainerCard` + `ContainerGrid`

**Files:** Create `src/components/ContainerCard.tsx` and `src/components/ContainerGrid.tsx`.

- [ ] **Step 1: Create `ContainerCard.tsx`:**

```tsx
import { Box, Chip, Stack, Typography } from "@mui/material";
import QrCodeIcon from "@mui/icons-material/QrCode2";
import type { Container } from "../types";

export function ContainerCard({ container }: { container: Container }) {
  return (
    <Box
      sx={{
        position: "relative",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        bgcolor: "background.paper",
        p: 1.5,
      }}
    >
      <QrCodeIcon sx={{ position: "absolute", top: 10, right: 10, fontSize: 14, color: "text.disabled" }} />
      <Chip
        label={container.identifier}
        size="small"
        sx={{
          bgcolor: "primary.light",
          color: "primary.dark",
          fontFamily: "'JetBrains Mono', ui-monospace, monospace",
          fontWeight: 700,
          fontSize: 11,
          height: 20,
        }}
      />
      <Typography sx={{ fontSize: 15, fontWeight: 600, mt: 1 }}>
        {container.amount} {container.unit}
      </Typography>
      {container.purity && (
        <Typography variant="caption" color="text.secondary">Purity {container.purity}</Typography>
      )}
      <Stack sx={{ mt: 1, pt: 1, borderTop: "1px solid", borderColor: "divider", fontSize: 11, color: "text.secondary" }} spacing={0.25}>
        <Row k="Location" v={container.location?.name ?? "—"} />
        <Row k="Supplier" v={container.supplier?.name ?? "—"} />
        <Row k="Received" v={container.purchased_at ?? "—"} />
      </Stack>
    </Box>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <Stack direction="row" spacing={0.75}>
      <Box sx={{ minWidth: 60, color: "text.disabled" }}>{k}</Box>
      <Box>{v}</Box>
    </Stack>
  );
}
```

- [ ] **Step 2: Create `ContainerGrid.tsx`:**

```tsx
import { Box, Button, Stack, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import type { Container } from "../types";
import { ContainerCard } from "./ContainerCard";

interface Props {
  containers: Container[];
  onAdd: () => void;
}

export function ContainerGrid({ containers, onAdd }: Props) {
  return (
    <Box sx={{ px: 2, pb: 2 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
        <Typography variant="h5">Containers ({containers.length})</Typography>
        <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={onAdd}>
          Container
        </Button>
      </Stack>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(auto-fill, minmax(210px, 1fr))" }, gap: 1.25 }}>
        {containers.map((c) => (
          <ContainerCard key={c.id} container={c} />
        ))}
      </Box>
    </Box>
  );
}
```

- [ ] **Step 3: Wire into `ChemicalList`** — render `<ContainerGrid containers={...} onAdd={() => openDrawer(...)} />` under each expanded info box. The `onAdd` stub can be `() => alert("drawer coming in Task 13")` until the drawer exists.

- [ ] **Step 4: Manual verify.** Expand a chemical with containers — see the grid of cards.

- [ ] **Step 5: Commit.**

```bash
git add src/components/ContainerCard.tsx src/components/ContainerGrid.tsx src/components/ChemicalList.tsx
git commit -m "feat(components): ContainerCard + ContainerGrid with +button"
```

---

## Task 11: `DrawerContext` + `EditDrawer` shell

**Files:** Create `src/components/drawer/EditDrawer.tsx` and `src/components/drawer/DrawerContext.tsx`.

- [ ] **Step 1: Create `DrawerContext.tsx`:**

```tsx
import { createContext, useContext, useState, type ReactNode } from "react";

type DrawerConfig =
  | { kind: "chemical-new" }
  | { kind: "chemical-edit"; chemicalId: string }
  | { kind: "container-new"; chemicalId: string }
  | { kind: "container-edit"; containerId: string }
  | null;

interface Ctx {
  config: DrawerConfig;
  open: (c: Exclude<DrawerConfig, null>) => void;
  close: () => void;
}

const DrawerCtx = createContext<Ctx | null>(null);

export function DrawerProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<DrawerConfig>(null);
  return (
    <DrawerCtx.Provider value={{ config, open: setConfig, close: () => setConfig(null) }}>
      {children}
    </DrawerCtx.Provider>
  );
}

export function useDrawer() {
  const v = useContext(DrawerCtx);
  if (!v) throw new Error("useDrawer outside DrawerProvider");
  return v;
}
```

- [ ] **Step 2: Create `EditDrawer.tsx`:**

```tsx
import { Drawer, Box, Stack, Typography, IconButton } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useDrawer } from "./DrawerContext";
import { ChemicalForm } from "./ChemicalForm";
import { ContainerForm } from "./ContainerForm";

const titles: Record<string, string> = {
  "chemical-new": "New chemical",
  "chemical-edit": "Edit chemical",
  "container-new": "New container",
  "container-edit": "Edit container",
};

export function EditDrawer() {
  const { config, close } = useDrawer();
  if (!config) return null;

  return (
    <Drawer
      anchor="right"
      open
      onClose={close}
      PaperProps={{ sx: { width: { xs: "100%", sm: 480 } } }}
    >
      <Stack direction="row" alignItems="center" sx={{ p: 2, borderBottom: "1px solid", borderColor: "divider" }}>
        <Typography variant="h3" sx={{ flex: 1 }}>{titles[config.kind]}</Typography>
        <IconButton onClick={close} size="small"><CloseIcon /></IconButton>
      </Stack>
      <Box sx={{ flex: 1, p: 2, overflowY: "auto" }}>
        {(config.kind === "chemical-new" || config.kind === "chemical-edit") && (
          <ChemicalForm
            chemicalId={config.kind === "chemical-edit" ? config.chemicalId : undefined}
            onDone={close}
          />
        )}
        {(config.kind === "container-new" || config.kind === "container-edit") && (
          <ContainerForm
            chemicalId={config.kind === "container-new" ? config.chemicalId : undefined}
            containerId={config.kind === "container-edit" ? config.containerId : undefined}
            onDone={close}
          />
        )}
      </Box>
    </Drawer>
  );
}
```

- [ ] **Step 3: Mount `DrawerProvider` + `<EditDrawer />`** inside the `Layout` component so the drawer context covers all routed pages.

- [ ] **Step 4: Stubs for forms.** Create `src/components/drawer/ChemicalForm.tsx` and `ContainerForm.tsx` as placeholders that return a single "Coming soon" `Typography`. They'll be fleshed out in Tasks 12 and 13.

- [ ] **Step 5: Commit.**

```bash
git add src/components/drawer/ src/components/Layout.tsx
git commit -m "feat(drawer): EditDrawer shell + DrawerProvider with form slots"
```

---

## Task 12: `ChemicalForm` (create + edit)

**Files:** Replace `src/components/drawer/ChemicalForm.tsx`.

- [ ] **Step 1: Implement the form:**

```tsx
import { Button, Stack, TextField, FormControlLabel, Switch, Alert, Typography } from "@mui/material";
import { useState, useEffect } from "react";
import { useCreateChemical, useUpdateChemical, useChemical } from "../../api/hooks/useChemicals";
import { useCurrentUser } from "../../api/hooks/useAuth";

interface Props {
  chemicalId?: string;
  onDone: () => void;
}

export function ChemicalForm({ chemicalId, onDone }: Props) {
  const { data: user } = useCurrentUser();
  const existing = useChemical(chemicalId);
  const create = useCreateChemical(user?.main_group_id);
  const update = useUpdateChemical(user?.main_group_id, chemicalId);

  const [name, setName] = useState("");
  const [cas, setCas] = useState("");
  const [comment, setComment] = useState("");
  const [isSecret, setIsSecret] = useState(false);

  useEffect(() => {
    if (existing.data) {
      setName(existing.data.name);
      setCas(existing.data.cas ?? "");
      setComment(existing.data.comment ?? "");
      setIsSecret(existing.data.is_secret);
    }
  }, [existing.data]);

  const saving = create.isPending || update.isPending;
  const err = create.error || update.error;

  return (
    <Stack spacing={2}>
      {err instanceof Error && <Alert severity="error">{err.message}</Alert>}

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
        helperText="Optional. PubChem lookup coming later."
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
        control={<Switch checked={isSecret} onChange={(_, v) => setIsSecret(v)} />}
        label={
          <Stack>
            <Typography variant="body2">Mark as secret</Typography>
            <Typography variant="caption" color="text.secondary">
              Only you and system admins will see this chemical.
            </Typography>
          </Stack>
        }
      />

      <Stack direction="row" spacing={1} justifyContent="flex-end" mt={2}>
        <Button onClick={onDone} disabled={saving}>Cancel</Button>
        <Button
          variant="contained"
          disabled={saving || !name.trim()}
          onClick={async () => {
            const payload = { name: name.trim(), cas: cas.trim() || null, comment: comment.trim() || null, is_secret: isSecret };
            if (chemicalId) {
              await update.mutateAsync(payload);
            } else {
              await create.mutateAsync(payload);
            }
            onDone();
          }}
        >
          {chemicalId ? "Save" : "Create"}
        </Button>
      </Stack>
    </Stack>
  );
}
```

Inspect the existing `useCreateChemical` / `useUpdateChemical` mutation signatures first and adapt the payload shape. If `useChemical(id)` doesn't exist yet, add a small hook that fetches a single chemical (or falls back to finding it in the list cache). Don't stop on this — if needed, the form can skip pre-fill on edit and accept stale values for now, but that's ugly; prefer adding the one-liner hook.

- [ ] **Step 2: Add "+ New chemical" button on `ChemicalsPage`** (top right of search row, before the filter icon). `onClick` → `openDrawer({ kind: "chemical-new" })`.

- [ ] **Step 3: Manual verify.** Click "+ New chemical" → drawer opens → enter name → create → drawer closes, new row appears. Edit an existing chemical via the "..." menu (Task 14) — for now trigger `open({kind:"chemical-edit", chemicalId})` manually via devtools.

- [ ] **Step 4: Commit.**

```bash
git add src/components/drawer/ChemicalForm.tsx src/pages/ChemicalsPage.tsx src/api/hooks/useChemicals.ts
git commit -m "feat(drawer): ChemicalForm with create/edit + secret toggle"
```

---

## Task 13: `ContainerForm` (create + edit)

**Files:** Replace `src/components/drawer/ContainerForm.tsx`.

- [ ] **Step 1: Implement the form** with fields: Identifier, Amount, Unit, Purity, Location (picker — use the existing `LocationPicker` component), Supplier (id picker from existing `useSuppliers` hook), Received date. Use `useCreateContainer` / `useUpdateContainer` from `useContainers` hook — inspect first.

Shape:

```tsx
<Stack spacing={2}>
  <TextField label="Identifier" required value={identifier} onChange={e => setIdentifier(e.target.value)} size="small" helperText="Unique within your group" />
  <Stack direction="row" spacing={1}>
    <TextField label="Amount" type="number" value={amount} onChange={e => setAmount(+e.target.value)} sx={{ flex: 1 }} size="small" />
    <TextField label="Unit" value={unit} onChange={e => setUnit(e.target.value)} sx={{ width: 80 }} size="small" />
  </Stack>
  <TextField label="Purity" value={purity} onChange={e => setPurity(e.target.value)} size="small" placeholder="e.g. 99.8%" />
  <LocationPicker value={locationId} onChange={setLocationId} />
  <SupplierPicker value={supplierId} onChange={setSupplierId} />
  <TextField label="Received" type="date" InputLabelProps={{ shrink: true }} value={receivedDate ?? ""} onChange={e => setReceivedDate(e.target.value || null)} size="small" />
  {/* actions: Cancel / Create|Save */}
</Stack>
```

If `LocationPicker` already exists, reuse it. If `SupplierPicker` doesn't, use a simple `Select` of suppliers from `useSuppliers`.

The field `Received` maps to backend `purchased_at` (date). The frontend label is "Received".

On 400 response with `Container identifier '...' already in use in this group` → show under the Identifier field as an error.

- [ ] **Step 2: Wire `+ Container` button** in `ContainerGrid` to `open({ kind: "container-new", chemicalId })`.

- [ ] **Step 3: Manual verify.** Expand a chemical → click + Container → drawer opens → fill in fields → create → card appears in the grid.

- [ ] **Step 4: Commit.**

```bash
git add src/components/drawer/ContainerForm.tsx src/components/ContainerGrid.tsx src/api/hooks/useContainers.ts
git commit -m "feat(drawer): ContainerForm with create/edit and group-unique identifier error"
```

---

## Task 14: "..." menu (Edit / Archive / Toggle secret)

**Files:** Create `src/components/ChemicalMenu.tsx`. Modify `src/components/ChemicalList.tsx`.

- [ ] **Step 1: Create `ChemicalMenu.tsx`:**

```tsx
import { IconButton, Menu, MenuItem, ListItemIcon, ListItemText, Divider } from "@mui/material";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import EditIcon from "@mui/icons-material/Edit";
import ArchiveIcon from "@mui/icons-material/Archive";
import UnarchiveIcon from "@mui/icons-material/Unarchive";
import LockIcon from "@mui/icons-material/Lock";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import { useState } from "react";
import type { Chemical } from "../types";
import { useArchiveChemical, useUnarchiveChemical, useUpdateChemical } from "../api/hooks/useChemicals";
import { useDrawer } from "./drawer/DrawerContext";
import { RoleGate } from "./RoleGate";
import { useCurrentUser } from "../api/hooks/useAuth";

export function ChemicalMenu({ chemical }: { chemical: Chemical }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const { open } = useDrawer();
  const { data: user } = useCurrentUser();
  const archive = useArchiveChemical(user?.main_group_id, chemical.id);
  const unarchive = useUnarchiveChemical(user?.main_group_id, chemical.id);
  const update = useUpdateChemical(user?.main_group_id, chemical.id);
  const close = () => setAnchor(null);

  return (
    <RoleGate allow={["admin", "superuser", "creator"]} creatorId={chemical.created_by}>
      <IconButton
        size="small"
        onClick={(e) => { e.stopPropagation(); setAnchor(e.currentTarget); }}
        sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1 }}
      >
        <MoreHorizIcon fontSize="small" />
      </IconButton>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={close}>
        <MenuItem onClick={() => { close(); open({ kind: "chemical-edit", chemicalId: chemical.id }); }}>
          <ListItemIcon><EditIcon fontSize="small" /></ListItemIcon>
          <ListItemText>Edit chemical</ListItemText>
        </MenuItem>
        {chemical.is_archived ? (
          <MenuItem onClick={async () => { await unarchive.mutateAsync(); close(); }}>
            <ListItemIcon><UnarchiveIcon fontSize="small" /></ListItemIcon>
            <ListItemText>Unarchive</ListItemText>
          </MenuItem>
        ) : (
          <MenuItem onClick={async () => { await archive.mutateAsync(); close(); }}>
            <ListItemIcon><ArchiveIcon fontSize="small" /></ListItemIcon>
            <ListItemText>Archive</ListItemText>
          </MenuItem>
        )}
        <Divider />
        <MenuItem onClick={async () => { await update.mutateAsync({ is_secret: !chemical.is_secret }); close(); }}>
          <ListItemIcon>
            {chemical.is_secret ? <LockOpenIcon fontSize="small" /> : <LockIcon fontSize="small" />}
          </ListItemIcon>
          <ListItemText>{chemical.is_secret ? "Make public" : "Mark as secret"}</ListItemText>
        </MenuItem>
      </Menu>
    </RoleGate>
  );
}
```

- [ ] **Step 2: Render `<ChemicalMenu chemical={c} />`** in the top-right of the expanded info-box area. Position it absolutely so it doesn't disrupt the grid layout. Use `position: "relative"` on the expanded container and `position: "absolute"; top: 12px; right: 12px` on the menu.

- [ ] **Step 3: Manual verify.** Expand a row → see `...` button top-right → click → menu with Edit / Archive / Mark as secret. Test: Archive a chemical → it disappears from the list. Toggle "Include archived" filter → comes back. Toggle again → unarchive works. Mark as secret → row updates (gains a lock indicator if you've added one — optional). Log in as a second user → the secret chemical is gone.

- [ ] **Step 4: Commit.**

```bash
git add src/components/ChemicalMenu.tsx src/components/ChemicalList.tsx
git commit -m "feat(components): ChemicalMenu with edit, archive, secret toggle"
```

---

## Task 15: Update `FilterDrawer` with `include_archived` option

**Files:** Modify `src/components/FilterDrawer.tsx`.

- [ ] **Step 1:** Read the existing drawer. Add a new section at the top with a switch `Include archived`. Wire it into the filter state maintained in `ChemicalsPage`. Remove any legacy filter fields that no longer match the spec (e.g. if there's an old "GHS code" filter still wired, leave it).

- [ ] **Step 2: Manual verify.** Open filter drawer → toggle Include archived → archived rows appear.

- [ ] **Step 3: Commit.**

```bash
git add src/components/FilterDrawer.tsx src/pages/ChemicalsPage.tsx
git commit -m "feat(filters): include_archived option in FilterDrawer"
```

---

## Task 16: Responsive polish

**Files:** Various.

- [ ] **Step 1: Verify breakpoints.** Resize browser to 375 px and confirm:
  - Info box stacks (grid becomes 1 column)
  - Structure drops to 80×80
  - Container cards become 1 column
  - Row header right column truncates name with ellipsis (add `minWidth: 0` + `noWrap` to the name Typography if missing)
  - Search row still fits

- [ ] **Step 2: Fix any issues** — most commonly adding `minWidth: 0` to flex children, removing fixed widths on mobile, and tuning `gap` spacing. Also ensure the mobile nav opens via the avatar menu (Settings / Sign out) — no need for a separate drawer right now.

- [ ] **Step 3: Commit.**

```bash
git add -u src/components/ src/pages/
git commit -m "fix(responsive): polish Chemicals page at mobile breakpoints"
```

---

## Task 17: Playwright E2E for the full Chemicals flow

**Files:** Create `e2e/chemicals.spec.ts`.

- [ ] **Step 1: Write the spec.** Use the existing Playwright setup — check `playwright.config.ts` for the base URL and auth helpers.

```ts
import { test, expect } from "@playwright/test";

test.describe("Chemicals page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[name="email"]', "admin@chaima.dev");
    await page.fill('input[name="password"]', "changeme");
    await page.click('button[type="submit"]');
    await page.waitForURL("/");
  });

  test("create, expand, archive, unarchive", async ({ page }) => {
    // Create
    await page.click("text=New chemical");
    await page.fill('input[name="name"]', "E2E Test Mol");
    await page.click("text=Create");
    await expect(page.locator("text=E2E Test Mol")).toBeVisible();

    // Expand
    await page.click("text=E2E Test Mol");
    await expect(page.locator("text=Containers")).toBeVisible();

    // Archive via "..." menu
    await page.click('[aria-label="More"]');  // whatever selector lands on the menu button
    await page.click("text=Archive");
    await expect(page.locator("text=E2E Test Mol")).not.toBeVisible();

    // Include archived
    await page.click('[aria-label="Filters"]');
    await page.click("text=Include archived");
    await expect(page.locator("text=E2E Test Mol")).toBeVisible();

    // Unarchive
    await page.click("text=E2E Test Mol");
    await page.click('[aria-label="More"]');
    await page.click("text=Unarchive");
  });

  test("mark as secret hides from other users", async ({ page, context }) => {
    // Create secret
    await page.click("text=New chemical");
    await page.fill('input[name="name"]', "Secret E2E");
    await page.click("text=Mark as secret");
    await page.click("text=Create");
    await expect(page.locator("text=Secret E2E")).toBeVisible();

    // Log in as another user in a different browser context
    // This test needs a second user to exist — create via API in beforeAll or skip here
    // If the second user flow is too much, narrow this test to just: creator still sees it.
    // await context.clearCookies();  // etc.
  });
});
```

Selectors (`text=`, `aria-label`) may not match — inspect the rendered DOM with devtools and tighten them. Add `aria-label` attributes in the components if needed to make selectors stable.

- [ ] **Step 2: Run the test locally.**

```bash
cd frontend
npm run test:e2e -- chemicals.spec.ts
```

Fix any failures.

- [ ] **Step 3: Commit.**

```bash
git add frontend/e2e/chemicals.spec.ts
# and any selector fixups in components
git commit -m "test(e2e): Chemicals page — create, expand, archive, secret flow"
```

---

## Task 18: Clean up dead files

**Files:** Delete obsolete files.

- [ ] **Step 1:** Now that ChemicalsPage is live, delete:

```bash
rm src/pages/SearchPage.tsx
rm src/components/ChemicalCard.tsx
rm src/components/ChemicalDetail.tsx
rm src/components/SwipeableRow.tsx
```

Before deleting, `grep -r` (or use the IDE) to confirm none of these are still imported anywhere. If they are, remove the imports or migrate the usage.

- [ ] **Step 2: Run type check + e2e.**

```bash
npm run build      # tsc -b && vite build
npm run test:e2e
```

Both green.

- [ ] **Step 3: Commit.**

```bash
git add -u
git commit -m "chore: remove old SearchPage / ChemicalCard / ChemicalDetail / SwipeableRow"
```

---

## Plan 2 complete

After Task 18, the main Chemicals page and theme are live. Login still works; Storage and Settings still use their old code (Plan 3 and Plan 4 will rebuild them). Dark mode works via `PATCH /users/me` — Plan 4 will add the UI toggle in Settings.

Known gaps handed to later plans:
- **PubChem lookup** on CAS blur — stub only, implement later
- **Structure image upload** in ChemicalForm — skipped for v1, users can set it via Swagger
- **Edit permission refinements** — backend still uses group-membership only; `RoleGate` is in place for when roles exist
- **Mobile nav drawer body** — avatar menu handles Settings/Sign out in v1; full slide-in can come later if needed

Next plan: Plan 3 Storage page, or Plan 4 Settings page. Both can be written now.
