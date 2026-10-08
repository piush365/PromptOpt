# PromptOpt: final results

Final evaluation of PromptOpt (Mini Project-I, 7CS345, WCE Sangli), run on 2026-10-02 and tagged `final-for-test`.
**Val** is the development split: everything new was tuned and decided on it. **Test** is the final split: run
**once**, after all decisions were committed (the last one in `3d6b81d`, category policy). Nothing was changed
after seeing test numbers; the only edit afterwards was a wording fix in the Stage C report text ("val prompts" ->
"prompts of the split"), no numbers. Sections 7-9 (coding tests, image mode, Compare) were added after
`final-for-test` in finish phases 4-6: they add measurements and features and change nothing in sections 1-6.

Dataset: PromptOpt Dataset v1.2 final (`docs/DATASET_CARD.md`): train 4,509 / val 149 / test 482 / benchmark 44
prompts, five categories. Detailed reports: `stage_a_test_final.md`, `stage_b_test_final.md`, `stage_c_eval.md` (val),
`stage_c_test.md` (test), `attachment_test.md`, `final_benchmark_summary.md`.

<!-- TOKEN:headline:start -->
**Optimized prompts reduce total tokens by 39.2% (95% CI 35.9–42.5%, n = 482)** (`evaluation/token_test.md`): input grows, the saving comes from shorter answers.
<!-- TOKEN:headline:end -->

## 1. Headline numbers (test)

| what | result |
|---|---|
| Stage A category accuracy (degraded prompts) | **74.7%** (macro-F1 0.746) |
| Stage B: output format stated | **3.1% -> 95.0%** of prompts |
| Stage B: prompts sent to Stage C | **6.4%** (31 of 482) |
| Stage B: wrong-category additions | 5.2% |
| Stage B on the benchmark with a real LLM (Cerebras gpt-oss-120b, Groq judge) | quality **8.2 -> 9.0**, task success **67% -> 85%**, total tokens **-57%** |
| Stage C answers usable (pass validation): zero-shot base vs LoRA | **5.0% vs 98.2%** |
| Stage C on routed prompts: output format stated | **22.6% -> 90.3%** (task intent 0.869 -> 0.843) |
| Stage C latency per prompt (laptop RTX 3050 / CPU), median | **0.74 s** / 4.55 s (requirement < 3 s on GPU: met) |
| Attachment rules, hand-made set | 30/30 correct |

## 2. Freeze

* Stage A and Stage B are byte-identical to `frozen-for-test` on prompts without an attachment:
  `python -m app.freeze_check` gives the same sha256 for both (`35f7d4dc...`, all Stage A features, IR, text, steps,
  routing and confidence of the 482 test prompts). Changes after the freeze only act with an attachment
  (B14 spreadsheet, B15 code file, B05 for data attachments; `phase2_freeze_check.md`).
* The Stage A test report is identical to the frozen one (except the timing line). The Stage B test report differs
  only by two rule rows, B14 and B15, each fired on 0 test prompts.

## 2a. Dataset validation (summary of `REVIEW_SUMMARY.md`)

PromptOpt Dataset v1.2 final: 5,184 pairs. Three team members rated 170 rows each (90 shared overlap rows, five
yes/no questions): 330 rows validated, **295 accepted, 35 rejected** (left out). The faculty accepted 19 of 20 rows.

| question (90 overlap rows, 3 raters) | % Y | all 3 agree | Fleiss' kappa | Gwet's AC1 |
|---|---|---|---|---|
| Q1 degraded same task | 96.3% | 90.0% | 0.065 | 0.928 |
| Q3 optimized same intent | 96.3% | 90.0% | 0.065 | 0.928 |
| Q4 optimized better | 98.1% | 94.4% | -0.019 | 0.962 |
| accept (all five Y) | 86.3% | 67.8% | 0.092 | 0.719 |

Kappa paradox: with 96-98% "yes", chance agreement is close to 1, so kappa is near 0 although raters agree on
89-94% of rows; Gwet's AC1 stays at 0.92-0.96 per question. The kappa target (> 0.6) is not met, for this reason.
LLM-assisted filter (not human): an LLM rater accepted 38 of 90 overlap rows (team majority 97.8%); of its Q3 = N rows,
those that add facts, leak the answer, set an impossible constraint or change the task were removed: 9 rows (train 7,
test 2).

