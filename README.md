# PromptOpt

A lightweight, self-hosted system that rewrites vague prompts into clear, structured, token-efficient prompts for LLMs, and then **measures whether the rewrite actually helps**.

Final-year Mini Project-I (7CS345), Walchand College of Engineering, Sangli. Results: [`evaluation/FINAL_RESULTS.md`](evaluation/FINAL_RESULTS.md).

## What it does

You type a prompt, pick the target LLM (GPT, Gemini or Claude), a category (auto-detect or one of five) and, optionally, an attachment type. PromptOpt returns the prompt rewritten for that model, explains every change, and can run the original and the optimized prompt side by side on a real model (**Compare**).

| Stage | What it does | How |
|---|---|---|
| **A: feature detection** | Task category, missing output format, missing constraints (length/tone/audience/language), filler, ambiguous references | spaCy + regex + Sentence-Transformers → `PromptFeatures` |
| **B: rule-based optimization** | Deterministic, individually testable rules B01–B15 (B09–B15: attachments). Every change is logged | Category rules only at ≥ 0.6 confidence, with a group-level fallback (B08) |
| **C: LoRA fallback** | Fills only what Stage B could not resolve (an ambiguous reference, or format/constraints when the category is unclear); the category itself is only suggested to the user | Qwen2.5-0.5B-Instruct + LoRA, validated output, falls back to Stage B |
| **IR + rendering** | One intermediate representation, rendered per target, same content everywhere | Claude XML tags · GPT `###` sections · Gemini labelled sections; tests round-trip every rendering |
| **Image mode** | Separate, explicitly chosen "Image generation" category for DALL-E, Nano Banana (Gemini image) and Stable Diffusion | Keeps the user's words; missing attributes become clickable suggestions |
| **Compare** | Original vs optimized prompt on the same model: answers, tokens (incl. reasoning), latency, sandbox tests for coding, optional blind judge | Groq / Cerebras gpt-oss now; Gemini with a key; GPT/Claude once keys are added |

Categories: `closed_qa`, `information_extraction`, `classification`, `summarization` (from Dolly-15k), `coding` (from CodeAlpaca-20k), and `other`.

## How to run the app

Linux (developed on Fedora 44), Python 3.14.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python -m spacy download en_core_web_sm

python -m app.stage_a.build_index      # Stage A's category index (from the dataset's train split; once)
python -m app.init_db                  # create the database tables and seed the rules (safe to re-run)
uvicorn app.api:app                    # then open http://127.0.0.1:8000
```

The optimizer itself runs fully offline. Without the dataset (it is not in the repo), Stage A falls back to a keyword classifier.

**Optional extras**

| Feature | What it needs |
|---|---|
| Stage C (LoRA) in the app | A CUDA venv with `transformers` and `peft` (`backend/.venv-gpu`, see `docs/STAGE_C_PLAN.md`) and the trained adapter in `backend/artifacts/stage_c_adapter`; start the app from that venv. Without them the app uses Stage A + B only and says so |
| Compare | API keys in `backend/.env` (never committed): `GROQ_API_KEY`, `CEREBRAS_API_KEY` (free tiers, gpt-oss-120b), optionally `GEMINI_API_KEY` (Google AI Studio). GPT and Claude show "add API key" until clients and keys are added. Compare stays within 70% of each free daily limit and caches answers |
| Sandbox tests in Compare | `bubblewrap` (`bwrap`): generated code runs with no network and a read-only system; without bwrap the runner refuses to run code |
| Generating tests for new coding prompts | `CEREBRAS_API_KEY` (tests are marked unvalidated: there is no reference solution) |

**In the browser:** type a prompt, choose target and category, *Optimize*. The page shows Stage A's findings, the rules that fired, whether Stage C was used, the prompt for each target with its input tokens, and the history (kept 30 days). Choose a model under *Run on* and press *Compare* to run both prompts. For image prompts, pick *Image generation* as the category; click the suggestion chips to add lighting, style, etc.

**API:** `POST /api/optimize`, `POST /api/compare`, `GET /api/compare/models`, `GET /api/history`, `GET /api/history/{id}`, `POST /api/coding-tests`, `GET /api/options` (FastAPI docs at `/docs`).

## Tests and evaluation

```bash
python -m pytest -q                    # ~740 tests, offline (recorded responses, no live API calls)
python -m app.freeze_check             # Stage A/B byte-identical to the frozen final-for-test tag
python -m app.demo --examples          # offline end-to-end demo in the terminal
```

Evaluation commands are listed in [`CLAUDE.md`](CLAUDE.md) and in each report's header. Reports: [`evaluation/FINAL_RESULTS.md`](evaluation/FINAL_RESULTS.md) (summary), `evaluation/token_test.md`, `stage_c_eval.md`, `coding_tests.md`, `image_mode.md`.

## Dataset

Degraded → optimized prompt pairs built from Dolly-15k and CodeAlpaca-20k, split into train/val/test/benchmark with no instruction shared across splits; human-validated sample and LLM-assisted filter. See [`docs/DATASET_CARD.md`](docs/DATASET_CARD.md). The dataset is kept out of the repo (Google Drive).

## Repo layout

```
backend/app/         Stage A/B/C, IR + rendering, pipeline, API + web UI (static/), DB layer,
                     coding/ (sandbox, tests), image/ (image mode), compare/ (providers), evaluation/
backend/tests/       offline test suite
docs/                dataset card, Stage C plan, coding tests, category templates, milestone review
evaluation/          all reports; FINAL_RESULTS.md is the summary
notebooks/           Stage C training notebook (Colab), dataset analysis
```

More detail on the backend and database: [`backend/README.md`](backend/README.md).
