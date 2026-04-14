# Frontend Redesign — Design Spec

**Date:** 2026-04-14
**Author:** Erik (with Claude Code)
**Status:** Draft — awaiting review

## Goal

Rebuild the ChAIMa frontend with a clinical/technical look and a desktop-optimised workflow that stays usable on mobile. Same backend, same feature surface, new visual and interaction layer. Introduce a small number of new capabilities (secret chemicals, dark mode, inline storage management) that fell out of the design conversation.

## Non-goals

- No backend rewrite. All existing routes in `src/chaima/routers/` stay; new endpoints are only added for the new capabilities (secret flag, SDS upload, dark mode preference, archive state, storage CRUD).
- No framework swap. React 19 + MUI 9 + React Query + React Router stay.
- No audit log.
- No QR/barcode scanning (the container-card QR icon is a visual placeholder for a future feature).
- No offline mode.

## Look and feel

Clinical / technical. Inspired by Linear, LabArchives, Notion-admin.

- **Palette (light, default):**
  - Background `#ffffff` / soft `#fafbfc`
  - Ink `#0f172a`, muted `#64748b`, subtle `#94a3b8`
  - Borders `#e2e8f0`, dividers `#f1f5f9`
  - Accent indigo `#4338ca` on `#eef2ff` (container IDs, active nav)
  - Primary action: ink-black `#0f172a` with white text
  - Warning/comment `#fffbeb` with `#f59e0b` left border
- **Palette (dark, user-toggleable):** Invert to `#0a0a0a` / `#141414` surfaces, `#e5e5e5` ink, `#262626` borders, accent `#818cf8` on `#1e1b4b`. Indigo hue preserved.
- **Typography:** Geist or system font stack. Base size 14 px (desktop) / 13 px (mobile). Monospace (JetBrains Mono) reserved for CAS numbers and container IDs.
- **Shape:** 3–6 px border-radius on everything. No shadows except modal/drawer elevation. `1px` borders, not `2px`.
- **Density:** High. Rows are ~44 px tall on desktop, ~40 px on mobile. No large empty areas.

## Information architecture

Three protected routes behind `ProtectedRoute`:

| Route | Title | Primary audience |
|---|---|---|
| `/` | Chemicals (main) | Everyone — search, view, create |
| `/storage` | Storage | Everyone for browsing; admins to manage structure |
| `/settings` | Settings | Everyone for Account/Group; admins for Members & Invites; superusers for Buildings/System |

Unauthenticated routes (outside layout): `/login`, `/invite/:token`.

Global navigation is a horizontal top bar on desktop (Chemicals · Storage · Settings, user avatar on the right). On mobile, the nav collapses to a drawer opened from a menu button in the header; the current route name is shown as the header title.

## Data model changes

Backend additions needed:

1. **`Chemical.is_secret: bool`** — default `False`. Filter: only the creator and superusers see secret chemicals.
2. **`Chemical.archived: bool`** — default `False`. Chemicals and containers are never hard-deleted. Archived rows are hidden from the main list unless the "Include archived" filter is on.
3. **`Container.archived: bool`** — same semantics.
4. **`Chemical.sds_file_id: Optional[uuid]`** — reference to uploaded PDF. Uploaded via a new file endpoint (separate module).
5. **`Chemical.structure_source: Literal["pubchem", "uploaded", "none"]`** and **`Chemical.structure_file_id: Optional[uuid]`** — user uploads get `"uploaded"`, PubChem-fetched structures get `"pubchem"`.
6. **`User.dark_mode: bool`** — default `False`. Persisted user preference.
7. **`Container.identifier: str`** — human-editable, e.g. `AB01`, `L2-09`. Must be unique per group. Replaces the internal UUID as the visible handle.
8. **`Container.purity: Optional[str]`**, **`Container.received_date: Optional[date]`** — new or renamed fields if missing.
9. **`StorageLocation`** tree with a fixed 4-level discriminator: `kind in {"building","room","cabinet","shelf"}`, enforced parent/child rules (building→room→cabinet→shelf). Each group references one or more buildings.

