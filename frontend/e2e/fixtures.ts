import { test as base, expect } from "@playwright/test";

/** Every test starts as a returning visitor (no tour) unless it asks for the first visit. */
export const test = base.extend<{ firstVisit: boolean }>({
  firstVisit: [false, { option: true }],
  page: async ({ page, firstVisit }, use) => {
    if (!firstVisit) await page.addInitScript(() => { if (!sessionStorage.getItem("e2e")) { localStorage.setItem("po-tour-seen", "1"); sessionStorage.setItem("e2e", "1"); } });
    await use(page);
  },
});
export { expect };
