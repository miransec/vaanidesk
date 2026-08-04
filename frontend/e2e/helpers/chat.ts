import { expect, type Page } from "@playwright/test";

export async function openDemoChat(page: Page): Promise<void> {
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "Support chat" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByLabel("Demo user")).toBeVisible();
}

export async function sendChatMessage(page: Page, text: string): Promise<void> {
  const input = page.getByRole("textbox", { name: "Message" });
  await input.fill(text);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(input).toHaveValue("");
}

export async function waitForAssistantReply(page: Page): Promise<void> {
  await expect(page.locator('div.rounded-lg >> text=assistant').first()).toBeVisible({
    timeout: 30_000,
  });
}
