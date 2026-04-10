import { test, expect } from "@playwright/test";

test.describe("Navigation", () => {
  test("login page renders without tab bar", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText("ChAIMa")).toBeVisible();
    await expect(page.getByText("Sign in to your account")).toBeVisible();
  });

  test("register page renders without tab bar", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByText("ChAIMa")).toBeVisible();
    await expect(page.getByText("Create a new account")).toBeVisible();
  });

  test("unauthenticated access redirects to login", async ({ page }) => {
    await page.goto("/storage");
    await expect(page).toHaveURL(/\/login/);
  });

  test("unauthenticated access to settings redirects to login", async ({ page }) => {
    await page.goto("/settings");
    await expect(page).toHaveURL(/\/login/);
  });
});
