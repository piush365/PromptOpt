# PromptOpt

Final-year Mini Project-I (7CS345), WCE Sangli. A lightweight, self-hosted system that rewrites vague user prompts
into clear, structured, token-efficient prompts for LLMs, and measures whether the rewrite actually helps.

## Pipeline
- **Stage A, feature detection:** task category, missing output format, missing constraints (length/tone/audience/language),
  filler/redundancy, ambiguous references. spaCy + regex + Sentence-Transformers. Output: PromptFeatures (Pydantic).
- **Stage B, rule-based optimization:** deterministic, independently testable rules (codes B01-B08 in `backend/app/db/seed.py`).
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
- **IR + rendering:** the result becomes a model-agnostic intermediate representation (task, context, constraints,
  requirements, output_format), rendered differently per target LLM (e.g. XML tags for Claude, markdown for GPT).
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

## Backend (`backend/`)
- Python + FastAPI (to be built), SQLAlchemy 2.0 ORM.
- Database: SQLite for development (default, `backend/promptopt.db`), PostgreSQL for deployment. Switch with `DATABASE_URL`.
- `app/db/models.py`: 10 tables. `app/db/repository.py`: the data entry module; the pipeline reads/writes ONLY through it.
  Functions flush but do not commit; the caller commits once per request.
- Privacy: `create_prompt` strips emails/phone numbers BEFORE storing. Every prompt has `expires_at`
  (RETENTION_DAYS, default 30); `python -m app.init_db --purge` deletes expired prompts with cascade.
- Commands (run inside `backend/` with `.venv` active):
  - `python -m app.init_db`: create tables and seed rules (safe to re-run)
  - `python -m pytest -q`: tests on SQLite; set `TEST_POSTGRES_URL` to also test PostgreSQL
  - `TEST_POSTGRES_URL` must point at the `promptopt_test` database only: the tests drop all tables.

## Conventions
- Never commit secrets: passwords and API keys go in `.env` (git-ignored). Never hard-code the Groq key.
- Keep every Stage B rule a separate, unit-tested function.
- New features come with tests; run the full test suite before saying something works.
- Environment: Fedora 44, zsh, Python 3.14 venv at `backend/.venv`.