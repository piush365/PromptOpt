# 1. Introduction, objectives and working method

[Back to the index](README.md)

This chapter says what problem PromptOpt solves, what it set out to do, what it deliberately does not do, and the
working method that makes its numbers trustworthy (development / validation / test discipline, the freeze, the tags).
Every later chapter assumes this method.

---

## 1.1 The problem

People write prompts the way they type a search query: short, vague, with no statement of what the answer should look
like. Typical examples from the dataset:

| what the user typed (degraded prompt) | what is missing |
|---|---|
| `hey can you please summarize this for me` | which text ("this"), how long, what format; three filler phrases |
| `write code to get all permutations of a string` | programming language, output format (the model writes several versions and long explanations) |
| `which instrument is string or percussion udu bulbul tarang` | the label set is implicit, no output layout, the items run into the question |
| `who's octavio tarquínio de sousa` | that the answer must come from the attached text, how long it may be |

A large language model (LLM) answers such a prompt by guessing. The guesses are expensive in a way that is easy to
miss: the model writes long, unrequested answers (alternatives, explanations, extra code), and every output token is
paid for, adds latency and makes the answer harder to use or check. The project measured this directly: on the 482
test prompts, the vague prompts produced on average **682 output tokens**, the optimized prompts **165**
(`evaluation/tokens/token_test.md`, see chapter 9).

Existing approaches do not fit a single user typing a single prompt:

* **Automatic prompt optimization** (APE, OPRO and similar) searches over many candidate instructions with many LLM
  calls, scoring each on a labelled development set. That is suitable for one fixed task, not for one ad-hoc user
  prompt, and the user does not see why the result is better.
* **Prompt compression** (e.g. LLMLingua) removes input tokens. PromptOpt's measurements show the opposite lever: the
  optimized prompt is *longer* (input 226 → 241 tokens on average) and the saving comes from *shorter answers*.
  A study that counts only input tokens would miss the effect entirely.

## 1.2 Objectives

From the Software Requirements Specification (`docs/SRS_PromptOpt.docx`), restated in `docs/PROJECT_REPORT.md`:

1. **Detect** what a prompt is missing: output format, constraints (length, tone, audience, programming language),
   task category, ambiguous references, filler.
2. **Fix** it with deterministic, individually testable rules; use a small fine-tuned model **only** for what the
   rules cannot resolve.
3. Produce **one model-agnostic intermediate representation (IR)** and render it for GPT, Gemini and Claude.
4. **Measure, not assume**: tokens (input **and** output), quality, task success, latency, with an ablation.
5. Run **self-hosted and offline** (the optimizer needs no API), treat target LLMs as black boxes, strip personal data.

Product goals (`CLAUDE.md`, "Product goals"): the user enters any prompt and selects a target LLM (GPT, Gemini or
Claude), a category (one of five, or auto-detect; a user choice overrides the detector) and optionally an attachment
type (image, PDF, PPTX, ...) that acts as a modifier, not a category. The core feature, **Compare**, runs the original
and the optimized prompt on a real model side by side.

## 1.3 Scope

**In scope**

* Five task categories, fixed for the whole project:

  | category | source dataset | what it means |
  |---|---|---|
  | `closed_qa` | Dolly-15k | a question answered from a given passage |
  | `information_extraction` | Dolly-15k | pull specific facts/items out of a passage |
  | `classification` | Dolly-15k | assign labels to items |
  | `summarization` | Dolly-15k | condense a passage |
  | `coding` | CodeAlpaca-20k | write, fix or explain code |
  | `other` | (none) | anything the detector cannot place: brainstorming, creative writing, chit-chat |

* Three target LLM families for rendering (Claude, GPT, Gemini), with exact token counts for GPT and approximate ones
  for the others (chapter 7).
* An attachment modifier with seven types (image, pdf, pptx, docx, spreadsheet, code, other).
* A separate, explicitly chosen **image-generation mode** (DALL-E, Nano Banana, Stable Diffusion; chapter 11).
* A web application with history (30-day retention) and Compare (chapter 12, chapter 13, chapter 14).

**Out of scope / not done (by decision)**

* Paid APIs. All LLM work uses free tiers (Groq, Cerebras; Gemini wired but never run live). Real GPT and Claude runs
  need API keys and are future work. The LLM numbers therefore use **gpt-oss-120b as a stand-in** for the target
  families; this is labelled everywhere it matters.
* Blind test sets written by people outside the team for attachments and image prompts (future work; results on
  these features rest on developer-written prompts only).
* Changing the frozen text pipeline after the final test run (section 1.5).

## 1.4 Constraints that shaped the design

| constraint | consequence in the design |
|---|---|
| a 4 GB laptop GPU (NVIDIA RTX 3050) and a CPU-only default install | Stage C uses a 0.5-billion-parameter model with LoRA (chapter 6); the app runs fully without it |
| free API tiers with daily token limits (Groq 200,000 tokens/day per model; Cerebras 1,000,000) | every LLM call is recorded in a rolling 24-hour ledger; tools stop at 70% of a limit (chapter 13.8) |
| examiners must be able to follow every change | Stage B rules are small pure functions, each change is logged with before/after text (chapter 5) |
| results must not be tuned on the test set | strict split discipline, a freeze tag and a byte-level freeze check (section 1.5) |
| privacy | emails and phone numbers are removed **before** anything is stored; prompts expire after 30 days (chapter 13.6) |

