// Screenshots of the simple app (/) with the review example (final report): node scripts/simple_shots.mjs <outdir>
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const out = process.argv[2] ?? "simple-shots";
const base = process.env.BASE ?? "http://127.0.0.1:8765";
mkdirSync(out, { recursive: true });
const PROMPT = "hey can you just tell me if this review is good or bad";
const REVIEW = "The battery lasts two days and the camera is great, but the phone heats up while gaming.";

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL ?? "chrome" });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light", reducedMotion: "reduce" });
await ctx.addInitScript(() => { localStorage.setItem("po-tour-seen", "1"); localStorage.setItem("po-theme", "light"); });
const page = await ctx.newPage();

await page.goto(base + "/");
await page.waitForLoadState("networkidle");
await page.screenshot({ path: `${out}/simple_home.png` });
await page.getByTestId("simple-prompt").fill(PROMPT);
await page.getByRole("button", { name: /Add the text it's about/ }).click();
await page.fill("#context", REVIEW);
await page.screenshot({ path: `${out}/simple_input.png` });
await page.getByTestId("simple-improve").click();
await page.waitForSelector('[data-testid="simple-result"]', { timeout: 120000 });
await page.waitForTimeout(1000);
await page.locator('[data-testid="simple-result"]').screenshot({ path: `${out}/simple_result.png` });

await page.getByTestId("simple-to-usage").click();
await page.waitForURL(/\/usage$/);
const usage = page.getByTestId("usage-result");
await usage.waitFor({ timeout: 200000 });
await page.waitForFunction(() => document.querySelector('[data-testid="usage-result"]')?.textContent?.includes("What the AI answered"),
  null, { timeout: 200000 });
await page.waitForTimeout(7000);  // let any toast fade
await page.addStyleTag({ content: "header { position: static !important; }" });  // keep the sticky bar off the result
await usage.screenshot({ path: `${out}/simple_usage.png` });

await page.getByRole("link", { name: "History" }).first().click();
await page.waitForLoadState("networkidle");
await page.waitForTimeout(800);
await page.screenshot({ path: `${out}/simple_history.png`, clip: { x: 0, y: 0, width: 1440, height: 600 } });
await browser.close();
console.log("done");
