import { test, expect } from "@playwright/test";
import { openDemoChat } from "./helpers/chat";

test.describe("Demo authentication", () => {
  test("login page links to demo chat", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Sign in to VaaniDesk/i })).toBeVisible();
    await page.getByRole("link", { name: /Continue with demo mode/i }).click();
    await expect(page).toHaveURL(/\/chat/);
    await expect(page.getByRole("heading", { name: "VaaniDesk Support" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Continue as /i }).first()).toBeVisible();
  });

  test("demo customer personas load curated identities only", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.getByRole("heading", { name: "VaaniDesk Support" })).toBeVisible({
      timeout: 30_000,
    });
    const list = page.getByLabel("Demo customers");
    await expect(list).toBeVisible();
    await expect(list).toContainText(/Aarav Sharma|Rahul Verma|Meera Patel/);
    await expect(list).not.toContainText(/Dup User|Pw User|Sess User|Brute User|Refresh User/);
    await expect(list).not.toContainText(/[0-9a-f]{8}-[0-9a-f]{4}-/i);
    await openDemoChat(page);
    await expect(page.getByText(/Signed in as/i)).toBeVisible();
  });
});
