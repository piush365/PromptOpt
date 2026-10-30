# Chapters 5-8 of the final report. Sources: evaluation/FINAL_RESULTS.md, evaluation/tokens/token_test.md,
# evaluation/correctness_suite/RESULTS.md, backend/tests (pytest --collect-only), frontend/e2e/app.spec.ts, git.

GPT = "OpenAI's GPT model gpt-oss-120b"

# ====================================================================== 5 Project diagrams
DIAGRAMS = ("Project diagrams", [
    ("p", "This chapter collects the project diagrams. Following the guidance of the review, it starts with the running "
          "example and then shows the architecture, the modules, the flow of one request through the pipeline and the "
          "database."),
    ("h2", "5.1 The example first"),
    ("p", "A student pastes a short product review and types " + "“hey can you just tell me if this review is good "
          "or bad”. The figure below follows this request: Stage A is not sure of the task type (summarization "
          "0.52 against classification 0.35, below the 0.6 gate) and finds filler words and no answer format; Stage B "
          "removes the filler but does not guess a format; Stage C adds “Provide only the label.” and "
          "suggests classification, which the user confirms; the GPT rendering is sent to the model; and Compare shows "
          "that the request now costs 162 tokens instead of 270."),
    ("fig", "diag_story.png", "The review example through the system", 6.5),
    ("h2", "5.2 System architecture"),
    ("p", "The architecture diagram shows the same example under each component. The React user interface sends the "
          "request to the FastAPI back end; Stage A, Stage B and (when needed) Stage C produce the IR; the renderers "
          "write it out for the target model; Compare (the token usage analysis in the simple app) sends both prompts to "
          "a live model, today Groq and Cerebras as stand-ins for GPT, with Gemini wired in but not yet run; and the "
          "database (SQLite or PostgreSQL) stores the results through one repository module."),
    ("fig", "diag_architecture.png", "System architecture with the review example under each component", 6.5),
    ("fig", "diag_modules.png", "Module diagram: core modules, supporting modules and the data layer", 6.4),
    ("tbl", "Main modules", ["Module", "Responsibility"],
     [["app/stage_a/", "feature detection: classifier, detectors A02-A05, PromptFeatures"],
      ["app/stage_b/", "IR, rules B01-B15 (+ B16 in the app), optimizer, routing"],
      ["app/stage_c/", "training data, parser, training script, runtime, contract and checker"],
      ["app/rendering.py", "renderers for GPT, Gemini and Claude; token counts"],
      ["app/pipeline.py", "runs one request end to end and stores it through the repository"],
      ["app/api.py, app/ui_api.py", "FastAPI endpoints for the user interface"],
      ["app/compare/", "Compare on real models, providers, budgets"],
      ["app/db/", "models (10 tables), repository, PII scrubbing, retention"],
      ["app/evaluation/, app/correctness/", "evaluation harness, judge, token evaluation, correctness suite"],
      ["app/coding/", "sandboxed test runner for coding answers"],
      ["frontend/", "React + TypeScript user interface"]],
     [2.2, 4.3]),
    ("h2", "5.3 Pipeline flow of one request"),
    ("p", "One optimization request is handled as one database transaction. The steps below are numbered as in the "
          "figure; every arrow in the figure is labelled with what passes along it."),
    ("num", [
        "The user submits the prompt, the target LLM, the category (auto or one of five) and an optional attachment "
        "type (POST /api/optimize).",
        "Old data is cleaned: prompts older than 30 days, and everything derived from them, are deleted.",
        "The prompt is saved after e-mail addresses and phone numbers are replaced by [EMAIL] and [PHONE] (table prompts).",
        "Stage A detects the features (table prompt_features).",
        "Stage B, and Stage C if the prompt is routed, produce the IR and the change log (tables optimization_results "
        "and transformations, one row per change).",
        "The IR is rendered for GPT, Claude and Gemini and the input tokens are counted (tables renderings and token_usage).",
        "Decision: did every step succeed? If yes, the request is committed once; if any step failed, the whole "
        "request is rolled back and nothing is stored.",
        "The response returns the features, the rules that fired, the renderings and the token counts to the user interface.",
        "Optionally, the user runs Compare: both prompts go to the same model and the run is stored.",
        "Later, History lists, searches, shows and deletes past prompts; deleting a prompt deletes everything derived from it.",
    ]),
    ("fig", "diag_pipeline.png", "Pipeline flow of one request, with the commit decision at step 7", 6.5),
    ("p", "Only the repository module (app/db/repository.py) reads or writes the database. Its functions flush, so that "
          "the identifiers of new rows exist, but never commit; the endpoint commits once at the end. A failure "
          "half-way therefore leaves nothing behind, and the privacy rules are applied in one place."),
    ("h2", "5.4 Database design"),
    ("p", "The database has ten tables, defined with the SQLAlchemy 2.0 ORM. The prompt-side tables are deleted in "
          "cascade with their prompt, so the retention purge removes everything derived from an expired prompt. The "
          "evaluation_runs table is deliberately not linked to prompts, so benchmark results are never purged. "
          "Constraints are enforced in the schema: a confidence between 0 and 1, a Stage B transformation must "
          "reference a rule, one rendering per result and target."),
    ("fig", "08_database_er.png", "Entity-relationship diagram (10 tables)", 5.0),
    ("tbl", "Tables of the database", ["Table", "Content", "Written by"],
     [["prompts", "prompt text after PII scrubbing, number of redactions, created and expiry time", "create_prompt"],
      ["prompt_features", "task type, confidence, missing constraints, filler, ambiguous references", "save_features"],
      ["optimization_results", "IR (JSON), optimized text, confidence, whether Stage C was used, latency", "save_optimization"],
      ["transformations", "one row per change: step number, stage (B or C), rule, text before and after", "save_optimization"],
      ["renderings", "the rendered prompt per target LLM", "save_renderings"],
      ["token_usage", "original and optimized input (and output) tokens per target, tokenizer", "save_token_usage"],
      ["rules", "the rule catalogue A01-A05, B01-B16 with an enabled flag", "seed"],
      ["lora_models", "metadata of Stage C adapters", "register_lora_model"],
      ["users", "optional display name (no e-mail or real name stored)", "–"],
      ["evaluation_runs", "one row per evaluated item, variant and target: tokens, latency, quality, task success", "record_evaluation"]],
     [1.6, 3.5, 1.4]),
    ("h2", "5.5 Evaluation flow"),
    ("p", "The evaluation runs each split through the variants being compared (the vague prompt, Stage A + B, Stage A + "
          "B + C, and the dataset's own optimized prompt) and measures each variant with the metrics of Section 4.10."),
    ("fig", "07_evaluation_flow.png", "Evaluation flow: splits, variants and metrics", 6.3),
])

