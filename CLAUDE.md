# PromptOpt

Final-year Mini Project-I (7CS345), WCE Sangli. A lightweight, self-hosted system that rewrites vague user prompts
into clear, structured, token-efficient prompts for LLMs, and measures whether the rewrite actually helps.

## Pipeline
- **Stage A, feature detection:** task category, missing output format, missing constraints (length/tone/audience/language),
  filler/redundancy, ambiguous references. spaCy + regex + Sentence-Transformers. Output: PromptFeatures (Pydantic).
- **Stage B, rule-based optimization:** deterministic, independently testable rules (codes B01-B15 in `backend/app/db/seed.py`;
  B09-B15 are the attachment modifier, one rule per attachment type: image, pdf, pptx, docx, other, spreadsheet, code;
  B14/B15 were added after the freeze and fire only when that attachment type is given; also after the freeze, B05
  gives a coding prompt with a data attachment (spreadsheet, PDF, image, ...) the default language instead of "Keep the
  language of the given code"). Any change after the freeze must keep `python -m app.freeze_check` byte-identical
  (Stage A + B on the test split vs `frozen-for-test`, no attachment).
  Category-specific rules (B03-B06) apply only when Stage A's category confidence is >= 0.6. Below that, B08 is the
  group-level fallback: if closed_qa + information_extraction + summarization together reach 0.6 and text is attached,
  it adds "Answer from the provided text in at most three sentences." (only the missing parts) and resolves the
  category at group level.
  Every change is logged for explainability.
- **Stage C, LoRA fallback:** small fine-tuned model (Qwen2.5-0.5B-Instruct or Phi-3 Mini), used ONLY when Stage B
  leaves something unresolved that Stage C can fix: the task category (still unresolved after the 0.6 gate and B08)
  or an ambiguous reference (`STAGE_C_REASONS` in `backend/app/stage_b/optimizer.py`). A missing label set or format
  is recorded but does not route; the confidence score is stored, not used for routing. Stage C patches the
  unresolved fields, not the whole prompt. Plan, data format, known limitations and evaluation: `docs/STAGE_C_PLAN.md`.
  Data: `python -m app.stage_c.data` (targets parsed from optimized prompts by `app/stage_c/parse.py`; Stage A on train
  cross-fitted) -> `data/stage_c/` + `data/stage_c_data_v1.zip` (git-ignored; manifest committed as
  `docs/stage_c_data_manifest.json`). Training: `app/stage_c/train.py`, locally in `backend/.venv-gpu` (CUDA torch;
  `.venv` stays CPU-only) or Colab `notebooks/train_stage_c.ipynb` (zip from `MyDrive/PromptOpt/stage_c/`).
  Category policy: when routed for the task category, Stage C's category is only a suggestion (the UI asks the user,
  pre-selecting it); its format/constraints are applied (`contract.category_decision`; plan section 6).
  Runtime + contract: `app/stage_c/runtime.py`, `app/stage_c/contract.py`; the app uses Stage C when the adapter is in
  `backend/artifacts/stage_c_adapter` and peft/transformers are installed (run the app from `.venv-gpu` for that).
  Evaluation: `python -m app.stage_c.evaluate --adapter artifacts/stage_c_adapter --out ../evaluation/stage_c_eval.md`.
- **IR + rendering:** the result becomes a model-agnostic intermediate representation (`app/stage_b/ir.py`: task,
  context, context_ref, constraints, requirements, output_format, attachment, target_llm, category_source, unresolved),
  rendered per target LLM by `app/rendering.py` with four sections, same content everywhere (Claude: XML tags, context
  first; GPT: `### Task / Context / Constraints / Output format`; Gemini: plain labels, instruction first, context
  last; requirements are listed first under constraints); tests parse every rendering back to check no field is lost.
  `token_counts` gives input tokens per target (GPT exact with tiktoken o200k_base, Claude/Gemini approx. chars/4,
  labelled). A user-selected category overrides Stage A (`optimize(..., category=...)`); `app/pipeline.py` runs one
  request end to end, saves the renderings and returns Stage A's own category and `category_disagreement`.
  Per-category templates: `docs/CATEGORY_TEMPLATES.md` (`python -m app.templates_doc`). Attachment rules on 30
  hand-made prompts: `evaluation/attachment_test.md` (`python -m app.attachment_eval`); the team's blind set
  (`evaluation/attachments/blind_test.csv`, instructions next to it) is reported separately with `--blind` in
  `evaluation/attachment_blind_test.md`. Named Stage C cases: `evaluation/stage_c/named_cases.json`.
