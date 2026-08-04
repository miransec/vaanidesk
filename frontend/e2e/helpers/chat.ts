import { expect, type Page } from "@playwright/test";

export async function openDemoChat(page: Page): Promise<void> {
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "VaaniDesk Support" })).toBeVisible({
    timeout: 30_000,
  });
  const message = page.getByRole("textbox", { name: "Message" });
  if (await message.isVisible().catch(() => false)) {
    return;
  }
  const firstPersona = page.getByRole("button", { name: /Continue as /i }).first();
  await expect(firstPersona).toBeVisible({ timeout: 15_000 });
  await firstPersona.click();
  // Retry once if a remount left the persona gate up (dev Strict Mode / slow hydrate).
  if (!(await message.isVisible().catch(() => false))) {
    if (await firstPersona.isVisible().catch(() => false)) {
      await firstPersona.click();
    }
  }
  await expect(message).toBeVisible({ timeout: 15_000 });
}

export async function sendChatMessage(page: Page, text: string): Promise<void> {
  const input = page.getByRole("textbox", { name: "Message" });
  await input.fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(input).toHaveValue("");
}

export async function waitForAssistantReply(page: Page): Promise<void> {
  const thread = page.getByLabel("Conversation");
  await expect(thread.getByText("is typing")).toHaveCount(0, { timeout: 30_000 });
  await expect(thread.getByText("VaaniDesk", { exact: true }).last()).toBeVisible({
    timeout: 30_000,
  });
}
