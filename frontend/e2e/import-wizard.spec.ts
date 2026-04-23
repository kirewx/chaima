import { test, expect, type Page } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function loginAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

test.describe("Import wizard", () => {
  test.beforeEach(async ({ page }) => {
    await loginAdmin(page);
  });

  test("imports a fixture xlsx end-to-end", async ({ page }) => {
    await page.goto("/settings");
    await page.getByRole("button", { name: /import & export/i }).click();

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(
      path.resolve(__dirname, "../../tests/fixtures/import_sample.xlsx"),
    );

    await page.getByRole("button", { name: /^next$/i }).click();

    await page.getByRole("button", { name: /^next$/i }).click();

    await page.getByRole("button", { name: /commit import/i }).click();

    await expect(page.getByText(/Created \d+ chemicals/i)).toBeVisible({ timeout: 15_000 });

    await page.goto("/chemicals");
    await expect(page.getByText("Ethanol", { exact: true })).toBeVisible();
    await expect(page.getByText("Acetone", { exact: true })).toBeVisible();
  });
});
