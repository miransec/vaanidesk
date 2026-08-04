import { test, expect } from "@playwright/test";

test.describe("JWT authentication", () => {
  test("register, sign in, and sign out", async ({ page }) => {
    const email = `e2e-${Date.now()}@example.com`;
    const password = "E2eTestPass1!";

    await page.goto("/login");
    await page.getByRole("button", { name: "Register" }).click();
    await page.getByPlaceholder("Your name").fill("E2E Tester");
    await page.getByPlaceholder("you@example.com").fill(email);
    await page.getByPlaceholder("Min. 8 characters").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page).toHaveURL(/\/chat/, { timeout: 30_000 });

    await page.getByRole("link", { name: "Account" }).click();
    await expect(page.getByRole("heading", { name: "Account" })).toBeVisible();
    await expect(page.getByText(email)).toBeVisible();

    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: /Sign in to VaaniDesk/i })).toBeVisible();
  });
});
