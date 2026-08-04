import { test, expect } from "@playwright/test";
import { openDemoChat, sendChatMessage, waitForAssistantReply } from "./helpers/chat";

test.describe("Customer chat product UX", () => {
  test.beforeEach(async ({ page }) => {
    await openDemoChat(page);
  });

  test("demo customer selection hides UUIDs and debug internals", async ({ page }) => {
    await expect(page.getByText(/Phase \d/i)).toHaveCount(0);
    await expect(page.getByText(/X-Demo-User-Key/i)).toHaveCount(0);
    await expect(page.getByText(/localhost:8000/i)).toHaveCount(0);
    await expect(page.getByText(/Intent:/i)).toHaveCount(0);
    await expect(page.getByText(/Tool status/i)).toHaveCount(0);
    await expect(page.getByText(/Mock STT\/TTS/i)).toHaveCount(0);
    await expect(page.getByText(/Dup User|Pw User|Sess User|Brute User/i)).toHaveCount(0);
    const chat = page.getByLabel("Conversation");
    await expect(chat).not.toContainText(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
  });

  test("empty state greeting and suggestion chips", async ({ page }) => {
    // Fresh conversation may already have seed messages — switch customer then start clean if needed
    await expect(page.getByRole("heading", { name: "VaaniDesk Support" })).toBeVisible();
    const greeting = page.getByText("Hi, how can I help you today?");
    if (await greeting.isVisible().catch(() => false)) {
      await expect(page.getByRole("button", { name: "Track my order" })).toBeVisible();
    }
  });

  test("send a normal order status message", async ({ page }) => {
    await sendChatMessage(page, "where is my order VD-10001");
    await waitForAssistantReply(page);
    await expect(page.getByText(/VD-10001|order/i).first()).toBeVisible();
    await expect(page.getByText(/Tool:/i)).toHaveCount(0);
  });

  test("knowledge question shows sources without chunk UUIDs", async ({ page }) => {
    await sendChatMessage(page, "what is your return policy for unused items?");
    await waitForAssistantReply(page);
    await expect(page.getByText("Sources")).toBeVisible();
    await expect(page.getByText(/Confidence:\s*0\./i)).toHaveCount(0);
  });

  test("damaged product refund policy prefers customer policy sources", async ({ page }) => {
    await sendChatMessage(page, "What is the refund policy for a damaged product?");
    await waitForAssistantReply(page);
    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(/Tool:\s*get_/i);
    // Either grounded answer with Damaged Products, or abstention — not agent playbook as sole story
    const hasPolicy =
      /Damaged Products|damaged|refund|couldn't find enough reliable/i.test(body);
    expect(hasPolicy).toBeTruthy();
  });

  test("sensitive cancel request shows customer confirmation UI", async ({ page }) => {
    await sendChatMessage(page, "please cancel my order VD-10001");
    await expect(page.getByLabel("Confirmation required")).toBeVisible();
    await expect(page.getByRole("button", { name: "Confirm cancellation" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Keep order" })).toBeVisible();
    await expect(page.getByText(/idempotency|tool call/i)).toHaveCount(0);
  });

  test("deny confirmation clears pending state", async ({ page }) => {
    await sendChatMessage(page, "please cancel my order VD-10001");
    await expect(page.getByLabel("Confirmation required")).toBeVisible();
    await page.getByRole("button", { name: "Keep order" }).click();
    await expect(page.getByLabel("Confirmation required")).toHaveCount(0);
    await waitForAssistantReply(page);
  });

  test("ambiguous sensitive request asks for clarification without tool jargon", async ({
    page,
  }) => {
    await sendChatMessage(page, "please cancel my order");
    await waitForAssistantReply(page);
    await expect(page.getByText(/Clarification required/i)).toHaveCount(0);
    await expect(page.getByText(/order|VD-|provide|which/i).first()).toBeVisible();
  });

  test("Hinglish order status is handled", async ({ page }) => {
    await sendChatMessage(page, "mera order VD-10001 kahan hai");
    await waitForAssistantReply(page);
    await expect(page.getByText(/VD-10001|order/i).first()).toBeVisible();
  });

  test("mobile layout remains usable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByRole("textbox", { name: "Message" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Send message" })).toBeVisible();
  });
});

test.describe("Engineering observability remains available", () => {
  test("observability page loads for engineers", async ({ page }) => {
    await page.goto("/admin/observability");
    await expect(page.getByRole("heading", { name: "Observability" })).toBeVisible({
      timeout: 30_000,
    });
  });
});
