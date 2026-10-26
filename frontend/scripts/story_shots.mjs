// Screenshots of the review example (final report and deck): node scripts/story_shots.mjs <outdir>
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const out = process.argv[2] ?? "story-shots";
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
await page.fill("#prompt", PROMPT);
await page.click('button[aria-controls="context"]');
await page.fill("#context", REVIEW);
await page.waitForTimeout(1500);
await page.screenshot({ path: `${out}/story_input.png` });
await page.click('[data-testid="optimize"]');
await page.waitForSelector('[data-testid="render"]', { timeout: 120000 });
await page.waitForTimeout(1500);
await page.screenshot({ path: `${out}/story_optimize_full.png`, fullPage: true });
for (const id of ["stage-a", "stage-b", "stage-c", "confirm-category", "render"]) {
  const el = page.locator(`[data-testid="${id}"]`).first();
  if (await el.count()) await el.screenshot({ path: `${out}/story_${id}.png` });
}
await page.click('a[href="/compare"]');
await page.waitForSelector("#cmp-model");
await page.click("#cmp-model");
await page.getByRole("option", { name: /Groq/ }).first().click();
await page.click('[data-testid="run-compare"]');
await page.waitForSelector('[data-testid="compare-result"]', { timeout: 180000 });
await page.waitForTimeout(7000);  // let the "Comparison finished" toast fade
await page.screenshot({ path: `${out}/story_compare_full.png`, fullPage: true });
await page.locator('[data-testid="compare-result"]').screenshot({ path: `${out}/story_compare_result.png` });
await browser.close();
console.log("done");