## 1.5 Working method: development, validation, test, freeze

### 1.5.1 The four splits

The dataset (chapter 3) is split by **original instruction**, so the same instruction never appears in two splits
(no leakage through paraphrases). Final sizes (v1.2 final): train 4,509 / val 149 / test 482 / benchmark 44.

| split | used for | who may look at it |
|---|---|---|
| train | building Stage A's k-NN index and logistic head; Stage C training data | everything |
| val | every tuning decision (thresholds, rule wording, Stage C policy, judge wording) | development |
| test | the final offline numbers (Stage A, Stage B, Stage C) | run **once**, after the last decision was committed |
| benchmark | the final LLM run (real model + judge) | run **once** |

The command-line tools enforce this: `python -m app.evaluation.run --split test` refuses to run without `--final`
(`backend/app/evaluation/run.py`, `FINAL_SPLITS`), `--refresh` is refused with `--final`, and `check_final_once`
refuses to repeat a final run on a different dataset version.

### 1.5.2 The freeze

On 2026-09-27 the code used for the final runs was tagged `frozen-for-test`. From then on:

* no Stage A or Stage B rule, threshold or judge change was allowed;
* if a bug was found it was **reported, not fixed** (two such bugs are documented in chapter 15.5);
* only data steps were allowed (merging ratings, dropping rejected rows, retraining the Stage A index on the final
  train split).

Features added later (attachment rules B14/B15, the B05 data-attachment refinement) had to prove that they act **only
when an attachment is given**. The proof is mechanical:

**Freeze check** (`backend/app/freeze_check.py`, `python -m app.freeze_check`):

1. check out `frozen-for-test` into a temporary git worktree;
2. with the reference code and with the current code, run Stage A + Stage B on every test prompt (no attachment) and
   dump, per prompt: all Stage A features, the IR, the optimized text, the change log, the Stage C routing flag and
   the confidence, as JSON with sorted keys;
3. compute the SHA-256 of both dumps; equal hashes mean the two pipelines produce byte-identical output.

Both runs use the current category index and the final dataset, so only code can differ. Result (also re-run after
the fixes of this review, 2026-10-10): `35f7d4dcc929cbd8eee98474f5f941e8a5ef320dd117bdcfe774f3189713cb5e` for both,
**BYTE-IDENTICAL** on 482 prompts.

Why SHA-256 of the whole dump: a single changed character anywhere (one word in one rule's output, one rounding of
one confidence) changes the hash, so "identical" is a strong, cheap and reproducible statement. It does not say *what*
changed if the hashes differ; for that the two JSON dumps are diffed.

### 1.5.3 Tags and timeline

Dates are from the git history.

| date | tag / event | meaning |
|---|---|---|
| 2026-08-13 | first commit | repository created |
| 2026-09 | dataset v1 (Colab), v1.1 repair, v1.2 expansion | chapter 3 |
| 2026-09-27 | `frozen-for-test` (`f4db6cb`) | Stage A/B code for the final numbers |
| 2026-09-28 | final benchmark run | 44 prompts × 3 variants on Cerebras gpt-oss-120b, judged by Groq qwen |
| 2026-10-02 | `final-for-test` (`62e54bf`) | the one test run of Stage A/B/C; `evaluation/FINAL_RESULTS.md` |
| 2026-10-02 → 10-08 | finish phases 4–7 | coding sandbox tests, image mode, Compare, full-test token evaluation |
| 2026-10-08 | `v1.0` (`3c0ab73`) | project close-out; GitHub release with the Stage C adapter and the Stage A index |
| 2026-10-09 → 10-10 | correctness suite, `pre-ui-v2` (`15a16ea`), UI v2 (branch `ui-v2`, `1986fd5`) | 50 hand-written cases; React UI |
| 2026-10-10 | this review | the fixes in chapter 15.4 and this documentation |

### 1.5.4 How numbers are reported

* Every result in this documentation is copied from a report file in `evaluation/` (cited next to it) or recomputed
  from committed data by a script whose output is shown. Settings are quoted from the code with the file they are in.
* "Illustrative" examples (one prompt through the pipeline) are labelled as such; they are not evidence.
* Where something was never measured, the documentation says so.
* Percentages are rounded to one decimal; differences that come only from rounding the inputs are pointed out where
  they occur (for example 55.3% vs 55.4% in chapter 9.3).

## 1.6 Team and roles

Mini Project-I (7CS345), Department of Computer Science and Engineering, Walchand College of Engineering, Sangli,
2026-27. Team: Nirzara Manade, Siddhi Bolaikar, Piush Gogi. Guide: Prof. A. S. Pawar. The three team members were also
the human raters of the dataset (chapter 3.8); the guide rated 20 rows as an independent check.

## 1.7 Where to go next

* For the system as a whole: [chapter 2](02_architecture.md).
* For how the data was made and validated: [chapter 3](03_dataset.md).
* For the three stages: chapters [4](04_stage_a_feature_detection.md), [5](05_stage_b_rule_optimizer.md),
  [6](06_stage_c_lora_fallback.md).
* For the numbers: [chapter 8](08_evaluation_methodology.md) (how) and [chapter 9](09_results.md) (what).
