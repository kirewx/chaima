# ChAIMa Frontend Design

**Date:** 2026-04-10
**Status:** Draft
**Stack:** Vite + React + TypeScript + MUI + TanStack Query + Axios

## Overview

Mobile-first React SPA for ChAIMa, a multi-tenant chemical inventory management system. Consumed by lab researchers at the bench for quick lookups, adding chemicals, and managing containers. Talks to the FastAPI backend via cookie auth (same-origin).

### Key decisions

- **Vite + React + TypeScript** — lightweight SPA, no SSR needed, fast dev with bun
- **MUI** — component library for mobile patterns (BottomNavigation, SwipeableDrawer, Breadcrumbs, Chips)
- **TanStack Query** — server state management with `useQuery`/`useMutation`, optimistic updates for swipe actions, cache invalidation after creates
- **Axios** — HTTP client with interceptors for error handling, global cookie credentials config
- **Mobile-first, responsive** — bottom tab bar on mobile, sidebar rail on desktop
- **Cookie auth** — httpOnly cookies, same-origin with FastAPI backend via Vite proxy in dev

## Project Structure

```
frontend/                      # Inside chaima repo root
├── src/
│   ├── main.tsx               # Entry point, QueryClientProvider
│   ├── App.tsx                # Router + Layout shell
│   ├── theme.ts               # MUI theme config (dark mode, palette)
│   ├── api/
│   │   ├── client.ts          # Axios instance (baseURL, withCredentials, interceptors)
│   │   └── hooks/
│   │       ├── useChemicals.ts
│   │       ├── useContainers.ts
│   │       ├── useStorageLocations.ts
│   │       ├── useSuppliers.ts
│   │       ├── useHazardTags.ts
│   │       ├── useGHSCodes.ts
│   │       ├── useGroups.ts
│   │       └── useAuth.ts
│   ├── components/
│   │   ├── Layout.tsx         # Shell: bottom tabs (mobile) / sidebar rail (desktop)
│   │   ├── SearchBar.tsx      # Controlled input, debounced 300ms
│   │   ├── FilterDrawer.tsx   # MUI SwipeableDrawer (bottom sheet)
│   │   ├── FilterBadges.tsx   # Row of dismissable MUI Chips
│   │   ├── ChemicalCard.tsx   # Collapsed + expandable chemical card
│   │   ├── ContainerRow.tsx   # Container line item within a chemical card
│   │   ├── SwipeableRow.tsx   # Swipe gesture wrapper (left=archive, right=add)
│   │   ├── UndoSnackbar.tsx   # Timed undo after archive
│   │   ├── LocationPicker.tsx # Breadcrumb tree picker dialog (reused in forms)
│   │   └── ProtectedRoute.tsx # Auth guard, redirects to login
│   ├── pages/
│   │   ├── SearchPage.tsx     # Chemical list with live search (landing)
│   │   ├── ChemicalForm.tsx   # Add/edit chemical
│   │   ├── ContainerForm.tsx  # Add/edit container
│   │   ├── StoragePage.tsx    # Breadcrumb drill-down storage browser
│   │   ├── SettingsPage.tsx   # Group selector, profile, tag/supplier management
│   │   ├── LoginPage.tsx
│   │   └── RegisterPage.tsx
│   └── types/
│       └── index.ts           # TS types mirroring API schemas
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts             # Proxy /api → FastAPI dev server
```

## Navigation

### Mobile (< 768px): Bottom Tab Bar

Four persistent tabs via MUI `BottomNavigation`:

| Tab | Icon | Page | Description |
|-----|------|------|-------------|
| Search | magnifying glass | SearchPage | Landing tab, live search + chemical list |
| Add | plus | ChemicalForm | Add new chemical |
| Storage | cabinet | StoragePage | Browse storage locations |
| Settings | gear | SettingsPage | Group, profile, tag management |

### Desktop (≥ 768px): Sidebar Rail

Same four items rendered as a slim vertical icon sidebar via MUI `Drawer` (permanent, mini variant). Content area gets full remaining width for richer table layouts.

### Routing

