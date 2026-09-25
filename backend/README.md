# PromptOpt backend

Database layer, Stage A (feature detection) and the dataset validation tools.

## Database layer

PostgreSQL in deployment, SQLite during development, both through the SQLAlchemy ORM.
The same code runs on both; only `DATABASE_URL` changes.

## Setup

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU build; skip if you have a GPU setup
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env        # then fill in the real passwords; .env is git-ignored

python -m app.init_db       # uses DATABASE_URL from .env, or SQLite ./promptopt.db if it is not set
```

Settings come from `.env` (loaded by `app/config.py`); variables already set in the shell win.

`init_db` creates the tables and seeds the rule catalogue. It is safe to run again: it never duplicates rules.

## Tables

| Table | Stores |
|---|---|
| `users` | Optional user record (no email or real name is stored) |
| `prompts` | Each submitted prompt, **after PII stripping**, with `expires_at` for the retention policy |
| `prompt_features` | Stage A output: task type, missing format/constraints, redundancy, ambiguity, confidence |
| `rules` | Catalogue of Stage A detectors and Stage B transformations (`enabled` is switched off for ablations) |
| `optimization_results` | Stage B/C output: optimized text, IR (JSON), confidence, whether LoRA was used |
| `transformations` | Every change applied, in order, with the rule responsible (explainability) |
| `renderings` | The IR rendered for each target LLM |
| `token_usage` | Input/output tokens and estimated cost, before vs after |
| `lora_models` | Metadata of Stage C adapters |
| `evaluation_runs` | Offline benchmark and ablation results per dataset item, variant and LLM |

```mermaid
erDiagram
    users ||--o{ prompts : submits
    prompts ||--o| prompt_features : "analysed by Stage A"
    prompts ||--o{ optimization_results : "optimized into"
    optimization_results ||--o{ transformations : "logs"
    rules ||--o{ transformations : "applied as"
    optimization_results ||--o{ renderings : "rendered for LLM"
    optimization_results ||--o{ token_usage : "measured by"
    lora_models ||--o{ optimization_results : "used in Stage C"
    evaluation_runs }o--|| prompt_dataset_v1_files : "benchmarks items from"
```

`evaluation_runs` is deliberately not linked to `prompts`: benchmark items come from PromptOpt Dataset v1 (kept as files) and must not be deleted by the retention purge.

## Data entry module (`app/db/repository.py`)

The pipeline writes only through these functions. They flush but do not commit, so the caller commits once per request and a failure halfway through leaves nothing behind.

```python
from app.db.base import SessionLocal
from app.db import repository as repo

with SessionLocal() as db:
    prompt = repo.create_prompt(db, raw_text)                    # PII stripped, expires in 30 days
    repo.save_features(db, prompt.id, features_dict)              # Stage A
    result = repo.save_optimization(db, prompt.id, optimized_text, ir_dict, confidence, steps)
    repo.save_renderings(db, result.id, {"gpt": gpt_prompt, "claude": claude_prompt})
    repo.save_token_usage(db, result.id, "gpt", "tiktoken:o200k_base", n_before, n_after)
    db.commit()
    history = repo.get_prompt_history(db, prompt.id)             # everything done to this prompt
```

In FastAPI use the `get_db` dependency from `app/db/base.py`.

## Privacy and retention

* `create_prompt` strips emails and phone numbers **before** the prompt is stored, so raw PII never reaches the database.
* Every prompt gets `expires_at = created_at + RETENTION_DAYS` (default 30, set with the `RETENTION_DAYS` env variable).
* `python -m app.init_db --purge` deletes expired prompts; features, results, transformations, renderings and token usage are removed with them by `ON DELETE CASCADE`. Run it daily (cron job, or a FastAPI startup/background task).

## Integrity rules enforced by the database itself

* task type must be one of the 5 categories (or `other`); confidence between 0 and 1
* a Stage B transformation must name its rule; a Stage C (LoRA) one may not have one
* one rendering per target LLM per result; step numbers unique per result
* an evaluation item/variant/LLM can only be recorded once per run

## Tests

```bash
python -m pytest -q                                   # SQLite
TEST_POSTGRES_URL="postgresql+psycopg://user:pass@localhost:5432/promptopt_test" python -m pytest -q   # + PostgreSQL
```

`TEST_POSTGRES_URL` is read from `.env` too, so a plain `python -m pytest -q` runs both databases once `.env` exists.

Database tests (11 per database): the full pipeline flow, PII stripping, retention purge with cascade, the LoRA step, input validation, database constraints and the evaluation summary.

`schema_postgres.sql` is the generated PostgreSQL DDL (`python -m app.init_db --sql`), for the report or for creating the schema by hand.

## Stage A: feature detection (`app/stage_a/`)

```python
from app.stage_a import detect_features
f = detect_features("hey can you summarize this for me")
f.task_type, f.confidence, f.missing_constraints, f.redundant_phrases, f.ambiguous_refs
repository.save_features(db, prompt.id, f.model_dump())
```

| code | detector | how |
|---|---|---|
| A01 | task category (+ `other`) | Sentence-Transformers (all-MiniLM-L6-v2) k-NN over the dataset's train split, blended with keyword cues, averaged with a logistic-regression head on the same embeddings + keyword features; `classifier.py` |
| A02 | output format present? | regex, returns the matched evidence; `rules.detect_format_spec` |
| A03 | length / tone / audience / language | regex; only constraints relevant to the category count as missing (`RELEVANT_CONSTRAINTS`) |
| A04 | filler and repetition | regex phrase list, repeated sentences (spaCy sentence split), doubled words |
| A05 | ambiguous references | "summarize this", "the passage" with no context; spaCy flags pronouns with nothing before them to refer to |

The k-NN index is built from the dataset (git-ignored), so build it once after downloading the dataset into
`../data/promptopt_dataset_v1/` and Dolly-15k into `../data/dolly/` (for the `other` examples):

```bash
python -m app.stage_a.build_index        # -> artifacts/category_index.npz (~30 s on CPU)
python -m app.stage_a.evaluate --split val                                   # while tuning
python -m app.stage_a.evaluate --split test --out ../evaluation/stage_a_test.md   # final numbers only
```

The index file also holds the linear head (trained by `build_index`, needs scikit-learn; prediction is plain numpy).
Without the index, Stage A falls back to the keyword classifier (57% accuracy on val instead of 77%).
Rebuild the index whenever the dataset's train split changes.
Hyper-parameters were tuned on val only; `../evaluation/stage_a_test.md` has the test-split results.

## Stage B: rule-based optimization (`app/stage_b/`)

```python
from app.stage_a import detect_features
from app.stage_b import optimize
f = detect_features(text, context)
out = optimize(text, f)                       # out.optimized_text, out.ir, out.steps, out.confidence, out.needs_stage_c
repository.save_optimization(db, prompt.id, out.optimized_text, out.ir.model_dump(mode="json"), out.confidence, out.steps)
```

The prompt is parsed into an IR (task, context, constraints, requirements, output format, unresolved) and each rule
is a pure function `(ir, features) -> ir` in `rules.py`. Every rule that changes the text is logged as a step with the
text before and after. `optimize(..., disabled={"B04_ADD_LENGTH"})` switches rules off for the ablation study.

| code | rule | what it does |
|---|---|---|
| B07 | standardize structure | runs first: moves a code block or a `task: item, item` list into the IR context, tidies the task |
| B01 | remove filler | deletes A04's filler phrases; "can you ...?" becomes an instruction |
| B02 | remove duplicates | doubled words and repeated sentences |
| B06 | add labels | classification: states the allowed labels; "which of these ... are X" becomes yes/no |
| B05 | add language | coding: `Use Python.`, or "keep the language" when code was supplied |
| B04 | add length | closed_qa and summarization only |
| B03 | add output format | per-category default, only when A02 found no format |

Category-specific rules (B03-B06) apply only when Stage A's category confidence is at least 0.6
(`CATEGORY_MIN_CONFIDENCE`): on val, Stage A is right 77-96% of the time above that and about 50% below, and a wrong
format is worse than none. Otherwise Stage B only cleans up and marks the category unresolved. Confidence = Stage A
confidence minus 0.2 per unresolved item; below 0.7 (`STAGE_C_THRESHOLD`) the prompt goes to Stage C.

```bash
python -m app.stage_b.evaluate --split val                                    # while tuning
python -m app.stage_b.evaluate --split test --out ../evaluation/stage_b_test.md   # final numbers only
```

## Dataset validation (`app/validation.py`)

Lab assistants validate 20 records (4 per category, from the benchmark split). All three students rate the same
90-record overlap set (18 per category) for Fleiss' Kappa, and each rates 60 extra records alone, most useful first
(benchmark/test, then borderline automatic-check scores, then the noisy categories). Records are keyed by
`source_id`, never `id`. See `../docs/validation_guide.md`.

```bash
python -m app.validation assign --students <name1> <name2> <name3>   # -> ../data/validation/*.xlsx
python -m app.validation report      # progress, Fleiss' Kappa per question, accepted count
python -m app.validation merge       # dataset + validation columns -> promptopt_dataset_v1_validated.csv
```

The choice is frozen in `../data/validation/assignment.csv`: re-running `assign` after the dataset grows keeps every
record already chosen, only tops up, keeps every answer, and clears (with a note) only pairs whose text was
regenerated. `--overlap-per-category` and `--extra` change the sizes; `--reset` ignores the frozen file and chooses
again (answers already in the sheets are still kept).
