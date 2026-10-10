# Appendix C. Glossary

[Back to the index](README.md)

| term | meaning in this project |
|---|---|
| **A+B, A+B+C, C-only** | ablation systems: Stage A + B; Stage A + B + Stage C on the requested fields; Stage C alone with no Stage B rules |
| **ablation** | switching parts off to measure each part's contribution |
| **AC1 (Gwet's)** | an agreement coefficient whose chance term does not collapse when one answer dominates (chapter 3.9.3) |
| **adapter (LoRA)** | the small trained matrices added to the frozen base model; `backend/artifacts/stage_c_adapter` |
| **aggregate reduction** | the reduction of the summed tokens over all prompts; a size-weighted mean of per-prompt reductions |
| **ambiguous reference** | a reference to material that is not there ("summarize this" with no text); detector A05 |
| **attachment modifier** | an attachment type (image, PDF, …) that adds instructions (B09–B15) without changing the category |
| **benchmark split** | 44 rows held out for the final real-LLM run |
| **bootstrap CI** | a confidence interval from resampling the data with replacement (chapter 8.3.1) |
| **bubblewrap (bwrap)** | the Linux sandbox tool used to run generated code without network or host files |
| **category gate** | Stage A confidence ≥ 0.6 required for category-specific rules (B03–B06) |
| **change log** | the list of steps (rule, before, after) Stage B (and Stage C) record; the `transformations` table |
| **Compare** | running the original and the optimized prompt on the same real model, side by side |
| **context** | material the task works on: text pasted next to the prompt, data inside the prompt, or an attachment |
| **correctness suite** | 50 new hand-written cases with gold answers, to test correctness rather than tokens |
| **cross-fitting** | classifying each train row with a model built without that row's fold (5 folds) |
| **degraded prompt** | how a rushed user types a request (dataset input) |
| **dev / val** | the validation split used for every tuning decision |
| **effective batch** | examples per optimizer step = micro-batch × gradient-accumulation steps (here 16) |
| **forced routing** | evaluation-only: asking Stage C for fields on every prompt, not just routed ones |
| **freeze / `frozen-for-test`** | the tag after which Stage A/B code may not change; checked byte-for-byte by `app.freeze_check` |
| **gold answer** | the verified correct answer of a correctness-suite case |
| **IR (intermediate representation)** | the structured, model-agnostic form of an optimized prompt (`PromptIR`) |
| **judge** | an LLM (qwen3.8-27b) that scores answers 0–10, blind to which prompt produced them |
| **kappa (Fleiss', Cohen's)** | chance-corrected agreement between raters (chapter 3.9) |
| **kappa paradox** | kappa near 0 despite high agreement when almost all answers are the same |
| **k-NN** | k-nearest-neighbour vote over labelled example prompts in embedding space |
| **lean mode** | proposed future option that adds less to prompts whose answer is short |
| **LoRA** | low-rank adaptation: training small matrices $A$, $B$ instead of the full model |
| **macro-F1** | the unweighted mean of per-category F1 scores |
| **McNemar test (exact)** | a test on paired yes/no outcomes using only the discordant pairs |
| **optimized prompt** | the clear version of a request (dataset target, or PromptOpt's output) |
| **`other`** | the category for prompts outside the five tasks (brainstorming, creative writing, chit-chat) |
| **PABAK** | prevalence- and bias-adjusted kappa, $2\bar P - 1$ |
| **pass@1 (strict / lenient)** | the one answer passes every validated test (lenient: also when only the function name differed) |
| **PII** | personally identifiable information; here emails and phone numbers, removed before storing |
| **reasoning tokens** | hidden "thinking" tokens of gpt-oss / Gemini, billed as output |
| **renderer** | turns the IR into a prompt for Claude (XML tags), GPT (`###` sections) or Gemini (labels) |
| **retention** | prompts are deleted 30 days after they were stored |
| **routed** | sent to Stage C because the category or a reference is still unresolved |
| **sign test** | an exact test on win/loss counts of paired comparisons |
| **source_id** | a row's permanent id: its row number in the original Dolly/CodeAlpaca download |
| **stand-in** | a model answering for a target family it does not belong to (gpt-oss for Claude) |
| **Stage A / B / C** | feature detection / rule-based optimization / LoRA fallback |
| **task intent** | cosine similarity between the final IR's task and the original instruction (Stage C ablation) |
| **task success** | a checkable correctness criterion (judge yes/no, labels, parseable code) |
| **unresolved** | what Stage B could not fix, recorded in `ir.unresolved` |
| **Wilcoxon signed-rank test** | a paired, rank-based significance test that does not assume normality |
