import { test, expect } from "@playwright/test";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  // Wait up to 15 s for the redirect away from /login after cookie is set
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

test.describe("Chemicals page", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("create, expand, archive, include archived, unarchive", async ({ page }) => {
    // Unique name so reruns don't collide
    const name = `E2E Test Mol ${Date.now()}`;

    // ── Create ──────────────────────────────────────────────────────────────
    await page.getByRole("button", { name: /new chemical/i }).click();
    // Wait for the drawer/form to appear
    await expect(page.getByLabel("Name")).toBeVisible();
    await page.getByLabel("Name").fill(name);
    await page.getByRole("button", { name: /^create$/i }).click();

    // New row appears in the list
    const row = page.getByText(name, { exact: true });
    await expect(row).toBeVisible();

    // ── Expand ───────────────────────────────────────────────────────────────
    await row.click();
    // Wait for the "Chemical actions" button to appear inside the expanded ChemicalInfoBox
    const actionsBtn = page.getByRole("button", { name: /chemical actions/i });
    await expect(actionsBtn).toBeVisible();

    // ── Archive (via "..." menu) ─────────────────────────────────────────────
    await actionsBtn.click();
    await page.getByRole("menuitem", { name: /^archive$/i }).click();

    // Row is gone from the default (non-archived) list
    await expect(page.getByText(name, { exact: true })).not.toBeVisible();

    // ── Include archived via Filters drawer ──────────────────────────────────
    await page.getByRole("button", { name: /filters/i }).click();
    // MUI renders the FormControlLabel Switch with role="switch" (not "checkbox").
    // The accessible name concatenates the label Stack's text nodes.
    const includeArchivedSwitch = page.getByRole("switch", { name: /include archived/i });
    await expect(includeArchivedSwitch).toBeVisible();
    // If not already checked, enable it
    if (!(await includeArchivedSwitch.isChecked())) {
      await includeArchivedSwitch.click();
    }
    // Close the drawer by clicking the "Apply" button
    await page.getByRole("button", { name: /^apply$/i }).click();

    // Archived row is now visible again
    await expect(page.getByText(name, { exact: true })).toBeVisible();

    // ── Re-expand, then Unarchive ────────────────────────────────────────────
    await page.getByText(name, { exact: true }).click();
    // Wait for the ChemicalInfoBox to appear (Chemical actions button becomes visible)
    await expect(page.getByRole("button", { name: /chemical actions/i })).toBeVisible();

    await page.getByRole("button", { name: /chemical actions/i }).click();
    // MUI Menu animates in; use force:true to click through any in-progress
    // animation on the menuitem
    await page
      .getByRole("menuitem", { name: /unarchive/i })
      .click({ force: true });

    // ── Turn off filter to confirm it's back in the default list ─────────────
    await page.getByRole("button", { name: /filters/i }).click();
    const switchAgain = page.getByRole("switch", { name: /include archived/i });
    await expect(switchAgain).toBeVisible();
    // Turn off the "include archived" filter
    if (await switchAgain.isChecked()) {
      await switchAgain.click();
    }
    await page.getByRole("button", { name: /^apply$/i }).click();

    // Chemical still visible after unarchive with archived filter off
    await expect(page.getByText(name, { exact: true })).toBeVisible();
  });

  test("secret chemical visible to creator", async ({ page }) => {
    const name = `Secret E2E ${Date.now()}`;

    await page.getByRole("button", { name: /new chemical/i }).click();
    await expect(page.getByLabel("Name")).toBeVisible();
    await page.getByLabel("Name").fill(name);

    // MUI FormControlLabel with Switch renders role="switch"; accessible name
    // includes the label Stack text ("Mark as secret" + caption).
    const secretSwitch = page.getByRole("switch", { name: /mark as secret/i });
    await expect(secretSwitch).toBeVisible();
    if (!(await secretSwitch.isChecked())) {
      await secretSwitch.click();
    }

    await page.getByRole("button", { name: /^create$/i }).click();

    // Creator still sees the secret chemical in their own list
    await expect(page.getByText(name, { exact: true })).toBeVisible();
  });
});
