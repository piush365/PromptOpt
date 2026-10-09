import { test, expect } from "./fixtures";

test.describe("Optimize", () => {
  test("example gallery → optimize shows every stage", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("optimize-empty")).toBeVisible();
    await page.locator('[data-example="permutations"]').click();

    const a = page.getByTestId("stage-a");
    await expect(a).toContainText("Coding");
    await expect(a).toContainText("confident");
    await expect(page.getByTestId("issues")).toContainText("No output format");

    const rules = page.getByTestId("rules");
    await expect(rules).toContainText("B05");
    await expect(rules).toContainText("Name the programming language");
    await expect(rules.locator("ins").filter({ hasText: "Use Python." })).toHaveCount(1);

    await expect(page.getByTestId("stage-c")).toContainText("not needed");
    await expect(page.getByTestId("rendering-gpt")).toContainText("### Task");
    await page.getByRole("tab", { name: /Claude/ }).click();
    await expect(page.getByTestId("rendering-claude")).toContainText("<task>");
    await expect(page.getByTestId("render")).toContainText("validated");
  });

  test("hovering an issue highlights the words in the prompt", async ({ page }) => {
    await page.goto("/");
    await page.locator('[data-example="summarize"]').click();
    await expect(page.getByTestId("issues")).toBeVisible();
    await page.getByTestId("issues").getByRole("button", { name: /Filler/ }).hover();
    await expect(page.locator(".mirror mark").first()).toHaveText(/hey|can you|just|for me/i);
  });

  test("Ctrl+Enter optimizes, undo restores the previous input, live counter updates", async ({ page }) => {
    await page.goto("/");
    const box = page.locator("#prompt");
    await box.fill("summarize this article in 3 bullet points");
    await expect(page.getByTestId("live-tokens")).toContainText(/\d+\s*input tokens for GPT/);
    await box.press("Control+Enter");
    await expect(page.getByTestId("render")).toBeVisible();
    await page.getByRole("radio", { name: "Claude" }).click();
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(page.getByRole("radio", { name: "GPT" })).toHaveAttribute("data-state", "on");
  });

  test("an unsure category asks the user to confirm", async ({ page }) => {
    await page.goto("/");
    await page.locator('[data-example="attachment"]').click();
    const ask = page.getByTestId("confirm-category");
    await expect(ask).toBeVisible();
    await ask.getByRole("button", { name: "Summarise" }).click();
    await expect(page.getByTestId("stage-a")).toContainText("your choice");
  });
});

test("compare runs both prompts on a real model", async ({ page, request }) => {
  const models = await (await request.get("/api/compare/models")).json();
  test.skip(!models.default, "no answering model configured (needs GROQ_API_KEY or CEREBRAS_API_KEY)");
  test.setTimeout(240_000);
  await page.goto("/");
  await page.locator('[data-example="permutations"]').click();
  await page.getByTestId("compare-this").click();
  await expect(page).toHaveURL(/\/compare$/);
  await expect(page.locator("#cmp-prompt")).toHaveValue("write code to get all permutations of a string");
  await page.getByTestId("run-compare").click();
  const result = page.getByTestId("compare-result");
  await expect(result).toBeVisible({ timeout: 200_000 });
  await expect(result).toContainText("Who answered");
  await expect(result).toContainText("Answer to the optimized prompt");
  await expect(page.getByRole("table").last()).toContainText("permutations");
});

test("test suite: summary, filter and case view", async ({ page }) => {
  await page.goto("/suite");
  await expect(page.getByTestId("suite-summary")).toContainText("%");
  await page.getByRole("radio", { name: "Fixed" }).click();
  const cards = page.getByTestId("case-grid").locator("button");
  await expect(cards.first()).toContainText("Fixed");
  await cards.first().click();
  const view = page.getByTestId("case-view");
  await expect(view).toContainText("Gold answer");
  await expect(view).toContainText("Answer to the optimized prompt");
  await expect(view).toContainText("correct");
  await page.keyboard.press("Escape");
  await expect(view).toBeHidden();
});

test("history: listed, searchable, viewable, deletable", async ({ page }) => {
  await page.goto("/");
  await page.locator('[data-example="classify"]').click();
  await expect(page.getByTestId("render")).toBeVisible();
  await page.goto("/history");
  const list = page.getByTestId("history-list");
  await expect(list).toContainText("classify these reviews");
  await page.getByTestId("history-search").fill("no-such-prompt-xyz");
  await expect(page.getByText("Nothing matches")).toBeVisible();
  await page.getByTestId("history-search").fill("reviews");
  await expect(list).toContainText("classify these reviews");
  await list.getByRole("button", { name: "View" }).first().click();
  await expect(page.getByRole("dialog")).toContainText("What changed");
  await page.keyboard.press("Escape");
  const before = await list.locator("li[data-history]").count();
  await list.getByRole("button", { name: "Delete" }).first().click();
  await list.getByRole("button", { name: "Delete for good" }).click();
  await expect(list.locator("li[data-history]")).toHaveCount(before - 1);
});

test("theme toggle switches and persists", async ({ page }) => {
  await page.goto("/results");
  const html = page.locator("html");
  const wasDark = (await html.getAttribute("class"))?.includes("dark") ?? false;
  await page.getByTestId("theme-toggle").click();
  await expect(html).toHaveClass(wasDark ? /^(?!.*dark)/ : /dark/);
  await page.reload();
  await expect(html).toHaveClass(wasDark ? /^(?!.*dark)/ : /dark/);
  await expect(page.getByTestId("token-hero")).toContainText("%");
});

test("image mode: suggestions are clickable and per-model renderings", async ({ page }) => {
  await page.goto("/image");
  await page.locator("#img-prompt").fill("oil painting of a sailboat in a storm");
  await page.getByTestId("optimize-image").click();
  const sugg = page.getByTestId("suggestions");
  await expect(sugg).toBeVisible();
  const chip = sugg.getByRole("button").first();
  const label = (await chip.textContent())!.trim();
  await chip.click();
  await expect(page.getByLabel("Added suggestions")).toContainText(label);
  await page.getByRole("tab", { name: "Stable Diffusion" }).click();
  await expect(page.getByTestId("image-rendering-stable_diffusion")).toContainText(/oil painting/i);
});

test("gallery image example opens Image mode and runs it there", async ({ page }) => {
  const posted: string[] = [];
  page.on("request", (r) => { if (r.url().endsWith("/api/optimize")) posted.push(r.postDataJSON().category); });
  await page.goto("/");
  await page.locator('[data-example="image"]').click();
  await expect(page).toHaveURL(/\/image$/);
  await expect(page.getByTestId("image-result")).toBeVisible();
  expect(posted).toEqual(["image_generation"]);
});

test.describe("first visit", () => {
  test.use({ firstVisit: true });
  test("tour shows once and can be skipped; ? opens shortcuts", async ({ page }) => {
    await page.goto("/");
    const tour = page.getByTestId("tour");
    await expect(tour).toContainText("Welcome to PromptOpt");
    await tour.getByRole("button", { name: "Next" }).click();
    await expect(tour).toContainText("Type your prompt");
    await page.keyboard.press("Escape");
    await expect(tour).toBeHidden();
    await page.reload();
    await expect(tour).toBeHidden();
    await page.keyboard.press("?");
    await expect(page.getByRole("dialog")).toContainText("Keyboard shortcuts");
  });
});

test("every page loads without console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  for (const path of ["/", "/compare", "/suite", "/results", "/how", "/history", "/image", "/status", "/classic"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
  }
  expect(errors).toEqual([]);
});