## 3. Stage A: feature detection (test, 482 prompts)

| category | n | precision | recall | F1 |
|---|---|---|---|---|
| closed_qa | 99 | 56.7% | 76.8% | 0.65 |
| information_extraction | 93 | 73.2% | 55.9% | 0.63 |
| classification | 98 | 93.1% | 95.9% | 0.94 |
| summarization | 94 | 60.0% | 44.7% | 0.51 |
| coding | 98 | 99.0% | 98.0% | 0.98 |

Accuracy 74.7% (val: 75.8%). Out-of-scope prompts (held-out Dolly brainstorming/creative writing): 68.5% classified
as `other`. Most errors are between closed_qa, information_extraction and summarization, which degraded prompts make
hard to tell apart; Stage B's B08 handles that group without picking one of them.

## 4. Stage B: rule-based optimization (test, 482 prompts)

| category | format: degraded | format: Stage B | format: dataset | words: degraded | words: Stage B | to Stage C |
|---|---|---|---|---|---|---|
| closed_qa | 0.0% | 96.0% | 66.7% | 9.1 | 18.8 | 4.0% |
| information_extraction | 4.3% | 94.6% | 90.3% | 9.1 | 20.9 | 5.4% |
| classification | 0.0% | 90.8% | 81.6% | 18.7 | 32.5 | 15.3% |
| summarization | 2.1% | 94.7% | 63.8% | 8.0 | 16.6 | 5.3% |
| coding | 9.2% | 99.0% | 92.9% | 10.6 | 20.8 | 2.0% |
| **all** | 3.1% | **95.0%** | 79.0% | 11.2 | 22.0 | **6.4%** |

Routed to Stage C: 24 for the task category, 7 for an ambiguous reference. Wrong-category additions: 25 of 482
(5.2%), partly Dolly label noise.

**With a real LLM** (benchmark split, 44 prompts; run before this phase, `final_benchmark_summary.md`): target
`cerebras/gpt-oss-120b`, blind judge `qwen/qwen3.8-27b`.

| variant | quality (0-10) | task success | input tokens | output tokens | total tokens | latency ms |
|---|---|---|---|---|---|---|
| degraded prompt | 8.2 | 67% | 221 | 673 | 894 | 1215 |
| **Stage B** | **9.0** | **85%** | 235 | 151 | **386** | 773 |
| dataset optimized prompt | 9.0 | 81% | 242 | 129 | 371 | 1189 |

### 4.1 Per-rule accuracy, B01-B08 (test, 482 prompts; added after `final-for-test`, measurement only)

Frozen rules, nothing tuned (`stage_b_rule_accuracy.md`, `python -m app.stage_b.rule_accuracy`). **Expected** = the
dataset's optimized prompt fixes the rule's defect while the degraded prompt has it, judged with the Stage A detectors
(B01 filler, B02 repetition, B03 format, B04 length, B05 programming language, B06 labels listed explicitly, B07 data
put in its own block, B08 answer grounded in the provided text). **Fired** = the rule's change-log entry.
**The targets are LLM-written**, so "expected" is the LLM's choice, not a human gold label.

| rule | TP | FP | FN | precision | recall | F1 |
|---|---|---|---|---|---|---|
| B01 remove filler | 18 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| B02 remove duplicates | 0 | 1 | 0 | 0.000 | - | - |
| B03 output format | 243 | 52 | 124 | 0.824 | 0.662 | 0.734 |
| B04 length | 67 | 14 | 146 | 0.827 | 0.315 | 0.456 |
| B05 language | 37 | 3 | 2 | 0.925 | 0.949 | 0.937 |
| B06 labels | 37 | 27 | 20 | 0.578 | 0.649 | 0.612 |
| B07 structure (change log) | 17 | 464 | 0 | 0.035 | 1.000 | 0.068 |
| B08 group fallback | 109 | 40 | 99 | 0.732 | 0.524 | 0.611 |
| **macro (B01-B08)** | | | | **0.615** | **0.728** | **0.631** |
| B07, data moved only (not in macro) | 14 | 33 | 3 | 0.298 | 0.824 | 0.438 |
| macro, with B07 = data moved | | | | 0.648 | 0.703 | 0.684 |

