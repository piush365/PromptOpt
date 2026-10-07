# PromptOpt in 10 minutes

A cheat sheet for presenting the project. Every number comes from `evaluation/FINAL_RESULTS.md` (cited by
section) or the report file named next to it.

## 1. The problem (2 lines)

People type short, vague prompts ("write code for permutations"), so the model guesses and writes long,
unrequested answers. PromptOpt rewrites the prompt for the model you use, and **measures** whether that helps.

## 2. The pipeline in plain words

| step | in plain words |
|---|---|
| **Stage A: look** | Read the prompt and work out what kind of task it is (closed_qa, information extraction, classification, summarization, coding) and how sure we are. Note what is missing: an output format, a length, a programming language, a label set. Note filler words and unclear references like "this article". |
| **Stage B: fix with rules** | Fixed, testable rules (B01-B15) add only what is missing, and every change is logged with before/after. Category-specific rules fire only when Stage A's confidence is at least 0.6. Otherwise a safe group rule (B08) is used, or the field is left unresolved. |
| **Stage C: small model, only if needed** | A small fine-tuned model (Qwen2.5-0.5B + LoRA) runs only when Stage B could not settle the category or an unclear reference: 6.4% of test prompts. Its answer is checked; if it is bad, Stage B's version is kept. Its category guess is only a suggestion the user confirms. |
| **IR + renderers** | One neutral representation (task, context, constraints, output format), written out per model: Claude gets XML tags, GPT gets `###` sections, Gemini gets plain labels. Same content in all three. |
| **Compare** | Run the original and the optimized prompt on the same real model, side by side: answers, tokens, latency, tests for code, optional blind judge. |
| **Image mode** | A separate mode for image generators. It keeps the user's words and offers missing details (lighting, style...) as clickable suggestions. |

### One prompt, walked through

**Typed:** `write code to get all permutations of a string`

1. **Stage A:** coding, fully confident; no output format; no programming language stated.
2. **Stage B:** B07 tidies the structure, B05 adds "Use Python.", B03 adds "Return only the code, in a single code
   block." Nothing is unresolved, so **Stage C is not called**.
3. **Rendered for Claude:**
   ```
   <task>
   Write code to get all permutations of a string.
   </task>

   <constraints>
   - Use Python.
   </constraints>

   <output_format>
   Return only the code, in a single code block.
   </output_format>
   ```
4. **Compare** (Groq gpt-oss-120b): total tokens 768 -> 248 (**-67.7%**), both answers pass 6/6 tests, judge 10/10
   (`FINAL_RESULTS.md` section 9, `compare_examples.md`).

