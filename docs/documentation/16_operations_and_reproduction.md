# 16. Operations: install, run, reproduce, troubleshoot

[Back to the index](README.md)

All commands run inside `backend/` unless stated. Tested from a fresh clone on Fedora 44 with Python 3.14
(`README.md`, "How to run").

---

## 16.1 Install (CPU, no GPU needed)

```bash
git clone https://github.com/piush365/PromptOpt.git && cd PromptOpt/backend
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements-lock.txt      # exact versions used for the results; CPU torch; includes en_core_web_sm
python -m app.init_db                     # SQLite at backend/promptopt.db: 10 tables, rules seeded (safe to re-run)
```

`requirements.txt` lists only direct dependencies with lower bounds (then install the CPU torch wheel first and
`python -m spacy download en_core_web_sm` after). The first run downloads `all-MiniLM-L6-v2` (about 90 MB).

**Stage A index** (optional but needed for the reported accuracy; without it the keyword classifier is used):

```bash
mkdir -p artifacts && curl -L -o artifacts/category_index.npz \
  https://github.com/piush365/PromptOpt/releases/download/v1.0/category_index.npz
# or rebuild from the train split (needs the dataset):  python -m app.stage_a.build_index
```

*Estimated rebuild time:* encoding 9,518 texts at the measured ~7.9 ms per text (batched, CPU) ≈ 75 s, plus the
logistic-regression fit.

**Stage C** (optional, GPU recommended):

```bash
python3.14 -m venv .venv-gpu && source .venv-gpu/bin/activate
pip install -r requirements-gpu-lock.txt  # CUDA build of torch; needs an NVIDIA driver
curl -L -o /tmp/stage_c_adapter.zip https://github.com/piush365/PromptOpt/releases/download/v1.0/stage_c_adapter.zip
unzip /tmp/stage_c_adapter.zip -d artifacts/
```

The base model (~1 GB) downloads on first use. CPU works too (`STAGE_C_DEVICE=cpu`, ~4.6 s instead of ~0.7 s per
routed prompt). `STAGE_C_ENABLED=0` switches it off.

**API keys** (Compare, evaluation): `cp .env.example .env` and fill in `GROQ_API_KEY`, `CEREBRAS_API_KEY`,
`GEMINI_API_KEY` (free tiers). **Sandbox:** `sudo dnf install bubblewrap` (without it, generated code is never run).

**Dataset** (not in git): put `promptopt_dataset_v1_2_final/` (Google Drive, access on request) into `data/` at the
repository root, or set `DATASET_DIR`.

## 16.2 Run

```bash
uvicorn app.api:app                       # http://127.0.0.1:8000 ; API docs at /docs ; first UI at /classic
python -m app.demo --examples             # offline terminal demo: one prompt per category, every stage
python -m app.demo "summarize this for me" --target claude
python -m app.init_db --purge             # delete expired prompts (the app also does this itself)
```

UI development: `cd frontend && npm ci && npm run dev` (proxies `/api` to port 8765); rebuild with `npm run build`.

## 16.3 Verify

```bash
python -m pytest -q                       # 777 tests, offline
python -m app.freeze_check                # Stage A/B byte-identical to frozen-for-test (needs dataset + index)
cd ../frontend && npx tsc -b && npm run e2e   # type check; end-to-end (system Chrome)
```

## 16.4 Reproduce every reported number

