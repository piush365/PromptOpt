# PromptOpt

Final-year Mini Project-I (7CS345), WCE Sangli. A lightweight, self-hosted system that rewrites vague user prompts
into clear, structured, token-efficient prompts for LLMs, and measures whether the rewrite actually helps.

## Pipeline
- **Stage A, feature detection:** task category, missing output format, missing constraints (length/tone/audience/language),
  filler/redundancy, ambiguous references. spaCy + regex + Sentence-Transformers. Output: PromptFeatures (Pydantic).
- **Stage B, rule-based optimization:** deterministic, independently testable rules (codes B01-B13 in `backend/app/db/seed.py`;
  B09-B13 are the attachment modifier, one rule per attachment type).
  Category-specific rules (B03-B06) apply only when Stage A's category confidence is >= 0.6. Below that, B08 is the
  group-level fallback: if closed_qa + information_extraction + summarization together reach 0.6 and text is attached,
  it adds "Answer from the provided text in at most three sentences." (only the missing parts) and resolves the
  category at group level.
  Every change is logged for explainability.
- **Stage C, LoRA fallback:** small fine-tuned model (Qwen2.5-0.5B-Instruct or Phi-3 Mini), used ONLY when Stage B
  leaves something unresolved that Stage C can fix: the task category (still unresolved after the 0.6 gate and B08)
  or an ambiguous reference (`STAGE_C_REASONS` in `backend/app/stage_b/optimizer.py`). A missing label set or format
  is recorded but does not route; the confidence score is stored, not used for routing. Stage C patches the
  unresolved fields, not the whole prompt.
- **IR + rendering:** the result becomes a model-agnostic intermediate representation (`app/stage_b/ir.py`: task,
  context, context_ref, constraints, requirements, output_format, attachment, target_llm, category_source, unresolved),
  rendered per target LLM by `app/rendering.py` (Claude XML tags, GPT markdown sections, Gemini labelled sections;
  tests parse every rendering back to check no field is lost). A user-selected category overrides Stage A
  (`optimize(..., category=...)`). `app/pipeline.py` runs one request end to end and saves the renderings.
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
| 4 | Coding test-case generation, validated against the reference solution, plus a sandboxed runner | Not started |
| 5 | Evaluation on val with Groq stand-in models | Not started (harness in `app/evaluation/` is built) |
| 6 | Validation results -> retrain classifier -> train Stage C LoRA | Not started |
| 7 | Ablation, then final test/benchmark evaluation (once, on Groq stand-ins) | **CURRENT**: Stage A retrained on final train; test split run once offline (Stage A 74.7%, macro-F1 0.746; Stage C 6.4%); benchmark LLM eval done (stage_b vs degraded: quality 9.0 vs 8.2, task success 85% vs 67%, total tokens -57%). Ablation not started |
| 8 | FastAPI + React app with history | Not started |
| 9 | Phase 2: image generation | Not started |

### Later, needs API keys (after step 7)
- Compare: original vs optimized prompt on the real target LLM (GPT, Gemini, Claude).
- Real-LLM evaluation: repeat the val/test/benchmark evaluation per target LLM.
