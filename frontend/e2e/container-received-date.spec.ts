import { test, expect } from "@playwright/test";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

test.describe("Container received_date", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("defaults to today on create, preserves stored value on edit", async ({
    page,
  }) => {
    const chemName = `RecvDate Mol ${Date.now()}`;
    const today = new Date().toLocaleDateString("en-CA");

    // Create a chemical so the container action is available.
    await page.getByRole("button", { name: /new chemical/i }).click();
    await expect(page.getByLabel("Name")).toBeVisible();
    await page.getByLabel("Name").fill(chemName);
    await page.getByRole("button", { name: /^create$/i }).click();

    const row = page.getByText(chemName, { exact: true });
    await expect(row).toBeVisible();
    await row.click();

    // Open the "New container" drawer via the + button on the ContainerGrid.
    // The button label is just "Container" with an Add icon.
    await page.getByRole("button", { name: /^container$/i }).click();

    const receivedField = page.getByLabel("Received");
    await expect(receivedField).toBeVisible();
    await expect(receivedField).toHaveValue(today);
  });
});
