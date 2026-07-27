# Structure Lightbox & Container Location Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the RDKit structure thumbnail clickable (enlarged MUI dialog) and show the parent location path (breadcrumb, building level dropped) on container cards.

**Architecture:** Frontend-only. A shared `locationPath` util walks the already-cached storage tree; a `LocationBreadcrumb` renders dimmed parents + bold leaf on `ContainerCard` (fed by `ContainerGrid` and `StoragePage`). A new `StructureDialog` reuses the cached structure SVG from `useChemicalStructureSvg`; the thumbnail in `ChemicalInfoBox` becomes an accessible button with hover-only magnifier affordance.

**Tech Stack:** React 19 + TypeScript, MUI v9, TanStack Query, Playwright e2e (no unit test runner in this repo).

**Spec:** `docs/superpowers/specs/2026-07-28-structure-lightbox-and-location-path-design.md`

## Prerequisites (once, before Task 4)

E2E tests need the real stack:

1. Backend on `http://localhost:8000` with the dev seed (`admin@chaima.dev` / `changeme`) and RDKit available. If it is not already running, start it in a **separate background process**: `uv run chaima run` (repo root). Do NOT kill an already-running instance (Windows zombie-listener gotcha).
2. Vite dev server on `http://localhost:5173`. Playwright's `webServer` is `bun dev` — if `bun` is unavailable, start `npm run dev` (in `frontend/`) yourself; `reuseExistingServer: true` picks it up.
3. Run e2e from `frontend/`: `npx playwright test e2e/<file>.spec.ts`

All git commands run from the repo root. All npm/npx commands run from `frontend/`.

---

### Task 1: Branch + commit spec

**Files:**
- Commit: `docs/superpowers/specs/2026-07-28-structure-lightbox-and-location-path-design.md` (already written, uncommitted)

- [ ] **Step 1: Create branch from main**

```bash
git checkout main
git checkout -b feat/structure-lightbox-and-location-path
```

- [ ] **Step 2: Commit the spec**

```bash
git add docs/superpowers/specs/2026-07-28-structure-lightbox-and-location-path-design.md
git commit -m "docs(specs): structure lightbox + container location path design"
```

---

### Task 2: `locationPath` util

**Files:**
- Create: `frontend/src/utils/locationPath.ts`

- [ ] **Step 1: Write the util**

```typescript
import type { StorageLocationNode } from "../types";

/**
 * Depth-first walk of the storage tree returning the node chain
 * root → target (inclusive), or null when the id is not in the tree.
 */
export function findLocationTrail(
  nodes: StorageLocationNode[],
  targetId: string,
  trail: StorageLocationNode[] = [],
): StorageLocationNode[] | null {
  for (const n of nodes) {
    const next = [...trail, n];
    if (n.id === targetId) return next;
    const found = findLocationTrail(n.children, targetId, next);
    if (found) return found;
  }
  return null;
}

/**
 * Display rule for container cards: drop building levels. If that leaves
 * nothing (container attached at building level), keep the full trail so
 * the display is never empty.
 */
export function displayTrail(
  trail: StorageLocationNode[],
): StorageLocationNode[] {
  const filtered = trail.filter((n) => n.kind !== "building");
  return filtered.length > 0 ? filtered : trail;
}
```

- [ ] **Step 2: Type-check**

Run (in `frontend/`): `npx tsc -b`
Expected: exit 0, no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/utils/locationPath.ts
git commit -m "feat(ui): add locationPath util (trail lookup + building filter)"
```

---

### Task 3: `LocationBreadcrumb` component

**Files:**
- Create: `frontend/src/components/LocationBreadcrumb.tsx`

- [ ] **Step 1: Write the component**

Parents dimmed with `›` separators, leaf bright and semibold (user-selected Variant B). Renders inside the card's 11px meta row, so no own font size.

```tsx
import { Box } from "@mui/material";

interface Props {
  /** Path segments root → leaf, building level already filtered out. */
  names: string[];
}

/** Breadcrumb-style location path: dimmed parents, bold leaf. */
export function LocationBreadcrumb({ names }: Props) {
  if (names.length === 0) return <>—</>;
  const parents = names.slice(0, -1);
  const leaf = names[names.length - 1];
  return (
    <Box component="span">
      {parents.map((name, i) => (
        <Box component="span" key={i} sx={{ color: "text.secondary" }}>
          {name}
          <Box component="span" sx={{ color: "text.disabled" }}>
            {" › "}
          </Box>
        </Box>
      ))}
      <Box component="span" sx={{ color: "text.primary", fontWeight: 600 }}>
        {leaf}
      </Box>
    </Box>
  );
}
```

- [ ] **Step 2: Type-check**

Run (in `frontend/`): `npx tsc -b`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LocationBreadcrumb.tsx
git commit -m "feat(ui): add LocationBreadcrumb component"
```

