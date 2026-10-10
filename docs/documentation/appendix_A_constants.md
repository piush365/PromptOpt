# Appendix A. Every constant, with its basis

[Back to the index](README.md)

**Basis codes:** **M** = measured (the measurement is cited) · **V** = tuned or checked on the val split ·
**CV** = cross-validation on train · **D** = design choice (reason given) · **E** = external limit or convention ·
**Δ** = derived from other values. Paths are relative to `backend/app/`.

## A.1 Stage A

| constant | value | where | basis |
|---|---|---|---|
| sentence encoder | `all-MiniLM-L6-v2`, 384-d, L2-normalized | `config.py` | D: same encoder as the dataset checks; ~90 MB; 7.9 ms/prompt on CPU (M) |
| k (neighbours) | 25 | `stage_a/classifier.py` | V |
| τ (k-NN temperature) | 0.05 | `classifier.py` | V; a neighbour 0.05 less similar weighs $e^{-1}$ = 0.37 |
| keyword weight | 0.3 | `classifier.py` | V |
| head weight | 0.5 | `classifier.py` | V; blend beats either part in 5-fold CV (72.9% vs 69.3% / 70.4%) |
| `other` threshold | 0.3 (nearest similarity) | `classifier.py` | V |
| backstop keep | $s_{\max}/0.6$ | `classifier.py` | Δ: guarantees `other` > 0.5 below the threshold |
| `HEAD_C` | 4.0 | `stage_a/build_index.py` | CV (5-fold, train) |
| class weights | balanced: $N/(K N_c)$ | `build_index.py` | D: every category counts equally (`other` 3.17, others 0.83–0.92) |
| `max_iter` | 3,000 | `build_index.py` | D: convergence of L-BFGS |
| `OTHER_PER_CATEGORY` | 250 (brainstorming + creative_writing) | `build_index.py` | D |
| `OTHER_EVAL_FRACTION` | 0.2 (hash bucket) | `build_index.py` | D: held-out `other` set (467 prompts) |
| open_qa / general_qa as `other` | excluded | `build_index.py` | V: including them cut closed_qa recall 0.80 → 0.70 |
| keyword cue weights | 0.5–3.0 per pattern | `classifier.py` | D: explicit verbs (summarize, extract, classify) 3.0; weaker hints 1.0–1.5 |
| context: quoted passage | ≥ 40 characters | `stage_a/rules.py` | D |
| context: commas | ≥ 2 | `rules.py` | D: a list of items |
| context: `head: tail` | head ≤ 25 words, tail ≥ 8 words or a comma | `rules.py` | D |
| context: long prompt | ≥ 60 words; or ≥ 8 words on lines after the first | `rules.py` | D |
| repeated sentence | ≥ 3 words | `rules.py` | D: shorter repeats are often intentional |
| allowed doubled words | that, had, is, no, bye, very, so | `rules.py` | D: grammatical doubles |
| confidence rounding | 4 decimals | `stage_a/detector.py` | D |

## A.2 Stage B

| constant | value | where | basis |
|---|---|---|---|
| `CATEGORY_MIN_CONFIDENCE` | 0.6 | `stage_b/rules.py` | V: Stage A right 77–96% above, 47–59% between 0.4 and 0.6 |
| B08 group sum threshold | 0.6 | `rules.py` | D: same gate, applied to the text group |
| B07 split | head ≤ 25 words; tail ≥ 8 words, a comma or a new line; tail not ending in `?` | `rules.py` | D: only clearly-data tails move |
| B01 content-verb window | 4 words | `rules.py` | D: "print please enter your name" keeps "please" |
| B01 minimum remaining | 2 words | `rules.py` | D: all-filler prompts are left for Stage C |
| B06 label shape | 1–4 words each, 2–8 distinct labels | `rules.py` | D |
| B04 defaults | closed_qa "at most two sentences"; summarization "under 100 words" | `rules.py` | D (effect measured on test, chapter 9) |
| B08 text | "Answer from the provided text in at most three sentences." | `rules.py` | D (wording shortened on val, commit `bbeb01f`) |
| B05 default language | Python | `rules.py` | M: the most common language of the coding items (47/98 test) |
| `UNRESOLVED_PENALTY` | 0.2 | `stage_b/optimizer.py` | D: stored heuristic, not used for routing |
| `OTHER_CONFIDENCE` | 0.3 | `optimizer.py` | D |
| `STAGE_C_REASONS` | task category, ambiguous reference | `optimizer.py` | D: the only gaps Stage C can fix; replaced a "confidence < 0.7" rule (commit `5b2111c`) |

## A.3 Stage C

