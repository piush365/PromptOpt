# 8. Evaluation methodology: how every number is produced

[Back to the index](README.md)

This chapter defines every metric, statistical test and estimate used in the project, with formulas, the reason each
was chosen, and its assumptions. The numbers themselves are collected in [chapter 9](09_results.md).

---

## 8.1 Map of all evaluations

| evaluation | split / set | n | what runs | script | report |
|---|---|---|---|---|---|
| Stage A | test (val in development) | 482 | Stage A on degraded prompts | `app.stage_a.evaluate` | `evaluation/stage_a/stage_a_test_final.md` |
| Stage B offline | test | 482 | Stage A + B | `app.stage_b.evaluate` | `evaluation/stage_b/stage_b_test_final.md` |
| Stage B per rule | test | 482 | Stage A + B vs dataset targets | `app.stage_b.rule_accuracy` | `evaluation/stage_b/stage_b_rule_accuracy.md` |
| Stage C | val (development), test (once) | 298 / 964 examples | base vs LoRA, ablation, category, latency | `app.stage_c.evaluate` | `evaluation/stage_c/stage_c_eval.md`, `stage_c_test.md` |
| benchmark with a real LLM | benchmark | 44 × 3 variants | target LLM + blind judge | `app.evaluation.run --split benchmark --final` | `evaluation/tokens/final_benchmark_summary.md` |
| development LLM run | val (v1.1) | 48 × 3 | same harness | `app.evaluation.run` | `evaluation/REVIEW_SUMMARY.md` §5 |
| full-test token evaluation | test | 482 × 2 (+31) | target LLM, no judge | `app.evaluation.tokens` | `evaluation/tokens/token_test.md` |
| coding pass@1 | test + benchmark Python items | 29 + 2 | target LLM + sandbox tests | `app.coding.evaluate` | `evaluation/coding/coding_tests.md` |
| attachments | hand-made | 30 | Stage A + B + renderers | `app.attachment_eval` | `evaluation/attachments/attachment_test.md` |
| image mode | dev 40, held-out 30 | 70 | SD 1.5 + CLIP | `app.image.generate`, `app.image.evaluate` | `evaluation/image/image_mode.md` |
| correctness suite | 50 new cases | 50 × 2 | target LLM + gold checks | `app.correctness.run` | `evaluation/correctness_suite/RESULTS.md` |
| freeze | test | 482 | Stage A + B, two code versions | `app.freeze_check` | `evaluation/stage_b/phase2_freeze_check.md` |

## 8.2 The LLM evaluation harness (`app/evaluation/`)

### 8.2.1 Variants

For each dataset row (`variants.build_variants`):

| variant | the request sent to the target LLM |
|---|---|
| `degraded` | the dataset's degraded prompt, as typed |
| `stage_b` | PromptOpt's output: Stage A + Stage B's optimized plain text (no Stage C) |
| `dataset_target` | the dataset's LLM-written optimized prompt (an upper reference, not something PromptOpt produces) |

**Context rule:** every variant gets the row's context appended after a blank line (`with_context`), exactly as a
user would paste the text below the request. Without it, prompts like "summarize that text" are unanswerable; and
since the same context is added to every variant, it adds the same tokens to each and cancels in comparisons.

### 8.2.2 Target model settings

