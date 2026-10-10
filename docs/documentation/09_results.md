# 9. Results

[Back to the index](README.md)

Every number here is copied from a report file (cited) or reconciled from them with the arithmetic shown. Methods:
[chapter 8](08_evaluation_methodology.md). Summary document of record: `evaluation/FINAL_RESULTS.md` ([FR §n]).

---

## 9.1 Headline numbers

| what | result | source |
|---|---|---|
| **total tokens, degraded → optimized (A+B), full test split** | **−39.2% per prompt (95% CI 35.9–42.5%), n = 482**, Wilcoxon p < 0.001 | `tokens/token_test.md` |
| Stage A category accuracy (degraded prompts, test) | **74.7%** (macro-F1 0.746) | FR §3 |
| Stage B: output format stated (test) | **3.1% → 95.0%** | FR §4 |
| Stage B: prompts sent to Stage C (test) | **6.4%** (31 of 482) | FR §4 |
| Stage B: wrong-category additions (test) | 5.2% (25 of 482) | FR §4 |
| benchmark with a real LLM (44 prompts) | quality **8.2 → 9.0**, task success **67% → 85%**, total tokens **−57%** | FR §4 |
| Stage C answers usable: zero-shot base vs LoRA (test) | **5.0% vs 98.2%** | FR §5.1 |
| Stage C on routed prompts: format stated | **22.6% → 90.3%** (task intent 0.869 → 0.843) | FR §5.2 |
| Stage C latency, median (laptop GPU / CPU) | **0.74 s** / 4.55 s (requirement < 3 s on GPU: met) | FR §5.5 |
| attachment rules (hand-made set) | 30/30 | FR §6 |
| coding pass@1 strict, test Python items (n = 29) | **20.7% → 34.5%** (sign test p = 0.125) | FR §7 |
| image mode v2 vs original, held-out (n = 30), CLIP | 33.08 vs 32.77 (no significant difference, p = 0.125), style kept 12/12 | FR §8 |
| correctness suite (50 cases), Groq gpt-oss-120b | correct **37 → 42** (McNemar p = 0.267), total tokens −29.6% aggregate | `correctness_suite/RESULTS.md` |
| freeze check | byte-identical to `frozen-for-test` (`35f7d4dc…`) | FR §2; re-run 2026-10-10 |

## 9.2 Stage A, Stage B, Stage C (offline, test split)

Detailed in chapters 4.4, 5.7 and 6.10. Key tables:

**Stage A** — accuracy 360/482 = 74.7%; F1: coding 0.985, classification 0.945, closed_qa 0.652,
information_extraction 0.634, summarization 0.512; out-of-scope prompts classified `other`: 68.5% of 467.

**Stage B** — format stated 3.1% → 95.0% (dataset optimized prompts 79.0%); words 11.2 → 22.0; routed 31 (24 task
category, 7 ambiguous reference); per-rule macro F1 0.631 (0.684 with B07 = data moved).

**Stage C** — passes validation 98.2% (base 5.0%); routed: task intent 0.869 → 0.843, format 22.6% → 90.3%, fallback
3.2%; forced routing lowers task intent 0.886 → 0.769 (hence routed-only); category on routed prompts: Stage A 9/24,
Stage C 14/24; latency 0.74 s median (GPU).

## 9.3 Tokens on the full test split (`tokens/token_test.md`)

Setup: degraded prompt vs Stage A + B, `cerebras/gpt-oss-120b`, temperature 0, max 2,048 tokens, reasoning "low", the
row's context appended to both, frozen pipeline, no judge; 482 of 482 prompts with both answers.

