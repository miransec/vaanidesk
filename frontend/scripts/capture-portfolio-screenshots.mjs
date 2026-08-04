/**
 * Portfolio screenshot capture for VaaniDesk v1.0.1.
 * Playwright against the live UI only — does not change application behavior.
 *
 * Prerequisites: healthy stack (default http://localhost:3000 + backend DB).
 *
 *   node scripts/capture-portfolio-screenshots.mjs        # full set
 *   node scripts/capture-portfolio-screenshots.mjs 06     # escalation only
 */
import { chromium } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import os from "node:os";
import { execFileSync } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "../../docs/assets/screenshots");
const BACKEND = path.resolve(__dirname, "../../backend");
const BASE = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

const VIEWPORT = { width: 1440, height: 1000 };
const SCALE = 2;

/** Unknown-intent escalation — one turn, no prior RAG answer in the thread. */
const ESCALATION_MESSAGE =
  "blorp zarf 77777 please help me with something completely unknown";

fs.mkdirSync(OUT, { recursive: true });

function resetAaravChatHistory() {
  const tmp = path.join(os.tmpdir(), `vd-clear-aarav-${process.pid}.py`);
  fs.writeFileSync(
    tmp,
    `
import asyncio
from sqlalchemy import text
from app.database.session import SessionLocal, get_engine, reset_engine

async def main():
    async with SessionLocal() as db:
        await db.execute(text("""
            DELETE FROM messages WHERE conversation_id IN (
              SELECT c.id FROM conversations c
              JOIN users u ON u.id = c.user_id
              WHERE u.demo_key = 'demo-anya'
            )
        """))
        await db.execute(text("""
            DELETE FROM conversations WHERE user_id IN (
              SELECT id FROM users WHERE demo_key = 'demo-anya'
            )
        """))
        await db.commit()
    await get_engine().dispose()
    reset_engine()

asyncio.run(main())
`.trimStart(),
  );
  try {
    execFileSync("uv", ["run", "python", tmp], {
      cwd: BACKEND,
      stdio: "ignore",
      shell: process.platform === "win32",
    });
  } finally {
    try {
      fs.unlinkSync(tmp);
    } catch {
      /* ignore */
    }
  }
}

async function continueAsAarav(page) {
  await page.goto(`${BASE}/chat`);
  await page.getByRole("heading", { name: "VaaniDesk Support" }).waitFor({ timeout: 30_000 });
  const message = page.getByRole("textbox", { name: "Message" });
  if (await message.isVisible().catch(() => false)) {
    const switchBtn = page.getByRole("button", { name: "Switch demo customer" });
    if (await switchBtn.isVisible().catch(() => false)) {
      await switchBtn.click();
      await page.getByRole("button", { name: "Continue as Aarav Sharma" }).waitFor({
        timeout: 10_000,
      });
    }
  }
  const gate = page.getByRole("button", { name: "Continue as Aarav Sharma" });
  if (await gate.isVisible().catch(() => false)) {
    await gate.click();
  }
  await message.waitFor({ state: "visible", timeout: 15_000 });
  await page.getByLabel("Conversation").evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
}

async function sendAndWait(page, text) {
  const input = page.getByRole("textbox", { name: "Message" });
  await input.fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
  await page.getByText("is typing").waitFor({ state: "hidden", timeout: 60_000 }).catch(() => {});
  await page
    .getByLabel("Conversation")
    .getByText("VaaniDesk", { exact: true })
    .last()
    .waitFor({ timeout: 60_000 });
  await page.waitForTimeout(800);
}

async function shot(page, name) {
  const dest = path.join(OUT, name);
  await page.screenshot({ path: dest, fullPage: false, type: "png" });
  console.log("wrote", dest);
  return dest;
}

async function bodyText(page) {
  return page.locator("body").innerText();
}

async function assertCleanCustomer(page, label) {
  const text = await bodyText(page);
  const bad = [];
  for (const pat of [
    /X-Demo-User-Key/i,
    /localhost:\d+/i,
    /Mock STT\/TTS/i,
    /Tool:\s*[a-z_]+/i,
    /idempotency/i,
    /Developer inspector/i,
    /Phase \d/i,
    /Dup User|Pw User|Sess User|Brute User/i,
    /Confidence:\s*0\.\d+/i,
  ]) {
    if (pat.test(text)) bad.push(String(pat));
  }
  if (bad.length) throw new Error(`${label} failed privacy checks: ${bad.join(", ")}`);
}

