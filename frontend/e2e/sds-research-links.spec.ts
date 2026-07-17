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
      // The settings nav renders section items as role="button" divs; plain
      // text matching also hits the top-level app nav link to "/chemicals".
      await page.getByRole("button", { name: "Chemicals", exact: true }).click();
      // MUI's Switch exposes role="switch", not "checkbox".
      const toggle = page.getByRole("switch", {
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
