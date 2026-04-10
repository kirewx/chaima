import { test, expect } from "@playwright/test";

test.describe("Storage Page (unauthenticated)", () => {
  test("redirects to login when not authenticated", async ({ page }) => {
    await page.goto("/storage");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe.skip("Storage Page (authenticated)", () => {
  test("shows Storage Locations heading at root", async ({ page }) => {
    await page.goto("/storage");
    await expect(page.getByText("Storage Locations")).toBeVisible();
  });

  test("shows empty state when no locations", async ({ page }) => {
    await page.goto("/storage");
    await expect(page.getByText("No storage locations yet")).toBeVisible();
  });

  test("can create a root storage location", async ({ page }) => {
    await page.goto("/storage");
    await page.getByRole("button", { name: /add/i }).click();
    await page.getByLabel("Name").fill("Room A");
    await page.getByRole("button", { name: /create/i }).click();
    await expect(page.getByText("Room A")).toBeVisible();
  });
});