| report | command | needs | estimated duration (basis) |
|---|---|---|---|
| Stage A (test) | `python -m app.stage_a.evaluate --split test --out ../evaluation/stage_a/stage_a_test_final.md` | dataset, index | about a minute (3 × 482 prompts at ~8 ms + held-out `other` set) |
| Stage B (test) | `python -m app.stage_b.evaluate --split test --out ../evaluation/stage_b/stage_b_test_final.md` | dataset, index | about a minute |
| per-rule accuracy | `python -m app.stage_b.rule_accuracy --out ../evaluation/stage_b/stage_b_rule_accuracy.md` | dataset, index | about a minute |
| Stage C data | `python -m app.stage_c.data` (train/val + package); `--test` for test | dataset, index | minutes (5 cross-fitted heads) |
| Stage C training | `.venv-gpu/bin/python app/stage_c/train.py --data ../data/stage_c --out <dir> --batch-size 1` | GPU venv | **51 min** on an RTX 3050 4 GB (measured; early stop at step 700) |
| Stage C evaluation | `.venv-gpu/bin/python -m app.stage_c.evaluate --split test --adapter artifacts/stage_c_adapter --out ../evaluation/stage_c/stage_c_test.md` | GPU venv, adapter | ≈ 964 × 2 base/LoRA generations + ablation; ~0.7 s each on GPU → roughly an hour |
| attachments | `python -m app.attachment_eval --out ../evaluation/attachments/attachment_test.md` | index | seconds |
| benchmark (LLM) | `python -m app.evaluation.run --split benchmark --final --per-category 10000 --target cerebras --run-name final-benchmark` | keys | 132 Cerebras calls × 24.5 s pacing ≈ **54 min** (the recorded run: 20:24–21:20, 56 min); 132 Groq judge calls |
| full-test tokens | `.venv-gpu/bin/python -m app.evaluation.tokens --out ../evaluation/tokens/token_test.md` | keys, GPU (Stage C variant) | 995 calls × 24.5 s ≈ **6.8 h** minimum; ≈ 0.64 M tokens, so it may span two days under the 70% budget |
| coding tests | `python -m app.coding.testgen && python -m app.coding.evaluate --out ../evaluation/coding/coding_tests.md` | Cerebras key, bwrap | test generation per Python item + 58 target calls × 24.5 s ≈ 24 min |
| image mode | `.venv-gpu/bin/python -m app.image.generate --set heldout && .venv-gpu/bin/python -m app.image.evaluate --out ../evaluation/image/image_mode.md` | GPU | 30 prompts × 4 variants × ~7.5 s ≈ 15 min (+ model load) |
| correctness suite | `python -m app.correctness.cases`, `.venv-gpu/bin/python -m app.correctness.prompts`, `python -m app.correctness.run` | keys | 100 target calls per model + extractor/judge calls |
| category templates | `python -m app.templates_doc` | – | seconds |

All LLM calls are cached, so re-running a report with `--report-only` (tokens) or after a completed run costs no quota.

## 16.5 Troubleshooting

| symptom | cause | fix |
|---|---|---|
| "No category index … using keyword classifier" in the log | `artifacts/category_index.npz` missing | download or build it (16.1) |
| "spaCy model en_core_web_sm not available" | the spaCy model is not installed | `python -m spacy download en_core_web_sm` (the regex detectors still work without it) |
| Stage C card says "not installed" | no adapter, or `peft`/`transformers` missing, or `STAGE_C_ENABLED=0` | run from `.venv-gpu` with the adapter in `backend/artifacts/stage_c_adapter` |
| GPT token count labelled approximate | `tiktoken` missing or its encoding file not downloadable (offline first use) | install `tiktoken`, run once online |
| Compare: 503 "Add GROQ_API_KEY …" | key missing | add it to `backend/.env` and restart uvicorn |
| Compare: 429 | 70% of the model's daily budget used | switch model (e.g. Cerebras) or wait (rolling 24 h) |
| "bubblewrap (bwrap) is not installed … refusing to run code" | sandbox requirement | install bubblewrap (`SANDBOX_REQUIRE_BWRAP=0` only for local experiments) |
| `Dataset not found at …` | dataset not in `data/` | place it or set `DATASET_DIR` / `DATASET_CSV` |
| freeze check fails | Stage A/B output changed | diff the two JSON dumps (chapter 1.5.2); revert unless the change is attachment-only and intended |
| tests against PostgreSQL wiped data | `TEST_POSTGRES_URL` pointed at a real database | always use a dedicated `promptopt_test` database |