```
/                    → SearchPage (default tab)
/add                 → ChemicalForm (new)
/chemicals/:id/edit  → ChemicalForm (edit)
/containers/new      → ContainerForm (with ?chemicalId= query param)
/containers/:id/edit → ContainerForm (edit)
/storage             → StoragePage (root)
/storage/:id         → StoragePage (drilled into location)
/settings            → SettingsPage
/login               → LoginPage
/register            → RegisterPage
```

All routes except `/login` and `/register` are wrapped in `ProtectedRoute`.

## Pages

### SearchPage (landing)

The primary view. Renders:

1. **SearchBar** — controlled text input. Debounced at 300ms. Fires `GET /api/v1/groups/{gid}/chemicals?search=<query>`. Shows match highlighting on name/CAS in results.
2. **Filter icon button** — next to search bar. Tapping opens `FilterDrawer`.
3. **FilterBadges** — row of MUI `Chip` components below search bar for active filters. Each chip has `onDelete` to remove that filter.
4. **Chemical list** — scrollable list of `ChemicalCard` components.

Pagination: infinite scroll via TanStack Query's `useInfiniteQuery`. Loads next page when scrolling near bottom.

#### FilterDrawer

MUI `SwipeableDrawer` anchored to bottom. Contains:

- **Has stock** toggle (maps to `has_containers=true`)
- **Hazard tag** chips (multi-select, maps to `hazard_tag_id`)
- **GHS code** chips (multi-select, maps to `ghs_code_id`)
- **Sort** dropdown: name, CAS, created_at, updated_at
- **Order** toggle: asc / desc
- **Apply** button closes drawer and triggers search

#### ChemicalCard

**Collapsed state** (default in list):
- Chemical name (bold), CAS number, molecular formula
- Hazard tag badges (colored chips, e.g., red "Flammable", yellow "Oxidizing")
- Container rows inline: each shows amount + unit, supplier, storage location path
- Chemicals with no containers shown dimmed with "No containers" text

**Expanded state** (tap to toggle):
- All collapsed info plus:
- Physical properties grid: molar mass, density, melting point, boiling point
- GHS code pictogram badges with signal word
- Richer container rows: identifier, purchase date, full location path
- Swipe hints for container actions

#### Swipe Gestures

- **Swipe left on ContainerRow** → reveals red "Archive" action. Triggers `DELETE /containers/{id}` (soft delete). Shows `UndoSnackbar` with timed undo (5 seconds) via `PATCH /containers/{id}` with `is_archived: false`.
- **Swipe right on ChemicalCard** → reveals green "Add" action. Navigates to `ContainerForm` with the chemical pre-selected.

Implemented with touch event handlers. Threshold: 80px horizontal swipe.

### ChemicalForm

Simple single-page form for creating/editing a chemical.

**Fields:**
- Name (required) — text input
- CAS — text input
- SMILES — text input
- PubChem CID — text input
- Molecular formula (structure) — text input
- Molar mass — number input
- Density — number input
- Melting point — number input
- Boiling point — number input
- Comment — multiline text

Optional fields collapsed under an "Additional details" expandable section. Only name is visible by default.

Submit: `POST /api/v1/groups/{gid}/chemicals` (create) or `PATCH /api/v1/groups/{gid}/chemicals/{id}` (edit). On success, navigate to SearchPage. TanStack Query invalidates chemicals cache.

Future: auto-complete from PubChem or AI photo upload will slot into this form as a pre-fill step before the fields.

### ContainerForm

Triggered by swipe-right on a chemical, or from expanded chemical detail.

**Fields:**
- Chemical — pre-filled and read-only when coming from swipe, otherwise searchable dropdown
- Location — `LocationPicker` dialog (breadcrumb drill-down, reuses StoragePage navigation)
- Supplier — autocomplete dropdown (from group suppliers)
- Identifier — text input (required)
- Amount — number input (required)
- Unit — text input (required, e.g., "mL", "g", "kg")
- Purchase date — date picker

Submit: `POST /api/v1/groups/{gid}/chemicals/{cid}/containers`. On success, navigate back. TanStack Query invalidates containers + chemicals cache.