# ====================================================================== 6 Test plan
UNIT_TC = [
    # id, module, test, input, expected, actual, status
    ["TC01", "Stage A", "Format detected", "“Answer in 3 bullet points”", "format found (A02)", "found", "PASS"],
    ["TC02", "Stage A", "Filler detected", "“hey can you please summarize…”", "“hey”, “can you please”", "as expected", "PASS"],
    ["TC03", "Stage A", "Ambiguous reference only without text", "“summarize this” with / without text", "flagged / not flagged", "as expected", "PASS"],
    ["TC04", "Stage A", "Unlike anything known → other", "prompt with no similar train prompt", "category = other", "other", "PASS"],
    ["TC05", "Stage B", "B01 removes filler", "“hey can you please summarize the text for me?”", "“Summarize the text.”", "as expected", "PASS"],
    ["TC06", "Stage B", "B05 defaults to Python", "“Write a function that reverses a list.”", "“Use Python.”", "as expected", "PASS"],
    ["TC07", "Stage B", "B08 group fallback", "“when was it finished” + passage, closed_qa 0.45", "“Answer from the provided text in at most three sentences.”", "as expected", "PASS"],
    ["TC08", "Stage B", "Running twice adds nothing", "an optimized prompt optimized again", "no new change", "none", "PASS"],
    ["TC09", "Stage C", "Category request", "unresolved task category", "asks for format, constraints, category", "as expected", "PASS"],
    ["TC10", "Stage C", "Invalid answer falls back", "malformed JSON / wrong keys", "Stage B's IR kept", "kept", "PASS"],
    ["TC11", "Stage C", "Dangling reference rejected", "task “Summarize the provided text”, no text", "rejected", "rejected", "PASS"],
    ["TC12", "Stage C", "Not routed means not called", "nothing unresolved", "Stage C not called", "not called", "PASS"],
    ["TC13", "Rendering", "No field lost", "13 IRs × 3 targets, parsed back", "equal to the IR", "equal", "PASS"],
    ["TC14", "Rendering", "Claude: XML, context first", "IR with context", "<context> before <task>", "as expected", "PASS"],
    ["TC15", "Rendering", "Fence longer than data", "data with ``` inside", "fence of 4+ backticks", "as expected", "PASS"],
    ["TC16", "Rendering", "Token counts labelled", "rendered prompt", "GPT exact, Claude/Gemini approx.", "as expected", "PASS"],
    ["TC17", "Database", "PII scrubbed before storage", "e-mail + two phone numbers", "1 [EMAIL], 2 [PHONE], 3 redactions", "as expected", "PASS"],
    ["TC18", "Database", "Retention purge cascades", "a 31-day-old and a fresh prompt", "old prompt and its rows deleted", "deleted", "PASS"],
    ["TC19", "Database", "Schema constraints hold", "confidence 1.5; Stage B step without rule", "rejected by the database", "rejected", "PASS"],
    ["TC20", "Database", "Full flow and history", "optimize, then history", "every stored part returned", "returned", "PASS"],
    ["TC21", "API", "Blank prompt", "POST /api/optimize, prompt “   ”", "HTTP 422 (not 500)", "422", "PASS"],
    ["TC22", "API", "Expired prompts hidden", "prompt older than 30 days", "deleted before history is listed", "deleted", "PASS"],
    ["TC23", "API", "Unsure category reported", "low-confidence prompt", "UI asked to confirm", "as expected", "PASS"],
    ["TC24", "API", "Models load once", "parallel requests", "one Stage A / Stage C instance", "one", "PASS"],
    ["TC25", "Compare", "End to end with recorded answers", "prompt + model", "both answers, tokens, change %", "as expected", "PASS"],
    ["TC26", "Compare", "Both prompts PII-scrubbed", "prompt with an e-mail", "provider sees [EMAIL] only", "as expected", "PASS"],
    ["TC27", "Compare", "Budget respected", "daily budget used up", "refused before calling the model", "refused", "PASS"],
    ["TC28", "Compare", "Rate limits", "per-minute / per-day 429", "retry / stop for the day", "as expected", "PASS"],
    ["TC29", "Sandbox", "No network", "code opening a socket to 1.1.1.1", "connection blocked", "blocked", "PASS"],
    ["TC30", "Sandbox", "Time limit", "infinite loop", "killed at the timeout", "killed", "PASS"],
    ["TC31", "Sandbox", "Host files hidden", "code reading the home folder", "not visible", "not visible", "PASS"],
    ["TC32", "Sandbox", "Refuses without bwrap", "bubblewrap missing", "refusal, code not run", "refused", "PASS"],
    ["TC33", "Image mode", "No user word lost", "image prompts (parametrized)", "every word kept, no default added", "as expected", "PASS"],
    ["TC34", "Image mode", "Suggestions only for gaps", "prompt that names a style", "no style suggestion", "as expected", "PASS"],
    ["TC35", "Image mode", "Aspect ratio only when implied", "prompts with and without an implied shape", "ratio only when implied", "as expected", "PASS"],
    ["TC36", "Image mode", "Accepted suggestions marked", "click two suggestions", "added after the user's words", "as expected", "PASS"],
    ["TC37", "UI (Playwright)", "Every stage shown", "click an example", "Stage A, B, C and rendering shown", "shown", "PASS"],
    ["TC38", "UI (Playwright)", "Unsure category asks the user", "low-confidence prompt", "confirmation box shown", "shown", "PASS"],
    ["TC39", "UI (Playwright)", "History works", "list, search, view, delete", "all four work", "work", "PASS"],
    ["TC40", "UI (Playwright)", "No console errors", "every page", "0 console errors", "0", "PASS"],
]


def cat_rows(rows):
    return [[cid, scen, v, o, "PASS" if o == "correct" else "FAIL"] for cid, scen, v, o in rows]


