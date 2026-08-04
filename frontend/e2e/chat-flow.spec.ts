import { test, expect } from "@playwright/test";
import { openDemoChat, sendChatMessage, waitForAssistantReply } from "./helpers/chat";

test.describe("Support chat workflow", () => {
  test.beforeEach(async ({ page }) => {
    await openDemoChat(page);
  });

  test("send a normal order status message", async ({ page }) => {
    await sendChatMessage(page, "where is my order VD-10001");
    await waitForAssistantReply(page);
    await expect(page.getByText(/VD-10001|order/i).first()).toBeVisible();
  });

  test("knowledge question shows citations", async ({ page }) => {
    await sendChatMessage(page, "what is your return policy for unused items?");
    await waitForAssistantReply(page);
    await expect(page.getByText("Citations")).toBeVisible();
    await expect(page.locator("ul li").first()).toBeVisible();
  });

  test("sensitive cancel request shows confirmation UI", async ({ page }) => {
    await sendChatMessage(page, "please cancel my order VD-10001");
    await expect(page.getByText("Confirmation required")).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve confirmation" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Deny confirmation" })).toBeVisible();
  });

  test("deny confirmation clears pending state", async ({ page }) => {
    await sendChatMessage(page, "please cancel my order VD-10001");
    await expect(page.getByText("Confirmation required")).toBeVisible();
    await page.getByRole("button", { name: "Deny confirmation" }).click();
    await expect(page.getByText("Confirmation required")).toHaveCount(0);
    await waitForAssistantReply(page);
  });

  test("ambiguous sensitive request surfaces clarification state", async ({ page }) => {
    await sendChatMessage(page, "please cancel my order");
    await waitForAssistantReply(page);
    await expect(page.getByText("Clarification required")).toBeVisible();
  });

  test("Hinglish order status is handled", async ({ page }) => {
    await sendChatMessage(page, "mera order VD-10001 kahan hai");
    await waitForAssistantReply(page);
    await expect(page.getByText(/VD-10001|order|language/i).first()).toBeVisible();
  });
});