| setting | value | basis |
|---|---|---|
| model | `openai/gpt-oss-120b` on Groq (development) or Cerebras (final runs) | the strongest model available on the free tiers; the same model on both providers |
| temperature | 0 | (near-)deterministic answers, so differences come from the prompt, not sampling |
| max output tokens | 2,048 (includes gpt-oss's hidden reasoning tokens) | identical for every variant; answers cut at the limit are counted (`finish_reason = "length"`) and reported |
| reasoning effort | `low` | as in the dataset notebook; recorded and identical for every variant |
| messages | one user message, no system prompt | measures the prompt alone, as a user would send it |

**Stand-in caveat:** gpt-oss-120b plays the role of GPT, Gemini and Claude. A prompt rendered for Claude and answered by
gpt-oss is labelled a stand-in wherever it appears (Compare does this automatically).

**Row selection** (`select_rows`): per category, rows sorted by SHA-256(`"promptopt-eval-v1:" + source_id`) and the
first `per_category` taken, then interleaved across categories so a partial run stays balanced. Final runs use every
row of the split.

### 8.2.3 Caching, resumability, discipline

* Every target call and judgment is appended to `data/evaluation/<run>.jsonl` as soon as it returns; every finished
  item is committed to the `evaluation_runs` table. Re-running skips what is recorded, reuses cached calls and only
  calls the API for what is missing. When a provider's daily limit is reached the run stops cleanly
  (`DailyLimitReached`) and resumes the next day.
* If a variant's prompt changed since it was cached (e.g. a Stage B fix during development), the cached answer is
  discarded and re-requested; `--refresh` does this for recorded items (development only).
* `--split test|benchmark` requires `--final`; `check_final_once` refuses a final run name that already has results
  for a different dataset version (version = `v1-<rows>-<first 8 hex of the CSV's SHA-256>`).

### 8.2.4 The judge (`evaluation/judge.py`)

| aspect | choice | reason |
|---|---|---|
| model | `qwen/qwen3.8-27b` on Groq | a **different** model family from the target, so it does not favour its own answers |
| blindness | never told which variant produced the answer | removes label bias |
| what it sees | the request exactly as the target received it, the attached text (≤ 2,000 characters), the dataset's reference answer, the response | "follows the requested format" is judged against what *that* prompt asked |
| rubric | one score 0–10 considering correctness (agrees with the reference and text, no invented facts), relevance, format (only if the request asked for one), completeness | a single holistic score is cheap and stable; the rubric is stated in the system prompt |
| closed_qa extra | `answers_correctly`: true/false, same answer as the reference | gives task success for closed_qa |
| decoding | temperature 0, reasoning "none", JSON mode, 512 max tokens | determinism, cost |
| long responses | ≤ 12,000 characters shown whole; longer: first 9,000 + last 3,000 with an explicit "[… N characters omitted by the evaluator …]" | with a plain cut at 6,000 characters the judge scored a complete 8,608-character answer 0 for "missing the main block" (val `codealpaca-15059`); the note tells it the omission is not the assistant's |
| failures | up to 3 attempts; on Groq's `json_validate_failed` the next attempt gets twice the tokens; an item whose judgment failed in 2 runs is skipped and **excluded for all variants** | every variant is compared on the same items |

Parsing: `<think>…</think>` blocks are removed, the first `{…}` is parsed, the score is clamped to [0, 10];
`answers_correctly` accepts true/false/yes/no.

### 8.2.5 Task success (`evaluation/success.py`)

Only where it can be checked without a human; `None` = not checkable (not counted).

* **closed_qa:** the judge's `answers_correctly`.
* **classification:** (1) the allowed labels come from the instruction (`extract_labels`, or "belongs to X or Y"),
  or are yes/no when the reference is a short yes/no answer (≤ 8 words); (2) the items are the list after the last
  `:` or `;` (or after the question mark), split on commas/semicolons/new lines/"and"; (3) labels are assigned to
  items sentence by sentence (a sentence with one label gives it to every item in it; with several labels it is read
  comma by comma); (4) **success = every item gets the reference's label**. One item only: the first label mentioned
  must equal the reference's. Unicode spaces and dashes are normalized first.
* **coding:** a fenced code block is present, and every block that is Python (tagged python/py/python3, or untagged
  when the instruction asks for Python) parses with `ast.parse`. (Functional correctness is measured separately with
  sandboxed tests, chapter 10.)
* **information_extraction, summarization:** not checkable automatically (quality score only).

### 8.2.6 Aggregation and exclusions

Per (category, variant): mean quality, mean input/output/total tokens, mean latency, task-success rate over the
checkable items (count shown in brackets), number of truncated answers. The "all" row weights each category by its
number of items. Items with a known wrong reference answer (`evaluation/dataset/wrong_references.csv`) or a failed
judgment are excluded **for every variant**, listed with the reason, and the headline is shown with and without the
exclusions, with a warning if an exclusion moves quality by more than 0.1 (1 point on a 0–100 scale) or task success
by more than 1 percentage point.

**Latency:** Groq's `usage.total_time` when reported (server-side), otherwise the wall clock of the HTTP call;
Cerebras: wall clock.

## 8.3 Token metrics

Let $b_i$ and $a_i$ be the tokens of prompt $i$ **before** (degraded) and **after** (optimized), for input, output
(**including hidden reasoning tokens**, as billed) or total = input + output, taken from the provider's usage fields.

**Per-prompt reduction** (positive = fewer tokens):

$$r_i = 100 \times \frac{b_i - a_i}{b_i}$$

**Mean reduction** $\bar r = \frac{1}{n}\sum_i r_i$ — the headline ("39.2%"): every prompt counts equally.
**Median reduction** — robust to a few extreme prompts.
**Aggregate reduction** — of the summed tokens:

$$R = 100 \times \frac{\sum_i b_i - \sum_i a_i}{\sum_i b_i} = \sum_i \underbrace{\frac{b_i}{\sum_j b_j}}_{w_i}\, r_i$$

*Derivation:* $\sum_i w_i r_i = \sum_i \frac{b_i}{B}\cdot 100\frac{b_i - a_i}{b_i} = \frac{100}{B}\sum_i (b_i - a_i) = R$
with $B = \sum_j b_j$. So the aggregate is a **weighted** mean of the per-prompt reductions, weighted by how many tokens
the prompt used before. Prompts with long unrequested answers (large $b_i$) are exactly the ones that shrink most, so
$R$ (55.4%) is larger than $\bar r$ (39.2%). Both are reported; the per-prompt mean is the conservative headline.

*Rounding note:* from the rounded means in the report (909 → 406) one gets $1 - 406/909 = 55.3\%$; the report's
55.4% is computed from the unrounded sums.

### 8.3.1 Confidence interval: percentile bootstrap

`evaluation/tokens.py`, `bootstrap_ci`, with $B = 10{,}000$ resamples and seed 20261002:

1. draw $n$ values **with replacement** from the $n$ per-prompt reductions $r_1 … r_n$;
2. compute their mean; repeat $B$ times;
3. sort the $B$ means and take the values at positions $\lfloor 0.025B \rfloor$ and $\lfloor 0.975B \rfloor - 1$
   (0-based) as the 95% interval.

**Why the bootstrap:** the reductions are bounded above by 100% and skewed (many prompts near 70–80%, some negative),
so a normal-theory interval would be questionable; the percentile bootstrap needs only that the prompts are a random
sample from the population of interest. Result for total tokens: **35.9%–42.5%** around 39.2% (n = 482).

### 8.3.2 Significance: Wilcoxon signed-rank test

On the **paired** token counts $(b_i, a_i)$ (same prompt, two variants), `scipy.stats.wilcoxon(after, before)`:

1. differences $d_i = a_i - b_i$; zero differences are dropped (`zero_method="wilcox"`);
2. rank $|d_i|$ from 1 to $n'$ (ties get the average rank);
3. $W^+$ = sum of ranks of positive differences, $W^-$ = of negative ones; the statistic is $\min(W^+, W^-)$;
4. under the null hypothesis (the distribution of $d$ is symmetric around 0), $W^+$ has mean $n'(n'+1)/4$ and variance
   $n'(n'+1)(2n'+1)/24$ (minus a tie correction); for $n' = 482$ SciPy uses this **normal approximation**
   (`method="auto"` uses the exact distribution only for small samples; verified to equal `method="approx"` here):

   $$z = \frac{W^+ - n'(n'+1)/4}{\sqrt{n'(n'+1)(2n'+1)/24}}, \qquad p = 2\,\Phi(-|z|)$$

**Why Wilcoxon and not a paired t-test:** token counts are heavy-tailed (answers from 20 to 2,048 tokens), so the
t-test's normality assumption is doubtful; the signed-rank test uses only the signs and ranks of the paired
differences. All reported token differences on the full test split have $p < 0.001$.

## 8.4 Exact tests for small paired yes/no outcomes

**Sign test** (image mode, coding) and **exact McNemar test** (correctness suite) are the same computation on the
**discordant** pairs: of $n$ items where the two variants differ, $w$ favour one and $l$ the other; under the null
each discordant pair is a fair coin, so with $k = \min(w, l)$:

$$p = \min\Big(1,\ 2\sum_{i=0}^{k}\binom{n}{i}2^{-n}\Big), \qquad n = w + l$$

(two-sided; `image/evaluate._sign_test`, `correctness/checks.mcnemar_exact`). Ties (image: |CLIP difference| < 0.5)
and concordant pairs are dropped.

| use | wins / losses | p |
|---|---|---|
| coding pass@1, test: only Stage B passes / only degraded passes | 4 / 0 | $2 \times 2^{-4} = 0.125$ |
| image v1 vs original, dev | 9 higher / 25 lower | 0.009 |
| image v1 vs original, held-out | 7 / 18 | 0.043 |
| image v2 vs original, held-out | 0 / 4 | 0.125 |
| correctness suite, Groq: only optimized right / only vague right | 9 / 4 | 0.267 |
| correctness suite, Cerebras | 2 / 4 | 0.688 |

With small $n$ these tests have little power: "not significant" means "not shown", not "no effect".

## 8.5 Agreement statistics (dataset validation)

Fleiss' kappa, Cohen's kappa, Gwet's AC1, PABAK and raw agreement are defined and derived in
[chapter 3.9](03_dataset.md#39-agreement-statistics-definitions-derivations-worked-example).

## 8.6 Cost estimation

The project runs on free tiers, so its measured money cost is zero; `token_usage` has `est_cost_*` columns that are
not filled. A cost for any paid model follows from the token counts:

$$\text{cost} = \frac{T_{in}\, p_{in} + T_{out}\, p_{out}}{10^6} \quad (\text{prices per million tokens})$$

Writing $\rho = p_{out}/p_{in}$ (output tokens usually cost several times more than input tokens), the relative saving
of the optimized prompts depends only on $\rho$. With the full-test means (input 226 → 241, output 682 → 165):

| $\rho = p_{out}/p_{in}$ | cost before ∝ $226 + 682\rho$ | after ∝ $241 + 165\rho$ | saving |
|---|---|---|---|
| 1 | 908 | 406 | 55.3% (= the aggregate token reduction) |
| 2 | 1,590 | 571 | 64.1% |
| 3 | 2,272 | 736 | 67.6% |
| 4 | 2,954 | 901 | 69.5% |
| 5 | 3,636 | 1,066 | 70.7% |

So for any model that prices output higher than input, the cost saving is **larger** than the token saving, because
the saving comes from output. (This is an aggregate over the test prompts; per-prompt savings vary, and 87 of 482
prompts cost more — chapter 9.3.) No provider price is assumed; insert the actual prices of a model to get dollars.

## 8.7 Latency measurement

* **Stage C:** wall clock around `model.generate` (with `torch.cuda.synchronize()` on GPU), batch 1, greedy, after one
  warm-up call; median and p95 (index $\min(n-1, \lfloor 0.95n \rfloor)$ of the sorted times), on GPU (40 examples)
  and CPU (20).
* **Target LLM:** provider-reported or wall clock (8.2.6). These include network and queueing, so they are indicative.
* **Stage A:** mean per prompt over a batched run of the split (7.9 ms on CPU).

## 8.8 Threats to validity (and what was done about each)

| threat | mitigation / status |
|---|---|
| tuning on the test set | val-only tuning, `frozen-for-test`, test run once, `--final` guard, freeze check |
| stand-in model | gpt-oss-120b for all families; labelled; real GPT/Claude/Gemini runs are future work |
| judge bias | different model family, blind to the variant, rubric, reference answer given |
| LLM-written targets | human validation sample (330 rows), LLM-assisted filter; per-rule accuracy explicitly called "agreement with LLM targets" |
| wrong references | static checks, exclusion list, with/without comparison |
| small samples (benchmark 44, routed 31, coding 29) | full-test token evaluation (482); confidence intervals; exact tests; per-category numbers called indicative |
| provider non-determinism at temperature 0 | one run per item, cached; differences averaged over hundreds of prompts |
| truncation at 2,048 tokens | counted and reported (degraded 31, A+B 3 on the full test split) |
| Dolly label noise | reported; B08 acts at group level; the user can choose the category |
| developer-written attachment/image prompts | stated everywhere; blind sets by outsiders are future work |
