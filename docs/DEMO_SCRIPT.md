# PromptOpt: demo script (5-7 minutes) and viva questions

## Before the demo (10 minutes earlier)

```bash
cd backend
source .venv-gpu/bin/activate          # GPU venv: Stage C on; with .venv the demo works too, Stage C shows "not installed"
uvicorn app.api:app                    # http://127.0.0.1:8000
```

* `backend/.env` has `GROQ_API_KEY` (and `CEREBRAS_API_KEY`) so Compare works. Check `GET /api/compare/models`.
* Open one terminal for the fallback (`python -m app.demo --examples`) in case the network fails: Stage A + B + C
  are offline, only Compare needs the network.
* Have `evaluation/FINAL_RESULTS.md` open in a second tab for numbers.
* Live model answers vary a little between runs; quote the measured numbers from the reports, not from the screen.

## Walkthrough

| time | do | point out |
|---|---|---|
| 0:00-0:45 | Say the problem in one line: short prompts get long, unrequested answers; we rewrite the prompt for the chosen model and **measure** whether it helps. Show the pipeline diagram (README / report section 4). | A -> B -> C -> IR -> renderers. Rules first; the small model only for what rules cannot fix. |
| 0:45-2:15 | Type `write code to get all permutations of a string`, target **GPT**, category **auto**, *Optimize*. | Stage A: coding, confidence 1.00, no format, no language. Rules that fired with before/after (B05 adds "Use Python", B03 "Return only the code, in a single code block"). Switch target tabs: same content, Claude XML tags vs GPT `###` vs Gemini labels. Input tokens per target: GPT exact (tiktoken), Claude/Gemini approximate, labelled. |
| 2:15-3:15 | *Run on* gpt-oss-120b (Groq), *Compare*. | Side by side: original answer is a long explanation; optimized answer is one code block. Tokens in/out/reasoning, latency, sandbox tests. Measured on this prompt: **total -67.7%, both 6/6 tests** (`compare_examples.md`). Label says it is a stand-in for GPT. |
| 3:15-4:00 | Type `which company bought hackpad according to that text?` and paste the Hackpad passage (from `compare_examples.md`), target **Claude**, *Optimize*, *Compare*. | **Honest case:** the original answer was already one line, so the optimized prompt costs more: **+17.2% total tokens**, same judge score. Savings come from long answers; for closed_qa, input grows more than output shrinks. Future work: "lean mode". |
| 4:00-5:00 | Type `hey can you just summarize this article for me`, *Optimize*. Then `describe what is happening in the picture` with attachment **image**. | First: ambiguous reference ("this article") -> routed to Stage C; Stage C's answer is validated, and if it still contains an unclear reference it is rejected and Stage B's text is kept (the contract). Second: Stage A unsure (coding, 0.37) -> Stage C suggests a category, the UI **asks the user** and pre-selects it. Stage C runs on only 6.4% of test prompts. |
| 5:00-5:45 | Category **Image generation**, target Stable Diffusion: `oil painting of a sailboat in a storm`. | v2 keeps the user's words first and adds nothing; missing attributes are clickable chips. v1 added "natural lighting" etc. and made images worse (held-out CLIP 30.78 vs original 33.08); v2 32.77, no significant difference, style kept 12/12. |
| 5:45-6:30 | Open *History*, reload a past prompt. Close with the headline. | 30-day retention, PII stripped before storing. Headline: <!-- TOKEN_HEADLINE --> *Pending: the full-test token run is in progress; filled in from `evaluation/token_test.md` when it ends.* Quality on the benchmark 8.2 -> 9.0, task success 67% -> 85%. |