- **Groq usage:** every Groq call records its tokens and cached tokens (failed JSON calls estimated) in
  `data/groq_usage.json`, over a rolling 24 hours like Groq's own limit; dataset generation stays within
  `--budget-fraction` (0.7) of each model's limit. Whether Groq counts cached tokens is not verified yet
  (`COUNT_CACHED = True` until measured); `generate --usage-log 10` writes the per-call token breakdown.
- **Evaluation:** net token change (input AND output), rubric quality score, task success on verifiable tasks, cost,
  latency, plus an ablation study. Target LLMs are treated as black boxes.

Priority order: rule-based optimizer -> evaluation harness -> ablation -> IR/rendering -> LoRA (optional, last).

## Categories (fixed)
closed_qa, information_extraction, classification, summarization (from Dolly-15k), coding (from CodeAlpaca-20k), plus
`other` for anything Stage A cannot place.

## Dataset
PromptOpt Dataset v1 is built in Colab (`PromptOpt_Dataset_Preparation_v2.ipynb`) and saved to Google Drive
(`MyDrive/PromptOpt/promptopt_dataset_v1`): degraded_prompt -> optimized_prompt pairs, splits train/val/test/benchmark,
no instruction shared across splits. The dataset is NOT stored in the database.
v1.1 (`data/promptopt_dataset_v1_1/`) is v1 with dropped instruction data put back:
`python -m app.dataset_repair --write` appends lost items/code deterministically, removes rows whose data exists
nowhere, and fixes dropped subjects with cached Groq edits (`regenerated.json`); every change is in `repair_log.csv`.
v1.2 final (`data/promptopt_dataset_v1_2_final/`, the default `DATASET_DIR`; `DATASET_CSV` = `<folder>/<folder>.csv`) is
v1.2 minus human-rejected and LLM-assisted-filter rows (`docs/DATASET_CARD.md`).

## Backend (`backend/`)
- Python + FastAPI (to be built), SQLAlchemy 2.0 ORM.
- Database: SQLite for development (default, `backend/promptopt.db`), PostgreSQL for deployment. Switch with `DATABASE_URL`.
- `app/db/models.py`: 10 tables. `app/db/repository.py`: the data entry module; the pipeline reads/writes ONLY through it.
  Functions flush but do not commit; the caller commits once per request.
- Privacy: `create_prompt` strips emails/phone numbers BEFORE storing. Every prompt has `expires_at`
  (RETENTION_DAYS, default 30); `python -m app.init_db --purge` deletes expired prompts with cascade.
- Commands (run inside `backend/` with `.venv` active):
  - `python -m app.init_db`: create tables and seed rules (safe to re-run)
  - `python -m app.demo --examples [--target claude]`: offline demo (Stage A features, Stage B rules before/after,
    Stage C routing); `docs/MILESTONE_REVIEW.md` has the review checklist
  - `python -m pytest -q`: tests on SQLite; set `TEST_POSTGRES_URL` to also test PostgreSQL
  - `TEST_POSTGRES_URL` must point at the `promptopt_test` database only: the tests drop all tables.

## Conventions
- Never commit secrets: passwords and API keys go in `.env` (git-ignored). Never hard-code the Groq key.
- Keep every Stage B rule a separate, unit-tested function.
- New features come with tests; run the full test suite before saying something works.
- Environment: Fedora 44, zsh, Python 3.14 venv at `backend/.venv`.

## Product goals
- The user enters any prompt and selects:
  1. Target LLM: GPT, Gemini or Claude.
  2. Category: one of the 5, or auto-detect. A user choice overrides Stage A.
  3. Optional attachment type (image, PDF, PPTX, ...) as a modifier, NOT a new category.
- Core feature, **Compare**: original vs optimized prompt on the chosen LLM, side by side: answers, input/output/total
  tokens, cost, latency, judge score. Plus a history of past prompts (30-day retention).
- Phase 2 (only after the core works): image-generation prompts (Nano Banana, DALL-E) as a sixth category.

## Freeze for the final numbers
Git tag `frozen-for-test` (2026-09-27) is the code Monday's test and benchmark runs use. From that tag until those
runs are done: no Stage A/B rule, threshold or judge change. If a bug turns up, report it; do not fix it. Only data
steps are allowed (merging ratings, dropping rejected rows, retraining the Stage A classifier's index on the final
train split); pass the final dataset with `--dataset`/`DATASET_DIR`, not by editing code.

## Roadmap (strict order)
Work only on the current step unless the user says otherwise. Development evaluation uses Groq models as stand-ins for
the target LLMs; real GPT/Gemini/Claude runs need API keys and come later.