---

### Task 4: e2e test for the location path (red)

**Files:**
- Create: `frontend/e2e/location-path.spec.ts`

- [ ] **Step 1: Write the failing e2e test**

Selector patterns come from `frontend/e2e/storage.spec.ts` (storage chain creation) and `frontend/e2e/container-supplier.spec.ts` (chemical + container drawer). If a `getByLabel` does not match at runtime, check the actual label text in `frontend/src/components/drawer/ContainerForm.tsx` and adjust the test — not the app.

```typescript
import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

function drawer(page: Page) {
  return page.locator(".MuiDrawer-paper");
}

test.describe("Container location path", () => {
  test("container card shows parent path without the building level", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await login(page);

    const stamp = Date.now();
    const building = `E2E PathBldg ${stamp}`;
    const room = `E2E PathRoom ${stamp}`;
    const cabinet = `E2E PathCab ${stamp}`;
    const shelf = `E2E PathShelf ${stamp}`;

    // ── Storage chain: building → room → cabinet → shelf ─────────────────
    await page.getByRole("link", { name: "Storage" }).click();
    await expect(page).toHaveURL(/\/storage$/);

    for (const [kind, name] of [
      ["building", building],
      ["room", room],
      ["cabinet", cabinet],
      ["shelf", shelf],
    ] as const) {
      await page.getByRole("button", { name: new RegExp(`add ${kind}`, "i") }).click();
      await expect(drawer(page).getByLabel("Name")).toBeVisible();
      await drawer(page).getByLabel("Name").fill(name);
      await drawer(page).getByRole("button", { name: /^create$/i }).click();
      await expect(drawer(page)).toHaveCount(0);
      if (kind !== "shelf") {
        await page.getByText(name, { exact: true }).click();
        await expect(page.getByRole("heading", { name })).toBeVisible();
      }
    }

    // ── Chemical + container in that shelf ───────────────────────────────
    await page.goto("/");
    const chemName = `E2E PathMol ${stamp}`;
    await page.getByRole("button", { name: /new chemical/i }).click();
    await expect(page.getByLabel("Name")).toBeVisible();
    await page.getByLabel("Name").fill(chemName);
    await page.getByRole("button", { name: /^create$/i }).click();

    const row = page.getByText(chemName, { exact: true });
    await expect(row).toBeVisible();
    await row.click();

    await page.getByRole("button", { name: /^container$/i }).click();
    const d = drawer(page);
    await d.getByLabel(/identifier/i).fill(`E2E-PATH-${stamp}`);
    await d.getByLabel(/amount/i).fill("500");
    await d.getByLabel(/unit/i).fill("mL");

    // LocationPicker: drill down building → room → cabinet, shelf is a leaf
    // (no children) so clicking its text selects it and closes the dialog.
    await d.getByRole("button", { name: /select location/i }).click();
    const picker = page.getByRole("dialog").filter({ hasText: "Select Location" });
    await picker.getByText(building, { exact: true }).click();
    await picker.getByText(room, { exact: true }).click();
    await picker.getByText(cabinet, { exact: true }).click();
    await picker.getByText(shelf, { exact: true }).click();
    await expect(picker).toHaveCount(0);

    await d.getByRole("button", { name: /^create$/i }).click();
    await expect(d).toHaveCount(0, { timeout: 10_000 });

    // ── Assertion: breadcrumb without building ───────────────────────────
    // LocationBreadcrumb renders one span whose textContent is
    // "room › cabinet › shelf" — matchable as a single string.
    await expect(
      page.getByText(`${room} › ${cabinet} › ${shelf}`),
    ).toBeVisible({ timeout: 10_000 });
    // Building name must not appear anywhere on the chemicals page.
    await expect(page.getByText(building)).toHaveCount(0);
  });
});
```

- [ ] **Step 2: Run it, expect the breadcrumb assertion to fail**

Run (in `frontend/`): `npx playwright test e2e/location-path.spec.ts`
Expected: FAIL at the `${room} › ${cabinet} › ${shelf}` assertion (card still shows only the leaf name). Everything before it (storage chain, chemical, container creation) must pass — if an earlier step fails, fix the test's selectors first.

- [ ] **Step 3: Commit the red test**

```bash
git add frontend/e2e/location-path.spec.ts
git commit -m "test(e2e): container card shows parent location path (red)"
```

---