| set | n | tokens | degraded (mean) | A+B (mean) | aggregate | **mean per prompt [95% CI]** | median | Wilcoxon p |
|---|---|---|---|---|---|---|---|---|
| all | 482 | input | 226 | 241 | −6.3% | **−11.1%** [−12.1, −10.2] | −6.3% | < 0.001 |
| | | output | 682 | 165 | 75.8% | **52.7%** [48.2, 57.1] | 71.1% | < 0.001 |
| | | total | 909 | 406 | 55.4% | **39.2%** [35.9, 42.5] | 47.6% | < 0.001 |
| closed_qa | 99 | total | 1,115 | 417 | 62.6% | **44.5%** [37.6, 51.3] | 53.6% | < 0.001 |
| information_extraction | 93 | total | 875 | 466 | 46.8% | **24.2%** [16.2, 32.4] | 12.6% | < 0.001 |
| classification | 98 | total | 488 | 278 | 43.0% | **28.5%** [21.1, 35.8] | 38.7% | < 0.001 |
| summarization | 94 | total | 1,169 | 552 | 52.8% | **43.3%** [37.0, 49.4] | 47.7% | < 0.001 |
| coding | 98 | total | 903 | 324 | 64.1% | **54.7%** [48.0, 60.8] | 67.2% | < 0.001 |

(Positive = fewer tokens; a negative input reduction means the optimized prompt is longer.)

**Reading the numbers.**
* Input **grows** (+11.1% per prompt): the optimized prompt states a format and constraints. The saving comes from
  **output** (−52.7% per prompt): a stated format and length stop long, unrequested answers.
* Mean per prompt (39.2%) < aggregate (55.4%) because the aggregate weights prompts by their original size and the
  biggest prompts shrink most (derivation in chapter 8.3). Rounding check: $1 - 406/909 = 55.3\%$ from the rounded
  means; 55.4% from the exact sums.
* Reasoning tokens (part of output): 26 → 36 per prompt. Answers cut at the 2,048 limit: degraded 31, A+B 3.
* **No category shows a net increase on average**, but **87 of 482 prompts (18.0%) individually cost more** (their
  answer was already short): information_extraction 35/93, classification 23/98, closed_qa 11/99, summarization
  10/94, coding 8/98. Future work: a lean mode.

**Task success where checkable without a judge** (same answers): classification 20/48 → 34/48 (42% → 71%); coding (a
code block that parses) 85/98 → 97/98 (87% → 99%).

**Routed prompts (31): A+B vs A+B+C.** Stage C's answer accepted for 30. Degraded → A+B: total tokens unchanged on
average (707 → 707) — for these prompts Stage B adds little; degraded → A+B+C: 707 → 327 (−33.3% per prompt,
p < 0.001); A+B → A+B+C: −26.7% per prompt. Small set, indicative only.

## 9.4 Benchmark with a real LLM (`tokens/final_benchmark_summary.md`)

`final-benchmark`, 2026-09-28: all 44 benchmark rows × 3 variants, target `cerebras/gpt-oss-120b`, judge Groq
`qwen/qwen3.8-27b` (blind); 132 of 132 items recorded, 0 judge failures, no exclusions.

| variant | n | quality (0–10) | task success | input | output | total | latency ms |
|---|---|---|---|---|---|---|---|
| degraded | 44 | 8.2 | 67% (27) | 221 | 673 | 894 | 1,215 |
| **stage_b** | 44 | **9.0** | **85% (27)** | 235 | 151 | **386** | **773** |
| dataset_target | 44 | 9.0 | 81% (27) | 242 | 129 | 371 | 1,189 |

Reconciliation: total $1 - 386/894 = 56.8\% \approx 57\%$; latency $1 - 773/1215 = 36.4\%$; task success on the 27
checkable items: 18 → 23 (67% → 85%). Stage B matches the dataset's LLM-written prompts on quality and task success at
almost the same token count.

Per category (quality; task success): classification 7.5; 43% → 10.0; 86% (n = 8) · closed_qa 8.6; 90% → 9.0; 90%
(n = 10) · coding 8.0; 60% → 7.8; 80% (n = 10) · information_extraction 8.1 → 8.9 · summarization 9.0 → 10.0 (n = 6).
In coding, Stage B raises task success but its judge quality is slightly lower (7.8 vs 8.0). Per-category numbers
rest on 6–10 items: indicative only.

