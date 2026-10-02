# PromptOpt

A lightweight, self-hosted system that rewrites vague prompts into clear, structured, token-efficient prompts for LLMs, and then **measures whether the rewrite actually helps**.

Final-year Mini Project-I (7CS345), Walchand College of Engineering, Sangli.

## Pipeline

| Stage | What it does | How |
|---|---|---|
| **A: feature detection** | Task category, missing output format, missing constraints (length/tone/audience/language), filler, ambiguous references | spaCy + regex + Sentence-Transformers → `PromptFeatures` |
| **B: rule-based optimization** | Deterministic, individually testable rules B01–B13. Every change is logged so it can be explained | Category rules apply only at ≥ 0.6 confidence, with a group-level fallback (B08) |
| **C: LoRA fallback** | Patches only what Stage B couldn't resolve (the category or an ambiguous reference) | Small fine-tuned model (Qwen2.5-0.5B / Phi-3 Mini) |
| **IR + rendering** | Model-agnostic intermediate representation, rendered per target | Claude XML tags · GPT markdown · Gemini labelled sections. Tests round-trip every rendering |

**Evaluation** covers net token change (input and output), a rubric quality score, task success on verifiable tasks, cost, latency, and an ablation over the stages.

Categories: `closed_qa`, `information_extraction`, `classification`, `summarization` (from Dolly-15k), `coding` (from CodeAlpaca-20k), and `other`.

## Dataset

The dataset is a set of degraded → optimized prompt pairs built from Dolly-15k and CodeAlpaca-20k, split into train/val/test/benchmark, with no instruction shared across splits. See [`docs/DATASET_CARD.md`](docs/DATASET_CARD.md) for versions (v1 → v1.1 repair → v1.2 final) and the filtering steps.

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python -m spacy download en_core_web_sm

python -m app.init_db                          # create tables and seed the rules
python -m app.demo --examples --target claude  # offline end-to-end demo
python -m pytest -q
```

SQLite is the default. Set `DATABASE_URL` to use PostgreSQL. Stored prompts have emails and phone numbers stripped and expire after `RETENTION_DAYS` (30 by default).

## Repo layout

```
backend/     FastAPI + SQLAlchemy app: Stage A/B/C, IR, rendering, DB layer, tests
docs/        dataset card, validation guide, milestone review checklist
evaluation/  benchmark summary, Stage A/B test reports, validation and LLM-rater results
*.ipynb      dataset EDA and preparation (Dolly, CodeAlpaca)
```

More detail: [`backend/README.md`](backend/README.md).