### StoragePage

Breadcrumb drill-down navigation through the storage location hierarchy.

**Layout:**
1. **Breadcrumb trail** — tappable segments: All > Room A > Shelf 1. Uses MUI `Breadcrumbs`.
2. **Current location header** — name, parent context, edit icon (rename/delete), "+ Add" button (creates child).
3. **Sub-locations list** — cards for each child location. Tap to drill in. Shows container count.
4. **Containers list** — containers stored directly at this location.

**Root level** shows all top-level locations with an "+ New" button for creating root locations.

**"+ Add" action** opens a dialog with name + description fields. Creates as child of current location via `POST /api/v1/groups/{gid}/storage-locations` with `parent_id`.

**Edit action** opens dialog to rename or delete (only if no containers).

### SettingsPage

- **Group selector** — dropdown for users in multiple groups. Changing group resets all caches.
- **Profile** — read-only email display
- **Hazard tags** — list with inline edit, delete, add new
- **Suppliers** — list with inline edit, delete, add new
- **Logout** button

### Auth Pages

**LoginPage** — email + password form. `POST /api/v1/auth/login`. On success, redirect to `/`.

**RegisterPage** — email + password form. `POST /api/v1/auth/register`. On success, redirect to login.

Both pages are full-screen, no tab bar.

## API Client Layer

### Axios Instance (`api/client.ts`)

```typescript
const client = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,   // Send cookies
});

// Response interceptor: 401 → redirect to /login
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);
```

### TanStack Query Hooks

Each hook file exports query/mutation hooks for a resource. Example pattern:

```typescript
// useChemicals.ts
export function useChemicals(groupId: string, params: ChemicalSearchParams) {
  return useInfiniteQuery({
    queryKey: ["chemicals", groupId, params],
    queryFn: ({ pageParam = 0 }) =>
      client.get(`/groups/${groupId}/chemicals`, {
        params: { ...params, offset: pageParam },
      }).then(res => res.data),
    getNextPageParam: (lastPage) => {
      const next = lastPage.offset + lastPage.limit;
      return next < lastPage.total ? next : undefined;
    },
  });
}
```

Mutations use `useMutation` with `onSuccess` cache invalidation and optimistic updates where appropriate (swipe-to-archive).

### Group Context

Active group stored in React context (`GroupContext`). All API hooks receive `groupId` from this context. Changing group in settings clears the TanStack Query cache via `queryClient.clear()`.

## Types (`types/index.ts`)

Mirror the API response schemas:

```typescript
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

interface ChemicalRead { ... }
interface ChemicalDetail extends ChemicalRead {
  synonyms: SynonymRead[];
  ghs_codes: GHSCodeRead[];
  hazard_tags: HazardTagRead[];
}
interface ContainerRead { ... }
interface StorageLocationNode {
  id: string;
  name: string;
  description: string | null;
  children: StorageLocationNode[];
}
// ... etc, matching API spec
```

## Theme

MUI dark theme. Custom palette:

- **Primary:** blue (#2563eb) — active tabs, search highlights, links
- **Success:** green (#4ade80) — container stock indicators, add actions
- **Error:** red (#f87171) — hazard tags, no-stock indicators, archive actions
- **Warning:** amber (#fbbf24) — GHS pictograms, caution states
- **Background:** near-black (#0a0a0a) with surface cards (#1a1a1a)
- **Text:** white primary, gray (#888) secondary

## Dev Setup

```bash
cd frontend
bun install
bun dev          # Starts Vite dev server with proxy to FastAPI
```

Vite config proxies `/api` to `http://localhost:8000` (FastAPI dev server) so cookies work same-origin during development.

## Out of Scope (v1)

- Image/photo upload (API endpoint not built yet)
- AI-powered auto-complete from label photos
- PubChem auto-fetch integration
- PWA / offline support
- Internationalization (i18n)
- Dark/light theme toggle (dark only for v1)
- Notifications / real-time updates
- CSV bulk import
- Usage/withdrawal tracking
