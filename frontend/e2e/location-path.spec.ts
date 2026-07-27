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
    await page.getByRole("button", { name: /^new$/i }).click();
    await expect(page.getByLabel("Name")).toBeVisible();
    await page.getByLabel("Name").fill(chemName);
    await page.getByRole("button", { name: /^create$/i }).click();

    // The list is sorted alphabetically and paginated, so the freshly
    // created chemical is not guaranteed to be on the first page — filter
    // for it via the search box.
    await page
      .getByPlaceholder(/search chemical/i)
      .fill(chemName);

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
