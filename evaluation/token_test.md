# Token evaluation on the full test split

**Optimized prompts reduce total tokens by 39.2% (95% CI 35.9-42.5%, n = 482)**: the mean of the per-prompt reductions in total tokens (input + output, output including the model's hidden reasoning), degraded prompt vs PromptOpt (Stage A + B), on `cerebras/gpt-oss-120b`.

**Input grows, the saving comes from output.** The optimized prompt is longer: input tokens 226 -> 241 per prompt on average (11.1% per prompt). The answers are much shorter: output tokens 682 -> 165 (52.7% fewer per prompt), because a stated format and length stop the model from writing long, unrequested answers.

Setup: test split (482 of 482 prompts with both answers), one run, temperature 0, max 2048 tokens, reasoning "low", one user message, the row's context appended to every variant: the final benchmark's settings. Frozen pipeline (`final-for-test`); nothing tuned. No judge. Reduction = (degraded - optimized) / degraded, per prompt; CI = 10,000 bootstrap resamples of the per-prompt reductions; Wilcoxon signed-rank test on the paired token counts; aggregate = reduction of the summed tokens.

## Degraded vs A+B (Stage A + Stage B)

| set | n | tokens | degraded (mean) | A+B (mean) | reduction: aggregate | mean per item [95% CI] | median per item | Wilcoxon p |
|---|---|---|---|---|---|---|---|---|
| all | 482 | input | 226 | 241 | -6.3% | **-11.1%** [-12.1%, -10.2%] | -6.3% | < 0.001 |
|  |  | output | 682 | 165 | 75.8% | **52.7%** [48.2%, 57.1%] | 71.1% | < 0.001 |
|  |  | total | 909 | 406 | 55.4% | **39.2%** [35.9%, 42.5%] | 47.6% | < 0.001 |
| closed_qa | 99 | input | 279 | 290 | -3.9% | **-4.6%** [-5.1%, -4.2%] | -4.6% | < 0.001 |
|  |  | output | 835 | 127 | 84.8% | **62.6%** [54.3%, 70.5%] | 82.1% | < 0.001 |
|  |  | total | 1115 | 417 | 62.6% | **44.5%** [37.6%, 51.3%] | 53.6% | < 0.001 |
| information_extraction | 93 | input | 338 | 351 | -4.1% | **-5.8%** [-6.8%, -4.9%] | -4.9% | < 0.001 |
|  |  | output | 538 | 115 | 78.7% | **32.1%** [18.1%, 44.9%] | 41.7% | < 0.001 |
|  |  | total | 875 | 466 | 46.8% | **24.2%** [16.2%, 32.4%] | 12.6% | < 0.001 |
| classification | 98 | input | 98 | 122 | -24.0% | **-26.1%** [-28.4%, -23.8%] | -29.8% | < 0.001 |
|  |  | output | 390 | 156 | 59.9% | **40.8%** [31.0%, 50.2%] | 59.4% | < 0.001 |
|  |  | total | 488 | 278 | 43.0% | **28.5%** [21.1%, 35.8%] | 38.7% | < 0.001 |
| summarization | 94 | input | 338 | 348 | -3.0% | **-3.8%** [-4.3%, -3.4%] | -3.8% | < 0.001 |
|  |  | output | 831 | 204 | 75.4% | **63.1%** [55.5%, 70.3%] | 78.3% | < 0.001 |
|  |  | total | 1169 | 552 | 52.8% | **43.3%** [37.0%, 49.4%] | 47.7% | < 0.001 |
| coding | 98 | input | 89 | 102 | -14.5% | **-14.7%** [-15.7%, -13.7%] | -15.1% | < 0.001 |
|  |  | output | 813 | 222 | 72.8% | **64.1%** [55.8%, 71.5%] | 79.3% | < 0.001 |
|  |  | total | 903 | 324 | 64.1% | **54.7%** [48.0%, 60.8%] | 67.2% | < 0.001 |

Reasoning tokens (part of output): 26 -> 36 per prompt. Answers cut off at the 2048-token limit: degraded 31, A+B 3.

### Task success where it is checkable without a judge

| category | degraded | A+B | n |
|---|---|---|---|
| classification | 20/48 (42%) | 34/48 (71%) | 48 |
| coding | 85/98 (87%) | 97/98 (99%) | 98 |

classification: every item gets the reference label; coding: a code block is present and Python code in it parses (functional tests: `coding_tests.md`). closed_qa needs the judge and is not checked here; extraction and summarization are not checkable automatically.

## Routed prompts: A+B vs A+B+C

The 31 prompts Stage B sends to Stage C (Stage C's answer accepted for 30; rejected ones keep Stage B's text). Small set: indicative only.

| set | n | tokens | before (mean) | after (mean) | reduction: aggregate | mean per item [95% CI] | median per item | Wilcoxon p |
|---|---|---|---|---|---|---|---|---|
| degraded -> A+B | 31 | input | 183 | 189 | -3.3% | **-7.2%** [-11.9%, -3.0%] | 0.0% | 0.003 |
|  |  | output | 524 | 518 | 1.2% | **3.5%** [-11.5%, 17.9%] | 8.3% | 0.984 |
|  |  | total | 707 | 707 | 0.0% | **4.5%** [-4.3%, 14.1%] | 1.8% | 0.891 |
| degraded -> A+B+C | 31 | input | 183 | 197 | -7.4% | **-12.3%** [-17.2%, -7.9%] | -7.5% | < 0.001 |
|  |  | output | 524 | 130 | 75.2% | **44.9%** [26.4%, 61.9%] | 64.9% | < 0.001 |
|  |  | total | 707 | 327 | 53.8% | **33.3%** [20.9%, 45.5%] | 33.4% | < 0.001 |
| A+B -> A+B+C | 31 | input | 189 | 197 | -3.9% | **-5.1%** [-7.3%, -2.5%] | -4.4% | < 0.001 |
|  |  | output | 518 | 130 | 74.9% | **34.4%** [12.5%, 54.0%] | 47.2% | < 0.001 |
|  |  | total | 707 | 327 | 53.8% | **26.7%** [13.5%, 39.9%] | 25.5% | < 0.001 |