### Task 5: Wire the breadcrumb into `ContainerCard`, `ContainerGrid`, `StoragePage`

**Files:**
- Modify: `frontend/src/components/ContainerCard.tsx`
- Modify: `frontend/src/components/ContainerGrid.tsx`
- Modify: `frontend/src/pages/StoragePage.tsx`

- [ ] **Step 1: `ContainerCard` — replace `locationName` with `locationNames`**

In `frontend/src/components/ContainerCard.tsx`:

Replace the prop in the `Props` interface (line ~13):

```tsx
  /** Location path segments root → leaf, building level filtered out. */
  locationNames?: string[];
```

(remove `locationName?: string;`), update the destructuring in the function signature (`locationName` → `locationNames`), add the import:

```tsx
import { LocationBreadcrumb } from "./LocationBreadcrumb";
```

Replace the Location meta row (line ~108):

```tsx
            <MetaRow
              k="Location"
              v={
                locationNames && locationNames.length > 0 ? (
                  <LocationBreadcrumb names={locationNames} />
                ) : (
                  "—"
                )
              }
            />
```

Widen `MetaRow` to accept nodes (line ~161) — change the signature to:

```tsx
function MetaRow({ k, v }: { k: string; v: ReactNode }) {
```

(`ReactNode` is already imported in this file.)

- [ ] **Step 2: `ContainerGrid` — one tree query instead of per-card location lookups**

Replace `ContainerCardWithLookups` in `frontend/src/components/ContainerGrid.tsx` with:

```tsx
function ContainerCardWithLookups({
  groupId,
  container,
}: {
  groupId: string;
  container: ContainerRead;
}) {
  const { data: tree = [] } = useStorageTree(groupId);
  const { data: supplier } = useSupplier(groupId, container.supplier_id);
  const trail = findLocationTrail(tree, container.location_id);
  const names = trail ? displayTrail(trail).map((n) => n.name) : undefined;
  const leafColor = trail ? trail[trail.length - 1].color : undefined;
  return (
    <ContainerCard
      container={container}
      groupId={groupId}
      locationNames={names}
      locationColor={leafColor}
      supplierName={supplier?.name}
    />
  );
}
```

Update imports: remove `useStorageLocation`, add:

```tsx
import { useStorageTree } from "../api/hooks/useStorageLocations";
import { displayTrail, findLocationTrail } from "../utils/locationPath";
```

(React Query dedupes the per-card `useStorageTree` calls into the one cached `["storageLocations", groupId, "tree"]` query.)

- [ ] **Step 3: `StoragePage` — pass the trail from the navigation path**

`nav.path` (from `useStorageNavigation`) is the ancestor chain to the current shelf; for superusers it includes the building, for regular users the building layer is already flattened away — `displayTrail` handles both. In `frontend/src/pages/StoragePage.tsx` change the card render (line ~106):

```tsx
              {containers.data!.items.map((c) => (
                <ContainerCard
                  key={c.id}
                  container={c}
                  locationNames={displayTrail(nav.path).map((n) => n.name)}
                  locationColor={nav.current?.color}
                  linkToChemical
                />
              ))}
```

Add the import:

```tsx
import { displayTrail } from "../utils/locationPath";
```

- [ ] **Step 4: Type-check**

Run (in `frontend/`): `npx tsc -b`
Expected: exit 0. (Any remaining `locationName=` usage will surface here.)

- [ ] **Step 5: Run the e2e test, expect green**

Run (in `frontend/`): `npx playwright test e2e/location-path.spec.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ContainerCard.tsx frontend/src/components/ContainerGrid.tsx frontend/src/pages/StoragePage.tsx
git commit -m "feat(ui): show parent location path on container cards"
```

---

### Task 6: Deduplicate `findLocationPath` in `ContainerForm`

**Files:**
- Modify: `frontend/src/components/drawer/ContainerForm.tsx`

The form keeps its full `Building > Room > Shelf` display (spec: no behavior change) but uses the shared trail walker.

- [ ] **Step 1: Remove the private helper, use the util**

Delete the private function `findLocationPath` (lines ~30–43, including its doc comment) and add the import:

```tsx
import { findLocationTrail } from "../../utils/locationPath";
```

Replace its single call site (in the edit-mode effect, line ~139):

```tsx
    const trail = findLocationTrail(locationTree, existing.data.location_id);
    if (trail) setLocationPath(trail.map((n) => n.name).join(" > "));
```

(The `StorageLocationNode` type import may become unused — remove it from the import list if `npx tsc -b` or lint flags it; it is still used by other code in the file, so check first.)

- [ ] **Step 2: Type-check + lint**