**Development run on val** (`dev-val-n10`, v1.1, Groq target; Stage B was tuned on these rows, so development numbers):
quality 9.2 → 9.6, task success 77% → 96%, total tokens 776 → 455 (−41.4%), with 2 wrong-reference items excluded.

## 9.5 Coding: tests in a sandbox (`coding/coding_tests.md`)

Scope (test): 98 coding items, 47 Python, **29 tested** (24 function items with 118 validated asserts, 2–6 per item;
7 script items), 4 reference suspects, 14 untestable. Other languages (not run): SQL 14, JavaScript 12, Java 7, C++ 5,
unknown 6, HTML 2, C# 2, CSS 2, Bash 1.

| test (29 items) | pass@1 strict | pass@1 lenient | pass | naming-only | wrong | ambiguous | no function | no Python |
|---|---|---|---|---|---|---|---|---|
| degraded | **6/29 (20.7%)** | 11/29 (37.9%) | 6 | 5 | 9 | 5 | 2 | 2 |
| Stage B | **10/29 (34.5%)** | 12/29 (41.4%) | 10 | 2 | 13 | 1 | 3 | 0 |

Paired (strict): both pass 6, only Stage B 4, only degraded 0, neither 19 → sign test $p = 2 \cdot 2^{-4} = 0.125$.
The gain is mostly **interface** (function naming, one solution, Python), not algorithmic correctness: real failures
(wrong + error + no function + no Python) are 13 vs 16.

## 9.6 Image mode (`image/image_mode.md`)

Held-out set (30 prompts written and committed before any v2 code, run once), Stable Diffusion 1.5, CLIP ViT-B/32
score against the user's **original** prompt:

| variant | CLIP (mean) | vs original: higher / lower / tie | sign test p | style kept (12 styled) |
|---|---|---|---|---|
| original prompt | 33.08 | – | – | 12/12 |
| v1 (default keywords) | 30.78 | 7 / 18 / 5 | 0.043 | 10/12 |
| **v2 (final)** | **32.77** | 0 / 4 / 26 | 0.125 | **12/12** |
| v2 + every first suggestion (simulated) | 31.07 | 3 / 20 / 7 | < 0.001 | 10/12 |

v1 coverage of the 9 attributes rose to 9.0 of 9 per prompt yet the images matched the request **worse** (dev: 28.44
vs 29.95, p = 0.009). v2 does no measurable harm. Details: chapter 11.

## 9.7 Compare (live examples, illustrations) and the correctness suite

**Compare** (Groq gpt-oss-120b, 2026-10-02; `compare/compare_examples.md`):

| prompt | original total | optimized total | change | quality |
|---|---|---|---|---|
| coding: "write code to get all permutations of a string" | 768 | 248 | **−67.7%** | both 6/6 tests, judge 10/10 |
| closed_qa: "which company bought hackpad according to that text?" + passage | 238 | 279 | **+17.2%** | both judge 10/10 |

The second is shown on purpose: the original answer was already one line, so the longer prompt cannot pay for itself.

**Correctness suite** (50 new hand-written cases with verifiable gold answers; chapter 12):

| model | vague correct | optimized correct | only optimized | only vague | McNemar p | total tokens (aggregate change) |
|---|---|---|---|---|---|---|
| gpt-oss-120b on Groq (primary) | 37/50 | 42/50 | 9 | 4 | 0.267 | −29.6% |
| gpt-oss-120b on Cerebras (replication) | 43/50 | 41/50 | 2 | 4 | 0.688 | −28.2% |

Neither difference in correctness is statistically significant; tokens fall clearly on both. Gold answers are
auto-validated; human review is pending (`team_input/correctness_review/`).

## 9.8 Dataset validation (chapter 3.8–3.10)

330 rows rated, 295 accepted, 35 rejected; Fleiss' κ 0.065 / Gwet's AC1 0.928 on Q1 (kappa paradox, chapter 3.9.5);
faculty accepted 19 of 20; LLM-assisted filter removed 9 rows; final 5,184 rows.