Macro = unweighted mean over the rules where the value is defined (B02 has no expected prompt, so its recall and F1
are left out). Reading:
* B07's change-log entry also covers tidying (capital letter, final '.'), so it fires on 481 prompts; the "data moved"
  row is the meaningful one for B07.
* B01 uses the same filler detector as its "expected", so 1.000 shows consistency, not independent accuracy.
* Low recall for B04 (0.315) and B08 (0.524) is mostly by design: lengths and formats are added only above the 0.6
  confidence gate and only for the categories where they matter, while the LLM targets add them almost everywhere;
  rules also share defects (a length can come from B04 or B08), and a defect fixed by another rule counts as a miss.

## 5. Stage C: LoRA fallback

Qwen2.5-0.5B-Instruct + LoRA (r 16), trained locally on the RTX 3050 (bf16, effective batch 16) on 4,456 train
examples. **Best val loss 0.7047 at step 550**; early stop at step 700 (51 min). Stage C fills only the fields
Stage B left unresolved, must return valid JSON with exactly those keys, and is validated with the Stage A detectors;
otherwise Stage B's result is kept (`docs/STAGE_C_PLAN.md`).

### 5.1 Zero-shot base vs LoRA (all Stage C examples)

| split | model | n | JSON valid | exact keys | passes validation | task sim. | format present/absent agrees | constraints present/absent agrees |
|---|---|---|---|---|---|---|---|---|
| val | zero-shot base | 298 | 95.0% | 50.0% | 3.4% | 0.667 | 66.8% | 49.2% |
| val | LoRA | 298 | 100% | 100% | 98.3% | 0.821 | 72.7% | 77.1% |
| **test** | zero-shot base | 964 | 93.5% | 51.2% | **5.0%** | 0.668 | 56.4% | 53.8% |
| **test** | LoRA | 964 | 100% | 100% | **98.2%** | 0.801 | 78.5% | 75.0% |

### 5.2 Ablation

`routed` = prompts Stage B actually sends to Stage C; `forced` = every prompt with task, output format and
constraints requested. **Task intent** (main intent number) = similarity of the final `task` field to the original
instruction; the degraded prompt keeps the original's own words, so it is close to the ceiling. Full-prompt similarity
is in the detailed reports as a reference only (it falls as format and constraints are added).

| split | set | system | n | task intent | format stated | fallback to Stage B | median s (GPU) |
|---|---|---|---|---|---|---|---|
| val | routed | A+B | 10 | 0.911 | 10.0% | - | - |
| val | routed | A+B+C | 10 | 0.885 | 90.0% | 0.0% | 0.51 |
| val | routed | C-only | 10 | 0.766 | 90.0% | 10.0% | 0.69 |
| **test** | routed | A+B | 31 | **0.869** | 22.6% | - | - |
| **test** | routed | **A+B+C** | 31 | **0.843** | **90.3%** | 3.2% | 0.47 |
| **test** | routed | C-only | 31 | 0.712 | 90.3% | 6.5% | 0.68 |
| val | forced | A+B | 149 | 0.855 | 94.0% | - | - |
| val | forced | A+B+C | 149 | 0.773 | 92.6% | 2.0% | 0.68 |
| val | forced | C-only | 149 | 0.769 | 91.9% | 2.0% | 0.68 |
| **test** | forced | **A+B** | 482 | **0.886** | **95.0%** | - | - |
| **test** | forced | A+B+C | 482 | 0.769 | 90.2% | 2.1% | 0.68 |
| **test** | forced | C-only | 482 | 0.765 | 88.6% | 1.9% | 0.67 |
| test | reference | degraded / dataset optimized | 482 | 0.903 / 0.826 | 3.1% / 79.0% | | |

Findings (the same on val and test):
* **Where Stage B routes a prompt, Stage C helps**: the format is stated in 90% of routed prompts instead of 10-23%,
  at a small loss in task intent (-0.03).
