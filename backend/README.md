# PromptOpt backend: database layer

PostgreSQL in deployment, SQLite during development, both through the SQLAlchemy ORM.
The same code runs on both; only `DATABASE_URL` changes.

## Setup

```bash
pip install -r requirements.txt

# SQLite (default): creates ./promptopt.db
python -m app.init_db

# PostgreSQL
export DATABASE_URL="postgresql+psycopg://promptopt:<password>@localhost:5432/promptopt"
python -m app.init_db
```

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

11 tests: the full pipeline flow, PII stripping, retention purge with cascade, the LoRA step, input validation, database constraints and the evaluation summary.

`schema_postgres.sql` is the generated PostgreSQL DDL (`python -m app.init_db --sql`), for the report or for creating the schema by hand.
