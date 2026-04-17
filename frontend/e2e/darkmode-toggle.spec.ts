import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

test.describe("AppBar dark mode toggle", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("flips theme from the AppBar toggle button", async ({ page }) => {
    const toggle = page.getByRole("button", { name: /toggle dark mode/i });
    await expect(toggle).toBeVisible();

    const startBg = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor,
    );
    const startedDark = /rgb\(10,\s*10,\s*10\)/.test(startBg);

    await toggle.click();

    const targetPattern = startedDark
      ? /rgb\(255,\s*255,\s*255\)/
      : /rgb\(10,\s*10,\s*10\)/;

    await expect
      .poll(
        async () =>
          page.evaluate(() => getComputedStyle(document.body).backgroundColor),
        { timeout: 5_000 },
      )
      .toMatch(targetPattern);

    // Flip back so subsequent tests start from the original state
    await page.getByRole("button", { name: /toggle dark mode/i }).click();
    await expect
      .poll(
        async () =>
          page.evaluate(() => getComputedStyle(document.body).backgroundColor),
        { timeout: 5_000 },
      )
      .toMatch(
        startedDark ? /rgb\(10,\s*10,\s*10\)/ : /rgb\(255,\s*255,\s*255\)/,
      );
  });
});