async function captureEscalation(page) {
  resetAaravChatHistory();
  await continueAsAarav(page);
  await sendAndWait(page, ESCALATION_MESSAGE);
  await page.getByText("Support request created").waitFor({ timeout: 30_000 });
  await page.getByText(/TKT-\d+/).first().waitFor();
  await page.getByText("Support request created").scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  const text = await bodyText(page);
  if (/Based on available policy|Sources/i.test(text)) {
    throw new Error("06 contains unintended RAG/policy answer");
  }
  if (/Tool:\s*transfer_to_human/i.test(text)) {
    throw new Error("06 leaked tool name");
  }
  if (!/not sure I understood/i.test(text)) {
    throw new Error("06 missing uncertainty language");
  }
  if (!/does not connect to a live support agent/i.test(text)) {
    throw new Error("06 missing demo limitation");
  }
  await assertCleanCustomer(page, "06-support-escalation");
  await shot(page, "06-support-escalation.png");
}

async function captureAll() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: VIEWPORT,
    deviceScaleFactor: SCALE,
  });
  const report = { messages: {}, ragSources: null };

  await page.goto(`${BASE}/`);
  await page.getByRole("heading", { name: "VaaniDesk" }).waitFor();
  await page.getByRole("link", { name: "Try the demo" }).waitFor();
  await assertCleanCustomer(page, "01-home");
  await shot(page, "01-home.png");

  resetAaravChatHistory();
  await continueAsAarav(page);
  const hinglish = "mera order VD-10021 kahan hai?";
  await sendAndWait(page, hinglish);
  await page.getByText(/VD-10021/i).last().scrollIntoViewIfNeeded();
  await assertCleanCustomer(page, "02-hinglish-order");
  await shot(page, "02-hinglish-order.png");
  report.messages.hinglish = hinglish;

  resetAaravChatHistory();
  await continueAsAarav(page);
  const orderQ = "where is my order VD-10021";
  await sendAndWait(page, orderQ);
  const orderCard = page.locator("p.font-medium", { hasText: /^Order VD-10021$/ });
  await orderCard.last().waitFor({ timeout: 20_000 });
  await orderCard.last().scrollIntoViewIfNeeded();
  await assertCleanCustomer(page, "03-order-status");
  await shot(page, "03-order-status.png");
  report.messages.orderStatus = orderQ;

  resetAaravChatHistory();
  await continueAsAarav(page);
  const ragQ = "What is the refund policy for a damaged product?";
  await sendAndWait(page, ragQ);
  await page.getByText("Sources").waitFor({ timeout: 30_000 });
  const sources = page.locator("details").filter({ hasText: "Sources" }).first();
  await sources.locator("summary").click();
  await page.waitForTimeout(500);
  const body = await bodyText(page);
  if (!/Damaged Products/i.test(body)) throw new Error("04 missing Damaged Products");
  await page.getByText(ragQ).scrollIntoViewIfNeeded();
  await assertCleanCustomer(page, "04-rag-refund-citations");
  await shot(page, "04-rag-refund-citations.png");
  report.messages.rag = ragQ;
  report.ragSources = await sources.locator("li").allTextContents();

  resetAaravChatHistory();
  await continueAsAarav(page);
  const cancelQ = "please cancel my order VD-10022";
  await sendAndWait(page, cancelQ);
  await page.getByLabel("Confirmation required").waitFor({ timeout: 30_000 });
  await page.getByLabel("Confirmation required").scrollIntoViewIfNeeded();
  await assertCleanCustomer(page, "05-cancellation-confirmation");
  await shot(page, "05-cancellation-confirmation.png");
  report.messages.cancel = cancelQ;
  await page.getByRole("button", { name: "Keep order" }).click();
  await page.waitForTimeout(800);

  await captureEscalation(page);
  report.messages.escalation = ESCALATION_MESSAGE;

  await page.goto(`${BASE}/admin/observability`);
  await page.getByRole("heading", { name: "Observability" }).waitFor({ timeout: 30_000 });
  await page.getByText("System Overview").waitFor({ timeout: 30_000 });
  await page.waitForTimeout(800);
  await shot(page, "07-observability.png");

  await page.goto(`${BASE}/admin/evaluations`);
  await page.getByRole("heading", { name: "Evaluations" }).waitFor({ timeout: 30_000 });
  await page.waitForTimeout(1000);
  await shot(page, "08-evaluations.png");

  await browser.close();
  console.log(JSON.stringify(report, null, 2));
}

async function main() {
  const mode = process.argv[2] ?? "all";
  if (mode === "06") {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({
      viewport: VIEWPORT,
      deviceScaleFactor: SCALE,
    });
    await captureEscalation(page);
    await browser.close();
    console.log("06 message:", ESCALATION_MESSAGE);
    return;
  }
  if (mode === "all") {
    await captureAll();
    return;
  }
  console.error("Supported modes: all | 06");
  process.exit(2);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
