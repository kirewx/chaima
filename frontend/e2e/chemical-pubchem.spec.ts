import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

// The ChemicalsPage "New" button opens a MUI Drawer (role="presentation").
// Scope helpers to the drawer's Paper element via its heading.
function drawer(page: Page) {
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
  synonyms: ["Acetone", "67-64-1", "Dimethyl ketone"],
  ghs_codes: [
    {
      code: "H225",
      description: "Highly flammable liquid and vapour",
      signal_word: "Danger",
      pictogram: "GHS02",
    },
    {
      code: "H319",
      description: "Causes serious eye irritation",
      signal_word: "Warning",
      pictogram: "GHS07",
    },
  ],
};

test.describe("PubChem lookup", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto("/");
    // Wait for the chemicals page to be loaded (search bar visible)
    await expect(
      page.getByPlaceholder(/search chemical/i),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("happy path: fetch, fill, save", async ({ page }) => {
    await page.route("**/api/v1/pubchem/lookup*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FAKE_LOOKUP),
      });
    });

    // The button has visible text "New" on sm+ viewports (sm viewport is the default headless).
    // It also contains an AddIcon but its accessible name is simply "New".
    await page.getByRole("button", { name: /^new$/i }).click();

    const d = drawer(page);
    await expect(d).toBeVisible({ timeout: 5_000 });

    // Type a query and click Fetch
    await d
      .getByLabel(/lookup from pubchem/i)
      .fill("e2e-fetch-acetone-" + Date.now());
    await d.getByRole("button", { name: /^fetch$/i }).click();

    // Fields should be populated with the fake response.
    // MUI TextField with required adds " *" to the label, so use a prefix match.
    await expect(d.getByLabel(/^name/i)).toHaveValue("propan-2-one", {
      timeout: 5_000,
    });
    await expect(d.getByLabel(/cas number/i)).toHaveValue("67-64-1");
    await expect(d.getByLabel(/molar mass/i)).toHaveValue("58.08");

    // Success badge rendered inside the drawer
    await expect(d.getByText(/fetched from pubchem/i)).toBeVisible();

    // Uniquify the saved name so the test is re-runnable against the same DB.
    const unique = "propan-2-one-e2e-" + Date.now();
    await d.getByLabel(/^name/i).fill(unique);

    await d.getByRole("button", { name: /^create$/i }).click();
    await expect(d).toHaveCount(0, { timeout: 10_000 });

    // The new chemical appears in the list.
    await expect(page.getByText(unique)).toBeVisible({ timeout: 10_000 });
  });

  test("upstream error: toast appears, fields untouched", async ({ page }) => {
    await page.route("**/api/v1/pubchem/lookup*", async (route) => {
      await route.fulfill({
        status: 502,
        contentType: "application/json",
        body: JSON.stringify({ detail: "PubChem unavailable" }),
      });
    });

    await page.getByRole("button", { name: /^new$/i }).click();

    const d = drawer(page);
    await expect(d).toBeVisible({ timeout: 5_000 });

    // Type a name first (should be preserved after failed fetch)
    await d.getByLabel(/^name/i).fill("preserved-manual-name");
    await d.getByLabel(/lookup from pubchem/i).fill("acetone");
    await d.getByRole("button", { name: /^fetch$/i }).click();

    // The error alert is shown inside the drawer
    await expect(d.getByText(/pubchem unavailable/i)).toBeVisible({
      timeout: 5_000,
    });

    // The manually-typed name was not overwritten
    await expect(d.getByLabel(/^name/i)).toHaveValue("preserved-manual-name");

    // Close the drawer — nothing was saved, DB state is clean.
    await d.getByRole("button", { name: /cancel/i }).click();
    await expect(d).toHaveCount(0, { timeout: 5_000 });
  });
});