* **Routing everything through Stage C hurts**: when Stage C rewrites tasks Stage B already handled, task intent
  drops (test 0.886 -> 0.769, below the dataset's own optimized prompts at 0.826) and no format is gained. Stage C
  stays a fallback for routed prompts only.
* **C-only is the weakest** (routed, test: task intent 0.712): Stage B's rules are worth keeping in front of Stage C.

### 5.3 Category on prompts routed for the task category

Policy (decided on val, plan section 6): Stage C's category is never used on its own; the UI asks the user and
pre-selects Stage C's guess. Right = equals the dataset label.

| split | prompts | n | Stage A right | Stage C guess right |
|---|---|---|---|---|
| val | routed, valid Stage C category | 9 | 2/9 (22%) | 3/9 (33%) |
| val | every prompt, Stage A confidence < 0.6 | 50 | 40.0% | 30.0% |
| **test** | routed, valid Stage C category | 24 | 9/24 (37.5%) | **14/24 (58.3%)** |
| **test** | every prompt, Stage A confidence < 0.6 | 171 | **45.0%** | 41.5% |
| test | every prompt | 476 | 74.4% | 61.6% |

On the small routed set Stage C's guess was better than Stage A's on test (14 vs 9 of 24), the opposite of val
(3 vs 2 of 9). Over the whole low-confidence range Stage A stays slightly ahead (45.0% vs 41.5%). Neither is reliable
enough to decide alone, which supports asking the user; pre-selecting Stage C's guess was the right default on test's
routed prompts. The policy was not changed after seeing these numbers.

### 5.4 Named case (illustrative, not evidence)

`describe what is happening in the picture` + image: Stage A says coding (0.37), so the prompt is routed; Stage C
guesses summarization, the expected label (set after a smoke run, so illustrative only); the UI pre-selects it.

### 5.5 Latency (Stage C call only, batch 1, greedy)

| split | device | median s | p95 s |
|---|---|---|---|
| val | RTX 3050 laptop GPU | 0.71 | 1.15 |
| val | CPU | 4.63 | 7.61 |
| **test** | **RTX 3050 laptop GPU** | **0.74** | 1.23 |
| test | CPU | 4.55 | 7.22 |
| test | zero-shot base, GPU | 1.47 | 3.30 |

Requirement under 3 s per prompt on the laptop GPU: **met**.

## 6. Attachments, rendering, app

* **Attachment rules** (B09-B15): 30/30 hand-made prompts correct (own rule fired, no other, requirements and the
  attachment note in all three renderings, ambiguous references resolved; `attachment_test.md`). **Attachment and image results are on developer-written prompts only.** Blind sets
  written by people outside the development team (attachments 15 rows, image 10 rows) are **future work**
  (`attachment_blind_test.md`, `image_blind_test.md`).
* **Renderers**: the same content for all three targets (Claude XML tags, GPT `###` sections, Gemini plain labels
  with the instruction first); every rendering is parsed back in the tests to check no field is lost. Input tokens per
  target: GPT exact (tiktoken o200k_base), Claude/Gemini approximate (characters / 4, labelled).
* **App**: FastAPI + plain HTML/JS, fully offline (`uvicorn app.api:app` in `backend/`); Compare is disabled until API
  keys for the real target LLMs exist.

## 7. Coding: tests in a sandbox (finish phase 4, after `final-for-test`)

Does the code the model writes actually work? Python test/benchmark coding items only (test: 47 of 98 coding items
are Python; other languages not run). Cerebras gpt-oss-120b writes 3-6 assert tests per item, each kept only if it
passes on the CodeAlpaca reference; references that fail are listed as suspects, not dropped. Code runs only in a
bubblewrap sandbox (no network, read-only system, memory/CPU/process limits). Target: Cerebras gpt-oss-120b, the
benchmark's settings. Details: `coding_tests.md`, `docs/CODING_TESTS.md`.

| test split (29 tested items) | pass@1 strict | pass@1 lenient (naming-only failures counted as passes) |
|---|---|---|
| degraded prompt | 6/29 (20.7%) | 11/29 (37.9%) |
| **Stage B prompt** | **10/29 (34.5%)** | 12/29 (41.4%) |

Paired (strict): Stage B passes 4 items degraded fails, never the reverse (sign test p = 0.125; n is small). The gain is
mostly interface: degraded answers more often name the function differently, give several alternatives, or are not
Python. Real failures (wrong results) are similar (13 vs 16). Scope: 4 reference suspects, 14 untestable items
(fragments, interactive, third-party packages), all reported.

## 8. Image-generation mode (finish phase 5)

A separate mode the user selects; Stage A/B/C are not involved. Details and images: `image_mode.md`. All prompts
(dev and held-out) were written by the developers; a blind set written by others is future work.

* **v1** filled every missing attribute (style, lighting, palette, ...) with "neutral" defaults. On a dev set of 40
  prompts, images from v1's Stable Diffusion prompts matched the user's request worse than the original prompt
  (CLIP vs original prompt 28.44 vs 29.95, worse in 25 of 40, p = 0.009): keywords like "natural lighting" turned a
  watercolor request into a photo.
* **v2** (the app's default) keeps the user's words first and adds nothing that can conflict; every other attribute is
  a clickable suggestion. Final configuration chosen on dev; then a **held-out set of 30 prompts, written and
  committed before any v2 code, run once** (SD 1.5 on the RTX 3050, 7.5 s/image):

| held-out (n = 30) | CLIP vs original prompt | vs original: higher / lower / tie | style kept (12 styled) |
|---|---|---|---|
| original prompt | 33.08 | - | 12/12 |
| v1 | 30.78 | 7 / 18 / 5 (p = 0.043) | 10/12 |
| **v2** | **32.77** | 0 / 4 / 26 (p = 0.125) | **12/12** |
| v2 + every first suggestion (simulated) | 31.07 | 3 / 20 / 7 (p < 0.001) | 10/12 |

v2 does no measurable harm; CLIP against the user's own wording can show harm but not improvement (it also ignores
negation: "without clouds" scores higher with clouds). Lesson: filling attributes raised coverage to 9.0 of 9 per
prompt and made the images worse; the image model's output against the user's request is the check that matters.

## 9. Compare (finish phase 6)

The app's Compare runs the original and the optimized prompt on the same model (temperature 0, same max tokens),
side by side: answers, input/output/reasoning/total tokens, latency, sandbox tests for dataset coding items, and an
optional blind judge. Available now: gpt-oss-120b on Groq and Cerebras; Gemini when `GEMINI_API_KEY` is set; GPT and
Claude are listed as "add API key". Every result says which model answered: a Claude-rendered prompt run on gpt-oss is
labelled as a stand-in. Live examples (`compare_examples.md`, Groq gpt-oss-120b; illustrations, not evidence):

| prompt | original total tokens | optimized total tokens | change | quality |
|---|---|---|---|---|
| coding: "write code to get all permutations of a string" | 768 | 248 | **-67.7%** | both 6/6 tests, judge 10/10 |
| closed_qa: "which company bought hackpad according to that text?" + passage | 238 | 279 | **+17.2%** | both judge 10/10 |

The closed_qa answer was already one line, so the longer optimized prompt cannot pay for itself.

## 9a. Token evaluation on the full test split (after `final-for-test`)

<!-- TOKEN:section:start -->
**Optimized prompts reduce total tokens by 39.2% (95% CI 35.9–42.5%, n = 482)** [`token_test.md`]: mean of the per-prompt changes in total tokens (input + output, output including hidden reasoning tokens), degraded prompt vs Stage A + B, on `cerebras/gpt-oss-120b`, temperature 0, the final benchmark's settings, frozen pipeline. Summed over all prompts: -55.4%; Wilcoxon signed-rank p < 0.001.

**Input grows; the saving comes from output.** Input tokens 226 -> 241 per prompt (+11.1% per prompt); output tokens 682 -> 165 (-52.7% per prompt): a stated format and length stop long, unrequested answers.

| category | n | input tokens (mean) | output tokens (mean) | total tokens (mean) | total: mean change per prompt [95% CI] | total: summed tokens |
|---|---|---|---|---|---|---|
| closed_qa | 99 | 279 -> 290 | 835 -> 127 | 1115 -> 417 | -44.5% [-51.3%, -37.6%] | -62.6% |
| information_extraction | 93 | 338 -> 351 | 538 -> 115 | 875 -> 466 | -24.2% [-32.4%, -16.2%] | -46.8% |
| classification | 98 | 98 -> 122 | 390 -> 156 | 488 -> 278 | -28.5% [-35.8%, -21.1%] | -43.0% |
| summarization | 94 | 338 -> 348 | 831 -> 204 | 1169 -> 552 | -43.3% [-49.4%, -37.0%] | -52.8% |
| coding | 98 | 89 -> 102 | 813 -> 222 | 903 -> 324 | -54.7% [-60.8%, -48.0%] | -64.1% |
| **all** | 482 | 226 -> 241 | 682 -> 165 | 909 -> 406 | -39.2% [-42.5%, -35.9%] | -55.4% |

**No category shows a net increase** in total tokens; the smallest saving is information_extraction (-24.2% per prompt). **Limitation:** input grows in every category, and **87 of 482 prompts (18.0%) individually cost more** in total, because their answer was already short: information_extraction 35/93, classification 23/98, closed_qa 11/99, summarization 10/94, coding 8/98. Future work: a **lean mode** that adds less (only the output-format line, or nothing) when the expected answer is short.

Routed prompts (A+B vs A+B+C) and task success where checkable without a judge: `token_test.md`.
<!-- TOKEN:section:end -->

## 10. Known limitations

* Stage C training targets come from LLM-written optimized prompts; only 111 train rows were individually
  human-validated (the rest passed the human-rejection pass and the LLM-assisted filter).
* The parser separates constraints from the task in 75% of the prompts that state one; lengths embedded in the task
  wording stay in the task (8.8% of constraint targets affected; plan section 2.5).
* Stage C's format/constraint content is only moderately close to the targets (format present/absent agreement 78.5%,
  similarity 0.62 on test).
