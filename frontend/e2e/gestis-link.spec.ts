import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

// Fabricate a unique, check-digit-valid CAS per run: unique so reruns don't
// trip the duplicate-CAS guard, fabricated so it's never in the real GESTIS
// index (the backend create-hook resolves against the real index when warm).
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

async function createChemical(page: Page, name: string, cas?: string) {
  await page.getByRole("button", { name: /^new$/i }).click();
  await expect(page.getByLabel("Name")).toBeVisible();
  await page.getByLabel("Name").fill(name);
  if (cas) {
    await page.getByLabel(/cas number/i).fill(cas);
  }
  await page.getByRole("button", { name: /^create$/i }).click();
  // The dev DB carries a large, alphabetically-sorted, paginated seed list,
  // so a freshly created chemical is rarely on the first page. Filter via
  // the (server-side) search box by its unique name to bring it into view.
  await page.getByPlaceholder(/search chemical/i).fill(name);
  await expect(page.getByText(name, { exact: true })).toBeVisible({
    timeout: 10_000,
  });
}

test.describe("GESTIS deeplink", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("auto-resolve hit shows GESTIS link with correct href", async ({ page }) => {
    const name = `GESTIS Hit ${Date.now()}`;
    await page.route("**/gestis-resolve", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          zvg: "010420",
          url: "https://gestis-database.dguv.de/data?name=010420",
        }),
      });
    });

    await createChemical(page, name, makeCas());
    await page.getByText(name, { exact: true }).click();

    const link = page.getByRole("link", { name: /gestis 010420/i });
    await expect(link).toBeVisible({ timeout: 10_000 });
    await expect(link).toHaveAttribute(
      "href",
      "https://gestis-database.dguv.de/data?name=010420",
    );
  });

  test("resolve miss renders no GESTIS row", async ({ page }) => {
    const name = `GESTIS Miss ${Date.now()}`;
    let resolveCalls = 0;
    await page.route("**/gestis-resolve", async (route) => {
      resolveCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ zvg: null, url: null }),
      });
    });

    await createChemical(page, name, makeCas());
    await page.getByText(name, { exact: true }).click();

    // Info box is open (actions button visible), resolve was attempted,
    // but no GESTIS link is rendered.
    await expect(
      page.getByRole("button", { name: /chemical actions/i }),
    ).toBeVisible();
    await expect.poll(() => resolveCalls, { timeout: 10_000 }).toBeGreaterThan(0);
    await expect(page.getByRole("link", { name: /gestis/i })).not.toBeVisible();
  });

  test("stored zvg renders immediately without a resolve call", async ({ page }) => {
    const name = `GESTIS Stored ${Date.now()}`;
    let resolveCalls = 0;
    await page.route("**/gestis-resolve", async (route) => {
      resolveCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ zvg: null, url: null }),
      });
    });
    // Inject a stored zvg into the list response for our chemical.
    await page.route("**/api/v1/groups/*/chemicals?*", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      for (const item of json.items ?? []) {
        if (item.name === name) item.zvg = "010420";
      }
      await route.fulfill({ response, json });
    });

    // No CAS: with zvg set the effect must not fire regardless.
    await createChemical(page, name);
    await page.getByText(name, { exact: true }).click();

    const link = page.getByRole("link", { name: /gestis 010420/i });
    await expect(link).toBeVisible({ timeout: 10_000 });
    expect(resolveCalls).toBe(0);
  });
});