| constant | value | where | basis |
|---|---|---|---|
| base model | Qwen/Qwen2.5-0.5B-Instruct (494 M) | `config.py`, `stage_c/data.py` | D: smallest current instruct model; fits 4 GB |
| LoRA r / α / dropout | 16 / 32 / 0.05 | `data.py` `TRAIN_CONFIG` | D (common LoRA settings; α/r = 2) |
| target modules | q, k, v, o, gate, up, down projections | `TRAIN_CONFIG` | D: all linear layers → 8,798,208 params (Δ) |
| max length | 512 tokens | `TRAIN_CONFIG` | M: examples median 291, p99 371, max 446 |
| epochs | ≤ 3 | `TRAIN_CONFIG` | D; early stopping decides |
| batch | 4 × 4 accumulation = 16 (run as 1 × 16) | `TRAIN_CONFIG`, `train.py --batch-size` | D/E: 4 GB GPU |
| learning rate | 2 × 10⁻⁴, AdamW, weight decay 0 | `TRAIN_CONFIG` | D (usual LoRA rate) |
| warm-up | 3% of steps (25 of 837) | `TRAIN_CONFIG` | D; Δ |
| gradient clip | 1.0 | `TRAIN_CONFIG` | D |
| eval every / patience | 50 steps / 3 evaluations; improvement > 10⁻⁴ | `TRAIN_CONFIG`, `train.py` | D |
| seed | 13 (test examples: 14) | `data.py` | D |
| folds (cross-fitting) | 5, by hash of the original instruction | `data.py` | D |
| forced-field probability | 0.5 per field | `data.py` | D → sizes 1/2/3 with p = 1/2, 3/8, 1/8 (Δ) |
| `MAX_NEW_TOKENS` | 192 | `stage_c/runtime.py` | M: longest training target 123 tokens (median 24) |
| task minimum | 2 words | `stage_c/contract.py` | D |
| GPU latency requirement | median < 3 s | plan | D; measured 0.74 s (M) |

## A.4 Rendering and tokens

| constant | value | where | basis |
|---|---|---|---|
| GPT tokenizer | tiktoken `o200k_base` | `rendering.py` | E: GPT-4o/4.1/5 family encoding |
| `CHARS_PER_TOKEN` | 4 | `rendering.py` | E (rule of thumb); M: median 4.25 characters per o200k token on our renderings |
| fence length | max(3, longest backtick run + 1) | `rendering.py` | Δ: the data cannot close the fence |

## A.5 Evaluation

| constant | value | where | basis |
|---|---|---|---|
| target model | `openai/gpt-oss-120b` (Groq / Cerebras) | `evaluation/run.py` | E: free tier |
| `TARGET_MAX_TOKENS` | 2,048 (incl. reasoning) | `run.py` | D: identical for all variants; truncations reported |
| `TARGET_REASONING` | low | `run.py` | D: as in the dataset notebook |
| temperature | 0 | `run.py` | D: determinism |
| `JUDGE_MODEL` | `qwen/qwen3.8-27b` | `run.py` | D: different family from the target |
| `JUDGE_MAX_TOKENS` / attempts / give-up runs | 512 (doubled on JSON failure) / 3 / 2 | `run.py` | D |
| judge context / response limits | 2,000 chars / 12,000 chars (else 9,000 head + 3,000 tail) | `evaluation/judge.py` | M: a cut at 6,000 made the judge score a complete 8,608-char answer 0 (val `codealpaca-15059`) |
| `QUALITY_WARN` / `SUCCESS_WARN` | 0.1 / 1 pp | `run.py` | D: "one point" on each scale |
| yes/no reference | ≤ 8 words | `evaluation/success.py` | D |
| bootstrap resamples / seed | 10,000 / 20261002 | `evaluation/tokens.py` | D |
| evaluation budget | 70% of the daily limit | `tokens.py`, `compare/providers.py`, `coding/testgen.py` | D: room for other tools the same day |
| row selection seed | `promptopt-eval-v1` | `run.py` | D |
| image tie | absolute CLIP difference < 0.5 | `image/evaluate.py` | D |

## A.6 LLM clients

| constant | value | where | basis |
|---|---|---|---|
| Groq spacing | 2.2 s → 27.3 req/min | `evaluation/llm.py` | E/Δ: under the per-minute request limit |
| Cerebras spacing | 24.5 s → 146.9 req/h | `cerebras.py` | E/Δ: under 150 requests/hour (binds first) |
| Groq daily limits | 1,000 requests, 200,000 tokens per model | `groq_budget.py` | E (checked 2026-09-26) |
| Groq per-minute tokens | 8,000 | `groq_budget.py` | E |
| Cerebras daily limits | 2,400 requests, 1,000,000 tokens | `cerebras.py` | E (response headers, 2026-09-26) |
| ledger window | rolling 24 h | `groq_budget.py` | E: Groq's limit is rolling |
| `COUNT_CACHED` | True | `groq_budget.py` | D: conservative until measured |
| retries / back-off | Groq 5 attempts, 429: retry-after or min(60, 5·2ᵃ) s, errors min(30, 3·2ᵃ) s; Cerebras 429 min(120, 15·2ᵃ) s; Gemini 3 attempts, 429 min(60, 10·2ᵃ) s | clients | D |

