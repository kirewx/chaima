# SDS Research Links ("Hilfsliste") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show group admins two Google research links (CAS search, SDS-PDF search) on chemicals that have a CAS but no uploaded SDS, toggleable per group in Settings → Chemicals.

**Architecture:** A new `show_sds_research_links` bool column on `Group` (default on) flows through the existing `GroupRead`/`GroupUpdate` schemas and the existing admin-gated `PATCH /groups/{group_id}`. The frontend builds the two Google URLs client-side in `ChemicalInfoBox` and gates them on four conditions (admin, no SDS, CAS present, group toggle on). A switch in `ChemicalsAdminSection` flips the group flag.

**Tech Stack:** FastAPI + SQLModel + Alembic (SQLite), React + MUI + TanStack Query, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-07-17-sds-research-links-design.md`

**Branch:** `feat/sds-research-links` (branched from `main` after the GESTIS merge; Alembic head is `d2f4a6b8c0e2`).

---

## File Structure

- Modify: `src/chaima/models/group.py` — new bool field on `Group`
- Create: `alembic/versions/b7e9d1f3a5c7_add_group_show_sds_research_links.py`
- Modify: `src/chaima/schemas/group.py` — field on `GroupRead` + `GroupUpdate`
- Modify: `src/chaima/services/groups.py` — `update_group` kwarg
- Modify: `src/chaima/routers/groups.py` — pass the new field through
- Create: `tests/test_models/test_group_settings.py`
- Modify: `tests/test_api/test_groups.py` — read/patch coverage
- Modify: `frontend/src/types/index.ts` — `GroupRead`/`GroupUpdate` interfaces
- Create: `frontend/src/utils/sdsResearch.ts` — URL builders (single source for app + e2e expectations)
- Modify: `frontend/src/components/ChemicalInfoBox.tsx` — two link rows
- Modify: `frontend/src/components/settings/ChemicalsAdminSection.tsx` — toggle
- Create: `frontend/e2e/sds-research-links.spec.ts`

---

### Task 1: Group model column + migration

**Files:**
- Modify: `src/chaima/models/group.py`
- Create: `alembic/versions/b7e9d1f3a5c7_add_group_show_sds_research_links.py`
- Test: `tests/test_models/test_group_settings.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models/test_group_settings.py`:

```python
from chaima.models.group import Group