Run (in `frontend/`): `npx tsc -b` then `npm run lint`
Expected: both exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/drawer/ContainerForm.tsx
git commit -m "refactor(ui): reuse shared findLocationTrail in ContainerForm"
```

---

### Task 7: e2e test for the structure lightbox (red)

**Files:**
- Create: `frontend/e2e/structure-lightbox.spec.ts`

- [ ] **Step 1: Write the failing e2e test**

Pattern from `frontend/e2e/chemical-pubchem.spec.ts`: mock the PubChem lookup so the created chemical has a SMILES (`CC(=O)C`) — the backend then renders `structure.svg` via RDKit for real.

```typescript
import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

function newChemicalDrawer(page: Page) {
  return page
    .locator('[role="presentation"]')
    .filter({ hasText: /new chemical/i });
}

const FAKE_LOOKUP = {
  cid: "180",
  name: "propan-2-one",
  cas: "67-64-1",
  molar_mass: 58.08,
  smiles: "CC(=O)C",
  synonyms: ["Acetone"],
  ghs_codes: [],
};

test.describe("Structure lightbox", () => {
  test("clicking the structure thumbnail opens an enlarged dialog", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await login(page);

    await page.route("**/api/v1/pubchem/lookup*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FAKE_LOOKUP),
      });
    });

    // Create a chemical with a SMILES via the mocked PubChem fetch.
    const unique = `E2E Lightbox ${Date.now()}`;
    await page.getByRole("button", { name: /new chemical/i }).click();
    const d = newChemicalDrawer(page);
    await expect(d).toBeVisible({ timeout: 5_000 });
    await d.getByLabel(/lookup from pubchem/i).fill("acetone-lightbox");
    await d.getByRole("button", { name: /^fetch$/i }).click();
    await expect(d.getByLabel(/^name/i)).toHaveValue("propan-2-one", {
      timeout: 5_000,
    });
    await d.getByLabel(/^name/i).fill(unique);
    await d.getByRole("button", { name: /^create$/i }).click();
    await expect(d).toHaveCount(0, { timeout: 10_000 });

    // Expand the chemical; wait for the structure SVG to arrive.
    await page.getByText(unique, { exact: true }).click();
    const thumb = page.getByRole("button", {
      name: new RegExp(`enlarged structure`, "i"),
    });
    await expect(thumb).toBeVisible({ timeout: 15_000 });

    // Open the lightbox.
    await thumb.click();
    const dialog = page.getByRole("dialog").filter({ hasText: unique });
    await expect(dialog).toBeVisible();
    await expect(dialog.locator("svg")).toBeVisible();

    // Esc closes it.
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  });
});
```

- [ ] **Step 2: Run it, expect failure at the thumbnail button**

Run (in `frontend/`): `npx playwright test e2e/structure-lightbox.spec.ts`
Expected: FAIL at `getByRole("button", { name: /enlarged structure/i })` — no such button exists yet. The chemical creation part must pass.

- [ ] **Step 3: Commit the red test**

```bash
git add frontend/e2e/structure-lightbox.spec.ts
git commit -m "test(e2e): structure thumbnail opens enlarged dialog (red)"
```

---

### Task 8: `StructureDialog` + clickable thumbnail in `ChemicalInfoBox`

**Files:**
- Create: `frontend/src/components/StructureDialog.tsx`
- Modify: `frontend/src/components/ChemicalInfoBox.tsx`

- [ ] **Step 1: Write `StructureDialog`**

Same shape as `HazardStatementsDialog` (title bar + close X, Esc/backdrop close via MUI defaults). The SVG uses `currentColor`, so `color: "text.primary"` keeps it theme-correct.

```tsx
import { Box, Dialog, DialogContent, DialogTitle, IconButton } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

interface Props {
  open: boolean;
  onClose: () => void;
  chemicalName: string;
  /** Raw SVG markup, from the cached useChemicalStructureSvg result. */
  svg: string;
}

