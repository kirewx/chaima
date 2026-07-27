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

// NOTE: the CAS below is deliberately NOT acetone's real CAS (67-64-1) —
// the dev-seed DB already has a chemical with that CAS ("Aceton"), and the
// app's duplicate-chemical check (by exact CAS/name match) would block
// creation with a 409. The SMILES is still real acetone so RDKit renders
// a genuine structure SVG.
const FAKE_LOOKUP = {
  cid: "180",
  name: "propan-2-one",
  cas: "999999-11-1",
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
    await page.getByRole("button", { name: /^new$/i }).click();
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
    // (The chemicals list is paginated/sorted — filter via the search box first.)
    await page.getByPlaceholder(/search chemical/i).fill(unique);
    await page.getByText(unique, { exact: true }).click();
    const thumb = page.getByRole("button", {
      name: /enlarged structure/i,
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
