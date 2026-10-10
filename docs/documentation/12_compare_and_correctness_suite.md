# 12. Compare and the correctness suite

[Back to the index](README.md)

Two features that put a real model behind the optimizer: **Compare** (finish phase 6) runs the user's original and
optimized prompt side by side; the **correctness suite** (50 hand-written cases with verifiable gold answers) asks
whether optimized prompts are not just shorter but *correct*.

---

## 12.1 Compare (`backend/app/compare/`, `POST /api/compare`)

### 12.1.1 Models (`providers.MODELS`)

| id | label | family | key | daily token budget we stay under |
|---|---|---|---|---|
| `cerebras/gpt-oss-120b` | gpt-oss-120b on Cerebras | gpt-oss | `CEREBRAS_API_KEY` | 70% of 1,000,000 |
| `groq/openai/gpt-oss-120b` | gpt-oss-120b on Groq (the default when available) | gpt-oss | `GROQ_API_KEY` | 70% of 200,000 |
| `gemini/gemini-2.5-flash` | Gemini (Google AI Studio) | gemini | `GEMINI_API_KEY` | the provider's own 429 decides |
| `openai/gpt` | GPT (OpenAI API) | gpt | `OPENAI_API_KEY` | listed, no client yet: disabled |
| `anthropic/claude` | Claude (Anthropic API) | claude | `ANTHROPIC_API_KEY` | listed, no client yet: disabled |

A model is **available** when its key is set **and** a client exists (Groq, Cerebras, Gemini). Keys are read from the
environment only and never logged or returned. The Gemini key goes in the `x-goog-api-key` header, never in the URL,
so it cannot end up in a log line.

### 12.1.2 What happens

1. The prompt is optimized and stored exactly as by `/api/optimize` (chapter 2.2).
2. **Both variants use the scrubbed text** (emails and phone numbers removed, as stored): the original prompt + the
   scrubbed pasted text after a blank line (`with_context`, as a user would paste it), and the optimized rendering for
   the chosen target (which already places the pasted text). *Fixed in this review:* previously the raw original was
   sent, so personal data left the machine and the two variants did not get the same input (chapter 15.4).
3. Each variant: one user message, temperature 0, max 2,048 tokens, reasoning "low" for gpt-oss — the evaluation
   harness's settings. Before each call, `check_budget` refuses if the model's rolling 24-hour usage plus
   (characters ÷ 4 + 2,048) would pass 70% of its daily limit (→ HTTP 429 with a hint to switch model).
4. Answers are **cached** in `data/compare/cache.jsonl` under SHA-256(model id, max tokens, reasoning, prompt), so a
   repeated comparison costs no quota (the result says `cached`).
5. **Honest labels:** `rendered_for` = the target the prompt was written for, `answered_by` = the model that ran it;
   when the families differ (a Claude-rendered prompt run on gpt-oss) the label says it is a stand-in.
6. **Tests:** if the prompt is a dataset coding item with validated tests, both answers are run against them in the
   sandbox (chapter 10); otherwise the result says no validated tests exist.
7. **Optional blind judge** (Groq qwen3.8-27b, temperature 0, JSON): scores each answer 0–10 against the user's
   **original request** (reference-free: correct, relevant, complete, sensible form), one answer at a time, never told
   which prompt produced it; skipped when the judge model's Groq usage passed 70% of its daily limit.
8. The result: both answers with input / output / reasoning / total tokens, latency, finish reason and cache flag;
   `change_pct` for input, output and total tokens and for latency, computed as $100 \cdot (a - b)/b$ (negative =
   the optimized prompt used fewer); tests; judge. The token counts are stored as a `token_usage` row tagged
   `compare:<model>`, so History shows past comparisons.

**Gemini specifics** (`GeminiChat`): system messages become `systemInstruction`; "thought" parts are excluded from the
answer text, but thinking tokens are **added to output tokens** (they are billed); a 429 for the per-day quota stops
with `DailyLimitReached`, a per-minute 429 is waited out (10, 20, 40 s, capped at 60) and retried (fixed in this
review); 400/401/403/404 → model unavailable. Gemini has never been run live (no key).

**Live examples** (illustrations): chapter 9.7 — coding −67.7% total tokens (both 6/6 tests), closed_qa +17.2% (the
answer was already one line).

## 12.2 Correctness suite (`backend/app/correctness/`, `evaluation/correctness_suite/`)

### 12.2.1 The cases

50 **new** hand-written cases, 10 per category (`cases.jsonl`), each with: a realistic scenario, a **material**
(notice, table, email, code spec …), the **vague prompt** a user would type, a single **gold** answer, a **check**
specification and evidence strings. Difficulty tags: distractor 28, edge case 23, calculation 13, ambiguous item 7
(a case can have several).