* The routed set is small (10 val, 31 test prompts); the forced rows give the larger picture.
* Category accuracy where prompts are routed is low for both Stage A and Stage C (about 40-45%), hence the user is
  asked.
* Real GPT/Gemini/Claude runs need API keys and are not done; the LLM numbers above use Cerebras/Groq stand-ins.
* After Stage B, 27 test prompts that are not sent to Stage C still state no programming language according to the A03
  detector (`stage_b_test_final.md`, "Missing constraints left after Stage B").
* Coding tests: Python items only (29 tested on test); the test writer is the same model as the target (tests are
  validated on an independent reference, which limits but does not remove the bias).
* Image mode: measured with SD 1.5 and CLIP only; DALL-E and Nano Banana prompts are untested without API keys.
* Attachment and image results are on developer-written prompts only; blind sets written by others are future work.
* Compare and all LLM numbers use gpt-oss-120b (Groq/Cerebras) as a stand-in for GPT, Gemini and Claude.
<!-- TOKEN:limitation:start -->
* **Token cost:** input tokens grow in every category; no category increases total tokens on average, but 87 of 482 test prompts (18.0%) individually cost more, most in information_extraction (35/93). Future work: lean mode (`token_test.md`).
<!-- TOKEN:limitation:end -->

## 11. Reproduce (inside `backend/`)

```
python -m app.freeze_check                                             # Stage A/B vs frozen-for-test
python -m app.stage_a.evaluate --split test --out ../evaluation/stage_a_test_final.md
python -m app.stage_b.evaluate --split test --out ../evaluation/stage_b_test_final.md
python -m app.stage_b.rule_accuracy --out ../evaluation/stage_b_rule_accuracy.md  # per-rule accuracy (4.1)
python -m app.stage_c.data --test                                      # data/stage_c/test.jsonl
.venv-gpu/bin/python -m app.stage_c.evaluate --split test --adapter artifacts/stage_c_adapter \
    --out ../evaluation/stage_c_test.md                                # and --split val for stage_c_eval.md
python -m app.attachment_eval --out ../evaluation/attachment_test.md
python -m app.coding.testgen && python -m app.coding.evaluate --out ../evaluation/coding_tests.md
.venv-gpu/bin/python -m app.image.generate --set heldout && .venv-gpu/bin/python -m app.image.evaluate --out ../evaluation/image_mode.md
.venv-gpu/bin/python -m app.evaluation.tokens --out ../evaluation/token_test.md
```
