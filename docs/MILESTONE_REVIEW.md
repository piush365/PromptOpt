# PromptOpt: milestone review checklist (2026-09-29)

Mini Project-I (7CS345), WCE Sangli. Code for the final numbers: tag `frozen-for-test`; since then only data steps,
reporting, the offline demo and the dataset path default changed (no Stage A/B rule, threshold or judge change).
Full write-up: `evaluation/REVIEW_SUMMARY.md`.

| # | Area | Status | Key numbers | Proof |
|---|---|---|---|---|
| 1 | Dataset | Done | v1.2 final: **5,184** pairs, 1,000-1,089 per category; train 4,509 / val 149 / test 482 / benchmark 44; no instruction in two splits | `docs/DATASET_CARD.md`, `evaluation/dataset/final_dataset_merge_log.csv` |
| 2 | Human validation | Done | 3 raters x 170 rows + faculty 20; **330 validated, 295 accepted, 35 rejected**; team per-question raw agreement 89-94%, Gwet's AC1 0.92-0.96, PABAK 0.85-0.93, Fleiss' kappa -0.04 to 0.07 | `evaluation/dataset/validation_report.md`, `docs/validation_guide.md` |
| 3 | Faculty check | Done | faculty vs team majority: agreement 85-100% per question, AC1 0.83-1.00 | `evaluation/dataset/validation_report.md` |
| 4 | LLM-assisted filter (automatic, not human) | Done | LLM rater on the 90 overlap rows; **9 rows removed** (answer leaked, impossible constraint, added facts, changed task); never counted in agreement | `evaluation/llm_rater/`, `evaluation/REVIEW_SUMMARY.md` section 4 |
| 5 | Stage A (feature detection) | Done, retrained on final train | test (482, run once): **accuracy 74.7%, macro-F1 0.746**; classification F1 0.945, coding 0.985, closed_qa 0.652, information_extraction 0.634, summarization 0.512; out-of-scope -> `other` 68.5% | `evaluation/stage_a/stage_a_test.md` |
| 6 | Stage B (rule-based optimizer, B01-B13) | Done | test: output format stated **3.1% -> 95.0%**; 11.2 -> 22.0 words; wrong-category additions 5.2%; **Stage C routing 6.4%** | `evaluation/stage_b/stage_b_test.md`, `backend/tests/test_stage_b.py` |
| 7 | IR + renderers (GPT / Gemini / Claude) | Done | every rendering parsed back, no field lost | `backend/app/rendering.py`, `backend/tests/test_rendering.py` |
| 8 | Evaluation: val (development) | Done | stage_b vs degraded: quality 9.6 vs 9.2, task success 96% vs 77%, total tokens -41% | `evaluation/REVIEW_SUMMARY.md` section 5 |
| 9 | Evaluation: benchmark (final, LLM) | Done, 132 of 132 | Cerebras gpt-oss-120b target, Groq qwen judge; stage_b vs degraded: **quality 9.0 vs 8.2, task success 85% vs 67%, total tokens 386 vs 894 (-57%), latency -36%** | `evaluation/tokens/final_benchmark_summary.md` |
| 10 | Ablation study | Not started | - | - |
| 11 | Stage C (LoRA), FastAPI + React app | Not started (planned) | - | `CLAUDE.md` roadmap |
| 12 | Tests | Passing | 416 tests (`python -m pytest -q`) | `backend/tests/` |

## Freeze proof

Tag `frozen-for-test` = `f4db6cb` (2026-09-27); checked against `cfb6a6b` on 2026-09-28. Stage A, Stage B (rules,
optimizer, IR), the rule seed and the whole evaluation harness (judge, success checks, variants, runner):

```console
$ git diff --stat frozen-for-test..cfb6a6b -- backend/app/stage_a backend/app/stage_b backend/app/evaluation backend/app/db/seed.py
$                                   # empty: no change
```

Everything that did change under `backend/app/` since the tag (none of it is a rule, threshold or judge):

```console
$ git diff --stat frozen-for-test..cfb6a6b -- backend/app
 backend/app/config.py     |   6 +-      default DATASET_DIR -> v1.2 final, new DATASET_CSV
 backend/app/dataset_io.py |   8 +--     reads DATASET_CSV
 backend/app/demo.py       | 102 +++++   new offline demo
 backend/app/validation.py | 162 +++---   rating merge and agreement report
 4 files changed, 244 insertions(+), 34 deletions(-)
```

Re-run: `git diff --stat frozen-for-test..HEAD -- backend/app/stage_a backend/app/stage_b backend/app/evaluation backend/app/db/seed.py`.

## Live demo (offline: no API call, no database)

```bash
cd backend && source .venv/bin/activate
python -m app.demo --examples                       # 5 ready prompts, one per category
python -m app.demo --examples --target claude       # ... plus the Claude rendering (or gpt / gemini)
python -m app.demo "hey can you just summarize this article for me"          # filler removed, goes to Stage C
python -m app.demo "classify these as fruit or veg: tomato, apple" --category classification --target gpt
```

Each run prints: Stage A category and confidence, the detected features (missing format, constraints, filler,
ambiguous references), every Stage B rule that changed the prompt with before/after, the optimized prompt (and its
rendering for the chosen LLM), and whether the prompt would go to Stage C and why.

Show the stored results: `python -m app.validation report` (agreement), `python -m app.evaluation.run --split
benchmark --final --per-category 10 --target cerebras --summary-only` (benchmark table, from the database).

## Limitations (say these out loud)

- **Kappa paradox.** 96-98% of all answers are Y, so Fleiss' kappa is near 0 (target 0.6 not met) although raters
  agree on 89-94% of rows; AC1 and PABAK are reported next to it. Agreement on the combined accept decision is lower
  (67.8% unanimous, AC1 0.72).
- **Dolly label noise.** Many summarization / information_extraction rows are plain questions. The LLM rater called
  the label debatable on 23 of 90 overlap rows (kept); most Stage A errors are between closed_qa,
  information_extraction and summarization.
- **Near-copy degraded prompts.** 19 of 90 overlap rows have a degraded prompt that is almost the original short
  question (kept).
- **Small benchmark.** 44 rows (summarization 6, classification 8) after human rejections; per-category benchmark
  numbers are indicative only. One stand-in target model (gpt-oss-120b) and one judge model (qwen); no real
  GPT/Gemini/Claude run yet.
- **Coding.** Stage B raises task success (60% -> 80%) but its judge quality is slightly below the degraded prompt's
  (7.8 vs 8.0) on the benchmark.
- **Stage A on text categories.** summarization F1 0.51; 35% of test prompts are below the 0.6 confidence gate and
  fall back to B08 or Stage C.
- **LLM-assisted filter** covered only the 90 overlap rows; similar problems likely remain in the 4,898 rows nobody
  rated. The LLM rater had seen one faculty answer (dolly-4205) before rating.
- **Stage B quirk (not fixed, freeze).** B07 adds a question mark at the very end of the prompt, so a question
  followed by its passage on the same line ends with the passage plus "?".
- Stage C (LoRA) and the ablation study are not built yet; "goes to Stage C" is a routing decision only.