## A.7 Coding sandbox and tests

| constant | value | where | basis |
|---|---|---|---|
| wall-clock timeout | 5 s (default), 15 s per test run, 3 s per test, 10 s reference runs | `coding/sandbox.py`, `harness.py`, `testgen.py` | D |
| memory | 512 MB address space | `sandbox.py` | D: Python needs ~30 MB |
| file size | 4 MB (stdout/stderr included) | `sandbox.py` | D |
| open files | 64 | `sandbox.py` | D |
| processes | user's current tasks + 32 | `sandbox.py` | D: RLIMIT_NPROC counts all the user's tasks |
| returned output | 20,000 characters | `sandbox.py` | D |
| tests per item | 3–6 | `testgen.py` | D |
| generation tokens | 3,000 | `testgen.py` | D |

## A.8 Image mode

| constant | value | where | basis |
|---|---|---|---|
| subject detail | > 3 content words | `image/attributes.py` | D |
| v1 default ratio | 1:1 | `image/optimizer.py` | D (v2: no default) |
| default negatives | text, watermarks, logos, distorted anatomy, extra limbs, blurry details | `optimizer.py` | E: common SD negatives |
| SD size | area ≈ 512², multiples of 8 | `image/render.py`, `v2.py` | E: SD 1.5 training resolution; VAE factor 8 |
| DALL-E sizes | 1024², 1792×1024, 1024×1792 | `render.py`, `v2.py` | E: DALL-E 3 sizes |
| SD steps / guidance / seed | 25 / 7.5 / 1000 + prompt index | `image/generate.py` | D |
| CLIP model | `openai/clip-vit-base-patch32` | `generate.py` | E: the CLIPScore model |

## A.9 Dataset building and validation

| constant | value | where | basis |
|---|---|---|---|
| `TARGET_PER_CATEGORY` | 1,000 | `dataset_expand.py` | D (roadmap step 2) |
| `SAMPLE_MARGIN` | 1.05 | `dataset_expand.py` | D: 5% safety on the v1 pass rate |
| split sizes | benchmark 10, val 30, test 100 per category | `dataset_expand.py` | D |
| outlier rule | median + 3σ of response words | `dataset_expand.py` | E/D (notebook) |
| coding output minimum | 3 words | `dataset_expand.py` | D |
| drift thresholds | degraded 0.45, optimized 0.35 (or no shared stem and < 0.50); identical > 0.98 | `dataset_expand.py` | D (notebook) |
| degraded length | ≤ 1.25 × original + 3 words | `dataset_expand.py` | D |
| optimized length | ≤ 120 words (excluding kept data) | `dataset_expand.py` | D |
| generation temperature | 0.7 | `dataset_expand.py` | D: varied degraded prompts |
| batch | 5 items per call; ≤ max(1024, 400n + 300) tokens | `dataset_expand.py` | M: ~1,070 → ~400 tokens per row on 10 rows |
| tokens per call (planning) | 1,050 until ≥ 20 rows measured | `dataset_expand.py` | M (2026-09-26) |
| generation budgets | Groq 0.5, Cerebras 0.95, all tools ≤ 0.95 | `dataset_expand.py` | D |
| pacing | max(2.2 s, 60 T / (0.9 × 8,000)) | `dataset_expand.py` | Δ: 90% of Groq's tokens per minute |
| repair coverage | < 0.5 of payload content words = dropped | `dataset_repair.py` | D |
| edit acceptance | all lost subjects named, ≤ 12 extra words | `dataset_repair.py` | D |
| rater design | overlap 18/category (90), faculty 4/category (20), extra 60/rater, v1.2 20/rater | `validation.py` | D |
| borderline margin | 0.10 above the drift thresholds | `validation.py` | D |
| kappa target | > 0.6 | `team_input/validation_guide.md` | E (Landis & Koch "substantial") |

## A.10 Application

| constant | value | where | basis |
|---|---|---|---|
| `RETENTION_DAYS` | 30 | `config.py` | D (SRS) |
| prompt / context / attachment name | ≤ 20,000 / 50,000 / 255 characters | `api.py` | D |
| accepted suggestions | ≤ 20 | `api.py` | D |
| history page size | 1–100 (`/api/history`), 1–200 (`/api/ui/history`) | `api.py`, `ui_api.py` | D |
| token counter text | ≤ 70,000 characters | `ui_api.py` | D |
| GZip threshold | 1,000 bytes | `api.py` | D |
