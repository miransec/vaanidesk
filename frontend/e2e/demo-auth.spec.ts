import { test, expect } from "@playwright/test";
import { openDemoChat } from "./helpers/chat";

test.describe("Demo authentication", () => {
  test("login page links to demo chat", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Sign in to VaaniDesk/i })).toBeVisible();
    await page.getByRole("link", { name: /Continue with demo mode/i }).click();
    await expect(page).toHaveURL(/\/chat/);
    await expect(page.getByRole("heading", { name: "Support chat" })).toBeVisible();
    await expect(page.getByLabel("Demo user")).toHaveValue("demo-anya");
  });

  test("demo user selector loads seeded identities", async ({ page }) => {
    await openDemoChat(page);
    const select = page.getByLabel("Demo user");
    await expect(select.locator("option")).not.toHaveCount(0);
    await expect(select).toContainText("demo-anya");
  });
});