If something fails live: run `python -m app.demo --examples` in the terminal (offline, shows Stage A features, every
rule's before/after and Stage C routing) and use `compare_examples.md` for the Compare part.

## Likely viva questions

**How is Stage B's accuracy measured?**
Three layers, because there is no single "correct" rewrite. (1) Offline on the 482 test prompts: does the output
state a format (Stage A's A02 detector: 3.1% -> 95.0%), how often a category-specific addition was for the wrong
category (5.2%), how many prompts are routed (6.4%) (`stage_b_test_final.md`). (2) With a real LLM on the 44-prompt
benchmark: blind judge quality 8.2 -> 9.0 and task success 67% -> 85% (`final_benchmark_summary.md`). (3) Coding:
generated tests validated on the reference solution, run in a sandbox: pass@1 20.7% -> 34.5% (`coding_tests.md`).
The format number uses our own detector, which is why (2) and (3) matter.

**What is the B -> C contract?**
Stage B lists what it could not resolve. Stage C is called only for the task category (Stage A confidence < 0.6
and B08 could not resolve the group) or an ambiguous reference. A missing format alone does not route. Stage C
must return JSON with exactly the unresolved keys; the result is checked with Stage A's detectors; if invalid,
Stage B's result is kept. Stage C's category is only a suggestion the user confirms (`docs/STAGE_C_PLAN.md`,
`app/stage_c/contract.py`).

**Why Stage C only for routed prompts?**
Ablation on test: on routed prompts A+B+C states a format in 90.3% vs 22.6% at a small loss of task intent
(0.869 -> 0.843). Forcing every prompt through Stage C lowers task intent from 0.886 to 0.769 and gains no format
(95.0% -> 90.2%): the small model rewrites tasks the rules already handled. Decided on val, confirmed on test
(`FINAL_RESULTS.md` 5.2).

**How are tokens counted per model?**
GPT: exact, tiktoken `o200k_base`. Claude and Gemini: their tokenizers are not public offline, so characters / 4,
labelled "approx." in the UI. In Compare and the evaluation, the counts are the provider's own usage numbers
(input, output, and hidden reasoning tokens) from the API response.

**Why does the optimized prompt reduce tokens if it is longer?**
Input grows (the format and constraints add words), output shrinks a lot (the model stops writing unrequested
explanations and alternatives). Net = input + output. <!-- TOKEN_ANSWER --> *Pending: the full-test token run is in progress; filled in from `evaluation/token_test.md` when it ends.*

**What is the kappa paradox?**
Kappa subtracts chance agreement computed from how often each answer is used. With 96-98% "yes", chance agreement
is almost 1, so kappa is near 0 or negative (0.065, -0.019) although the three raters agree on 89-94% of rows.
Gwet's AC1 (0.92-0.96) and PABAK do not collapse. We report all of them and say the kappa target was not met
(`REVIEW_SUMMARY.md` section 2).

**Why did image mode v1 fail?**
v1 filled every missing attribute with a "neutral" default. Coverage reached 9 of 9, but the defaults conflicted
with the request ("natural lighting" turned a watercolor into a photo): CLIP similarity to the user's prompt fell
(dev 29.95 -> 28.44, p = 0.009; held-out 33.08 -> 30.78, p = 0.043). v2 keeps the user's words and offers
suggestions instead; on the held-out set, written before v2's code, it is not significantly different from the
original (32.77) and keeps the style 12/12 (`image_mode.md`).

**Was the test set used for tuning?**
No. Everything was tuned on val; the test split was run once (2026-10-02, tag `final-for-test`); Stage A/B are
frozen and checked byte-identical (`python -m app.freeze_check`). The full-test token run is a measurement on the
frozen pipeline.

**Are the GPT/Claude/Gemini results real?**
No, they are stand-ins: gpt-oss-120b on Groq/Cerebras answers every rendering, and the UI labels it. Real runs need
API keys (future work).

**What does the LLM-assisted filter do, and is it human validation?**
It is not. An LLM rater reviewed the 90 overlap rows; only rows where the optimized prompt adds facts, leaks the
answer, sets an impossible constraint or changes the task were removed (9 rows). It is reported separately and
never counted in the agreement statistics.

**Why a 0.6 confidence gate?**
Below 0.6 Stage A is often wrong between closed_qa, extraction and summarization; adding a category-specific rule
there would add the wrong format. B08 adds only what the whole group shares instead. The threshold is part of the
design fixed before the test run (35% of test prompts fall below it, `docs/MILESTONE_REVIEW.md`).
