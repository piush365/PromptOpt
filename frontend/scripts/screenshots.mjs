// Screenshots of every page at 1440 and 390 px, light and dark: node scripts/screenshots.mjs <outdir> [page...]
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const out = process.argv[2] ?? "screenshots";
const only = process.argv.slice(3);
const base = process.env.BASE ?? "http://127.0.0.1:8765";
mkdirSync(out, { recursive: true });

const PAGES = [
  { name: "optimize", path: "/", prep: async (p) => {
      await p.click('[data-example="permutations"]');
      await p.waitForSelector('[data-testid="render"]', { timeout: 60000 });
      await p.waitForTimeout(1500);
    } },
  { name: "optimize-empty", path: "/" },
  { name: "compare", path: "/compare" },
  { name: "suite", path: "/suite", prep: async (p) => { await p.waitForSelector('[data-testid="case-grid"]'); } },
  { name: "suite-case", path: "/suite", prep: async (p) => {
      await p.click('[data-case="cqa-01"]'); await p.waitForSelector('[data-testid="case-view"]'); await p.waitForTimeout(400);
    }, viewportOnly: true },
  { name: "results", path: "/results", prep: async (p) => { await p.waitForSelector('[data-testid="token-hero"]'); await p.waitForTimeout(500); } },
  { name: "how", path: "/how" },
  { name: "history", path: "/history", prep: async (p) => { await p.waitForSelector('[data-testid="history-list"]'); } },
  { name: "image", path: "/image", prep: async (p) => {
      await p.fill("#img-prompt", "oil painting of a sailboat in a storm");
      await p.click('[data-testid="optimize-image"]'); await p.waitForSelector('[data-testid="image-result"]');
    } },
  { name: "status", path: "/status", prep: async (p) => { await p.waitForSelector('[data-testid="providers"]'); } },
];

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL ?? "chrome" });
for (const width of [1440, 390]) {
  for (const theme of ["light", "dark"]) {
    const ctx = await browser.newContext({ viewport: { width, height: width > 500 ? 900 : 844 }, colorScheme: theme,
      deviceScaleFactor: width > 500 ? 1 : 2, reducedMotion: "reduce" });
    await ctx.addInitScript((t) => { localStorage.setItem("po-tour-seen", "1"); localStorage.setItem("po-theme", t); localStorage.removeItem("po-draft"); }, theme);
    for (const pg of PAGES) {
      if (only.length && !only.includes(pg.name)) continue;
      const page = await ctx.newPage();
      await page.goto(base + pg.path);
      await page.waitForLoadState("networkidle");
      if (pg.prep) await pg.prep(page);
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${out}/${pg.name}-${width}-${theme}.png`, fullPage: !pg.viewportOnly });
      await page.close();
    }
    await ctx.close();
  }
}
await browser.close();
console.log("done");
