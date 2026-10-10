# PromptOpt — complete technical documentation

**Token-efficient prompt optimization for LLMs.** Mini Project-I (7CS345), Department of Computer Science and
Engineering, Walchand College of Engineering, Sangli, 2026-27. Team: Nirzara Manade, Siddhi Bolaikar, Piush Gogi.
Guide: Prof. A. S. Pawar.

This is the full reference documentation of the project: every step and sub-step of the system and of the work that
produced it, every setting with **how it was chosen**, every estimate with **its basis**, and every formula with
**where it comes from**. It was written on 2026-10-10 from the code on branch `ui-v2` (after the review fixes of
chapter 15.4) and the committed evaluation reports.

---

## The system in one paragraph

A user types a vague prompt (and picks a target LLM, a category or "auto", and optionally an attachment type).
**Stage A** detects what is missing — the task category (embedding k-NN + keywords + logistic head, 74.7% on test),
output format, constraints, filler, dangling references — without changing anything. **Stage B** fixes what fixed
rules can fix: 15 small rules (plus B16 in the app) on a structured intermediate representation (IR), each change logged; category-specific
additions only when Stage A is ≥ 0.6 confident. Only if the category or a reference is still unresolved (6.4% of test
prompts) does **Stage C**, a LoRA-tuned Qwen2.5-0.5B, fill exactly those fields, validated by the same detectors (98.2%
of its answers pass). The IR is **rendered** for Claude, GPT or Gemini. On a real model the optimized prompts cut
total tokens by **39.2% per prompt (95% CI 35.9–42.5%, n = 482)** — input grows, output shrinks — and raised
benchmark quality from 8.2 to 9.0.

| at a glance | |
|---|---|
| categories | closed_qa, information_extraction, classification, summarization, coding (+ `other`) |
| dataset | 5,184 degraded → optimized pairs (train 4,509 / val 149 / test 482 / benchmark 44) |
| code | Python 3.14 + FastAPI + SQLAlchemy (backend), React + TypeScript (frontend); 795 offline tests |
| models | all-MiniLM-L6-v2 (Stage A), Qwen2.5-0.5B-Instruct + LoRA r = 16 (Stage C); gpt-oss-120b as the target stand-in; qwen3.8-27b as judge |
| hardware | a laptop with an RTX 3050 (4 GB); everything except Stage C runs on CPU |

## Chapters

| # | chapter | contents |
|---|---|---|
| 1 | [Introduction and methodology](01_introduction_and_methodology.md) | problem, objectives, scope, constraints, the dev/val/test discipline, the freeze and the freeze check, timeline |
| 2 | [Architecture](02_architecture.md) | components; one request through every step and sub-step; module map; pinned technology stack; where data and artifacts live |
| 3 | [Dataset](03_dataset.md) | sources, cleaning (outlier rule), v1, v1.1 repair, v1.2 expansion (sampling formula, stratified allocation, generation, budgets, quality thresholds, splits), human validation, agreement statistics with derivations and a worked example, LLM-assisted filter, final reconciliation |
| 4 | [Stage A: feature detection](04_stage_a_feature_detection.md) | embedding, k-NN softmax vote, keyword cues, logistic head, backstop proof, worked examples, every detector, metrics and confusion matrix, cross-fitting |
| 5 | [Stage B: rule-based optimizer](05_stage_b_rule_optimizer.md) | the IR, the run order, the 0.6 gate and how it was chosen, every rule with its exact condition and basis, routing, confidence, metrics and per-rule accuracy |
| 6 | [Stage C: LoRA fallback](06_stage_c_lora_fallback.md) | contract, input/output, training data (routed/forced, probabilities), parser, base model, LoRA maths and parameter count, loss, AdamW, schedule, early stopping history, validation, category policy, evaluation, latency |
| 7 | [Rendering and token counting](07_rendering_and_token_counting.md) | three layouts and their basis, safe fencing, round-trip tests, exact vs approximate tokens and the measured error of characters ÷ 4 |
| 8 | [Evaluation methodology](08_evaluation_methodology.md) | every evaluation, harness settings and their basis, the judge, task success, token metrics (mean vs aggregate, derivation), bootstrap, Wilcoxon, sign/McNemar tests, cost model, threats to validity |
| 9 | [Results](09_results.md) | every reported number with its source and the arithmetic that reconciles them |
| 10 | [Coding tests and sandbox](10_coding_tests_and_sandbox.md) | bubblewrap + rlimits sandbox, item modes, test generation and validation, naming, pass@1 |
| 11 | [Image mode](11_image_mode.md) | attribute detectors, v1 and why it failed, v2, Stable Diffusion size derivation, CLIP evaluation, held-out results |
| 12 | [Compare and the correctness suite](12_compare_and_correctness_suite.md) | Compare flow, honesty labels, budgets; 50-case suite: validation, scoring, McNemar, results |
| 13 | [Backend: API, database, privacy, configuration, LLM clients](13_backend_api_database.md) | endpoint reference, 10 tables, repository, PII, retention, environment variables, rate limits, usage ledger, budgets with a planning example |
| 14 | [Frontend](14_frontend.md) | pages, structure, build optimizations, UI tests |
| 15 | [Testing, quality and the 2026-10-10 review](15_testing_quality_and_review.md) | test suite map, conventions, the review's method, what was fixed, what is reported but frozen |
| 16 | [Operations and reproduction](16_operations_and_reproduction.md) | install, run, verify, reproduce every report (with duration estimates and their basis), troubleshooting |
| 17 | [Limitations and future work](17_limitations_and_future_work.md) | |
| A | [Every constant, with its basis](appendix_A_constants.md) | value, file, and whether it was measured, tuned on val, cross-validated, a design choice, an external limit, or derived |
| B | [Formula index](appendix_B_formulas.md) | 46 formulas with code location and the section that derives them |
| C | [Glossary](appendix_C_glossary.md) | |

## Conventions

* **Sources.** Results are copied from report files in `evaluation/` and cited (e.g. `tokens/token_test.md`, or
  [FR §n] for `evaluation/FINAL_RESULTS.md` section n). Settings are quoted from the code with the file they are in.
  Numbers recomputed for this documentation (e.g. the sampling plan, the rating distributions, the LoRA parameter
  count, the accuracy of characters ÷ 4) were produced by running the project's own code on the committed data.
* **Basis of a constant.** M = measured, V = tuned on val, CV = cross-validated on train, D = design choice,
  E = external limit/convention, Δ = derived (Appendix A).
* **Illustrative vs evidence.** Single-prompt walkthroughs are labelled illustrative; evidence comes from whole splits.
* **Maths** is written in LaTeX (`$…$`), which GitHub renders.
* Paths are relative to the repository root unless the chapter says `backend/app/`.

## Related documents

| document | role |
|---|---|
| `README.md` (repository root) | overview, architecture diagrams, how to run |
| `evaluation/FINAL_RESULTS.md` | the results of record |
| `docs/HOW_IT_WORKS.md` | plain-English walkthrough of Stages A, B, C with viva questions |
| `docs/PROJECT_REPORT.md` | the project report |
| `docs/EXPLAIN_IN_10_MIN.md`, `docs/DEMO_SCRIPT.md` | short explanation, demo walkthrough |
| `docs/DATASET_CARD.md`, `docs/STAGE_C_PLAN.md`, `docs/CODING_TESTS.md`, `docs/CATEGORY_TEMPLATES.md` | focused references (this documentation expands each) |
| `docs/diagrams/` | the eight architecture diagrams (Mermaid source, SVG, PNG) |