CORR = {
    "closed_qa": [
        ("cqa-01", "hostel fee notice: total for a late second-year payer", "wrong", "correct"),
        ("cqa-02", "timetable with a corrigendum that moves one paper", "correct", "correct"),
        ("cqa-03", "T20 scorecard without the total: target for the chasing side", "correct", "correct"),
        ("cqa-04", "recipe for 4 scaled to 10 people (Stage C)", "correct", "correct"),
        ("cqa-05", "placement notice: one company's CGPA cut-off", "correct", "correct"),
        ("cqa-06", "recharge plans: cheapest per day with 2 GB/day", "correct", "correct"),
        ("cqa-07", "library overdue fine with two slabs", "correct", "correct"),
        ("cqa-08", "bus timetable on a Sunday: earliest arrival", "correct", "correct"),
        ("cqa-09", "online deal with coupon and capped bank discount", "correct", "correct"),
        ("cqa-10", "attendance: lectures one can still miss and keep 75%", "wrong", "correct")],
    "information_extraction": [
        ("ie-01", "drive notice: branches eligible for one company", "correct", "correct"),
        ("ie-02", "coordinator's e-mail: the revised deadlines", "correct", "correct"),
        ("ie-03", "bug thread: OS versions that crash", "correct", "correct"),
        ("ie-04", "result sheet: students with a backlog", "correct", "correct"),
        ("ie-05", "recipe: dairy ingredients (Stage C)", "correct", "correct"),
        ("ie-06", "PNR status: passengers with confirmed berths", "correct", "correct"),
        ("ie-07", "lab timetable: labs of one batch", "wrong", "correct"),
        ("ie-08", "bank statement: debits above Rs 5,000", "wrong", "correct"),
        ("ie-09", "Django traceback: files in the failing traces (Stage C)", "correct", "correct"),
        ("ie-10", "scholarship notice: documents for a renewal", "wrong", "correct")],
    "classification": [
        ("cls-01", "pressure-cooker reviews: positive / negative / mixed", "correct", "correct"),
        ("cls-02", "monthly expenses into four categories (Stage C)", "correct", "correct"),
        ("cls-03", "college-app issue triage with a label guide", "correct", "correct"),
        ("cls-04", "mess menu: veg / non-veg under the egg rule (Stage C)", "correct", "correct"),
        ("cls-05", "placement offers: Normal / Dream / Super Dream", "wrong", "correct"),
        ("cls-06", "SMS inbox: legit / promo / scam", "correct", "correct"),
        ("cls-07", "student queries routed to the right office (Stage C)", "wrong", "wrong"),
        ("cls-08", "Big-O of short Python snippets", "correct", "correct"),
        ("cls-09", "attendance status per student", "correct", "wrong"),
        ("cls-10", "language of each class-group message (Stage C)", "wrong", "correct")],
    "summarization": [
        ("sum-01", "accounts circular with an extended date", "correct", "correct"),
        ("sum-02", "bug report for a team lead", "correct", "correct"),
        ("sum-03", "six laptop reviews into pros and cons", "correct", "correct"),
        ("sum-04", "placement-drive notice for WhatsApp", "correct", "correct"),
        ("sum-05", "recipe method for a beginner (Stage C)", "wrong", "wrong"),
        ("sum-06", "industrial-visit message with a postponed date", "correct", "wrong"),
        ("sum-07", "fest committee minutes", "wrong", "wrong"),
        ("sum-08", "municipal water-cut notice", "wrong", "wrong"),
        ("sum-09", "mini-project abstract for a slide", "correct", "correct"),
        ("sum-10", "PG agreement summarised for parents", "correct", "wrong")],
    "coding": [
        ("cod-01", "SGPA from (grade, credits) pairs", "correct", "correct"),
        ("cod-02", "fix an attendance-percentage function", "correct", "correct"),
        ("cod-03", "library fine with slabs, cap and reference books", "correct", "correct"),
        ("cod-04", "timetable clash detection", "correct", "correct"),
        ("cod-05", "Indian digit grouping (lakh/crore commas)", "wrong", "correct"),
        ("cod-06", "PRN format validation", "correct", "correct"),
        ("cod-07", "fix a class average that crashes on “AB”", "correct", "correct"),
        ("cod-08", "trip expense splitter", "correct", "correct"),
        ("cod-09", "fix a second-highest-marks function", "wrong", "correct"),
        ("cod-10", "recipe quantity scaler with fractions (Stage C)", "correct", "wrong")],
}
CORR_SUM = {"closed_qa": "vague 8/10, optimized 10/10", "information_extraction": "vague 7/10, optimized 10/10",
            "classification": "vague 7/10, optimized 8/10", "summarization": "vague 7/10, optimized 5/10",
            "coding": "vague 8/10, optimized 9/10"}

