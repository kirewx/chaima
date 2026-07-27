# Structure Lightbox & Container Location Path — Design

**Date:** 2026-07-28
**Status:** Approved, awaiting implementation
**Scope:** Frontend only — no backend or API changes, no migrations.

## Problem

1. **Structure images are view-only.** The RDKit-rendered structure SVG in the
   ChemicalInfoBox is capped at 100 px. There is no way to inspect a molecule
   closely, even though the SVG is vector-based and scales losslessly.
2. **Container location shows only the leaf.** The container card renders
   `Location: Fridge` — the leaf storage location's name. With locations nested
   as `building > room > cabinet > shelf`, the leaf alone (e.g. "Floor 2") is
   ambiguous; users need the parent path to actually find the container.

## Decisions (user-confirmed, via visual mockups)

1. **Lightbox style:** Variant A — a standard MUI dialog with a title bar
   (chemical name + close button), matching existing dialogs such as
   `HazardStatementsDialog`. Content is the enlarged structure only (no extra
   data rows).
2. **Click affordance:** hover-only magnifier pictogram (MUI `SearchIcon`) over
   a dimmed structure, blue border, `zoom-in` cursor — gated behind
   `@media (hover: hover)`. Touch devices get no icon/dimming; the box is
   simply tappable. No emoji.
3. **Path rule:** show **all levels except `building`**.
   `Haus > Room XX > Fridge` → `Room XX › Fridge`;
   `Haus > Room XX > Cabinet C > Floor X` → `Room XX › Cabinet C › Floor X`.
4. **Path presentation:** Variant B — breadcrumb style: parent segments dimmed
   (`text.secondary`-ish), `›` separators, leaf segment bright and semibold.
5. **Surface:** the container card only (chemical expanded view + Storage
   page). The chemical list row and the container form keep their current
   display.

## Design

### Feature 1 — Structure lightbox

**New component `StructureDialog`** (`frontend/src/components/StructureDialog.tsx`):

- Props: `open`, `onClose`, `chemicalName`, `svg` (the raw SVG string).
- MUI `Dialog` with title bar: chemical name left, close `IconButton` (X)
  right. Backdrop click and Esc close it (MUI default).
- Body renders the SVG via `dangerouslySetInnerHTML` (same mechanism as the
  thumbnail), scaled to roughly `min(80vw, 70vh)` square, `color:
  text.primary` so the `currentColor` strokes follow the theme.
- No new fetch: the SVG string comes from the already-cached
  `useChemicalStructureSvg` result.

**`ChemicalInfoBox` changes:**

- The existing 100 px structure box becomes an accessible trigger **only when
  a SVG is present** (`role="button"`, `tabIndex=0`, Enter/Space handling,
  `aria-label` like "Show enlarged structure"). The loading and
  "no structure" states stay exactly as today (non-interactive).
- Hover styles under `@media (hover: hover)`: structure opacity ~0.55,
  centered `SearchIcon` fades in, border `primary.main`, cursor `zoom-in`.
- Click/keyboard opens `StructureDialog` (local `useState`).

### Feature 2 — Container location path

**New util `frontend/src/utils/locationPath.ts`:**

- `findLocationTrail(nodes: StorageLocationNode[], targetId: string):
  StorageLocationNode[] | null` — depth-first walk of the storage tree,
  returning the node chain root → leaf (generalizes the private
  `findLocationPath` currently in `ContainerForm`).
- `displayTrail(trail)` — drops `kind === "building"` nodes. If that leaves
  the trail empty (container attached at building level), fall back to the
  unfiltered trail so the display is never empty.

**New component `LocationBreadcrumb`** (`frontend/src/components/LocationBreadcrumb.tsx`):

- Props: `names: string[]`.
- Renders parents dimmed with `›` separators, the last segment bright and
  semibold (fontWeight 600). Single-element trails render as just the bold
  leaf. Inherits the card's 11 px font size.

**`ContainerCard`:**

- Prop `locationName?: string` is replaced by `locationNames?: string[]`.
- The `Location` meta row renders `LocationBreadcrumb`, or `—` when the trail
  is missing (location not found in the tree, e.g. stale data).

**`ContainerGrid`:**

- Fetches `useStorageTree(groupId)` **once** and computes each card's trail
  with the util — replacing today's per-card `useStorageLocation` request
  (N lookups → 1 cached query).
- The identifier chip color comes from the trail's leaf node (`color` is on
  `StorageLocationNode`); fallback `DEFAULT_STORAGE_COLOR` as today.

**`StoragePage`:**

- Passes `locationNames` computed from the same tree/util for its container
  cards (the tree query is already used on that page's navigation), so both
  surfaces render identically.

**`ContainerForm`:**

- Its private `findLocationPath` helper is removed in favor of the shared
  util; the form keeps its current full-path `Haus > Room > …` string
  (joined from the unfiltered trail). No behavior change.

### Error handling

- Location id not present in the tree → card shows `—` (same as today's
  missing-lookup fallback).
- SVG absent or still loading → structure box is not clickable; no dialog can
  open with empty content.

### Testing

Playwright e2e (existing patterns in `frontend/e2e/`):

- **Lightbox:** clicking the structure box on a chemical with a structure
  opens a dialog titled with the chemical name; Esc closes it. A chemical
  without a structure has no clickable box.
- **Location path:** a container stored in a nested location
  (building > room > shelf) shows `Room › Shelf` on its card in the expanded
  chemical view; the building name does not appear.
- Production build (`npm run build`) clean.

## Out of scope

- Zoom/pan inside the lightbox (SVG scaling suffices).
- Higher-resolution re-render via backend size parameters.
- Path display in the chemical list row and the container form's picker
  (form keeps its existing full-path text).
- Server-side `path` field on containers or locations.
