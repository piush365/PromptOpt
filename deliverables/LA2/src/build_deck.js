// LA-2 deck for PromptOpt. Numbers: evaluation/FINAL_RESULTS.md, evaluation/correctness_suite/RESULTS.md, git, test runs 14 Oct 2026.
const pptxgen = require("pptxgenjs");
const path = require("path");
const { applyTheme } = require("/home/piush/.claude/skills/synced/b1877002-e2e9-41e8-8443-164d37f7962e_32623b44-b694-4da0-9c72-32d2ea9ff10d/pptx/scripts/apply_theme.js");
const FIG = path.join(__dirname, "..", "fig");
const OUT = process.argv[2];

const THEME = { name: "PromptOpt Forest", headFontFace: "Arial", bodyFontFace: "Calibri",
  colors: { dk1: "1B2B22", lt1: "FFFFFF", dk2: "2F6B4F", lt2: "EAF4EE", accent1: "2F6B4F", accent2: "D9822B",
            accent3: "6FA287", accent4: "1F4E79", accent5: "B42318", accent6: "7A8580", hlink: "1F4E79", folHlink: "6FA287" } };
const HEX = THEME.colors;
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "PromptOpt LA-2"; pres.author = "Piush Gogi, Nirzara Manade, Siddhi Bolaikar";
const C = pres.SchemeColor;
const logo = path.join(FIG, "wce_logo.png");

pres.defineSlideMaster({ title: "CONTENT", background: { color: HEX.lt2 },
  objects: [
    { image: { path: logo, x: 0.35, y: 0.22, w: 0.78, h: 0.78 } },
    { placeholder: { options: { name: "title", type: "title", x: 1.3, y: 0.25, w: 10.9, h: 0.8, fontFace: "Arial", fontSize: 30, bold: true,
        color: C.text2, align: "left", valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "PromptOpt · Mini Project-I (7CS345) · LA-2", options: { x: 0.45, y: 7.05, w: 6, h: 0.3, fontSize: 10, color: C.accent6, margin: 0 } } },
  ],
  slideNumber: { x: 12.4, y: 7.02, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent6 } });
pres.defineSlideMaster({ title: "DARK", background: { color: HEX.dk2 }, objects: [] });

let n = 0;
function content(title, section, notes) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  s.addNotes(notes); n++; return s;
}
const card = (s, x, y, w, h, fill = C.background1) =>
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: HEX.accent3, width: 0.75 },
    shadow: { type: "outer", color: "9DB8A8", opacity: 0.35, blur: 4, offset: 2, angle: 90 } });
const txt = (s, text, o) => s.addText(text, Object.assign({ isTextBox: true, fontSize: 15, color: C.text1, valign: "top", margin: 0.05 }, o));
function stat(s, x, y, w, big, label, color = C.text2, size = 40) {
  card(s, x, y, w, 1.75);
  txt(s, big, { x: x + 0.15, y: y + 0.15, w: w - 0.3, h: 0.95, fontSize: size, bold: true, color, fontFace: "Arial", valign: "middle", align: "center" });
  txt(s, label, { x: x + 0.15, y: y + 1.08, w: w - 0.3, h: 0.6, fontSize: 13, color: C.text1, align: "center" });
}
function bullets(s, items, o) {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    Object.assign({ isTextBox: true, fontSize: 16, color: C.text1, valign: "top", paraSpaceAfter: 8, margin: 0.08 }, o));
}
const P = "Presenter: ";

// 1 Title ---------------------------------------------------------------------------------------------
pres.addSection({ title: "Opening" });
{
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Opening" }); n++;
  s.addShape(pres.shapes.OVAL, { x: 0.55, y: 0.45, w: 1.5, h: 1.5, fill: { color: C.background1 }, line: { color: C.background1 } });
  s.addImage({ path: logo, x: 0.67, y: 0.57, w: 1.26, h: 1.26 });
  txt(s, "Walchand College of Engineering, Sangli", { x: 2.3, y: 0.55, w: 10.4, h: 0.55, fontSize: 26, bold: true, color: C.background1, fontFace: "Arial" });
  txt(s, "(Government Aided Autonomous Institute) · Department of Computer Science and Engineering\nTY CSE · Mini Project-I (7CS345) · LA-2 Evaluation (Release 2), 2026-27",
      { x: 2.3, y: 1.1, w: 10.4, h: 0.85, fontSize: 15, color: "D5E8DC" });
  txt(s, "PromptOpt", { x: 0.6, y: 2.45, w: 12, h: 1.0, fontSize: 54, bold: true, color: C.background1, fontFace: "Arial" });
  txt(s, "Token-efficient prompt optimization for LLMs: rewrite vague prompts, explain every change, and measure that it helps",
      { x: 0.6, y: 3.45, w: 11.5, h: 0.9, fontSize: 20, color: "D5E8DC" });
  card(s, 0.6, 4.75, 6.3, 1.95, "3A7A5C");
  txt(s, "Team", { x: 0.85, y: 4.9, w: 3, h: 0.4, fontSize: 14, bold: true, color: "F2C894" });
  txt(s, "Piush U. Gogi · 255200005\nNirzara A. Manade · 255200006\nSiddhi S. Bolaikar · 255200008",
      { x: 0.85, y: 5.3, w: 5.9, h: 1.3, fontSize: 17, color: C.background1, paraSpaceAfter: 4 });
  card(s, 7.2, 4.75, 5.5, 1.95, "3A7A5C");
  txt(s, "Guide", { x: 7.45, y: 4.9, w: 3, h: 0.4, fontSize: 14, bold: true, color: "F2C894" });
  txt(s, "Prof. A. S. Pawar", { x: 7.45, y: 5.3, w: 5, h: 0.5, fontSize: 20, bold: true, color: C.background1 });
  txt(s, "15 October 2026", { x: 7.45, y: 5.85, w: 5, h: 0.4, fontSize: 15, color: "D5E8DC" });
  s.addNotes(P + "Piush. Greet the panel, introduce the team and the guide. One line: PromptOpt rewrites a vague prompt into a clear, model-specific one, shows every change, and we measured that it saves tokens. Today: Release 2 in the order of the LA-2 checklist, then a live demo.");
}

