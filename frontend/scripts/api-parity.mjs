// Runs the demo prompts through the new UI, captures every /api/optimize request and response, replays the same
// requests against a reference server (e.g. main) and checks the JSON is identical (prompt_id aside: it is the
// database row id). Usage: BASE=http://127.0.0.1:8765 REF=http://127.0.0.1:8770 node scripts/api-parity.mjs
import { chromium } from "@playwright/test";
import { isDeepStrictEqual } from "node:util";

const BASE = process.env.BASE ?? "http://127.0.0.1:8765";
const REF = process.env.REF ?? "http://127.0.0.1:8770";
const browser = await chromium.launch({ channel: process.env.PW_CHANNEL ?? "chrome" });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await ctx.addInitScript(() => localStorage.setItem("po-tour-seen", "1"));
const page = await ctx.newPage();
const captured = [];
const isOptimize = (r) => r.url().endsWith("/api/optimize") && r.request().method() === "POST";
/** Do `action`, wait for the /api/optimize response it triggers, and keep request + response. */
async function capture(action) {
  const [r] = await Promise.all([page.waitForResponse(isOptimize, { timeout: 90000 }), action()]);
  captured.push({ body: r.request().postDataJSON(), status: r.status(), json: await r.json() });
}

const strip = (o) => { const c = structuredClone(o); delete c.prompt_id; return c; };

// 1. Every example in the gallery (the demo script's prompts are among them).
await page.goto(BASE + "/");
const ids = await page.$$eval("[data-example]", (els) => els.map((e) => e.getAttribute("data-example")));
for (const id of ids) {
  await page.goto(BASE + "/");
  await capture(() => page.click(`[data-example="${id}"]`));
}
// 2. The "confirm category" path (a user-chosen category overrides Stage A).
await page.goto(BASE + "/");
await capture(() => page.click('[data-example="attachment"]'));
await capture(() => page.getByTestId("confirm-category").getByRole("button", { name: "Summarise" }).click());
// 3. Image mode with a clicked suggestion, and each target LLM for one prompt.
await page.goto(BASE + "/image");
await page.fill("#img-prompt", "a cozy reading nook, phone wallpaper, no people");
await page.getByRole("radio", { name: "Stable Diff." }).click();
await capture(() => page.click('[data-testid="optimize-image"]'));
await capture(() => page.locator('[data-testid="suggestions"] button').first().click());
// 4. Typed prompts: each target LLM, a pasted text, an attachment and a chosen category, set through the form.
await page.evaluate(() => localStorage.removeItem("po-draft"));
for (const [t, cat, att] of [["GPT", "Auto-detect", "No attachment"], ["Gemini", "Extract information", "PDF"], ["Claude", "Coding", "Code file"]]) {
  await page.goto(BASE + "/");
  await page.fill("#prompt", "Could you please kindly extract all the email addresses and dates mentioned in this text?");
  await page.getByRole("radio", { name: t }).click();
  await page.click("#category"); await page.getByRole("option", { name: cat }).click();
  await page.click("#attachment"); await page.getByRole("option", { name: att }).click();
  await capture(() => page.click('[data-testid="optimize"]'));
}
await page.goto(BASE + "/");
await page.fill("#prompt", "which company bought hackpad according to that text?");
await page.getByRole("button", { name: /Pasted text/ }).click();
await page.fill("#context", "In April 2014, Hackpad was acquired by Dropbox.");
await page.click("#category"); await page.getByRole("option", { name: "Auto-detect" }).click();
await page.click("#attachment"); await page.getByRole("option", { name: "No attachment" }).click();
await capture(() => page.keyboard.press("Control+Enter"));
await browser.close();

let same = 0;
for (const c of captured) {
  const r = await fetch(REF + "/api/optimize", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(c.body) });
  const ref = await r.json();
  const ok = r.status === c.status && isDeepStrictEqual(strip(ref), strip(c.json));
  same += ok ? 1 : 0;
  console.log(ok ? "IDENTICAL" : "DIFFERENT", `${c.body.category}/${c.body.target}`, JSON.stringify(c.body.prompt).slice(0, 60),
    c.body.attachment_type !== "none" ? `+${c.body.attachment_type}` : "", c.body.accepted_suggestions?.length ? `+${c.body.accepted_suggestions}` : "");
  if (!ok) console.log("   ui-v2:", JSON.stringify(strip(c.json)).slice(0, 300), "\n   ref:  ", JSON.stringify(strip(ref)).slice(0, 300));
}
console.log(`${same}/${captured.length} identical`);
process.exit(same === captured.length && captured.length > 0 ? 0 : 1);
