// Reports horizontal overflow at phone width for every page: node scripts/overflow.mjs
import { chromium } from "@playwright/test";
const base = process.env.BASE ?? "http://127.0.0.1:8765";
const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await ctx.addInitScript(() => localStorage.setItem("po-tour-seen", "1"));
for (const path of ["/", "/compare", "/suite", "/results", "/how", "/history", "/image", "/status"]) {
  const p = await ctx.newPage();
  await p.goto(base + path); await p.waitForLoadState("networkidle"); await p.waitForTimeout(500);
  if (path === "/") { await p.click('[data-example="permutations"]'); await p.waitForSelector('[data-testid="render"]'); await p.waitForTimeout(800); }
  const r = await p.evaluate(() => {
    const W = document.documentElement.clientWidth;
    const bad = [...document.querySelectorAll("body *")].filter((e) => { const b = e.getBoundingClientRect(); return b.right > W + 1 && b.width > 0; })
      .filter((e) => !e.closest(".overflow-x-auto, .overflow-auto, pre"))
      .slice(0, 6).map((e) => `${e.tagName.toLowerCase()}.${String(e.className).slice(0, 60)} right=${Math.round(e.getBoundingClientRect().right)}`);
    return { sw: document.documentElement.scrollWidth, W, bad };
  });
  console.log(path, r.sw > r.W ? `OVERFLOW ${r.sw}>${r.W}` : "ok", r.bad.join(" | "));
  await p.close();
}
await browser.close();