**When Stage C runs:** `hey can you just summarize this article for me` contains an unclear reference ("this
article"), so it is routed to Stage C. If Stage C's rewrite still has an unclear reference, the check rejects it and
Stage B's text is kept.

## 3. Key numbers

<!-- TOKEN:headline:start -->
**[PLACEHOLDER: token headline, filled automatically when the full-test token run finishes]** Optimized prompts reduce total tokens by X% (95% CI a–b, n = N).
<!-- TOKEN:headline:end -->

| what | number | source |
|---|---|---|
| Dataset | 5,184 pairs; test split 482 prompts | `FINAL_RESULTS.md` 2a, `DATASET_CARD.md` |
| Human validation | 330 rows rated, 295 accepted, 35 rejected; AC1 0.92-0.96 per question | `FINAL_RESULTS.md` 2a, `REVIEW_SUMMARY.md` |
| Stage A category accuracy (test) | **74.7%** | `FINAL_RESULTS.md` 3 |
| Stage B: output format stated (test) | **3.1% -> 95.0%** | `FINAL_RESULTS.md` 4 |
| Prompts routed to Stage C (test) | **6.4%** (31 of 482) | `FINAL_RESULTS.md` 4 |
| Benchmark, real LLM: quality / task success | **8.2 -> 9.0** / **67% -> 85%** | `FINAL_RESULTS.md` 4 |
| Benchmark: total tokens per prompt | 894 -> 386 | `FINAL_RESULTS.md` 4 |
| Stage C valid answers: zero-shot vs LoRA | 5.0% vs **98.2%** | `FINAL_RESULTS.md` 5.1 |
| Stage C on routed prompts: format stated | **22.6% -> 90.3%** | `FINAL_RESULTS.md` 5.2 |
| Stage C on all prompts (forced): task intent | 0.886 -> 0.769 (worse, so routed only) | `FINAL_RESULTS.md` 5.2 |
| Stage C latency, laptop GPU / CPU | 0.74 s / 4.55 s | `FINAL_RESULTS.md` 5.5 |
| Coding tests pass@1 (strict) | **20.7% -> 34.5%** (n = 29) | `FINAL_RESULTS.md` 7 |
| Image v2 vs original, held-out CLIP | 32.77 vs 33.08 (no significant difference); v1 30.78 | `FINAL_RESULTS.md` 8 |
| Freeze | Stage A/B byte-identical to `frozen-for-test` on 482 prompts | `FINAL_RESULTS.md` 2 |

## 4. What to say about each limitation

| limitation | what to say |
|---|---|
| Real GPT/Claude/Gemini never called | "All LLM numbers use gpt-oss-120b on Groq/Cerebras as a stand-in, and the app labels it. Real runs need API keys; the code paths are there." |
| The optimized prompt is longer | "Input tokens grow; the saving comes from shorter answers. When the answer is already short, for example a one-line closed_qa answer, the prompt can cost more (+17.2% in our live example). Future work: a lean mode." |
| Stage A at 74.7% | "Coding and classification are near-perfect; closed_qa, extraction and summarization are hard to tell apart from a vague prompt. That is why there is a 0.6 gate and a group rule instead of guessing." |
| "Format stated" measured with our own detector | "That's why we also report an independent LLM judge and task success on the benchmark, and real tests for code." |
| Kappa target missed | "It's the kappa paradox: with 96-98% yes answers, kappa collapses even though raters agree on 89-94% of rows. AC1 is 0.92-0.96; we report everything." |
| Stage C trained on LLM-written targets, small routed set (31) | "Stage C is a fallback for a few prompts. The forced ablation on all 482 shows why it isn't used everywhere." |
| Coding tests: Python only, n = 29 | "Small and paired; Stage B never lost an item the degraded prompt passed (sign test p = 0.125, so not significant)." |
| Attachments and image mode on developer-written prompts only | "Blind sets written by others are future work. The held-out image set was at least written before any v2 code." |
| Image mode: SD 1.5 + CLIP only | "DALL-E and Nano Banana need API keys; CLIP can show harm but not improvement, so we claim 'no harm'." |

## 5. Top 10 viva questions (2-line answers)

1. **How is Stage B's accuracy measured?** Offline on 482 test prompts (format stated 3.1% -> 95.0%, wrong-category
   additions 5.2%), plus a blind LLM judge and task success on the benchmark (8.2 -> 9.0, 67% -> 85%) and sandbox tests for code.
2. **What is the B -> C contract?** Stage C runs only for an unresolved category or an unclear reference, must return
   JSON with exactly those fields, and is checked by Stage A's detectors; if it fails, Stage B's result stays.
3. **Why Stage C only for routed prompts?** On routed prompts it raises format stated 22.6% -> 90.3%; on all prompts
   it lowers task intent 0.886 -> 0.769 and adds nothing. Decided on val, confirmed on test.
4. **How do you count tokens per model?** GPT exactly with tiktoken o200k_base; Claude and Gemini approximately
   (characters / 4, labelled). In Compare and the evaluation we use the provider's own usage numbers, including reasoning tokens.
5. **If the prompt is longer, how do you save tokens?** Input grows; output shrinks because a stated format and length
   stop long, unrequested answers. We report net = input + output (see the token headline above).
6. **What is the kappa paradox?** With nearly all answers "yes", chance agreement is near 1, so kappa is near 0 even at
   89-94% raw agreement; Gwet's AC1 (0.92-0.96) does not collapse.
7. **Why did image v1 fail?** Default keywords like "natural lighting" conflicted with requests (watercolor became a
   photo): held-out CLIP 33.08 -> 30.78. v2 keeps the user's words: 32.77, style kept 12/12.
8. **Was the test set used for tuning?** No: everything was tuned on val; test ran once (tag `final-for-test`), and
   `python -m app.freeze_check` proves Stage A/B are byte-identical.
9. **Why rules first and not just an LLM?** Rules are free, offline, instant, explainable and testable one by one;
   the C-only ablation is the weakest (routed task intent 0.712).
10. **Are GPT/Claude/Gemini results real?** No: gpt-oss-120b stands in for all three and the UI says so; real runs
    need API keys (future work).
