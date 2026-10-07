# PromptOpt: project report

**Token-efficient prompt optimization for LLMs.** Mini Project-I (7CS345), Department of Computer Science and
Engineering, Walchand College of Engineering, Sangli, 2026-27. Team: Nirzara Manade, Siddhi Bolaikar, Piush Gogi.
Guide: Prof. A. S. Pawar.

Every number below is copied from an evaluation file in this repository, cited next to it in brackets.
`FINAL_RESULTS.md` means `evaluation/FINAL_RESULTS.md`; other report files are in `evaluation/` unless a path is
given. Code at tag `v1.0`; the final test numbers come from tag `final-for-test`.

<!-- TOKEN:headline:start -->
**Optimized prompts reduce total tokens by 39.2% (95% CI 35.9–42.5%, n = 482)** (`evaluation/token_test.md`): input grows, the saving comes from shorter answers.
<!-- TOKEN:headline:end -->

---

## 1. Problem

People write prompts the way they type a search query: short, vague, without saying what the answer should look
like ("summarize this", "write code for permutations"). The model then guesses, often writing long, unrequested
answers (explanations, alternatives, several code versions). That costs output tokens, latency and money, and the
answer is harder to use or check.

Automatic prompt optimization exists, but mostly as a research method that searches for a better *task* prompt with
many LLM calls on a labelled development set. A user typing one prompt needs something else: a cheap, immediate,
explainable rewrite of *their* prompt, for the model they actually use, plus evidence that it helps.

## 2. Objectives

From the SRS (`docs/SRS_PromptOpt.docx`):

1. Detect what a prompt is missing (output format, constraints, task category, ambiguous references, filler).
2. Fix it with deterministic, individually testable rules; use a small fine-tuned model only for what the rules
   cannot resolve.
3. Produce one model-agnostic intermediate representation (IR) and render it for GPT, Gemini and Claude.
4. Measure, not assume: tokens (input **and** output), quality, task success, latency, with an ablation.
5. Run self-hosted and offline (the optimizer needs no API), treat target LLMs as black boxes, strip PII.

## 3. Literature and gap (short)

* **Automatic prompt optimization** (survey: Ramnath et al., EMNLP 2025; e.g. APE, OPRO) searches over candidate
  instructions with an LLM, scoring each on a labelled dev set. Good for a fixed task; expensive per task, not
  per user prompt, and not explainable to the user.
* **Cost-aware optimization** (CAPO, Zehle et al., AutoML 2025) adds prompt length to the objective, but still
  optimizes a task prompt with many LLM evaluations.
* **Prompt compression** (e.g. LLMLingua) removes input tokens. Our measurements show the opposite lever: the
  optimized prompt is *longer*, and the saving comes from *shorter answers*. Input-only token counts miss this.
* **Format sensitivity** (Ngweta et al., NAACL-SRW 2025): LLMs react to prompt formatting, which motivates rendering
  the same content per model family.

**Gap addressed:** a per-prompt, offline, rule-first optimizer with a small LoRA fallback, model-specific rendering,
and an honest evaluation of *net* tokens (input + output, including hidden reasoning tokens) on a held-out test
split, with every change logged.

## 4. Architecture

```
user prompt + target LLM + category (auto / 5) + optional attachment type
        |
  Stage A  feature detection (spaCy, regex, sentence-transformers + linear head)  -> PromptFeatures
        |
  Stage B  rules B01-B15 (category rules only at confidence >= 0.6; B08 group fallback;
        |  B09-B15 attachment modifiers), every change logged                     -> IR + unresolved fields
        |
  Stage C  Qwen2.5-0.5B-Instruct + LoRA, ONLY if Stage B left the category or an
        |  ambiguous reference unresolved; patches those fields, validated, else Stage B is kept
        |
  IR (task, context, constraints, requirements, output_format, attachment, ...)
        |
  renderers: Claude (XML tags, context first) | GPT (### sections) | Gemini (plain labels, instruction first)
        |
  web app (FastAPI + HTML/JS): optimized prompt per target, input tokens, history (30 days), Compare
```

* **Stage A** (`backend/app/stage_a/`): category with a confidence (embedding classifier trained on the train split,
  keyword cues as fallback), missing output format (A02), missing constraints (A03: length, tone, audience,
  language), filler (A04), ambiguous references (A05).
