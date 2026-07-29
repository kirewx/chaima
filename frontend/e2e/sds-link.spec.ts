import { test, expect, type Page } from "@playwright/test";

const SDS_URL = "https://example.com/sds.pdf";

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

/**
 * Create a chemical carrying an external SDS link, then bring it into view.
 * The dev DB holds a large, alphabetically sorted, paginated seed list, so a
 * fresh chemical is rarely on the first page — filter by its unique name.
 */
async function createChemicalWithSdsUrl(page: Page, name: string) {
  await page.getByRole("button", { name: /^new$/i }).click();
  const drawer = newChemicalDrawer(page);
  await expect(drawer).toBeVisible({ timeout: 5_000 });
  // The field is required, so MUI renders its label as "Name *".
  await drawer.getByLabel(/^name/i).fill(name);
  await drawer.getByLabel(/sds link \(url\)/i).fill(SDS_URL);
  await drawer.getByRole("button", { name: /^create$/i }).click();
  await expect(drawer).toHaveCount(0, { timeout: 10_000 });

  await page.getByPlaceholder(/search chemical/i).fill(name);
  await expect(page.getByText(name, { exact: true })).toBeVisible({
    timeout: 10_000,
  });
}

test.describe("SDS external link", () => {
  test("admin sees the external link and can fetch the PDF from it", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await login(page);
    const name = `E2E SDS URL ${Date.now()}`;

    // The real /sds-fetch would have to download from the (non-existent)
    // upstream URL, so it is mocked. On success the hook invalidates
    // ["chemicals", groupId], which refetches the list — from that point on the
    // list mock has to serve the post-fetch state (sds_path set), otherwise the
    // UI would flip straight back to the "external link only" branch.
    let fetched = false;
    let listItem: Record<string, unknown> | null = null;

    await page.route("**/api/v1/groups/*/chemicals?*", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      for (const item of json.items ?? []) {
        if (item.name !== name) continue;
        if (fetched) item.sds_path = "g/abc.pdf";
        listItem = item;
      }
      await route.fulfill({ response, json });
    });

    await page.route("**/sds-fetch", async (route) => {
      fetched = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...(listItem ?? {}), sds_path: "g/abc.pdf" }),
      });
    });

    await createChemicalWithSdsUrl(page, name);
    await page.getByText(name, { exact: true }).click();

    const externalLink = page.getByRole("link", { name: "SDS link (external)" });
    await expect(externalLink).toBeVisible({ timeout: 10_000 });
    await expect(externalLink).toHaveAttribute("href", SDS_URL);
    // No PDF stored yet, so neither the stored-SDS link nor its "Source"
    // companion may be on screen.
    await expect(page.getByRole("link", { name: "Safety data sheet" })).toHaveCount(0);

    const fetchButton = page.getByRole("button", { name: "Fetch PDF" });
    await expect(fetchButton).toBeVisible();
    await fetchButton.click();

    // The stored-PDF branch takes over: a link to the archived SDS plus the
    // original URL as "Source"; the fetch action is gone.
    const storedLink = page.getByRole("link", { name: "Safety data sheet" });
    await expect(storedLink).toBeVisible({ timeout: 10_000 });
    await expect(storedLink).toHaveAttribute("href", /\/chemicals\/[^/]+\/sds$/);
    const sourceLink = page.getByRole("link", { name: "Source" });
    await expect(sourceLink).toBeVisible();
    await expect(sourceLink).toHaveAttribute("href", SDS_URL);
    await expect(page.getByRole("button", { name: "Fetch PDF" })).toHaveCount(0);
  });

  test("a non-admin member sees the link but no fetch action", async ({ page }) => {
    test.setTimeout(60_000);
    await login(page);
    const name = `E2E SDS URL Member ${Date.now()}`;

    // Create as admin first, then demote the session for the UI's admin gate.
    await createChemicalWithSdsUrl(page, name);

    // useIsGroupAdmin: superuser wins outright, otherwise the group membership
    // must carry is_admin — strip both so the component renders as a member.
    await page.route("**/api/v1/users/me", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      json.is_superuser = false;
      await route.fulfill({ response, json });
    });
    let memberCalls = 0;
    await page.route("**/api/v1/groups/*/members", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      memberCalls += 1;
      await route.fulfill({
        response,
        json: (json ?? []).map((m: Record<string, unknown>) => ({
          ...m,
          is_admin: false,
        })),
      });
    });

    await page.goto("/");
    await page.getByPlaceholder(/search chemical/i).fill(name);
    await page.getByText(name, { exact: true }).click();

    const externalLink = page.getByRole("link", { name: "SDS link (external)" });
    await expect(externalLink).toBeVisible({ timeout: 10_000 });
    await expect(externalLink).toHaveAttribute("href", SDS_URL);
    // A pending membership query would also read as "not admin", so make sure
    // the demoted membership has actually been served before asserting.
    await expect.poll(() => memberCalls, { timeout: 10_000 }).toBeGreaterThan(0);
    await expect(page.getByRole("button", { name: "Fetch PDF" })).toHaveCount(0);

    // Background refetches may still be in flight when the test ends; drop the
    // handlers so a request cut short by teardown doesn't fail the test.
    await page.unrouteAll({ behavior: "ignoreErrors" });
  });
});
