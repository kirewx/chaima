import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

// The settings nav items render as role="button" inside <nav aria-label="Settings sections">.
// Scope to that nav so the labels don't collide with the SectionHeader (which is a real heading).
function navButton(page: Page, label: string) {
  return page
    .getByRole("navigation", { name: "Settings sections" })
    .getByRole("button", { name: label, exact: true });
}

test.describe("Settings page", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto("/settings");
    // Account is the default section
    await expect(page.getByRole("heading", { name: "Account" })).toBeVisible();
  });

  test("theme toggle persists across reload", async ({ page }) => {
    // Read initial body bg so we can restore at the end regardless of starting state.
    const startBg = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor,
    );
    const startedDark = /rgb\(10,\s*10,\s*10\)/.test(startBg);

    // Flip to dark
    await page.getByRole("button", { name: "Dark theme" }).click();

    // useUpdateMe invalidation cascades into useAppTheme — body bg should flip live.
    await expect
      .poll(
        async () =>
          page.evaluate(() => getComputedStyle(document.body).backgroundColor),
        { timeout: 5_000 },
      )
      .toMatch(/rgb\(10,\s*10,\s*10\)/);

    // Persist across reload
    await page.reload();
    await expect(page.getByRole("heading", { name: "Account" })).toBeVisible();
    const bgAfter = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor,
    );
    expect(bgAfter).toMatch(/rgb\(10,\s*10,\s*10\)/);

    // Reset to whatever the user started with so other tests / reruns are stable.
    if (!startedDark) {
      await page.getByRole("button", { name: "Light theme" }).click();
      await expect
        .poll(
          async () =>
            page.evaluate(
              () => getComputedStyle(document.body).backgroundColor,
            ),
          { timeout: 5_000 },
        )
        .toMatch(/rgb\(255,\s*255,\s*255\)/);
    }
  });

  test("generate and revoke invite", async ({ page }) => {
    await navButton(page, "Members & Invites").click();
    await expect(
      page.getByRole("heading", { name: "Members & Invites" }),
    ).toBeVisible();

    await page.getByRole("tab", { name: "Pending invites" }).click();

    await page.getByRole("button", { name: "New invite" }).click();
    await expect(page.getByText("New invite link")).toBeVisible();

    // Wait for the read-only token field to populate inside the dialog
    const dialog = page.getByRole("dialog");
    const tokenInput = dialog.locator("input[readonly]");
    await expect(tokenInput).toHaveValue(/\/invite\/[A-Za-z0-9_-]{10,}/, {
      timeout: 10_000,
    });

    await dialog.getByRole("button", { name: "Done" }).click();
    await expect(dialog).toHaveCount(0);

    // The newly created invite shows up in the list with a Revoke button.
    const revokeBtn = page.getByRole("button", { name: "Revoke" }).first();
    await expect(revokeBtn).toBeVisible();
    await revokeBtn.click();
  });

  test("hazard tag create and delete", async ({ page }) => {
    page.on("dialog", (d) => d.accept());

    const name = `E2E Flammable ${Date.now()}`;

    await navButton(page, "Hazard tags").click();
    await expect(
      page.getByRole("heading", { name: "Hazard tags" }),
    ).toBeVisible();

    await page.getByRole("button", { name: "New tag" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByLabel("Name")).toBeVisible();
    await dialog.getByLabel("Name").fill(name);
    await dialog.getByRole("button", { name: /^create$/i }).click();
    await expect(dialog).toHaveCount(0);

    const row = page.getByText(name, { exact: true });
    await expect(row).toBeVisible();

    await page.getByRole("button", { name: `Delete ${name}` }).click();
    await expect(page.getByText(name, { exact: true })).toHaveCount(0);
  });
});