* **Stage B** (`backend/app/stage_b/`, rule catalogue `backend/app/db/seed.py`): B01 filler, B02 duplicates, B03
  output format, B04 length, B05 programming language, B06 explicit label set, B07 structure, B08 text-group
  fallback, B09-B15 one rule per attachment type. Category-specific rules (B03-B06) fire only at Stage A confidence
  >= 0.6; below that, B08 handles the closed_qa / extraction / summarization group without choosing one.
* **B -> C contract** (`backend/app/stage_b/optimizer.py` `STAGE_C_REASONS`, `backend/app/stage_c/contract.py`):
  Stage C runs only when the category is still unresolved after the 0.6 gate and B08, or an ambiguous reference
  remains. It must return JSON with exactly the unresolved keys; the answer is checked with Stage A's own detectors
  and rejected (Stage B's result kept) if invalid. Stage C's category is only a suggestion: the UI asks the user
  and pre-selects it.
* **Rendering** (`backend/app/rendering.py`): the same four sections for every target; tests parse each rendering
  back to check that nothing is lost. Input tokens per target: GPT exact (tiktoken o200k_base), Claude and Gemini
  approximate (characters / 4, labelled as such).
* **Image mode** (`backend/app/image/`): a separate, explicitly chosen mode for DALL-E, Nano Banana and Stable
  Diffusion; Stage A/B/C are not involved (section 9).
* **Compare** (`backend/app/compare/`): runs the original and the optimized prompt on the same real model, side by
  side, with tokens, latency, sandbox tests for coding items and an optional blind judge (section 11).
* **Database** (`backend/app/db/`): 10 tables, SQLite or PostgreSQL through SQLAlchemy; PII (emails, phone numbers)
  stripped before storing; 30-day retention.

## 5. Dataset and validation

**PromptOpt Dataset v1.2 final**: 5,184 degraded -> optimized prompt pairs, five categories, built from Dolly-15k
(closed_qa, information_extraction, classification, summarization) and CodeAlpaca-20k (coding). Splits with no
instruction shared across them: train 4,509 / val 149 / test 482 / benchmark 44 [`REVIEW_SUMMARY.md` section 1;
`docs/DATASET_CARD.md`]. Optimized prompts were written by LLMs (Groq / Cerebras gpt-oss-120b, gpt-oss-20b,
qwen3.8-27b) under explicit rules, then checked automatically and repaired deterministically (v1.1: data dropped from
the instruction put back) [`docs/DATASET_CARD.md`].

**Human validation** [`REVIEW_SUMMARY.md` section 2]: three team members rated 170 rows each (90 shared overlap
rows), five yes/no questions per row; 330 rows validated, **295 accepted, 35 rejected** and left out.

| question (90 overlap rows, 3 raters) | % Y | all 3 agree | Fleiss' kappa | Gwet's AC1 |
|---|---|---|---|---|
| Q1 degraded same task | 96.3% | 90.0% | 0.065 | 0.928 |
| Q3 optimized same intent | 96.3% | 90.0% | 0.065 | 0.928 |
| Q4 optimized better | 98.1% | 94.4% | -0.019 | 0.962 |
| accept (all five Y) | 86.3% | 67.8% | 0.092 | 0.719 |

**Kappa paradox:** with 96-98% "yes", chance agreement is already near 1, so kappa is near 0 or negative although
the raters agree on 89-94% of rows. Gwet's AC1 does not collapse this way (0.92-0.96 per question). The guide's
target (kappa > 0.6) is not met, for this reason [`REVIEW_SUMMARY.md` section 2]. Faculty check: 19 of 20 rows
accepted [`REVIEW_SUMMARY.md` section 3].

**LLM audit and filter** [`REVIEW_SUMMARY.md` section 4]: an LLM rater (Claude) rated the 90 overlap rows as a
strict reviewer, never counted in any human statistic. It accepted 38 of 90 (team majority 97.8%). Only rows where
it found the optimized prompt changed the intent (Q3 = N, 26 rows) were reviewed, and only rows that add facts, leak
the answer, set an impossible constraint or change the task were removed: **9 rows** (train 7, test 2).

## 6. Stage A results (test, 482 prompts)

**Category accuracy 74.7%** (macro-F1 0.746; val 75.8%). Coding F1 0.98, classification 0.94; closed_qa 0.65,
information_extraction 0.63, summarization 0.51: degraded prompts in this group are genuinely hard to tell apart.
Out-of-scope prompts (held-out Dolly brainstorming / creative writing): 68.5% classified as `other`
[`FINAL_RESULTS.md` sections 1, 3; `stage_a_test_final.md`].

## 7. Stage B results

**Test, 482 prompts** [`FINAL_RESULTS.md` section 4; `stage_b_test_final.md`]:

| metric | result |
|---|---|
| output format stated (A02 detector): degraded -> Stage B | **3.1% -> 95.0%** (dataset's LLM-written optimized prompts: 79.0%) |
| mean words: degraded -> Stage B | 11.2 -> 22.0 |
| prompts routed to Stage C | **6.4%** (31: 24 for the category, 7 for an ambiguous reference) |
| wrong-category additions | 5.2% (25 of 482; partly Dolly label noise) |

**With a real LLM** (benchmark split, 44 prompts, target Cerebras gpt-oss-120b, blind judge qwen3.8-27b)
[`FINAL_RESULTS.md` section 4; `final_benchmark_summary.md`]:

| variant | quality (0-10) | task success | input tok | output tok | total tok |
|---|---|---|---|---|---|
| degraded prompt | 8.2 | 67% | 221 | 673 | 894 |
| **Stage B** | **9.0** | **85%** | 235 | 151 | **386** |
| dataset optimized prompt | 9.0 | 81% | 242 | 129 | 371 |

**Freeze:** Stage A and B are byte-identical to tag `frozen-for-test` on all 482 test prompts without an attachment
(`python -m app.freeze_check`, sha256 `35f7d4dc...`); later rules (B14, B15, B05 for data attachments) act only with
an attachment [`FINAL_RESULTS.md` section 2; `phase2_freeze_check.md`].

**Attachments:** 30/30 hand-made prompts correct [`attachment_test.md`]. **Attachment and image results are on
developer-written prompts only**; blind sets written by people outside the development team are future work
[`attachment_blind_test.md`, `image_blind_test.md`].

## 8. Stage C results and ablation

Qwen2.5-0.5B-Instruct + LoRA (r 16), trained locally on an RTX 3050 laptop GPU (bf16, effective batch 16) on 4,456
train examples; **best val loss 0.7047 at step 550**, early stop at 700, 51 min [`FINAL_RESULTS.md` section 5].

| (test) | zero-shot base | LoRA |
|---|---|---|
| answers that pass validation | 5.0% | **98.2%** |
| JSON valid | 93.5% | 100% |

**Ablation** (test) [`FINAL_RESULTS.md` section 5.2; `stage_c_test.md`]:

| set | system | n | task intent | format stated |
|---|---|---|---|---|
| routed | A+B | 31 | 0.869 | 22.6% |
| routed | **A+B+C** | 31 | 0.843 | **90.3%** |
| routed | C-only | 31 | 0.712 | 90.3% |
| forced (all prompts) | **A+B** | 482 | **0.886** | **95.0%** |
| forced (all prompts) | A+B+C | 482 | 0.769 | 90.2% |

* Where Stage B routes a prompt, Stage C states a format in 90% instead of 23%, at a small loss of task intent.
* Routing everything through Stage C hurts (task intent 0.886 -> 0.769): **Stage C stays routed-only.**
* C-only is weakest: the rules are worth keeping in front of the model.
* Latency: median **0.74 s** per Stage C call on the laptop GPU, 4.55 s on CPU (requirement < 3 s on GPU met)
  [`FINAL_RESULTS.md` section 5.5].
* Category on routed prompts: Stage C's guess right 14/24, Stage A 9/24 on test; over all low-confidence prompts
  Stage A 45.0% vs Stage C 41.5%. Neither is reliable alone, hence the user is asked [`FINAL_RESULTS.md` 5.3].

## 9. Coding tests in a sandbox

Do the answers' programs work? Python test-split items, 3-6 assert tests per item written by Cerebras gpt-oss-120b
and **kept only if they pass on the CodeAlpaca reference solution**; code runs only in a bubblewrap sandbox (no
network, read-only system) [`FINAL_RESULTS.md` section 7; `coding_tests.md`; `docs/CODING_TESTS.md`].

| test split, 29 tested items | pass@1 strict | pass@1 lenient |
|---|---|---|
| degraded prompt | 6/29 (20.7%) | 11/29 (37.9%) |
| **Stage B prompt** | **10/29 (34.5%)** | 12/29 (41.4%) |

Stage B passes 4 items the degraded prompt fails, never the reverse (sign test p = 0.125, small n). The gain is
mostly interface (function naming, one solution, Python), not algorithmic correctness.

## 10. Image mode: v1 -> v2

[`FINAL_RESULTS.md` section 8; `image_mode.md`]

* **v1** filled every missing attribute (style, lighting, palette, ...) with "neutral" defaults. Attribute coverage
  rose to 9.0 of 9, but Stable Diffusion images matched the user's request **worse** (dev, 40 prompts: CLIP vs
  original prompt 28.44 vs 29.95, p = 0.009): "natural lighting" turned a watercolor request into a photo.
* **v2** (the app's default) keeps the user's words first and adds nothing that can conflict; other attributes are
  clickable suggestions. On a **held-out set of 30 prompts written before any v2 code**, run once (all image prompts
  are developer-written):

| held-out (n = 30) | CLIP vs original prompt | style kept (12 styled) |
|---|---|---|
| original prompt | 33.08 | 12/12 |
| v1 | 30.78 (worse, p = 0.043) | 10/12 |
| **v2** | **32.77** (no significant difference, p = 0.125) | **12/12** |

Lesson: coverage is the wrong target; the image model's output against the user's own request is the check.

## 11. Token results (full test split)

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

## 12. Compare: live examples

[`FINAL_RESULTS.md` section 9; `compare_examples.md`] Groq gpt-oss-120b, temperature 0; illustrations, not evidence.

| prompt | original total tokens | optimized total tokens | change | quality |
|---|---|---|---|---|
| coding: "write code to get all permutations of a string" | 768 | 248 | **-67.7%** | both 6/6 tests, judge 10/10 |
| closed_qa: "which company bought hackpad according to that text?" + passage | 238 | 279 | **+17.2%** | both judge 10/10 |

The closed_qa case is shown on purpose: the original answer was already one line, so the longer optimized prompt
cannot pay for itself. Savings come from long, unrequested answers.

## 13. Limitations

[`FINAL_RESULTS.md` section 10, plus the token results above]

* All LLM numbers use gpt-oss-120b on Groq/Cerebras as a **stand-in** for GPT, Gemini and Claude; no API keys for
  the real targets. Claude/Gemini token counts in the app are approximate (characters / 4).
* The optimized prompt is **longer**: input tokens grow; net savings depend on the model writing shorter answers.
  On the full test split no category increases total tokens on average, but prompts whose answer is already short
  can cost more (87 of 482; the live closed_qa example: +17.2%).
<!-- TOKEN:limitation:start -->
* **Token cost:** input tokens grow in every category; no category increases total tokens on average, but 87 of 482 test prompts (18.0%) individually cost more, most in information_extraction (35/93). Future work: lean mode (`token_test.md`).
<!-- TOKEN:limitation:end -->
* Stage A: 74.7% category accuracy; the closed_qa / extraction / summarization group is the weak spot.
* Stage B's "format stated" is measured with Stage A's own A02 detector; quality and task success come from the
  judge and the sandbox tests on smaller sets.
* Stage C: trained on LLM-written targets (111 train rows individually human-validated); the routed set is small
  (31 test prompts); format/constraint content only moderately close to the targets.
* Human validation: kappa target not met (kappa paradox); the LLM-assisted filter covered only the 90 overlap rows.
* Coding tests: Python only, n = 29; the test writer is the same model family as the target.
* Image mode: SD 1.5 + CLIP only; DALL-E and Nano Banana untested.
* Attachment and image results are on developer-written prompts only (no blind set written by others).

## 14. Future work

* **Lean mode** for prompts with short answers (87 of 482 test prompts cost more, most in information_extraction):
  add only the output-format line, or nothing, when the
  expected answer is already short, so the input overhead does not exceed the output saving.
* Real GPT / Claude / Gemini runs (Compare and the full evaluation) once API keys are available; exact token
  counters for Claude and Gemini.
* Better separation of closed_qa / information_extraction / summarization in Stage A (more human-labelled degraded
  prompts).
* More human-validated Stage C targets; a larger routed evaluation set.
* Coding tests beyond Python; image mode on DALL-E / Nano Banana.
* Blind test sets for attachments (15) and image prompts (10), written by people outside the development team.

## 15. Reproduce

Commands for every number: `evaluation/FINAL_RESULTS.md` section 11; setup: `README.md`.
