import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

test.describe("Supplier free-solo in ContainerForm", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("surfaces the Create option for a new supplier name", async ({
    page,
  }) => {
    const chemName = `Supplier FS Mol ${Date.now()}`;
    const supplierName = `Supplier FS ${Date.now()}`;

    // Create a chemical so we can open the container drawer from it.
    await page.getByRole("button", { name: /new chemical/i }).click();
    await expect(page.getByLabel("Name")).toBeVisible();
    await page.getByLabel("Name").fill(chemName);
    await page.getByRole("button", { name: /^create$/i }).click();

    const row = page.getByText(chemName, { exact: true });
    await expect(row).toBeVisible();
    await row.click();

    // Open the New container drawer (button is labeled "Container" with an Add icon).
    await page.getByRole("button", { name: /^container$/i }).click();

    // Type a new supplier name in the Autocomplete and click the synthetic Create option.
    const supplierInput = page.getByLabel("Supplier");
    await supplierInput.click();
    await supplierInput.fill(supplierName);

    const createOption = page.getByRole("option", {
      name: new RegExp(`Create\\s+"${supplierName}"`, "i"),
    });
    await expect(createOption).toBeVisible();
    await createOption.click();

    // After picking the Create option the mutation fires and the input now reflects
    // the newly created supplier's name (freeSolo resolves to the created object).
    await expect(supplierInput).toHaveValue(supplierName, { timeout: 10_000 });
  });
});