| # | Step | Status |
|---|------|--------|
| 1 | Dataset v1.1 repair, then send rater sheets | Done: team 3 x 170 and faculty 20 rated; 295 of 330 accepted; v1.2 final = 5,184 rows (35 human-rejected + 9 LLM-assisted-filter rows left out); `evaluation/REVIEW_SUMMARY.md` |
| 2 | Expand dataset to ~1,000 per category (frozen splits) | Done: v1.2 = 5,228 rows (1,009-1,093 per category); test 100 per category (extra rows only from new v1.2 rows), val 30, benchmark 10; `docs/DATASET_CARD.md`. The default dataset is now v1.2 final (`config.DATASET_DIR` / `DATASET_CSV`), so no command needs `--dataset` |
| 3 | IR + renderers for GPT/Gemini/Claude, user-selected category + attachment modifier | Done (started early, in parallel with step 2) |
| 4 | Coding test-case generation, validated against the reference solution, plus a sandboxed runner | Finish phase 4: `app/coding/` (bwrap sandbox, Cerebras-generated asserts validated on the reference, naming discovery); method `docs/CODING_TESTS.md`, results `evaluation/coding_tests.md` |
| 5 | Evaluation on val with Groq stand-in models | Not started (harness in `app/evaluation/` is built) |
| 6 | Validation results -> retrain classifier -> train Stage C LoRA | Done (finish phases 1 and 3): LoRA trained locally, best val loss 0.7047 at step 550 (early stop at 700); `evaluation/stage_c_eval.md` |
| 7 | Ablation, then final test/benchmark evaluation (once, on Groq stand-ins) | Done: final test run once on 2026-10-02, tag `final-for-test`; `evaluation/FINAL_RESULTS.md` (Stage A 74.7%; Stage B format 3.1% -> 95.0%, 6.4% routed; Stage C ablation: helps on routed prompts only; benchmark: quality 8.2 -> 9.0, task success 67% -> 85%, tokens -57%) |
| 8 | FastAPI + web app with history | Done (finish phase 3): `uvicorn app.api:app` in `backend/`, plain HTML/JS in `app/static/`, Compare disabled until API keys |
| 9 | Phase 2: image generation | Not started |

### Finish phase (started 2026-10-02; due Sunday 2026-10-04, buffer to Thursday 2026-10-08)
Product goal unchanged: prompt + target LLM + category (auto/5) + optional attachment type -> optimized, model-specific
prompt. Image generation out of scope; no paid APIs (Groq/Cerebras within quota). Stage A/B rules stay unchanged; new
attachment rules may be added only if they fire ONLY when an attachment type is given (prove it: Stage B test metrics
offline identical to the frozen ones). Tune new things on val only; the test split runs once at the very end, then tag
`final-for-test`. Commit after every phase.

| Phase | Work | Status |
|---|---|---|
| 1 | Stage C data (parser coverage: task 100%, format 94.0%, constraints 75.0%, accepted), Colab notebook, `docs/STAGE_C_PLAN.md` | Done; trained locally (`.venv-gpu`, RTX 3050, micro-batch 1 x 16, bf16, 51 min); adapter in `backend/artifacts/stage_c_adapter` (git-ignored); Colab not needed |
| 2 | Renderers per target + token counts, category override with disagreement shown, attachment types (image, pdf, pptx, docx, spreadsheet, code file) with a 30-prompt hand-made test set, category templates | Done: attachments 30/30 correct; Stage B on test byte-identical to frozen-for-test (482 prompts) |
| 3 | Integrate Stage C under the routing contract; val eval (base vs LoRA, ablation A+B / A+B+C / C-only, routed + forced); FastAPI + plain HTML/JS UI (Compare button disabled) | Done: LoRA passes validation 98.3% vs zero-shot 3.4%; routed prompts: format stated 10% -> 90%, task intent 0.911 -> 0.885; forced routing lowers task intent (0.855 -> 0.773), so Stage C stays routed-only; GPU 0.72 s median, CPU 5.0 s; `evaluation/stage_c_eval.md`. Final test run done: `evaluation/FINAL_RESULTS.md`, tag `final-for-test` |

- **Coding tests (phase 4):** `python -m app.coding.testgen` (items + validated tests, Cerebras, cached in
  `data/coding/`), `python -m app.coding.evaluate --out ../evaluation/coding_tests.md` (pass@1 degraded vs Stage B).
  Code only ever runs through `app.coding.sandbox.run_python` (bwrap: no network, read-only system; refuses to run
  without bwrap unless `SANDBOX_REQUIRE_BWRAP=0`).

### Later, needs API keys (after step 7)
- Compare: original vs optimized prompt on the real target LLM (GPT, Gemini, Claude).
- Real-LLM evaluation: repeat the val/test/benchmark evaluation per target LLM.