def test_group_show_sds_research_links_defaults_true():
    group = Group(name="Lab")
    assert group.show_sds_research_links is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models/test_group_settings.py -v`
Expected: FAIL with `AttributeError` (or assertion on missing attribute).

- [ ] **Step 3: Add the field to the model**

In `src/chaima/models/group.py`, inside `class Group`, after the `description` field:

```python
    show_sds_research_links: bool = Field(default=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models/test_group_settings.py -v`
Expected: PASS

- [ ] **Step 5: Write the migration**

Create `alembic/versions/b7e9d1f3a5c7_add_group_show_sds_research_links.py` (same shape as `d2f4a6b8c0e2_add_chemical_zvg.py`):

```python
"""add group show_sds_research_links

Revision ID: b7e9d1f3a5c7
Revises: d2f4a6b8c0e2
Create Date: 2026-07-17 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e9d1f3a5c7'
down_revision: Union[str, Sequence[str], None] = 'd2f4a6b8c0e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'group',
        sa.Column(
            'show_sds_research_links',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('1'),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('group', 'show_sds_research_links')
```

- [ ] **Step 6: Verify the migration applies and is the new head**

Run: `uv run alembic upgrade head && uv run alembic heads`
Expected: upgrade runs without error; head is `b7e9d1f3a5c7`.

- [ ] **Step 7: Run the full backend suite (migration must not break existing tests)**

Run: `uv run pytest`
Expected: all green (491+ tests).

- [ ] **Step 8: Commit**

```bash
git add src/chaima/models/group.py alembic/versions/b7e9d1f3a5c7_add_group_show_sds_research_links.py tests/test_models/test_group_settings.py
git commit -m "feat(groups): show_sds_research_links flag on Group"
```

---

### Task 2: Schemas, service, router passthrough

**Files:**
- Modify: `src/chaima/schemas/group.py`
- Modify: `src/chaima/services/groups.py:150-181` (`update_group`)
- Modify: `src/chaima/routers/groups.py:170-199` (`update_group` route)
- Test: `tests/test_api/test_groups.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_api/test_groups.py` (fixtures `client`, `group`, `admin_membership` already exist in `tests/test_api/conftest.py`; `GroupRead` is already imported at the top of the file):

```python
@pytest.mark.asyncio
async def test_group_read_includes_research_links_flag(client, group, membership):
    """GET /api/v1/groups/{group_id} should expose show_sds_research_links (default true)."""
    resp = await client.get(f"/api/v1/groups/{group.id}")
    assert resp.status_code == 200
    assert resp.json()["show_sds_research_links"] is True


@pytest.mark.asyncio
async def test_update_group_toggles_research_links(client, group, admin_membership):
    """PATCH /api/v1/groups/{group_id} should toggle show_sds_research_links."""
    resp = await client.patch(
        f"/api/v1/groups/{group.id}",
        json={"show_sds_research_links": False},
    )
    assert resp.status_code == 200
    assert resp.json()["show_sds_research_links"] is False
    # Other fields untouched by the partial update.
    assert resp.json()["name"] == group.name


@pytest.mark.asyncio
async def test_update_group_without_flag_keeps_it(client, group, admin_membership):
    """A patch that omits show_sds_research_links must not change it."""
    resp = await client.patch(
        f"/api/v1/groups/{group.id}",
        json={"show_sds_research_links": False},
    )
    assert resp.status_code == 200
    resp = await client.patch(
        f"/api/v1/groups/{group.id}",
        json={"name": "Renamed"},
    )
    assert resp.status_code == 200
    assert resp.json()["show_sds_research_links"] is False
    assert resp.json()["name"] == "Renamed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_groups.py -v -k research_links`
Expected: FAIL — `KeyError: 'show_sds_research_links'` (field not in `GroupRead`).

- [ ] **Step 3: Extend the schemas**

In `src/chaima/schemas/group.py`:

In `GroupUpdate`, after `description: str | None = None` add (and mention it in the docstring):

```python
    show_sds_research_links: bool | None = None
```

In `GroupRead`, after `description: str | None` add (and mention it in the docstring):

```python
    show_sds_research_links: bool
```

- [ ] **Step 4: Extend the service**

In `src/chaima/services/groups.py`, change `update_group`'s signature and body (docstring gets a matching parameter entry):

```python
async def update_group(
    session: AsyncSession,
    group: Group,
    *,
    name: str | None = None,
    description: str | None = None,
    show_sds_research_links: bool | None = None,
) -> Group:
```

and after the `description` block:

```python
    if show_sds_research_links is not None:
        group.show_sds_research_links = show_sds_research_links
```

- [ ] **Step 5: Pass through in the router**

In `src/chaima/routers/groups.py`, `update_group` route, extend the service call:

```python
    updated = await group_service.update_group(
        session,
        group,
        name=body.name,
        description=body.description,
        show_sds_research_links=body.show_sds_research_links,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_groups.py -v`
Expected: PASS (all, including the three new ones).

- [ ] **Step 7: Run the full backend suite**

Run: `uv run pytest`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add src/chaima/schemas/group.py src/chaima/services/groups.py src/chaima/routers/groups.py tests/test_api/test_groups.py
git commit -m "feat(groups): expose show_sds_research_links via read/patch API"
```

---

### Task 3: Frontend — types, URL builders, ChemicalInfoBox rows

**Files:**
- Modify: `frontend/src/types/index.ts:19-34`
- Create: `frontend/src/utils/sdsResearch.ts`
- Modify: `frontend/src/components/ChemicalInfoBox.tsx`

There is no frontend unit-test runner in this repo; frontend verification is `npm run build` (Task 5 adds e2e).

- [ ] **Step 1: Extend the TS interfaces**

In `frontend/src/types/index.ts`, add to `GroupRead`:

```typescript
  show_sds_research_links: boolean;
```

and to `GroupUpdate`:

```typescript
  show_sds_research_links?: boolean;
```

- [ ] **Step 2: Create the URL builders**

Create `frontend/src/utils/sdsResearch.ts`:

```typescript
/** Google research links for backfilling missing SDS. Pure CAS search found
 *  chemicals reliably in manual testing; the filetype:pdf variant often hits
 *  the SDS PDF directly for well-known substances. */
export function casSearchUrl(cas: string): string {
  return `https://www.google.com/search?q=${encodeURIComponent(`"${cas}"`)}`;
}

export function sdsPdfSearchUrl(cas: string): string {
  return `https://www.google.com/search?q=${encodeURIComponent(
    `"${cas}" sicherheitsdatenblatt filetype:pdf`,
  )}`;
}
```

- [ ] **Step 3: Render the rows in ChemicalInfoBox**

In `frontend/src/components/ChemicalInfoBox.tsx`:

Add imports:

```typescript
import SearchIcon from "@mui/icons-material/Search";
import { useGroup } from "../api/hooks/useGroups";
import { casSearchUrl, sdsPdfSearchUrl } from "../utils/sdsResearch";
```

(`useGroup` joins the existing `useIsGroupAdmin` import from `../api/hooks/useGroups` — merge into one import statement.)

In the component body, next to the existing `useIsGroupAdmin` call:

```typescript
  const { data: group } = useGroup(groupId);
```

Insert directly AFTER the GESTIS block (`{chemical.zvg && ( ... )}`) and BEFORE the `{chemical.sds_path ? (` block:

```tsx
        {isAdmin && !chemical.sds_path && chemical.cas && group?.show_sds_research_links && (
          <>
            <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", mb: 0.5 }}>
              <SearchIcon sx={{ fontSize: 12, color: "primary.main" }} />
              <MuiLink
                href={casSearchUrl(chemical.cas)}
                target="_blank"
                rel="noopener"
                sx={{ fontSize: 11 }}
              >
                CAS-Recherche (Google)
              </MuiLink>
            </Stack>
            <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", mb: 0.5 }}>
              <SearchIcon sx={{ fontSize: 12, color: "primary.main" }} />
              <MuiLink
                href={sdsPdfSearchUrl(chemical.cas)}
                target="_blank"
                rel="noopener"
                sx={{ fontSize: 11 }}
              >
                SDS-PDF-Suche (Google)
              </MuiLink>
            </Stack>
          </>
        )}
```

- [ ] **Step 4: Build to verify**

Run: `cd frontend && npm run build`
Expected: build succeeds, no TS errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/utils/sdsResearch.ts frontend/src/components/ChemicalInfoBox.tsx
git commit -m "feat(sds): Google research links in chemical info box"
```

---

### Task 4: Frontend — Settings toggle

**Files:**
- Modify: `frontend/src/components/settings/ChemicalsAdminSection.tsx`

- [ ] **Step 1: Add the toggle component**

In `frontend/src/components/settings/ChemicalsAdminSection.tsx`:

Add to the MUI import: `FormControlLabel, Switch` (join the existing `@mui/material` import list). Add hook import:

```typescript
import { useGroup, useUpdateGroup, useIsGroupAdmin } from "../../api/hooks/useGroups";
```

Add this component at the end of the file:

```tsx
function ResearchLinksToggle({ groupId }: { groupId: string }) {
  const { data: group } = useGroup(groupId);
  const update = useUpdateGroup(groupId);

  if (!group) return null;
  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
      <FormControlLabel
        control={
          <Switch
            size="small"
            checked={group.show_sds_research_links}
            disabled={update.isPending}
            onChange={(e) =>
              update.mutate({ show_sds_research_links: e.target.checked })
            }
          />
        }
        label="Show SDS research links"
        slotProps={{ typography: { variant: "body2" } }}
      />
      <Typography variant="body2" color="text.secondary">
        Admins see Google research links on chemicals with a CAS but no
        uploaded SDS.
      </Typography>
    </Stack>
  );
}
```

- [ ] **Step 2: Render it for group admins**

In `ChemicalsAdminSection`, add next to the existing hooks:

```typescript
  const isGroupAdmin = useIsGroupAdmin(groupId);
```

and inside the `<Stack spacing={2} sx={{ maxWidth: 600 }}>`, before the `{isSuperuser && (` block:

```tsx
        {isGroupAdmin && <ResearchLinksToggle groupId={groupId} />}
```

- [ ] **Step 3: Build to verify**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/settings/ChemicalsAdminSection.tsx
git commit -m "feat(sds): per-group toggle for research links in settings"
```

---

### Task 5: E2E coverage

**Files:**
- Create: `frontend/e2e/sds-research-links.spec.ts`

Follows the conventions of `frontend/e2e/gestis-link.spec.ts` (login helper, fabricated check-digit-valid CAS, gestis-resolve stubbed to a miss so GESTIS never interferes). Note: `bun` is missing on the dev box — if Playwright's webServer fails, start the app manually and run with an existing server; the suite has 10 pre-existing baseline failures unrelated to this feature.

- [ ] **Step 1: Write the spec**

Create `frontend/e2e/sds-research-links.spec.ts`:

```typescript
import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

// Unique, check-digit-valid, guaranteed-unknown CAS per run (see gestis-link.spec.ts).
function makeCas(): string {
  const first = String(Date.now()).slice(-7);
  const second = "13";
  const digits = (first + second).split("").reverse();
  let total = 0;
  digits.forEach((d, i) => {
    total += Number(d) * (i + 1);
  });
  return `${Number(first)}-${second}-${total % 10}`;
}

async function createChemical(page: Page, name: string, cas: string) {
  await page.getByRole("button", { name: /^new$/i }).click();
  await expect(page.getByLabel("Name")).toBeVisible();
  await page.getByLabel("Name").fill(name);
  await page.getByLabel(/cas number/i).fill(cas);
  await page.getByRole("button", { name: /^create$/i }).click();
  await page.getByPlaceholder(/search chemical/i).fill(name);
  await expect(page.getByText(name, { exact: true })).toBeVisible({
    timeout: 10_000,
  });
}

test.describe("SDS research links", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    // Keep GESTIS out of the picture: every resolve is a miss.
    await page.route("**/gestis-resolve", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ zvg: null, url: null }),
      });
    });
  });

  test("admin sees both Google links on a chemical without SDS", async ({ page }) => {
    const name = `SDS Links ${Date.now()}`;
    const cas = makeCas();
    await createChemical(page, name, cas);
    await page.getByText(name, { exact: true }).click();

    const casLink = page.getByRole("link", { name: "CAS-Recherche (Google)" });
    await expect(casLink).toBeVisible({ timeout: 10_000 });
    await expect(casLink).toHaveAttribute(
      "href",
      `https://www.google.com/search?q=${encodeURIComponent(`"${cas}"`)}`,
    );

    const pdfLink = page.getByRole("link", { name: "SDS-PDF-Suche (Google)" });
    await expect(pdfLink).toBeVisible();
    await expect(pdfLink).toHaveAttribute(
      "href",
      `https://www.google.com/search?q=${encodeURIComponent(
        `"${cas}" sicherheitsdatenblatt filetype:pdf`,
      )}`,
    );
  });

  test("settings toggle hides the links and can be re-enabled", async ({ page }) => {
    const name = `SDS Toggle ${Date.now()}`;
    const cas = makeCas();
    await createChemical(page, name, cas);

    const setToggle = async (checked: boolean) => {
      await page.goto("/settings");
      await page.getByText("Chemicals", { exact: true }).click();
      const toggle = page.getByRole("checkbox", {
        name: /show sds research links/i,
      });
      await expect(toggle).toBeVisible({ timeout: 10_000 });
      if ((await toggle.isChecked()) !== checked) {
        await toggle.click();
        await expect(toggle).toBeChecked({ checked, timeout: 10_000 });
      }
    };

    await setToggle(false);
    try {
      await page.goto("/");
      await page.getByPlaceholder(/search chemical/i).fill(name);
      await page.getByText(name, { exact: true }).click();
      await expect(
        page.getByRole("button", { name: /chemical actions/i }),
      ).toBeVisible({ timeout: 10_000 });
      await expect(
        page.getByRole("link", { name: "CAS-Recherche (Google)" }),
      ).not.toBeVisible();
    } finally {
      // Restore the default so reruns and other tests see the links again.
      await setToggle(true);
    }
  });
});
```

- [ ] **Step 2: Run the new spec**

Run: `cd frontend && npx playwright test e2e/sds-research-links.spec.ts`
(App must be reachable; if the `bun dev` webServer fails on this box, start the backend + `npm run dev` manually first and rerun.)
Expected: both tests PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/sds-research-links.spec.ts
git commit -m "test(sds): e2e coverage for research links and settings toggle"
```

---

### Task 6: Final verification

- [ ] **Step 1: Full backend suite**

Run: `uv run pytest`
Expected: all green.

- [ ] **Step 2: Frontend production build**

Run: `cd frontend && npm run build`
Expected: clean build (required because bundled mode serves `src/chaima/static/`).

- [ ] **Step 3: Manual smoke (bundled mode)**

Run the app (`chaima run` or uvicorn), open a CAS-bearing chemical without SDS as admin: both links render below GESTIS/PubChem and open the right Google queries. Toggle off in Settings → Chemicals: rows disappear. Toggle back on.

- [ ] **Step 4: Leave the branch for user review**

Do NOT push or merge — the user reviews the branch diff himself first.