/** Enlarged, losslessly scaled view of a chemical's structure SVG. */
export function StructureDialog({ open, onClose, chemicalName, svg }: Props) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="md">
      <DialogTitle sx={{ pr: 6 }}>
        {chemicalName}
        <IconButton
          aria-label="close"
          onClick={onClose}
          sx={{ position: "absolute", right: 8, top: 8 }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        <Box
          sx={{
            width: "min(80vw, 70vh)",
            height: "min(80vw, 70vh)",
            color: "text.primary",
            "& svg": { width: "100%", height: "100%", display: "block" },
          }}
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Make the thumbnail a trigger in `ChemicalInfoBox`**

In `frontend/src/components/ChemicalInfoBox.tsx`:

Add imports (SearchIcon is already imported):

```tsx
import { StructureDialog } from "./StructureDialog";
```

Extend the existing react import (line 1) with the event type — `React.KeyboardEvent` is NOT available here (no React namespace import):

```tsx
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
```

Add state next to `hpOpen` (line ~55):

```tsx
  const [structureOpen, setStructureOpen] = useState(false);
```

Replace the thumbnail box (the `<Box sx={{ width: { xs: 80, md: 100 }, ... }}>` at line ~130 with its three-state content) with:

```tsx
          <Box
            {...(structureSvg
              ? {
                  role: "button",
                  tabIndex: 0,
                  "aria-label": `Show enlarged structure of ${chemical.name}`,
                  onClick: () => setStructureOpen(true),
                  onKeyDown: (e: KeyboardEvent) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setStructureOpen(true);
                    }
                  },
                }
              : {})}
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
              overflow: "hidden",
              position: "relative",
              ...(structureSvg && {
                cursor: "zoom-in",
                "@media (hover: hover)": {
                  "&:hover": { borderColor: "primary.main" },
                  "&:hover .structure-thumb": { opacity: 0.55 },
                  "&:hover .structure-zoom-icon": { opacity: 1 },
                },
              }),
            }}
          >
            {structureSvg ? (
              <>
                <Box
                  className="structure-thumb"
                  aria-label={`${chemical.name} structure`}
                  sx={{
                    maxWidth: "100%",
                    maxHeight: "100%",
                    color: "text.primary",
                    transition: "opacity 0.15s",
                    "& svg": {
                      width: "100%",
                      height: "100%",
                      display: "block",
                    },
                  }}
                  dangerouslySetInnerHTML={{ __html: structureSvg }}
                />
                <SearchIcon
                  className="structure-zoom-icon"
                  sx={{
                    position: "absolute",
                    fontSize: 28,
                    color: "text.primary",
                    opacity: 0,
                    transition: "opacity 0.15s",
                    pointerEvents: "none",
                  }}
                />
              </>
            ) : svgLoading ? (
              <Typography variant="caption" color="text.disabled">
                …
              </Typography>
            ) : (
              <Typography variant="caption" color="text.disabled">
                no structure
              </Typography>
            )}
          </Box>
```

At the bottom of the component, next to `<HazardStatementsDialog …/>` (line ~477), add:

```tsx
      {structureSvg && (
        <StructureDialog
          open={structureOpen}
          onClose={() => setStructureOpen(false)}
          chemicalName={chemical.name}
          svg={structureSvg}
        />
      )}
```

- [ ] **Step 3: Type-check**

Run (in `frontend/`): `npx tsc -b`
Expected: exit 0.

- [ ] **Step 4: Run the e2e test, expect green**

Run (in `frontend/`): `npx playwright test e2e/structure-lightbox.spec.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StructureDialog.tsx frontend/src/components/ChemicalInfoBox.tsx
git commit -m "feat(ui): clickable structure thumbnail with enlarged dialog"
```

---

### Task 9: Full verification + PR

- [ ] **Step 1: Production build + lint**

Run (in `frontend/`): `npm run build` then `npm run lint`
Expected: both exit 0.

- [ ] **Step 2: Full e2e suite**

Run (in `frontend/`): `npx playwright test`
Expected: all specs pass (pre-existing skips stay skipped). If a spec unrelated to this change fails, check whether it also fails on `main` before touching anything.

- [ ] **Step 3: Push and open the PR**

```bash
git push -u origin feat/structure-lightbox-and-location-path
gh pr create --title "feat(ui): structure lightbox + container location path" --body "## Summary
- Structure thumbnail in ChemicalInfoBox is now clickable and opens an enlarged StructureDialog (cached SVG, no extra request); hover-only magnifier affordance, plain tap on touch devices
- Container cards show the parent location path as a breadcrumb (building level dropped, parents dimmed, leaf bold) on both the Chemicals and Storage pages
- ContainerGrid now resolves locations from the one cached storage-tree query instead of one lookup per card
- Shared findLocationTrail util replaces the private helper in ContainerForm (no behavior change there)

Spec: docs/superpowers/specs/2026-07-28-structure-lightbox-and-location-path-design.md

## Test plan
- [ ] e2e: location-path.spec.ts — nested container card shows \`Room › Cabinet › Shelf\`, no building name
- [ ] e2e: structure-lightbox.spec.ts — thumbnail button opens dialog with SVG, Esc closes
- [ ] npm run build + npm run lint clean
- [ ] Full playwright suite green

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

Expected: PR URL printed.