tp = [
    ("p", "Testing is automated and has three levels. Unit tests check every detector, rule and module on its own; "
          "integration tests check the modules working together, through the API and through the correctness suite of "
          "real cases; system tests run the complete application in a browser and the complete pipeline on the dataset "
          "splits. Unit and integration tests run with pytest and need no network: LLM providers are faked or replayed "
          "from recorded answers, and database tests run on an in-memory SQLite database (and on PostgreSQL when a test "
          "database is configured). Browser tests run with Playwright against the real FastAPI application on a "
          "throw-away database. Manual testing covered the demonstration flow and the human review of the dataset and "
          "of the correctness-suite gold answers."),
    ("tbl", "Types of testing and tools", ["Level", "Tool", "What is tested", "Result"],
     [["Unit", "pytest", "every Stage A detector, every Stage B rule, Stage C contract, renderers, database, sandbox, clients", "720 test cases, 60 per module, all pass"],
      ["Integration (API)", "pytest + FastAPI TestClient", "endpoints end to end, pipeline storage, Compare with recorded answers, retention", "included in the 720"],
      ["Integration (correctness)", "correctness suite", "50 hand-written cases, 10 per category, with verifiable answers", "vague 37/50, optimized 42/50"],
      ["System (UI)", "Playwright + Chrome", "simple app and developer view: optimize, token usage analysis, compare, test suite, history, image mode, tour, console errors", "16 / 16 passed"],
      ["System (pipeline)", "evaluation harness", "482-prompt test split, 44-prompt benchmark, ablation", "Chapter 7"],
      ["Regression", "freeze check", "Stage A + B on 482 test prompts against the frozen code", "byte-identical"],
      ["Security", "sandbox tests", "no network, read-only system, memory, time and process limits", "passed"]],
     [1.3, 1.4, 2.6, 1.2]),
    ("h2", "6.1 Unit testing"),
    ("p", "Every Stage B rule is a separate pure function with its own tests, and every Stage A detector has positive and "
          "negative tests. Each of the 12 modules has exactly 60 test cases, 720 in all; a check that runs over a whole "
          "example set (for instance every example prompt of image mode) counts as one test case. All 720 pass. The "
          "68 database-backed cases run a second time on PostgreSQL, and all 68 pass there too; this is why pytest "
          "reports 788 tests (720 + 68). The commands are: cd backend && source .venv/bin/activate && python -m "
          "pytest -q (788 passed) and python -m app.test_report, which writes the per-module table below."),
    ("tbl", "Unit test cases per module and their pass rate", ["Module", "Test cases", "Passed", "Pass rate"],
     [["Stage A: feature detection", "60", "60", "100%"],
      ["Stage B: rule-based optimizer", "60", "60", "100%"],
      ["Stage C: small-model fallback", "60", "60", "100%"],
      ["Rendering and pipeline", "60", "60", "100%"],
      ["Image mode", "60", "60", "100%"],
      ["Database and privacy", "60", "60", "100%"],
      ["API, web UI, spelling and demo", "60", "60", "100%"],
      ["Coding tests and sandbox", "60", "60", "100%"],
      ["Token usage analysis and live models", "60", "60", "100%"],
      ["Evaluation harness", "60", "60", "100%"],
      ["Dataset building", "60", "60", "100%"],
      ["Dataset repair and checks", "60", "60", "100%"],
      ["Total", "720", "720", "100%"]],
     [3.4, 1.1, 1.0, 1.0]),
    ("p", "The test-case table below shows four of these cases for each of ten modules, each taken from the real test "
          "suite, with the input, the expected and the actual result."),
    ("tc", "Unit and module test cases: four sample cases per module", ["ID", "Module", "Test", "Input", "Expected", "Actual", "Status"],
     UNIT_TC, [0.45, 0.8, 1.15, 1.35, 1.15, 0.85, 0.55]),
    ("p", "Examples of real unit tests (backend/tests):"),
    ("code", "def test_b05_defaults_to_python():\n"
             "    text = \"Write a function that reverses a list.\"\n"
             "    assert b.b05_add_language(ir_of(text, \"coding\"),\n"
             "                              feats(text, \"coding\")).constraints == (\"Use Python.\",)\n\n"
             "def test_pii_is_scrubbed_before_storage(db):\n"
             "    p = repo.create_prompt(db, \"mail rahul.k@example.com or call 98765 43210 / 555-123-4567 about the report\")\n"
             "    db.commit()\n"
             "    stored = db.scalar(select(Prompt.original_text).where(Prompt.id == p.id))\n"
             "    assert stored.count(\"[EMAIL]\") == 1 and stored.count(\"[PHONE]\") == 2\n"
             "    assert p.pii_redactions == 3\n\n"
             "def test_blank_prompt_is_rejected_with_422_not_500(client):\n"
             "    r = client.post(\"/api/optimize\", json={\"prompt\": \"   \\n \", \"target\": \"gpt\"})\n"
             "    assert r.status_code == 422 and \"empty\" in r.json()[\"detail\"]"),
    ("h2", "6.2 Integration testing"),
    ("h3", "6.2.1 API integration"),
    ("p", "API tests send real HTTP requests through the FastAPI test client and check the whole chain: the pipeline "
          "with and without Stage C, the storage of every part through the repository, History, Compare with recorded "
          "model answers, image mode, input errors (HTTP 422 instead of 500), retention before History is listed, and "
          "removal of personal data from what Compare sends to the provider."),
    ("h3", "6.2.2 Correctness suite, by category"),
    ("p", "The correctness suite tests the optimizer together with a real model on 50 new, hand-written cases that are "
          "close to students' daily use: hostel notices, timetables, placement circulars, bank statements, recipes and "
          "small coding tasks. There are exactly ten cases per category. Each case has one verifiable gold answer, "
          "confirmed by the team (50 of 50), and a vague prompt written the way a student would type it. The vague "
          "prompt and the optimized prompt are both sent to " + GPT + "; the answer is checked deterministically where "
          "possible (numbers, item sets, labels, hidden unit tests run in the sandbox) and with a blind checklist judge "
          "for summaries. A case passes when the optimized prompt's answer is correct. Cases marked (Stage C) were "
          "routed to Stage C."),
]
for cat, rows in CORR.items():
    tp.append(("tbl", f"Correctness suite: {cat} (correct answers: {CORR_SUM[cat]})",
               ["Case", "Scenario", "Vague prompt", "Optimized prompt", "Status"], cat_rows(rows), [0.7, 3.0, 0.95, 1.1, 0.75]))
tp += [
    ("tbl", "Correctness suite: accuracy and tokens per category (" + GPT + ")",
     ["Category", "Vague correct", "Optimized correct", "Input tokens (vague / optimized)", "Output tokens (vague / optimized)", "Input + output (vague / optimized)"],
     [["closed_qa", "8/10", "10/10", "217 / 244", "308 / 166", "525 / 410"],
      ["information_extraction", "7/10", "10/10", "244 / 274", "289 / 110", "532 / 384"],
      ["classification", "7/10", "8/10", "251 / 282", "320 / 254", "571 / 535"],
      ["summarization", "7/10", "5/10", "257 / 274", "155 / 170", "412 / 444"],
      ["coding", "8/10", "9/10", "176 / 210", "1104 / 354", "1279 / 563"],
      ["all (50)", "37/50 (74%)", "42/50 (84%)", "229 / 257", "435 / 211", "664 / 467"]],
     [1.8, 0.9, 1.0, 0.95, 1.0, 1.0]),
    ("fig", "chart_correctness.png", "Correctness suite: correct answers per category, vague vs optimized", 6.0),
    ("p", "Optimization made 9 wrong answers right and 4 right answers wrong; the exact McNemar test gives p = 0.267, so "
          "the gain is not statistically significant with 50 cases. On a second provider (Cerebras) the same model "
          "gave 43/50 for the vague and 41/50 for the optimized prompts, while total tokens fell by 28.2%: the token "
          "saving is robust across providers, the correctness gain is not. The four cases where optimization hurt are "
          "analysed in Section 7.4."),
    ("h2", "6.3 System testing"),
    ("tbl", "Browser end-to-end tests (Playwright, real application)", ["#", "Test", "Result"],
     [["1", "example gallery → optimize shows every stage", "PASS"],
      ["2", "hovering an issue highlights the words in the prompt", "PASS"],
      ["3", "Ctrl+Enter optimizes, undo restores the previous input, live counter updates", "PASS"],
      ["4", "possible typos are suggested, and Fix all corrects the prompt and runs again", "PASS"],
      ["5", "an unsure category asks the user to confirm", "PASS"],
      ["6", "Compare runs both prompts on a real model", "PASS"],
      ["7", "test suite: summary, filter and case view", "PASS"],
      ["8", "history: listed, searchable, viewable, deletable", "PASS"],
      ["9", "theme toggle switches and persists", "PASS"],
      ["10", "image mode: suggestions are clickable and per-model renderings", "PASS"],
      ["11", "gallery image example opens Image mode and runs it there", "PASS"],
      ["12", "tour shows once and can be skipped; ? opens shortcuts", "PASS"],
      ["13", "simple app: improve a prompt, then analyse its token usage", "PASS"],
      ["14", "simple app: picture prompts, then history shows them and can reuse them", "PASS"],
      ["15", "old developer links redirect to /dev", "PASS"],
      ["16", "every page loads without console errors", "PASS"]],
     [0.4, 5.1, 0.9]),
    ("bul", [
        "Full pipeline on the 482-prompt test split and the 44-prompt benchmark, with a real model and a blind judge "
        "(Chapter 7).",
        "Freeze check: Stage A + B of the current code and the frozen code on all 482 test prompts give byte-identical "
        "output (equal SHA-256 hashes).",
        "Coding sandbox: answers to coding prompts are run against 3-6 assert tests per item, kept only if they pass on "
        "the reference solution, in a bubblewrap sandbox with no network and a read-only system.",
        "Attachment rules: 30 hand-made prompts (5 per attachment type); in all 30 the right rule fires and no other.",
    ]),
]
TESTPLAN = ("Test plan", tp)