**Automatic validation** (`python -m app.correctness.cases` → `validation.md`; the suite is not run until all pass):

| check | what it verifies |
|---|---|
| schema | required fields, 10 cases per category, unique ids |
| no duplicates | no shared vague prompt; no two materials with > 50% word 5-gram overlap |
| new, not from the training data | no vague prompt equals a dataset prompt; no material shares 3+ word 8-grams with any of the 5,184 dataset rows (one case shares a code idiom, listed) |
| gold derivable from the material | closed_qa: evidence present and the `compute` expression (arithmetic over the material's numbers) gives the gold; extraction: every gold item and distractor appears (closed world); classification: items present, labels from the set, the rule recomputes each label; summarization: every key fact's evidence present, 3–5 key facts, 2 forbidden statements, a word limit; coding: the reference solution passes all 5–8 of its own asserts in the sandbox |
| privacy | material and prompt unchanged by the app's PII scrubber |
| leak (`prompts.py`) | no gold form appears in the optimized **request** (the IR rendered without the pasted material) unless it was already in the vague prompt — Stage C's patch included |

Result: all 50 cases pass; 0 leaks.

### 12.2.2 The two prompts per case (`prompts.py`)

Exactly the app's path on the frozen v1.0 pipeline: **vague** = the vague prompt + the material after a blank line;
**optimized** = Stage A on (prompt, material) → Stage B (category auto, material as separate text) → Stage C under the
contract for the 10 routed cases → rendered per target with the material as the Document. gpt-oss runs get the GPT
rendering.

### 12.2.3 Scoring (`checks.py`)

| category | correct when | how |
|---|---|---|
| closed_qa | the gold answer (any alias) is found and no known wrong value (distractor) is | normalized match (lower case, no markdown, no thousands separators, unified dashes/spaces/quotes); if both gold and a distractor appear, the blind extractor reads the answer's final value |
| information_extraction | the predicted set equals the gold set exactly | items matched in a closed world; if a distractor is mentioned (listed or mentioned as excluded) the extractor lists what the answer gives as its answer; P/R/F1 also reported |
| classification | every item gets the right label | each item's label read from the lines mentioning it (or the heading above); unread or double-labelled items → the extractor reads all; per-item accuracy also reported |
| summarization | all key facts covered, no forbidden statement, within the word limit | blind checklist judge for facts and forbidden statements; words counted in code |
| coding | every hidden assert passes | the answer's code in the bubblewrap sandbox (chapter 10) |

The extractor/judge is Groq `qwen/qwen3.8-27b`, blind: it sees the user's request and one answer, never the gold
answer or which prompt produced the answer; used only where a deterministic check cannot decide; cached.

**Statistics:** exact McNemar test on the discordant cases (chapter 8.4); tokens: per-case mean reduction and the
aggregate (summary table shows the aggregate as a change, e.g. −29.6%; the category tables show reductions, e.g.
+29.6% = 29.6% fewer).

### 12.2.4 Results (`RESULTS.md`)

| model | vague correct | optimized correct | both | only optimized | only vague | both wrong | McNemar p | total tokens (aggregate) |
|---|---|---|---|---|---|---|---|---|
| Groq gpt-oss-120b (primary) | 37/50 | 42/50 | 33 | 9 | 4 | 4 | 0.267 | −29.6% |
| Cerebras gpt-oss-120b (replication) | 43/50 | 41/50 | 39 | 2 | 4 | 5 | 0.688 | −28.2% |

Mean tokens per case (Groq): input 229 → 257, output 435 → 211, total 664 → 467.

**Where optimization hurt (Groq, 4 cases), with the analysis recorded in the report:**
* `cls-09`: Stage A read an attendance table as code (coding, 0.84 ≥ 0.6), so B05/B03 asked for code; the model
  returned a script instead of labels — a Stage A error amplified by the category rules (choosing the category in the
  UI avoids it).
* `sum-06`: B03 turned "4–5 lines" into bullet points; the bulleted answer was 92 words against a 90-word limit.
* `sum-10`: only B07 fired; the answer added a title line and reached 83 words against 80 — a near miss, not a rule
  effect.
* `cod-10`: routed to Stage C; the spec was identical in both prompts and the model's code rounded fractions wrongly —
  a model error under a near-identical request.

**Status:** gold answers are auto-validated; the human review of the gold answers is pending
(`team_input/correctness_review/cases_review.xlsx`; import with `python -m app.correctness.review --import <file>`).
Gemini: not run (no key). The UI's "Test suite" page shows every case, both prompts, both answers, the verdicts and
tokens, and can re-run a case live (cached).
