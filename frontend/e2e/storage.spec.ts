import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

// The EditDrawer is an MUI Drawer with role="presentation"; scope form inputs
// and submit buttons to the drawer paper so they don't collide with the page.
function drawer(page: Page) {
  return page.locator(".MuiDrawer-paper");
}

test.describe("Storage page", () => {
  test("unauthenticated /storage redirects to login", async ({ page }) => {
    await page.goto("/storage");
    await expect(page).toHaveURL(/\/login/);
  });

  test("superuser creates building → room → cabinet → shelf, then archives", async ({
    page,
  }) => {
    // window.confirm from the Archive flow — must register BEFORE the click
    page.on("dialog", (d) => d.accept());

    await login(page);

    // Unique suffix so reruns don't hit "duplicate name"
    const stamp = Date.now();
    const building = `E2E Building ${stamp}`;
    const room = `E2E Lab ${stamp}`;
    const cabinet = `E2E Cabinet ${stamp}`;
    const shelf = `E2E Shelf ${stamp}`;

    await page.getByRole("link", { name: "Storage" }).click();
    await expect(page).toHaveURL(/\/storage$/);

    // ── Create building ───────────────────────────────────────────────────
    await page.getByRole("button", { name: /add building/i }).click();
    await expect(drawer(page).getByLabel("Name")).toBeVisible();
    await drawer(page).getByLabel("Name").fill(building);
    await drawer(page).getByRole("button", { name: /^create$/i }).click();
    await expect(drawer(page)).toHaveCount(0);

    const buildingRow = page.getByText(building, { exact: true });
    await expect(buildingRow).toBeVisible();
    await buildingRow.click();
    await expect(page.getByRole("heading", { name: building })).toBeVisible();

    // ── Create room ───────────────────────────────────────────────────────
    await page.getByRole("button", { name: /add room/i }).click();
    await expect(drawer(page).getByLabel("Name")).toBeVisible();
    await drawer(page).getByLabel("Name").fill(room);
    await drawer(page).getByRole("button", { name: /^create$/i }).click();
    await expect(drawer(page)).toHaveCount(0);

    await page.getByText(room, { exact: true }).click();
    await expect(page.getByRole("heading", { name: room })).toBeVisible();

    // ── Create cabinet ────────────────────────────────────────────────────
    await page.getByRole("button", { name: /add cabinet/i }).click();
    await expect(drawer(page).getByLabel("Name")).toBeVisible();
    await drawer(page).getByLabel("Name").fill(cabinet);
    await drawer(page).getByRole("button", { name: /^create$/i }).click();
    await expect(drawer(page)).toHaveCount(0);

    await page.getByText(cabinet, { exact: true }).click();
    await expect(page.getByRole("heading", { name: cabinet })).toBeVisible();

    // ── Create shelf (leaf) ───────────────────────────────────────────────
    await page.getByRole("button", { name: /add shelf/i }).click();
    await expect(drawer(page).getByLabel("Name")).toBeVisible();
    await drawer(page).getByLabel("Name").fill(shelf);
    await drawer(page).getByRole("button", { name: /^create$/i }).click();
    await expect(drawer(page)).toHaveCount(0);

    await page.getByText(shelf, { exact: true }).click();
    await expect(page.getByRole("heading", { name: shelf })).toBeVisible();

    // Leaf view: Containers (0) + empty-state copy
    await expect(page.getByText(/containers \(0\)/i)).toBeVisible();
    await expect(
      page.getByText(/no containers on this shelf yet/i),
    ).toBeVisible();

    // ── Archive the shelf via Edit drawer ─────────────────────────────────
    await page.getByRole("button", { name: /^edit shelf$/i }).click();
    await expect(
      drawer(page).getByRole("button", { name: /^archive$/i }),
    ).toBeVisible();
    await drawer(page).getByRole("button", { name: /^archive$/i }).click();
    await expect(drawer(page)).toHaveCount(0);

    // Navigate back up to the cabinet via the top nav and drill down, then
    // confirm the archived shelf is gone from the cabinet's child list.
    await page.getByRole("link", { name: "Storage" }).click();
    await expect(page).toHaveURL(/\/storage$/);
    await page.getByText(building, { exact: true }).click();
    await page.getByText(room, { exact: true }).click();
    await page.getByText(cabinet, { exact: true }).click();
    await expect(page.getByRole("heading", { name: cabinet })).toBeVisible();
    await expect(page.getByText(shelf, { exact: true })).toHaveCount(0);
  });

  test("regular (non-superuser) user does not see the building level", async () => {
    // The dev seed only provisions a single superuser (admin@chaima.dev). There
    // is no regular-user fixture in the current backend seed, so we cannot
    // meaningfully exercise the non-SU path here. Skipped with a note so the
    // intent is preserved per the Plan 3 Task 9 acceptance criteria.
    test.skip(
      true,
      "No regular-user fixture in current seed — only admin@chaima.dev exists.",
    );
  });

  test("leaf container links back to Chemicals page", async () => {
    test.skip(
      true,
      "Requires a seeded container on a shelf — not in current fixtures.",
    );
  });
});