# ====================================================================== 7 Results
RESULTS = ("Results", [
    ("h2", "7.1 Results with screenshots and description"),
    ("p", "This section first follows the review example through the working application, screen by screen: first "
          "the simple app that everyday users see, then every stage in the developer view. It then summarises the "
          "results on the full test data."),
    ("h3", "7.1.1 What the user sees: the simple app"),
    ("fig", "user_input.png", "Improve prompt (simple app): the vague prompt, the pasted review and the target AI", 6.0),
    ("p", "The user types the prompt the way they normally would, adds the review under “The text your prompt is "
          "about” and picks the AI they will send it to, here ChatGPT. More options (the kind of task and an "
          "attached file) stay folded away; by default the task type is detected automatically."),
    ("fig", "user_result.png", "The improved prompt, written in ChatGPT's layout (50 tokens), with the task-type question", 4.4),
    ("p", "The improved prompt comes back in ChatGPT's layout, with a task, the review as the document and the output "
          "format “Provide only the label.”, ready to copy. Because the system was not sure which kind of task this "
          "is, it asks the user to pick one instead of guessing; the button below leads to the token usage analysis."),
    ("fig", "user_usage.png", "Token usage analysis: both prompts on the same AI, 162 tokens instead of 270 (40% fewer)", 5.0),
    ("p", "Token usage analysis sends both prompts to the same model, " + GPT + " on Groq, labelled as a stand-in for "
          "ChatGPT. The improved prompt is a little longer to send (121 instead of 104 tokens) but the answer shrinks "
          "from 166 tokens to 41, the single word “good”, so the total falls from 270 to 162 tokens, 40% fewer, and the "
          "answer arrives in 0.1 s instead of 0.4 s. The 50 tokens shown on the previous screen are the prompt alone; "
          "the model adds about 70 tokens of its own message framing, which is why 121 tokens are sent."),
    ("fig", "user_history.png", "History (simple app): the prompt, the improved prompt and its token saving, kept for 30 days", 6.0),
    ("p", "History keeps every prompt for 30 days with its improved version and, when it was analysed, the token "
          "saving; a prompt can be used again, copied or deleted. E-mail addresses and phone numbers are removed "
          "before anything is stored."),
    ("h3", "7.1.2 Every stage in the developer view"),
    ("fig", "story_input.png", "Developer view, Optimize: the vague prompt and the pasted review, target GPT, category auto-detect", 6.0),
    ("p", "The developer view shows the same request with every stage. The review is pasted under “Pasted text”; the "
          "live counter shows 33 input tokens for GPT (counted exactly with OpenAI's tokenizer)."),
    ("fig", "story_stage-a.png", "Stage A on the review example: summarization 0.52, below the 0.6 gate, so marked unsure", 5.0),
    ("p", "Stage A shows its best guess, Summarise, with a confidence of 0.52, and the score of every category "
          "(classification 0.35 is second). The confidence bar stops before the 0.6 gate mark, so the category is "
          "marked unsure. Below, the detected gaps are listed with their detector codes: no output format (A02), no "
          "length, audience or tone (A03), and the filler words “hey, can you, just” (A04)."),
    ("fig", "story_stage-b.png", "Stage B on the review example: two rules fired, each shown with the text before and after", 5.0),
    ("p", "Stage B lists the two rules that fired, each with the deleted text in red and the added text in green: B07 "
          "tidied the sentence (capital letter and full stop) and B01 removed “Hey can you just”. No format was "
          "added because the category is unsure; the task category and the output format are left unresolved."),
    ("fig", "story_stage-c.png", "Stage C on the review example: the model filled format, constraints and category; the user is asked to confirm", 5.0),
    ("p", "Stage C was called because the task category was unresolved. It filled exactly the requested fields, and its "
          "answer passed all three checks shown (valid JSON, exactly the requested fields, Stage A's checks). Its "
          "category suggestion is not applied automatically: the application asks “Is this a Classify task?” and "
          "pre-selects Classify, while the format “Provide only the label.” is applied."),
    ("fig", "story_render.png", "The optimized prompt rendered for GPT, with 50 input tokens", 5.0),
    ("fig", "story_compare.png", "Compare: the vague and the optimized prompt answered by the same model", 6.2),
    ("p", "Compare sends both prompts to the same model, " + GPT + " on Groq, which stands in for GPT and is labelled as "
          "such on the screen. The vague prompt produced a 166-token explanation (“Overall assessment: Mixed …”); "
          "the optimized prompt produced the single word “good” in 41 output tokens. Total tokens fell from 270 "
          "to 162 (−40.0%) and the response time by 72.5%, even though the optimized prompt is longer (input 104 to "
          "121 tokens, +16.3%). The vague answer's “mixed” is a fair reading of the review, but it is not one of the "
          "two labels the user asked for; the optimized prompt makes the model answer the question as asked."),
    ("fig", "chart_story_tokens.png", "Review example: input, output and total tokens on the same model", 5.0),
    ("tbl", "Headline results on held-out data (output tokens measured on " + GPT + ")", ["What", "Result"],
     [["Total tokens, optimized vs vague (482 test prompts)", "−39.2% per prompt (95% CI 35.9-42.5%)"],
      ["Output tokens per prompt", "165 (vague prompt: 682)"],
      ["Input tokens per prompt", "241 (vague prompt: 226)"],
      ["Output format stated after Stage B", "95.0% (vague prompt: 3.1%)"],
      ["Stage A category accuracy (vague prompts)", "74.7% (macro-F1 0.746)"],
      ["Prompts routed to Stage C", "6.4% (31 of 482)"],
      ["Benchmark (44 prompts, blind judge): quality / task success", "9.0 / 85% (vague prompt: 8.2 / 67%)"],
      ["Stage C answers passing the checker: base model vs LoRA", "5.0% vs 98.2%"],
      ["Stage C on routed prompts: output format stated", "90.3% (without Stage C: 22.6%)"],
      ["Coding tests pass@1, strict (29 Python items)", "34.5% (vague prompt: 20.7%)"],
      ["Correctness suite (50 cases): vague vs optimized correct", "37/50 vs 42/50, total tokens −29.6%"],
      ["Attachment rules, hand-made set", "30/30 correct"]],
     [4.2, 2.3]),
    ("h2", "7.2 Comparative analysis: input, output and input + output tokens"),
    ("p", "The table below compares the vague prompt with the optimized prompt (Stage A + B) on all 482 test prompts, "
          "separately for input tokens, output tokens and their sum. All counts are the provider's own counts for "
          + GPT + "; output includes the model's hidden reasoning tokens. Claude and Gemini were not run."),
    ("tbl", "Mean tokens per prompt: input, output and input + output (482 test prompts, " + GPT + ")",
     ["Category", "n", "Input (vague / optimized)", "Output (vague / optimized)", "Input + output (vague / optimized)", "Change of input + output per prompt [95% CI]"],
     [["closed_qa", "99", "279 / 290", "835 / 127", "1115 / 417", "−44.5% [−51.3, −37.6]"],
      ["information_extraction", "93", "338 / 351", "538 / 115", "875 / 466", "−24.2% [−32.4, −16.2]"],
      ["classification", "98", "98 / 122", "390 / 156", "488 / 278", "−28.5% [−35.8, −21.1]"],
      ["summarization", "94", "338 / 348", "831 / 204", "1169 / 552", "−43.3% [−49.4, −37.0]"],
      ["coding", "98", "89 / 102", "813 / 222", "903 / 324", "−54.7% [−60.8, −48.0]"],
      ["all", "482", "226 / 241", "682 / 165", "909 / 406", "−39.2% [−42.5, −35.9]"]],
     [1.6, 0.4, 0.95, 0.95, 1.1, 1.5]),
    ("fig", "chart_io_tokens.png", "Input, output and input + output tokens per category, vague vs optimized", 6.5),
    ("tbl", "Change per prompt by token type (482 test prompts, " + GPT + ")", ["Token type", "Vague (mean)", "Optimized (mean)", "Mean change per prompt [95% CI]", "Wilcoxon p"],
     [["input", "226", "241", "+11.1% [10.2, 12.1]", "< 0.001"],
      ["output", "682", "165", "−52.7% [−57.1, −48.2]", "< 0.001"],
      ["input + output", "909", "406", "−39.2% [−42.5, −35.9]", "< 0.001"]],
     [1.3, 1.1, 1.2, 1.9, 1.0]),
    ("p", "Input tokens grow in every category, by about 4-26% per prompt, because the optimized prompt states a format, a length or "
          "labels. Output tokens fall by much more, because the model no longer writes alternatives, explanations and "
          "examples nobody asked for. The sum therefore falls in every category, most for coding (−54.7%), where "
          "vague prompts produced several versions of the code with explanations. 87 of the 482 prompts (18.0%) "
          "individually cost more, mostly short-answer information_extraction prompts (35 of 93) whose answer was "
          "already short."),
    ("p", "The −39.2% is the mean of the per-prompt changes, so every prompt counts equally. The mean totals in the "
          "table (909 and 406 tokens) correspond to the aggregate reduction of 55.4% (Section 4.10), which is larger "
          "because a few very long vague answers dominate the totals. This report always quotes the smaller, "
          "per-prompt figure."),
    ("fig", "chart_tokens.png", "Mean input + output tokens per prompt by category, vague vs optimized", 6.2),
    ("tbl", "Stage C ablation on the test split", ["Prompt set", "System", "n", "Task intent", "Format stated", "Fallback"],
     [["routed", "A + B", "31", "0.869", "22.6%", "–"], ["routed", "A + B + C", "31", "0.843", "90.3%", "3.2%"],
      ["routed", "C only", "31", "0.712", "90.3%", "6.5%"], ["forced (all)", "A + B", "482", "0.886", "95.0%", "–"],
      ["forced (all)", "A + B + C", "482", "0.769", "90.2%", "2.1%"], ["forced (all)", "C only", "482", "0.765", "88.6%", "1.9%"]],
     [1.2, 1.1, 0.6, 1.1, 1.2, 1.0]),
    ("p", "Where Stage B routes a prompt, Stage C states a format in 90% of cases instead of 23%, at a small loss in "
          "task intent (the similarity of the final task to the original instruction). Sending every prompt through "
          "Stage C hurts (task intent falls from 0.886 to 0.769), and Stage C alone without the rules is the weakest, so the rules are "
          "worth keeping in front of the model and Stage C stays a fallback for routed prompts only. On the 31 routed "
          "prompts, adding Stage C to A + B reduced input + output tokens by a further 26.7% per prompt."),
    ("fig", "chart_benchmark.png", "Benchmark split: quality, task success and input + output tokens", 6.2),
    ("h2", "7.3 Performance measures in tabular form and graphs"),
    ("tbl", "Stage A per-category results (482 test prompts)", ["Category", "n", "Precision", "Recall", "F1"],
     [["closed_qa", "99", "56.7%", "76.8%", "0.65"], ["information_extraction", "93", "73.2%", "55.9%", "0.63"],
      ["classification", "98", "93.1%", "95.9%", "0.94"], ["summarization", "94", "60.0%", "44.7%", "0.51"],
      ["coding", "98", "99.0%", "98.0%", "0.98"], ["accuracy (all)", "482", "", "", "74.7%"]],
     [2.2, 0.7, 1.2, 1.2, 1.2]),
    ("fig", "chart_stage_a.png", "Stage A F1 per category (test split)", 5.4),
    ("tbl", "Stage B per category (482 test prompts)", ["Category", "n", "Format stated (vague / Stage B)", "Words (vague / Stage B)", "Sent to Stage C"],
     [["closed_qa", "99", "0.0% / 96.0%", "9.1 / 18.8", "4.0%"], ["information_extraction", "93", "4.3% / 94.6%", "9.1 / 20.9", "5.4%"],
      ["classification", "98", "0.0% / 90.8%", "18.7 / 32.5", "15.3%"], ["summarization", "94", "2.1% / 94.7%", "8.0 / 16.6", "5.3%"],
      ["coding", "98", "9.2% / 99.0%", "10.6 / 20.8", "2.0%"], ["all", "482", "3.1% / 95.0%", "11.2 / 22.0", "6.4%"]],
     [1.8, 0.5, 1.6, 1.4, 1.2]),
    ("tbl", "Per-rule agreement with the dataset's optimized prompts (test)", ["Rule", "Precision", "Recall", "F1"],
     [["B01 remove filler", "1.000", "1.000", "1.000"], ["B03 output format", "0.824", "0.662", "0.734"],
      ["B04 length", "0.827", "0.315", "0.456"], ["B05 language", "0.925", "0.949", "0.937"],
      ["B06 labels", "0.578", "0.649", "0.612"], ["B07 data moved", "0.298", "0.824", "0.438"],
      ["B08 group fallback", "0.732", "0.524", "0.611"]],
     [2.6, 1.2, 1.2, 1.2]),
    ("p", "The per-rule table measures agreement with the LLM-written targets of the dataset, not with a human gold "
          "standard: a reasonable addition that the LLM left out counts against the rule. Low recall for B04 and B08 is "
          "largely by design, because lengths are added only above the confidence gate and only where they matter."),
    ("tbl", "Stage C: zero-shot base model vs LoRA (964 test examples)", ["Model", "Valid JSON", "Exact keys", "Passes the checker", "Task similarity"],
     [["Qwen2.5-0.5B, zero-shot", "93.5%", "51.2%", "5.0%", "0.668"], ["Qwen2.5-0.5B + LoRA", "100%", "100%", "98.2%", "0.801"]],
     [2.2, 1.0, 1.0, 1.3, 1.1]),
    ("tbl", "Other components", ["Component", "Measure", "Result"],
     [["Coding (29 Python test items)", "pass@1 strict / lenient", "strict 34.5% (vague 20.7%); lenient 41.4% (vague 37.9%)"],
      ["Attachment rules (30 hand-made prompts)", "right rule only, in every rendering", "30/30"],
      ["Image mode (30 held-out prompts, Stable Diffusion 1.5)", "CLIP similarity to the request", "original 33.08, v1 30.78 (worse, p = 0.043), v2 32.77"]],
     [2.4, 1.9, 2.2]),
    ("h2", "7.4 Result analysis"),
    ("p", "Where the saving comes from. The optimized prompt is slightly longer, but the answer is much shorter. The "
          "review example shows the mechanism on one prompt (166 output tokens fall to 41), and the test split shows it "
          "on 482 prompts (682 output tokens fall to 165). A stated format and length stop the model from writing long, "
          "unrequested answers. For a model that prices output higher than input, the money saving is larger than the "
          "token saving."),
    ("p", "When it costs more. Prompts whose answer is already short can cost more: the added format line costs input "
          "tokens without shortening the answer. In Compare, a one-line closed_qa answer cost 17.2% more. Of the 482 "
          "test prompts, 87 cost more, mostly short extractions."),
    ("p", "Correctness. Optimization helped most where the vague prompt left the expected answer shape open: all ten "
          "extraction cases and all ten closed_qa cases were correct with the optimized prompt. The suite viewer of the "
          "application shows each case with its gold answer and both answers side by side."),
    ("pair", "ui_suite.png", "Test suite: correctness summary and the case grid",
             "ui_suite-case.png", "One case (cqa-01): gold answer 80300; the vague answer was wrong, the optimized right"),
    ("p", "Honest failures. The four cases where optimization made a correct answer wrong each have a clear cause:"),
    ("bul", [
        "cls-09: Stage A read an attendance table as code (coding, 0.84, above the gate), so B05 and B03 asked for "
        "code; the model returned a Python script instead of a label per student. Choosing the category in the "
        "application avoids it.",
        "sum-06: B03 turned “4-5 lines” into “Use bullet points”; the bulleted answer had every key fact "
        "but 92 words against a 90-word limit.",
        "sum-10: only B07 fired, so the request was the same as the vague one; the answer added a title line and "
        "reached 83 words against 80. A near miss, not a rule effect.",
        "cod-10: routed to Stage C, which added only a code-block format; the model's fraction handling was wrong in "
        "4 of 8 hidden tests although the specification was identical in both prompts.",
    ]),
    ("p", "Stage A is the main weak spot. Closed_qa, information_extraction and summarization are hard to tell apart on "
          "vague prompts (F1 0.51-0.65), partly because Dolly's labels in this group are noisy. The 0.6 gate, the group "
          "rule B08 and the user's confirmation keep these errors from turning into wrong formats. The Results page of "
          "the application collects these numbers from the final results file."),
    ("pair", "ui_results.png", "Results page: headline numbers, read from the final results file",
             "ui_optimize-stagec.png", "A rejected Stage C answer: the checker failed, so Stage B's result is kept"),
    ("p", "Image mode. Version 1 inserted default keywords for every missing attribute (for example “natural "
          "lighting”), which pulled Stable Diffusion images away from the request: CLIP similarity fell from 33.08 "
          "to 30.78 on 30 held-out prompts (p = 0.043). Version 2 keeps the user's words first and offers missing "
          "attributes only as clickable suggestions; it shows no measurable harm (32.77) and keeps the requested style "
          "in 12 of 12 styled prompts."),
    ("h2", "7.5 GUI images and screenshots"),
    ("p", "The application runs as a FastAPI server that also serves the React user interface. The screens below are "
          "the ones not already shown in Section 7.1."),
    ("fig", "ui_optimize.png", "Optimize with a coding example: B07, B05 and B03 fire; Stage C is skipped", 4.6),
    ("p", "Optimize with the coding example “write code to get all permutations of a string”: Stage A is sure "
          "(coding, 1.00), Stage B adds “Use Python.” and “Return only the code, in a single code block.”, "
          "and Stage C is skipped because nothing is unresolved."),
    ("fig", "ui_compare-result.png", "Compare on the coding example: 248 tokens instead of 768 (−67.7%), both answers pass 6 of 6 tests", 5.0),
    ("pair", "ui_how.png", "How it works: the pipeline explained inside the application",
             "ui_history.png", "History: search, view and delete; prompts expire after 30 days"),
    ("pair", "ui_image.png", "Image mode: the user's words are kept, missing attributes are suggestions",
             "ui_status.png", "Status: providers with 24-hour usage, Stage C device, sandbox"),
    ("h2", "7.6 Screenshots of the GitHub project upload"),
    ("p", "The code is public at https://github.com/piush365/PromptOpt."),
    ("fig", "gh_repo.png", "GitHub repository piush365/PromptOpt: branches, tags and top-level folders", 5.4),
    ("pair", "gh_release.png", "Release v1.0 with the Stage C adapter and the Stage A index",
             "gh_branches.png", "Branches: main (default), ui-v2, correctness-suite"),
    ("h2", "7.7 Use of Git and GitHub"),
    ("tbl", "Git and GitHub usage", ["Item", "Value"],
     [["Repository", "github.com/piush365/PromptOpt (public)"],
      ["Commits (all branches)", "102 (main 99; ui-v2 3 ahead of main with the final report and deck updates; correctness-suite merged into main)"],
      ["Branches", "main (default), ui-v2 (React user interface), correctness-suite"],
      ["Tags", "frozen-for-test (code for the final numbers), final-for-test (test split run once), v1.0 (release), pre-ui-v2"],
      ["Release", "PromptOpt v1.0: Stage C adapter, Stage A category index, Stage C data manifest"],
      ["Work tracking", "roadmap and phase tables in the repository, tags as evaluation checkpoints, one release; GitHub Issues and Projects were not used"]],
     [1.8, 4.7]),
    ("fig", "chart_commits.png", "Commits per week (all branches)", 4.6),
    ("p", "Tags were used as evaluation checkpoints: frozen-for-test marks the code that produced the final test "
          "numbers; after it, no Stage A or Stage B rule, threshold or judge was changed, and the freeze check proves it."),
    ("h2", "7.8 Challenges faced and how we solved them"),
    ("tbl", "Challenges and solutions", ["Challenge", "What happened", "How we solved it"],
     [["Dataset quality", "LLM-written optimized prompts dropped data from the instruction or changed the task", "automatic checks, deterministic repair with a log, human rating and an LLM-assisted filter"],
      ["Kappa paradox", "raters agreed on 89-94% of rows, but Fleiss' kappa was near 0 because 96-98% of answers were yes", "reported Gwet's AC1 (0.92-0.96) next to kappa and explained the paradox"],
      ["Free API quotas", "Groq 200,000 tokens per day per model; Cerebras 150 requests per hour", "rolling 24-hour usage ledger, pacing, a 70% budget rule, resumable runs"],
      ["Stage C hallucination", "the zero-shot model passed the checks in only 5% of cases and could keep “this”", "LoRA fine-tuning (98.2%), a strict JSON contract, the checker and a fallback to Stage B"],
      ["Image mode v1", "default keywords turned a watercolor request into a photo", "version 2: the user's words first, defaults only as suggestions"],
      ["Regex edge cases", "“thank you so much” inside a button text; “tell me X or Y” labels", "a unit test per edge case; B16 wider label detection in the application"],
      ["4 GB GPU", "fine-tuning and serving on a laptop GPU", "micro-batch 1 × 16, bf16, gradient checkpointing; models loaded once"]],
     [1.4, 2.5, 2.6]),
])