// 2 At a glance -------------------------------------------------------------------------------------
{
  const s = content("Release 2 at a glance", "Opening",
    P + "Piush. Four numbers to remember. -39.2% total tokens on 482 held-out test prompts (95% CI 35.9-42.5%). 95% of optimized prompts state an output format, vs 3.1% before. 798 automated tests plus 13 browser tests, all passing as of yesterday. Correctness: 42 of 50 vs 37 of 50, with 29.6% fewer tokens. Then name the order of the talk: modules, transactions, testing, prototype, Git, challenges, plans, demo.");
  stat(s, 0.6, 1.4, 2.9, "-39.2%", "total tokens, 482 test prompts");
  stat(s, 3.75, 1.4, 2.9, "95.0%", "state an output format (was 3.1%)");
  stat(s, 6.9, 1.4, 2.9, "798", "pytest tests passing + 13/13 UI tests");
  stat(s, 10.05, 1.4, 2.7, "42/50", "correct vs 37/50 vague (correctness suite)");
  card(s, 0.6, 3.5, 12.15, 3.25);
  txt(s, "What this review covers", { x: 0.85, y: 3.65, w: 6, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
  const items = ["1  Core modules: Stage A, B, C, IR + renderers, image mode, attachments, Compare, web app, database",
    "2  Transaction flow: submit → optimize → store (one commit) → Compare → History → retention",
    "3  Unit testing · 4  Integration & system testing · 5  Working prototype",
    "6  Test cases with real results, including honest failures",
    "7  Git / GitHub · 8  Challenges and fixes · 9  Plans · Live demo"];
  txt(s, items.join("\n"), { x: 0.85, y: 4.15, w: 11.6, h: 2.5, fontSize: 16, paraSpaceAfter: 6 });
}

// 3 Architecture -------------------------------------------------------------------------------------
pres.addSection({ title: "Core modules" });
{
  const s = content("System architecture", "Core modules",
    P + "Piush. Walk the diagram left to right: the React UI sends prompt, target LLM, category and attachment type. Stage A detects what is missing, Stage B fixes it with rules and builds the IR. Only if the category or a reference is still unresolved (6.4% of test prompts) does Stage C, the LoRA model, run. Renderers write the same IR for Claude, GPT or Gemini. Compare runs both prompts on a real model. Everything is stored through one repository module. Image mode is a separate path the user picks.");
  s.addImage({ path: path.join(FIG, "01_system_architecture.png"), x: 0.5, y: 1.45, w: 12.3, h: 12.3 * 338 / 1568 });
  const cols = [["Stage A", "spaCy + regex + sentence-embedding classifier: category, missing format/constraints, filler, ambiguous refs"],
    ["Stage B", "15 deterministic rules B01-B15, every change logged; category rules only at confidence ≥ 0.6"],
    ["Stage C", "Qwen2.5-0.5B + LoRA, called only for unresolved fields; validated, else Stage B kept"],
    ["Output", "IR rendered per target LLM with token counts; Compare, History, 30-day retention"]];
  cols.forEach(([h, b], i) => { const x = 0.5 + i * 3.1; card(s, x, 4.45, 2.95, 2.3);
    txt(s, h, { x: x + 0.15, y: 4.55, w: 2.65, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
    txt(s, b, { x: x + 0.15, y: 5.0, w: 2.65, h: 1.7, fontSize: 14 }); });
}

// 4 Stage A + B -------------------------------------------------------------------------------------
{
  const s = content("Stage A detects, Stage B fixes with 15 rules", "Core modules",
    P + "Piush. Stage A on the test split: 74.7% category accuracy; coding and classification are near perfect, the closed QA / extraction / summarization group is hard on degraded prompts. Stage B: each rule is a separate unit-tested function. Example: 'write code to get all permutations of a string' gets B07 tidy, B05 'Use Python', B03 'Return only the code, in a single code block'. Result: an output format is stated in 95% of prompts instead of 3.1%. Below 0.6 confidence, B08 handles the text group without guessing the category.");
  card(s, 0.5, 1.4, 5.2, 5.4);
  txt(s, "Stage A · feature detection", { x: 0.7, y: 1.5, w: 4.8, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
  bullets(s, ["Task category + confidence (embedding classifier, keyword fallback)", "A02 missing output format", "A03 missing length / tone / audience / language", "A04 filler and repetition", "A05 ambiguous reference (\"summarize this\")"], { x: 0.7, y: 2.0, w: 4.8, h: 2.9, fontSize: 15 });
  txt(s, "74.7%", { x: 0.7, y: 5.0, w: 2.2, h: 0.9, fontSize: 40, bold: true, color: C.text2, fontFace: "Arial" });
  txt(s, "category accuracy on 482 test prompts (coding F1 0.98, classification 0.94)", { x: 2.9, y: 5.05, w: 2.7, h: 1.4, fontSize: 13 });
  const rules = [["B01", "Remove filler"], ["B02", "Remove duplicates"], ["B03", "Output format"], ["B04", "Length limit"], ["B05", "Programming language"],
    ["B06", "Label set"], ["B07", "Structure / data block"], ["B08", "Group fallback"], ["B09-B15", "Attachment modifiers"]];
  txt(s, "Stage B · rules (each a unit-tested function)", { x: 6.0, y: 1.45, w: 6.8, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
  rules.forEach(([c, t], i) => { const x = 6.0 + (i % 3) * 2.3, y = 2.0 + Math.floor(i / 3) * 0.95;
    card(s, x, y, 2.15, 0.8); txt(s, [{ text: c + "  ", options: { bold: true, color: C.text2 } }, { text: t }], { x: x + 0.1, y: y + 0.08, w: 1.95, h: 0.65, fontSize: 13, valign: "middle" }); });
  card(s, 6.0, 4.95, 6.75, 1.85, C.background1);
  txt(s, "3.1% → 95.0%", { x: 6.2, y: 5.05, w: 3.6, h: 0.9, fontSize: 36, bold: true, color: C.accent2, fontFace: "Arial" });
  txt(s, "of test prompts state an output format after Stage B; 6.4% (31 of 482) are routed to Stage C", { x: 9.75, y: 5.1, w: 2.9, h: 1.6, fontSize: 13 });
}

// 5 Stage C -----------------------------------------------------------------------------------------
{
  const s = content("Stage C: a small LoRA model, only where rules stop", "Core modules",
    P + "Piush. Stage C is Qwen2.5-0.5B-Instruct with a LoRA adapter, trained on our 4 GB laptop GPU in 51 minutes. It runs only when Stage B leaves the category or an ambiguous reference unresolved. It must answer with JSON containing exactly the requested keys; we check it with Stage A's own detectors and keep Stage B's result if it fails. Without fine-tuning only 5% of answers pass; with LoRA 98.2%. On routed prompts the format is stated in 90.3% instead of 22.6%. Forcing every prompt through Stage C hurts task intent (0.886 to 0.769), so it stays routed-only. Median 0.74 s on GPU.");
  s.addImage({ path: path.join(FIG, "04_b_to_c_contract.png"), x: 0.5, y: 1.35, w: 6.1, h: 6.1 * 928 / 1568 });
  stat(s, 6.95, 1.4, 2.8, "5% → 98%", "answers pass validation: base vs LoRA", C.text2, 30);
  stat(s, 9.95, 1.4, 2.8, "22.6 → 90.3%", "format stated on routed prompts", C.text2, 28);
  stat(s, 6.95, 3.35, 2.8, "0.74 s", "median per call, RTX 3050 (CPU 4.55 s)");
  stat(s, 9.95, 3.35, 2.8, "6.4%", "of test prompts routed to Stage C");
  card(s, 6.95, 5.3, 5.8, 1.5);
  txt(s, "Forced on every prompt, Stage C lowers task intent (0.886 → 0.769), so it stays a fallback. Its category is only a suggestion: the UI asks the user.",
      { x: 7.1, y: 5.38, w: 5.5, h: 1.35, fontSize: 14 });
}

// 6 IR, renderers, attachments, image ----------------------------------------------------------------
{
  const s = content("IR, renderers, attachments and image mode", "Core modules",
    P + "Nirzara. One intermediate representation, three layouts. Claude gets XML tags with context first, GPT gets ### sections, Gemini gets plain labels with the instruction first; tests parse every rendering back to prove no field is lost. GPT tokens are exact with tiktoken, Claude and Gemini approximate and labelled. Attachments are modifiers: B09-B15, one rule per file type, 30 of 30 hand-made prompts correct. Image mode v2 keeps the user's words and offers missing attributes as suggestions; v1, which inserted defaults, made images worse.");
  const r = [["Claude", "<task>Write code to get all\npermutations of a string.</task>\n<constraints>- Use Python.\n</constraints>\n<output_format>Return only\nthe code ...</output_format>"],
    ["GPT", "### Task\nWrite code to get all\npermutations of a string.\n### Constraints\n- Use Python.\n### Output format\nReturn only the code ..."],
    ["Gemini", "Task: Write code to get all\npermutations of a string.\nConstraints: Use Python.\nOutput format: Return only\nthe code ..."]];
  r.forEach(([h, code], i) => { const x = 0.5 + i * 2.75; card(s, x, 1.4, 2.6, 3.4);
    txt(s, h, { x: x + 0.12, y: 1.48, w: 2.3, h: 0.4, fontSize: 17, bold: true, color: C.text2 });
    txt(s, code, { x: x + 0.12, y: 1.92, w: 2.38, h: 2.8, fontSize: 11, fontFace: "Courier New" }); });
  txt(s, "Same content, layout per model · every rendering parsed back in the tests", { x: 0.5, y: 4.9, w: 8.1, h: 0.4, fontSize: 14, italic: true, color: C.text2 });
  card(s, 0.5, 5.4, 8.1, 1.4);
  txt(s, [{ text: "Attachments  ", options: { bold: true, color: C.text2 } }, { text: "B09-B15: image, PDF, PPTX, DOCX, spreadsheet, code, other; fire only with an attachment · " },
          { text: "30/30", options: { bold: true, color: C.accent2 } }, { text: " hand-made prompts correct" }], { x: 0.65, y: 5.5, w: 7.8, h: 1.2, fontSize: 15, valign: "middle" });
  card(s, 8.9, 1.4, 3.9, 5.4);
  txt(s, "Image mode (separate, user-selected)", { x: 9.05, y: 1.5, w: 3.6, h: 0.75, fontSize: 17, bold: true, color: C.text2 });
  txt(s, "Held-out CLIP vs the user's prompt (30 prompts)", { x: 9.05, y: 2.3, w: 3.6, h: 0.6, fontSize: 13 });
  const rows = [["original", "33.08"], ["v1 defaults", "30.78 (worse, p=0.043)"], ["v2 suggestions", "32.77 (no sig. harm)"]];
  rows.forEach(([a, b], i) => { txt(s, [{ text: a + "\n", options: { bold: true } }, { text: b }], { x: 9.05, y: 2.95 + i * 0.95, w: 3.6, h: 0.9, fontSize: 14 }); });
  txt(s, "Style kept in 12/12 styled prompts with v2", { x: 9.05, y: 5.9, w: 3.6, h: 0.7, fontSize: 13, italic: true });
}

// 7 Web app + Compare --------------------------------------------------------------------------------
{
  const s = content("Web app and Compare on a real model", "Core modules",
    P + "Nirzara. FastAPI back end with a React + TypeScript front end: Optimize, Compare, Test suite, Results, How it works, History, Image mode, Status. The screenshot is a live Compare on gpt-oss-120b: the vague permutations prompt used 768 tokens, the optimized one 248, minus 67.7%, both passing 6 of 6 sandbox tests. Every result says which model actually answered; GPT and Claude themselves need paid keys, so gpt-oss is labelled as a stand-in.");
  s.addImage({ path: path.join(FIG, "ui_compare-result.png"), x: 0.5, y: 1.3, w: 5.6, h: 5.6 * 1480 / 1440, sizing: { type: "crop", w: 5.6, h: 5.6 } });
  stat(s, 6.5, 1.4, 3.0, "-67.7%", "total tokens: 768 → 248 (live, gpt-oss-120b)");
  stat(s, 9.75, 1.4, 3.0, "6/6 = 6/6", "sandbox tests pass for both answers");
  card(s, 6.5, 3.4, 6.25, 3.4);
  txt(s, "What the app does", { x: 6.7, y: 3.5, w: 5.8, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
  bullets(s, ["Optimize: every stage shown, rule by rule, with before/after text", "Compare: same model, temperature 0, tokens, latency, tests, optional blind judge", "History: search, view, delete; prompts expire after 30 days", "Status: providers' 24-hour usage, Stage C on CUDA, sandbox"], { x: 6.7, y: 4.0, w: 5.9, h: 2.75, fontSize: 15 });
}

// 8 Transaction flow --------------------------------------------------------------------------------
pres.addSection({ title: "Transactions" });
{
  const s = content("Transaction flow: one request, one commit", "Transactions",
    P + "Nirzara. Follow the numbers. The endpoint first purges expired prompts. create_prompt scrubs emails and phone numbers and sets expires_at. Stage A results go to prompt_features, Stage B and C to optimization_results and one transformations row per change, renderings and token_usage per target. All through repository.py: its functions flush but never commit; the endpoint commits once, so a failure half-way stores nothing. Then Compare, History, and retention close the loop.");
  s.addImage({ path: path.join(FIG, "diag_transaction.png"), x: 1.45, y: 1.2, w: 10.4, h: 10.4 * 1440 / 2600 });
}

// 9 Database ---------------------------------------------------------------------------------------
{
  const s = content("Database layer: 10 tables, repository only", "Transactions",
    P + "Nirzara. SQLAlchemy 2.0, SQLite in development, PostgreSQL in deployment. The six tables on the right are written in one optimization transaction. Children cascade on delete, so the retention purge removes everything derived from an expired prompt. evaluation_runs is deliberately not linked to prompts so benchmark results are never purged. Constraints live in the schema: confidence between 0 and 1, a Stage B step must name a rule, one rendering per target.");
  s.addImage({ path: path.join(FIG, "08_database_er.png"), x: 0.5, y: 1.3, w: 4.85, h: 4.85 * 1786 / 1568 });
  card(s, 5.7, 1.4, 7.05, 5.4);
  txt(s, "Written in one optimize transaction", { x: 5.9, y: 1.5, w: 6.6, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
  const rows = [["prompts", "create_prompt", "PII-scrubbed text, expires_at"], ["prompt_features", "save_features", "category, confidence, gaps"],
    ["optimization_results", "save_optimization", "IR, optimized text, used_lora"], ["transformations", "save_optimization", "one row per change, rule_id"],
    ["renderings", "save_renderings", "prompt per target LLM"], ["token_usage", "save_token_usage", "tokens per target"]];
  s.addTable([[{ text: "Table", options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 } } }, { text: "Repository call", options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 } } }, { text: "Stores", options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 } } }]]
    .concat(rows.map(r => r.map(t => ({ text: t })))), { x: 5.9, y: 2.05, w: 6.65, colW: [2.1, 2.05, 2.5], fontSize: 13, fontFace: "Calibri", color: HEX.dk1, border: { type: "solid", color: "B9CFC2", pt: 0.75 }, fill: { color: "FFFFFF" }, rowH: 0.45 });
  txt(s, "Cascade on delete · PII scrubbed before storing · 30-day retention enforced before every request", { x: 5.9, y: 5.4, w: 6.6, h: 1.2, fontSize: 15, italic: true, color: C.text2 });
}

// 10 Unit testing ----------------------------------------------------------------------------------
pres.addSection({ title: "Testing" });
{
  const s = content("Unit testing: 798 tests, all passing", "Testing",
    P + "Siddhi. We ran the full suite yesterday, 14 October: 798 passed in 25 seconds, offline, because providers are faked or replayed from recordings. Biggest groups: image mode 215, Stage B 123, dataset tooling 107, rendering and pipeline 77. Every Stage B rule has its own tests. Example: test_pii_is_scrubbed_before_storage stores 'mail rahul.k@example.com or call 98765 43210' and checks one [EMAIL] and two [PHONE] tags. Command: python -m pytest -q in backend.");
  const mods = [["Image mode", 215], ["Stage B rules", 123], ["Dataset tooling", 107], ["Rendering + pipeline", 77], ["Evaluation harness", 74], ["Stage A", 47], ["API + UI API", 37], ["Stage C", 30], ["Database", 22], ["Coding sandbox", 21], ["Correctness suite", 17], ["Compare + clients", 16], ["Spelling + demo", 12]].reverse();
  s.addChart(pres.charts.BAR, [{ name: "tests", labels: mods.map(m => m[0]), values: mods.map(m => m[1]) }],
    { x: 0.5, y: 1.3, w: 7.0, h: 5.55, barDir: "bar", chartColors: [HEX.dk2], showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11,
      dataLabelColor: HEX.dk1, catAxisLabelFontSize: 12, valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
      catAxisLabelColor: HEX.dk1, showLegend: false, catAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
      showTitle: true, title: "pytest tests per module (798)", titleFontSize: 14, titleColor: HEX.dk2, titleFontFace: "+mn-lt" });
  card(s, 7.85, 1.4, 4.9, 2.0, C.background1);
  txt(s, "Run", { x: 8.05, y: 1.5, w: 4.5, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
  txt(s, "cd backend\nsource .venv/bin/activate\npython -m pytest -q\n→ 798 passed in 24.6 s", { x: 8.05, y: 1.92, w: 4.6, h: 1.4, fontSize: 13, fontFace: "Courier New" });
  card(s, 7.85, 3.65, 4.9, 3.15);
  txt(s, "Real examples", { x: 8.05, y: 3.75, w: 4.5, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
  bullets(s, ["test_b05_defaults_to_python", "test_pii_is_scrubbed_before_storage", "test_retention_purge_cascades", "test_blank_prompt_is_rejected_with_422_not_500", "test_invalid_answers_fall_back_to_stage_b"], { x: 8.05, y: 4.2, w: 4.6, h: 2.5, fontSize: 13, fontFace: "Courier New", paraSpaceAfter: 5 });
}

// 11 Integration + system -------------------------------------------------------------------------
{
  const s = content("Integration and system testing", "Testing",
    P + "Siddhi. Beyond unit tests: the freeze check recomputes Stage A and B on all 482 test prompts and compares a sha256 with the frozen-for-test tag; yesterday it was byte-identical. Thirteen Playwright tests drive the real app in Chrome, 13 of 13 pass. API tests go end to end through FastAPI. The full pipeline ran once on the 482-prompt test split and the 44-prompt benchmark. Coding answers run in a bubblewrap sandbox with no network. And the 50-case correctness suite checks real answers.");
  const items = [["Freeze check", "BYTE-IDENTICAL", "482 test prompts, Stage A+B vs tag frozen-for-test (sha256 35f7d4dc…)"],
    ["UI end-to-end", "13 / 13", "Playwright + Chrome: optimize, compare, suite, history, image mode, no console errors"],
    ["API end-to-end", "pytest", "FastAPI TestClient: Stage C on/off, 422 errors, retention, PII-scrubbed Compare"],
    ["Full pipeline", "482 + 44", "test split run once (2 Oct) · benchmark with real LLM + blind judge"],
    ["Coding sandbox", "20.7 → 34.5%", "pass@1 strict, 29 Python items; bubblewrap: no network, read-only"],
    ["Correctness suite", "37 → 42 / 50", "hand-written cases with verifiable answers, gold human-reviewed"]];
  items.forEach(([h, big, b], i) => { const x = 0.5 + (i % 3) * 4.15, y = 1.4 + Math.floor(i / 3) * 2.75; card(s, x, y, 3.95, 2.55);
    txt(s, h, { x: x + 0.15, y: y + 0.1, w: 3.65, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
    txt(s, big, { x: x + 0.15, y: y + 0.5, w: 3.65, h: 0.75, fontSize: 28, bold: true, color: C.accent2, fontFace: "Arial" });
    txt(s, b, { x: x + 0.15, y: y + 1.3, w: 3.65, h: 1.15, fontSize: 13 }); });
}

// 12 Test cases + correctness ---------------------------------------------------------------------
{
  const s = content("Test cases and correctness, including failures", "Testing",
    P + "Siddhi. The report has 38 test cases; here are six. The correctness suite: 50 new hand-written cases. Vague prompts 37 correct, optimized 42, with 29.6% fewer tokens. Optimization fixed 9 answers and broke 4; McNemar p = 0.267, so not significant at n = 50, and on Cerebras it was 43 vs 41. Be honest about the failures: cls-09, Stage A read an attendance table as code so the model wrote a script; two summaries went 2-3 words over the limit; one Stage C coding case failed 4 of 8 asserts.");
  const H = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 } } });
  const st = (t) => ({ text: t, options: { bold: true, color: t === "PASS" ? "1E7B34" : "B42318" } });
  const rows = [["TC04", "B01 removes filler", "\"hey can you please summarize the text for me?\"", "\"Summarize the text.\"", "PASS"],
    ["TC16", "PII scrubbed", "mail rahul.k@example.com … 98765 43210", "1 [EMAIL], 2 [PHONE]", "PASS"],
    ["TC26", "Freeze check", "482 test prompts", "byte-identical", "PASS"],
    ["TC31", "cqa-01 hostel fee", "\"if i pay on 18 july how much total??\"", "80300 (vague said 85300)", "PASS"],
    ["TC34", "cls-09 attendance", "\"mark each student safe warning or detained\"", "got a Python script", "FAIL"],
    ["TC37", "cod-10 recipe scaler", "\"write the scale fn for recipe app\"", "4/8 asserts", "FAIL"]];
  s.addTable([[H("ID"), H("Case"), H("Input"), H("Result"), H("Status")]].concat(rows.map(r => [r[0], r[1], r[2], r[3]].map(t => ({ text: t })).concat([st(r[4])]))),
    { x: 0.5, y: 1.4, w: 7.9, colW: [0.7, 1.75, 2.85, 1.85, 0.75], fontSize: 12, fontFace: "Calibri", color: HEX.dk1, border: { type: "solid", color: "B9CFC2", pt: 0.75 }, fill: { color: "FFFFFF" }, rowH: 0.55 });
  s.addChart(pres.charts.BAR, [{ name: "Vague", labels: ["QA", "Extract", "Classify", "Summary", "Coding"], values: [8, 7, 7, 7, 8] },
                               { name: "Optimized", labels: ["QA", "Extract", "Classify", "Summary", "Coding"], values: [10, 10, 8, 5, 9] }],
    { x: 8.7, y: 1.3, w: 4.1, h: 3.4, barDir: "col", chartColors: [HEX.accent2, HEX.dk2], showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelColor: HEX.dk1,
      valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, catAxisLabelFontSize: 11, catAxisLabelColor: HEX.dk1, valAxisMaxVal: 11,
      showLegend: true, legendPos: "b", legendFontSize: 11, catAxisLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
      showTitle: true, title: "Correct of 10, per category", titleFontSize: 13, titleColor: HEX.dk2, titleFontFace: "+mn-lt" });
  stat(s, 8.7, 5.0, 1.95, "42/50", "optimized (vague 37)", C.text2, 28);
  stat(s, 10.85, 5.0, 1.95, "-29.6%", "total tokens", C.text2, 28);
  txt(s, "Fixed 9 · broke 4 · McNemar p = 0.267 (not significant at n = 50)", { x: 0.5, y: 5.6, w: 7.9, h: 0.5, fontSize: 15, bold: true, color: C.text2 });
  txt(s, "Failures: Stage A misread a table as code (cls-09); two summaries 2-3 words over the limit; a Stage C coding case 4/8 asserts.", { x: 0.5, y: 6.1, w: 7.9, h: 0.75, fontSize: 14 });
}

// 13 Results tokens ----------------------------------------------------------------------------------
pres.addSection({ title: "Results" });
{
  const s = content("Results: -39.2% total tokens on 482 test prompts", "Results",
    P + "Siddhi. The headline: across the 482-prompt test split, total tokens drop 39.2% per prompt, CI 35.9 to 42.5%, Wilcoxon p below 0.001. The optimized prompt is a bit longer, 226 to 241 input tokens, but answers shrink from 682 to 165 because the format and length are stated. Every category saves on average; the limitation is that 87 of 482 short-answer prompts cost more, which is why lean mode is our first next step. On the benchmark with a blind judge, quality went 8.2 to 9.0 and task success 67 to 85%.");
  const cats = ["closed_qa", "extraction", "classification", "summarization", "coding", "all"];
  s.addChart(pres.charts.BAR, [{ name: "Vague prompt", labels: cats, values: [1115, 875, 488, 1169, 903, 909] }, { name: "Optimized", labels: cats, values: [417, 466, 278, 552, 324, 406] }],
    { x: 0.5, y: 1.3, w: 8.1, h: 5.55, barDir: "col", chartColors: [HEX.accent2, HEX.dk2], showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelColor: HEX.dk1,
      valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, catAxisLabelFontSize: 12, catAxisLabelColor: HEX.dk1,
      showLegend: true, legendPos: "b", legendFontSize: 12, catAxisLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
      showTitle: true, title: "Mean total tokens per prompt (input + output), gpt-oss-120b", titleFontSize: 14, titleColor: HEX.dk2, titleFontFace: "+mn-lt" });
  stat(s, 8.95, 1.4, 3.8, "682 → 165", "output tokens per prompt (input 226 → 241)");
  stat(s, 8.95, 3.35, 3.8, "8.2 → 9.0", "benchmark quality; task success 67% → 85%");
  card(s, 8.95, 5.3, 3.8, 1.5);
  txt(s, "Limitation: 87 of 482 prompts cost more (short answers, mostly extraction)", { x: 9.1, y: 5.4, w: 3.5, h: 1.3, fontSize: 14 });
}

// 14 Prototype -------------------------------------------------------------------------------------
{
  const s = content("Working prototype", "Results",
    P + "Nirzara. Left: Optimize on the permutations example, every stage visible, rules with before and after text, the rendered prompt and validated tests. Right: a prompt with an ambiguous reference, 'summarize this article', routed to Stage C; Stage C's answer failed validation, so the app kept Stage B's result and says so. This honesty is on purpose. The app runs on the laptop as a service and is reachable on the LAN.");
  s.addImage({ path: path.join(FIG, "ui_optimize.png"), x: 0.5, y: 1.3, w: 6.05, h: 6.05 * 1817 / 1440, sizing: { type: "crop", w: 6.05, h: 5.6 } });
  s.addImage({ path: path.join(FIG, "ui_optimize-stagec.png"), x: 6.75, y: 1.3, w: 6.05, h: 6.05 * 1400 / 1440, sizing: { type: "crop", w: 6.05, h: 5.6 } });
}

// 15 Git / GitHub ----------------------------------------------------------------------------------
pres.addSection({ title: "Process" });
{
  const s = content("Git and GitHub", "Process",
    P + "Nirzara. All numbers are from git. 92 commits between 13 August and 10 October, on three branches: main, ui-v2 and correctness-suite. Tags were our evaluation checkpoints: frozen-for-test marks the code for the final numbers, final-for-test the one-time test run, v1.0 the release with the Stage C adapter attached. We did not use GitHub Issues or Projects; we tracked work with the roadmap and phase tables in the repository and with tags.");
  s.addImage({ path: path.join(FIG, "gh_repo.png"), x: 0.5, y: 1.3, w: 6.2, h: 6.2 * 900 / 1280 });
  stat(s, 7.0, 1.4, 1.85, "92", "commits");
  stat(s, 8.98, 1.4, 1.85, "3", "branches");
  stat(s, 10.95, 1.4, 1.8, "4", "tags · 1 release");
  card(s, 7.0, 3.35, 5.75, 3.45);
  bullets(s, ["frozen-for-test (27 Sep): code for the final numbers", "final-for-test (2 Oct): test split run once", "v1.0 (8 Oct): release + Stage C adapter", "Commits/month: Aug 7 · Sep 38 · Oct 47", "Tracking: roadmap + phase tables in CLAUDE.md, tags, release (no Issues/Projects used)"],
    { x: 7.15, y: 3.45, w: 5.5, h: 3.3, fontSize: 15 });
  txt(s, "github.com/piush365/PromptOpt", { x: 0.5, y: 5.8, w: 6.2, h: 0.4, fontSize: 14, bold: true, color: C.text2 });
}

// 16 Challenges ------------------------------------------------------------------------------------
{
  const s = content("Challenges and how we solved them", "Process",
    P + "Piush. Seven problems, seven fixes. LLM-written targets dropped data, so we built a deterministic repair with a log. Raters agreed on 90% of rows but kappa was near zero: the kappa paradox, so we report Gwet's AC1 too. Free API quotas: a rolling usage ledger and a 70% budget rule. Stage C invented fields zero-shot, so we fine-tuned and validate every answer. Image v1 made pictures worse; v2 suggests instead of inserting. Regex edge cases got their own tests. And the model trained on a 4 GB GPU with gradient accumulation.");
  const ch = [["Dataset generation bugs", "LLM targets dropped data → deterministic repair: 349 prompts fixed, all logged"],
    ["Kappa paradox", "90% agreement, kappa 0.065 → report Gwet's AC1 0.92-0.96 too"],
    ["API quota limits", "Groq 200k tokens/day → 24-h usage ledger, 70% budget rule, resumable runs"],
    ["Stage C hallucination", "base model 5% valid → LoRA 98.2%, strict JSON contract, fallback to Stage B"],
    ["Image mode v1 failure", "defaults turned watercolor into photo → v2: suggestions only"],
    ["Label / regex edge cases", "\"thank you so much\" in a button → a unit test per edge case, B16 in the app"],
    ["4 GB GPU training", "micro-batch 1 × 16, bf16, checkpointing: 51 min; models loaded once"]];
  ch.forEach(([h, b], i) => { const col = i % 4, row = Math.floor(i / 4); const x = 0.5 + col * 3.1, y = 1.4 + row * 2.75; card(s, x, y, 2.95, 2.55);
    txt(s, h, { x: x + 0.12, y: y + 0.1, w: 2.7, h: 0.75, fontSize: 16, bold: true, color: C.text2 });
    txt(s, b, { x: x + 0.12, y: y + 0.85, w: 2.7, h: 1.6, fontSize: 14 }); });
  card(s, 9.8, 4.15, 2.95, 2.55, C.text2);
  txt(s, "Rule: report it, don't hide it", { x: 9.95, y: 4.3, w: 2.65, h: 0.75, fontSize: 16, bold: true, color: C.background1 });
  txt(s, "After the freeze, bugs were reported, not fixed; failures are in the results.", { x: 9.95, y: 5.05, w: 2.65, h: 1.5, fontSize: 14, color: C.background1 });
}

// 17 Future plans ----------------------------------------------------------------------------------
{
  const s = content("Plans for the upcoming phases", "Process",
    P + "Siddhi. In priority order. Lean mode, because 87 short-answer prompts cost more. Route label-set and typo prompts to Stage C, and let users confirm spelling fixes. Blind tests with prompts written by people outside the team. Compare on real GPT, Claude and Gemini once we have paid keys. A larger correctness suite so the gain can reach significance. Then deployment with PostgreSQL, HTTPS and login.");
  const plans = [["1", "Lean mode", "add only the format line when the answer is short"], ["2", "Smarter routing", "send label-set and typo prompts to Stage C"],
    ["3", "Spelling normalisation", "user-confirmed fixes before optimizing"], ["4", "Blind user tests", "prompts written outside the team"],
    ["5", "Real GPT / Claude / Gemini", "Compare with paid API keys"], ["6", "Larger correctness suite", "more cases and providers for significance"],
    ["7", "Deployment", "PostgreSQL, HTTPS, login, beyond the LAN"]];
  plans.forEach(([k, h, b], i) => { const col = i % 2, row = Math.floor(i / 2); const x = 0.5 + col * 6.2, y = 1.4 + row * 1.37;
    card(s, x, y, 6.0, 1.2);
    s.addShape(pres.shapes.OVAL, { x: x + 0.18, y: y + 0.25, w: 0.7, h: 0.7, fill: { color: C.text2 }, line: { color: C.text2 } });
    txt(s, k, { x: x + 0.18, y: y + 0.25, w: 0.7, h: 0.7, fontSize: 20, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0 });
    txt(s, h, { x: x + 1.05, y: y + 0.12, w: 4.8, h: 0.45, fontSize: 17, bold: true, color: C.text2 });
    txt(s, b, { x: x + 1.05, y: y + 0.58, w: 4.8, h: 0.5, fontSize: 14 }); });
}

// 18 Live demo -----------------------------------------------------------------------------------
{
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Process" }); n++;
  s.addShape(pres.shapes.OVAL, { x: 0.55, y: 0.45, w: 1.2, h: 1.2, fill: { color: C.background1 }, line: { color: C.background1 } });
  s.addImage({ path: logo, x: 0.65, y: 0.55, w: 1.0, h: 1.0 });
  txt(s, "Live demo", { x: 0.6, y: 1.9, w: 12, h: 1.1, fontSize: 54, bold: true, color: C.background1, fontFace: "Arial" });
  const steps = ["Optimize: \"write code to get all permutations of a string\"", "Stage C: \"hey can you just summarize this article for me\"", "Compare on gpt-oss-120b: tokens, latency, tests",
    "Image mode: \"oil painting of a sailboat in a storm\"", "History, Test suite and Results pages"];
  steps.forEach((t, i) => { const y = 3.25 + i * 0.72;
    s.addShape(pres.shapes.OVAL, { x: 0.65, y, w: 0.52, h: 0.52, fill: { color: "F2C894" }, line: { color: "F2C894" } });
    txt(s, String(i + 1), { x: 0.65, y, w: 0.52, h: 0.52, fontSize: 16, bold: true, color: C.text2, align: "center", valign: "middle", margin: 0 });
    txt(s, t, { x: 1.4, y: y - 0.02, w: 11, h: 0.56, fontSize: 19, color: C.background1, valign: "middle" }); });
  txt(s, "Thank you · questions welcome", { x: 0.6, y: 6.85, w: 8, h: 0.4, fontSize: 14, color: "D5E8DC" });
  s.addNotes(P + "Piush drives the laptop; Nirzara narrates Optimize and Compare, Siddhi narrates Test suite and Results. Follow DEMO_LA2.md. If the network fails, Compare shows the cached past comparisons table; if the GPU fails, the app falls back to Stage A + B and says Stage C is unavailable. End with thanks and questions.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("slides:", n);
})();