Migrations needed for each addition; the existing initial migration can be extended rather than adding a new file, since there are no production deployments yet.

## Permissions

Three effective roles:

- **User** — read chemicals/containers in their group (excluding secret ones they didn't create), create chemicals, create containers, edit/archive own chemicals and containers, toggle own chemicals' secret flag.
- **Admin** (group admin) — everything User can do, plus: edit/archive any non-secret chemical/container in the group, manage members and invites, create/edit/archive storage units within the group's building(s) (rooms, cabinets, shelves).
- **Superuser** — everything, across groups: see secret chemicals (so they can clean up legacy data), create buildings, assign groups to buildings, system settings.

A regular User cannot see or touch another user's secret chemicals. A group Admin also cannot — only creator + superuser.

## Page: Chemicals (`/`)

The main page users spend most of their time on.

### Header

Row 1: search input (full width) + hamburger filter button. The search searches name, CAS, synonyms, and container identifier. The filter button opens a side drawer with filters; a small dot indicator appears on the button when at least one filter is active.

Row 2: active-filter chip row (only rendered when filters are active). Each chip shows the filter and an `×` to remove it. Hidden otherwise.

### List

Each row represents one chemical:

```
Name                              Location · ContainerID-pill
CAS (mono, muted)                 QuantityOfFirstContainer [+N]
```

- **Left:** Chemical name (500 weight), CAS underneath in monospace and muted. If no CAS: italic "no CAS" in light grey.
- **Right top:** Location of the first container + container-ID pill (indigo, mono).
- **Right bottom:** Quantity of first container in muted grey. If the chemical has additional containers, append `+N` as a small grey pill.
- Row is clickable. Multiple rows can be expanded simultaneously.
- Archived chemicals are hidden by default. "Include archived" is a filter option.

### Expanded row — unified info box

When expanded, the row reveals a single bordered card (the "info box") divided by a vertical rule into a main area and a sidebar. On mobile, the sidebar stacks below the main area.

**Main area** (left ~2/3):
- **Structure thumbnail** — 100×100 on desktop, 80×80 on mobile. Box with 1 px border. Label underneath: `PUBCHEM` (muted) or `UPLOADED` (green) depending on `structure_source`. `NONE` shows an empty placeholder box.
- **Properties bullets** — free-form key/value pairs. Each bullet is `<key muted, ~90 px> <value>`. Examples: Type, Molar mass, Boiling point, Hazard, Synthesis, Storage. The key column is right-padded so values align.
- **Comment bullet** — optional. Rendered inside the same bullet list with a yellow background (`#fffbeb`), 2 px `#f59e0b` left border, and a `COMMENT` uppercase label above the text. Important for own chemicals and materials without a CAS.
- **"Also known as"** — a single quiet footer line at the bottom of the main area, separated by a dashed border, showing synonyms as `·`-separated text (not chips). Uppercase "Also known as" label.

**Sidebar** (right ~240 px, inside the same box frame):
- **Hero stat** — big number showing total stock across all containers, sub-text: `<N> containers · <location list>`. Bottom divider.
- **Tags** — chip list. Subtle cyan fill.
- **Links** — icon rows for: PubChem link (if `pubchem_cid` set), Safety data sheet (if `sds_file_id` set). Admin-only action rows below: "Upload SDS" or "Replace SDS", italic and muted.
- **Provenance** — `Added <date> · <user>` and `Updated <date> · <user>`, tiny text.

**"..." menu** — absolute top-right of the expanded area, one border, no label. Opens a small dropdown: `Edit chemical`, `Archive`, and (if secret) `Make public` / (if not secret) `Mark as secret`. No "Delete". Menu is only rendered for admins of the group, superusers, and the chemical's creator.

### Containers section

Below the info box, still inside the expanded row:

- Heading `CONTAINERS (N)` on the left, primary button `+ Container` (ink-black) on the right.
- Card grid. Each card:
  - Container identifier pill (mono, indigo) at top-left
  - Quantity as large value (15 px, 600 weight)
  - Purity underneath (small, muted)
  - Meta block: `Location`, `Supplier`, `Received` as key-value rows
  - Small QR icon in top-right corner (visual placeholder, not wired)
- Cards auto-fill with `minmax(210px, 1fr)` on desktop. Single column on mobile.

### Create / edit drawer

One shared right-side drawer (`~480 px` wide, full width on mobile) that handles:

- **New chemical** (opened from a `+ New chemical` button in the page header)
- **Edit chemical** (opened from the `...` menu)
- **New container** for a chemical (opened from `+ Container` in an expanded row)
- **Edit container** (opened from a container-card context menu)

The drawer slides in, the list stays visible behind it. The drawer contents are form-specific, but the chrome (header, close button, Cancel/Primary actions) is the same.

**New chemical form fields:**
- Name (required)
- CAS number (optional) — on enter, triggers a PubChem lookup that pre-fills molar mass, synonyms, hazard, and structure thumbnail
- Structure (if CAS didn't fill it) — upload image or SDF
- Tags (chip input)
- Properties (bullet list, add-row button)
- Comment (text area, optional)
- "Mark as secret" checkbox — explanatory hint: "Only you and system admins will see this chemical."
- Initial container section (toggled): Identifier, Quantity, Purity, Location (picker), Supplier, Received date

**New container form:** the initial-container section above, without the chemical fields.

## Page: Storage (`/storage`)

Hierarchical browser. Four fixed levels enforced in data: `building → room → cabinet → shelf`.

### What a user sees

Regular users don't see the building level. Their breadcrumbs start at Room:

`Storage › Lab 201 › Cabinet A1 › Shelf 2`

Superusers see the building level:

`Storage › Main Building › Lab 201 › Cabinet A1 › Shelf 2`

### Layout

- Top: breadcrumbs (clickable to jump up).
- Body: list of child nodes. Each child is a row with its name, optional description, and a container-count badge on the right (`42`).
- Clicking a child navigates one level deeper.
- The deepest level (shelf) does **not** show further children. Instead, it shows the list of containers that live on that shelf, rendered with the same container-card grid as on the Chemicals expanded view. Each container card links back to its chemical (click → opens the Chemicals page with that row expanded).

### Admin / superuser tools (inline on the page)

- **Admin (group admin):** can add/edit/archive rooms, cabinets, shelves within the buildings their group is assigned to. An `+ Add room` / `+ Add cabinet` / `+ Add shelf` button appears on the relevant level (below the child list). Clicking a row shows an edit pencil icon.
- **Superuser:** same, plus can add/edit/archive buildings (managed from Settings › Buildings, not here).

Creating or editing a storage unit opens the same drawer component, with a storage-unit form.

## Page: Settings (`/settings`)

Left navigation, right content.

### Nav sections

```
PERSONAL
  Account
  Group

GROUP ADMIN
  Members & Invites        (visible to Admin + SU)

SYSTEM
  Buildings [SU]           (visible to SU only)
  System [SU]              (visible to SU only)
```

### Account

- Name, email (edit)
- Password change (current + new)
- **Theme:** radio or switch `Light / Dark / System` — persisted to `User.dark_mode`. Applied app-wide immediately.
- Sign out button

### Group

- Current group info (name, main group)
- If the user is a member of multiple groups: a group picker to change their main group

### Members & Invites

One section with a tab bar at the top:

**Tab 1: Members** (default)
- Header: `<group name> · <N> members`
- Table-like list of rows: avatar, name, email, role pill (`Admin` indigo / `User` grey / `Inactive` red), `...` menu (Set role, Deactivate, Reactivate, Remove)
- Action button top-right: `Set role` (bulk) — optional, nice-to-have, can ship without

**Tab 2: Pending invites**
- Table-like list: invite link (mono), role preset, expires-in, Revoke button
- `+ New invite` button creates a new invite link via a small modal (role + TTL), shows the generated URL with a copy button

### Buildings (SU only)

- List of buildings. Each with name, address, assigned groups, edit/archive actions.
- `+ New building` button opens the drawer with a building form.

### System (SU only)

- Global settings (for future). For v1, this section can be a stub with Admin email, Group creation policy, etc. — enough to exist but not a blocker.

## Responsive behaviour

| Element | Desktop | Mobile |
|---|---|---|
| Top nav | Horizontal bar | Drawer from menu button |
| Info box | 2 columns (main + sidebar) | Stacks: main on top, sidebar below |
| Structure thumbnail | 100×100 | 80×80 |
| Container cards | `auto-fill minmax(210px, 1fr)` | 1 column |
| Create drawer | ~480 px from right | Full-width modal-like drawer |
| Row header right column | Fixed right | Shrinks with `min-width:0` + ellipsis on name |
| Property bullet keys | `min-width: 92px` | `min-width: 70px` |

Break-point for stacking behaviours: `~720 px`.

## Component structure (frontend)

Proposed file layout — follows the existing `src/` structure:

```
src/
  theme.ts                     → clinical light theme + dark variant, swap via ThemeProvider context
  pages/
    ChemicalsPage.tsx          → /  (was SearchPage)
    StoragePage.tsx            → /storage (rewritten; supports leaf container view)
    SettingsPage.tsx           → /settings (rewritten with section nav)
    LoginPage.tsx              → unchanged
    InvitePage.tsx             → unchanged
  components/
    Layout.tsx                 → top-nav shell, theme toggle hookup
    ChemicalList.tsx           → renders rows, handles multi-expand
    ChemicalRow.tsx            → collapsed row rendering
    ChemicalInfoBox.tsx        → the unified info box (main area + sidebar) used when expanded
    ContainerCard.tsx          → single container card
    ContainerGrid.tsx          → grid of cards with + button
    FilterBar.tsx              → active filter chips above the list
    FilterDrawer.tsx           → side drawer with filter form
    EditDrawer.tsx             → shared drawer shell (header, cancel/primary)
    ChemicalForm.tsx           → form body for new/edit chemical (rendered inside EditDrawer)
    ContainerForm.tsx          → form body for new/edit container
    StorageForm.tsx            → form body for new/edit storage unit
    StorageBreadcrumbs.tsx     → breadcrumb rendering that hides building for non-SU
    StorageChildList.tsx       → list of child storage nodes with counts + admin actions
    settings/
      AccountSection.tsx
      GroupSection.tsx
      MembersInvitesSection.tsx
      BuildingsSection.tsx
      SystemSection.tsx
    auth/
      ProtectedRoute.tsx       → unchanged
      RoleGate.tsx              → new: wraps admin-only / SU-only UI
  hooks/
    useChemicals.ts            → list query, filter state
    useChemical.ts             → single chemical + containers
    useStorage.ts              → storage tree queries
    useInvites.ts, useMembers.ts, useBuildings.ts
    useAuth.ts, useCurrentUser.ts
    useTheme.ts                → reads user.dark_mode, applies theme, persists
  api/                         → axios wrappers per resource
  types/                       → TS types matching backend schemas
```

## Out-of-scope (explicit YAGNI)

- Real QR scanning. Card icon is decorative.
- Audit log.
- Multi-tab chemical detail (everything fits in the info box).
- Drag-and-drop reorganisation of storage.
- CSV import/export.

## Open questions for review

1. Building level — is "superuser-only" the right gate? Could some large-lab setups want group admins to manage buildings themselves?
2. Secret chemicals — when a secret chemical's creator leaves the group (is removed/deactivated), who inherits visibility? Current plan: stays secret, only superuser can still see/clean up. Confirm.
3. Container editing by non-owners — can any User edit any container in their group, or only their own? Current plan: own only, plus admin/superuser can edit any. Confirm.
4. "Mark as secret" is a one-way-ish decision in many tools — here it's reversible. OK?
5. Theme "System" option — is that needed, or just Light/Dark?

---

**Next step:** This spec is saved. Please review it. If it's correct and complete, I will invoke the `writing-plans` skill to turn it into a task-by-task implementation plan.