# ====================================================================== 8 Conclusion
CONCLUSION = ("Conclusion", [
    ("p", "PromptOpt shows that a cheap, explainable, rule-first optimizer can make vague prompts clearer and cheaper. "
          "The review example summarises the whole system: Stage A notices that the task type is uncertain and that "
          "no answer format is given, Stage B removes the filler without guessing, Stage C supplies the missing format "
          "and asks the user to confirm the category, and the same model then answers in 162 instead of 270 tokens. "
          "On 482 held-out test prompts, measured on " + GPT + ", optimized prompts reduce input + output tokens by "
          "39.2% per prompt (95% CI 35.9-42.5%): input grows from 226 to 241 tokens, while output falls from 682 to "
          "165. The output format is stated in 95.0% of prompts instead of 3.1%, and on the benchmark quality rises "
          "from 8.2 to 9.0 and task success from 67% to 85%. A small LoRA model, trained on a 4 GB laptop GPU, helps "
          "exactly where the rules stop (format stated on 90.3% of routed prompts instead of 22.6%) and is kept out of "
          "everything else. The working application (FastAPI + React: a simple app with token usage analysis and history, "
          "a developer view with every stage, and a ten-table database with one commit per request) is covered by 720 unit test cases (60 for each of 12 modules) and 16 browser "
          "tests, all passing."),
    ("h2", "Limitations of the proposed solution"),
    ("bul", [
        "All output-token, quality and correctness numbers come from OpenAI's GPT model gpt-oss-120b on free tiers; "
        "Claude and Gemini were not run, and their input-token counts are approximate.",
        "Input tokens grow in every category; 87 of 482 test prompts cost more in total because their answer was already short.",
        "Stage A reaches 74.7% category accuracy; closed_qa, information_extraction and summarization remain hard to separate.",
        "Correctness suite: 42/50 vs 37/50 is not statistically significant (p = 0.267) and was not reproduced on a second provider (41 vs 43).",
        "Stage C is trained on LLM-written targets, and the routed test set is small (31 prompts).",
        "Attachment and image results are on developer-written prompts only; coding tests cover Python only (29 items).",
        "The kappa target for dataset validation was not met (the kappa paradox), although raw agreement and AC1 are high.",
    ]),
    ("h2", "Future scope and possible extensions"),
    ("bul", [
        "Lean mode for short-answer prompts: add only the format line, or nothing, when the expected answer is short.",
        "Send label-set and typo-heavy prompts to Stage C; spelling normalisation that the user confirms.",
        "Blind user tests with prompts written by people outside the team (the attachment and image test sets are ready).",
        "Compare and the full evaluation on GPT, Claude and Gemini through their paid APIs.",
        "A larger correctness suite, with more cases per category and more providers, to reach statistical significance.",
        "Deployment beyond the local network (PostgreSQL, HTTPS, login); coding tests beyond Python.",
    ]),
])
