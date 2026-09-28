# PromptOpt: review summary

Status on 2026-09-28. Code for the final numbers: tag `frozen-for-test` (no Stage A/B rule, threshold or judge change
since; only data steps and the validation report tooling). Development evaluation uses Groq/Cerebras models as
stand-ins for the target LLMs.

## 1. Dataset

PromptOpt Dataset **v1.2 final**: 5,184 degraded -> optimized prompt pairs over five categories (from Dolly-15k and
CodeAlpaca-20k). Built from v1.2 (5,228 rows) by leaving out the rows the team rejected (35) and the rows removed by
the automatic LLM-assisted filter (9). Details: `docs/DATASET_CARD.md`; every left-out row with its reason:
`evaluation/final_dataset_merge_log.csv`.

| category | train | val | test | benchmark | total |
|---|---|---|---|---|---|
| closed_qa | 951 | 29 | 99 | 10 | 1,089 |
| information_extraction | 867 | 30 | 93 | 10 | 1,000 |
| classification | 906 | 30 | 98 | 8 | 1,042 |
| summarization | 920 | 30 | 94 | 6 | 1,050 |
| coding | 865 | 30 | 98 | 10 | 1,003 |
| **all** | 4,509 | 149 | 482 | 44 | 5,184 |

Rows left out, by split: human rejection train 11, val 1, test 17, benchmark 6; LLM-assisted filter train 7, test 2.

## 2. Human validation

Three team members (Nirzara Manade, Siddhi Bolaikar, Piush Gogi) rated 170 rows each: 90 shared **overlap** rows
(18 per category), 60 extra rows and 20 v1.2 rows alone. 330 distinct rows rated; every sheet is complete. Full
report: `evaluation/validation_report.md`.

**Acceptance rule.** Overlap rows are decided per question by majority vote (at least 2 of 3); a row is accepted
only if the majority says Y on all five questions. Extra and v1.2 rows take their single rater's answers (accepted
only if all five are Y). The faculty never decide a row. Result: **330 validated, 295 accepted, 35 rejected** (left
out of the final dataset). Rows nobody rated (4,898) rely on the automatic checks.

**Inter-rater agreement, 3 team raters, 90 overlap rows**

| question | % Y (prevalence) | raw agreement (all 3 agree) | Fleiss' kappa | Gwet's AC1 | PABAK |
|---|---|---|---|---|---|
| Q1 degraded same task | 96.3% | 90.0% | 0.065 | 0.928 | 0.867 |
| Q2 degraded realistic | 96.3% | 88.9% | -0.038 | 0.920 | 0.852 |
| Q3 optimized same intent | 96.3% | 90.0% | 0.065 | 0.928 | 0.867 |
| Q4 optimized better | 98.1% | 94.4% | -0.019 | 0.962 | 0.926 |
| Q5 category correct | 98.1% | 94.4% | -0.019 | 0.962 | 0.926 |
| accept (all five Y) | 86.3% | 67.8% | 0.092 | 0.719 | 0.570 |

**Kappa paradox.** Kappa subtracts the agreement expected by chance, computed from how often each answer is used.
When almost every answer is Y (here 96-98% per question), chance agreement is already close to 1, so kappa is low or
even negative although the raters agree on 89-94% of the rows. Gwet's AC1 and PABAK (2 x agreement - 1) do not
collapse this way: by them, agreement per question is high (AC1 0.92-0.96). The target in the validation guide
(Fleiss' kappa > 0.6) is not met, and this is why; agreement on the combined accept decision is clearly lower
(67.8% of rows unanimous, AC1 0.72), because one differing answer on any of five questions splits the raters.

Acceptance rate per rater on the overlap rows: Nirzara 94.4%, Piush 86.7%, Siddhi 77.8% (team majority 97.8%).

## 3. Faculty agreement

The faculty (one rater, via a Google Form mapped to `faculty.xlsx` by record order) rated 20 of the overlap rows (4 per
category), compared with the team's majority vote. An independent check only.

| question | % Y (prevalence) | percent agreement | Cohen's kappa | Gwet's AC1 | PABAK |
|---|---|---|---|---|---|
| Q1 degraded same task | 95.0% | 90.0% | -0.053 | 0.890 | 0.800 |
| Q2 degraded realistic | 100.0% | 100.0% | n/a (all Y) | 1.000 | 1.000 |
| Q3 optimized same intent | 95.0% | 90.0% | -0.053 | 0.890 | 0.800 |
| Q4 optimized better | 100.0% | 100.0% | n/a (all Y) | 1.000 | 1.000 |
| Q5 category correct | 97.5% | 95.0% | 0.000 | 0.947 | 0.900 |
| accept (all five Y) | 92.5% | 85.0% | -0.071 | 0.826 | 0.700 |

The faculty accepted 19 of 20; the one rejection (dolly-4205, "why is the grand canyon a big deal?", labelled
summarization) was accepted by the team majority. Same kappa paradox as above.

## 4. LLM-assisted filter (automatic, not human)

Separate from the human validation, and not part of any statistic above.

An LLM rater (Claude, `claude-opus-5-5`, labelled "LLM rater (Claude)") rated the 90 overlap rows with the same five
questions and guide, as a strict reviewer, before seeing any human answer (it had seen the faculty answer for
dolly-4205 and the aggregate report counts beforehand; recorded in its prompt). Prompt, answers and comparison:
`evaluation/llm_rater/`. It is never counted in Fleiss' kappa and never changes a human answer.

It accepted 38 of 90 rows (42.2%; the team majority 97.8%). Against the team majority: raw agreement Q1 96.7%, Q2
78.9%, Q3 70.0%, Q4 98.9%, Q5 74.4%; Gwet's AC1 0.97, 0.74, 0.60, 0.99, 0.67; Cohen's kappa about 0 on every question
(the team majority is Y on 99-100% of rows, the paradox again).

**Filter.** Only rows where the LLM rater said N on Q3 were considered (26), and of those only rows where the optimized
prompt **adds facts, leaks the answer, sets an impossible constraint, or changes the task** were removed; an added
output format or length was not a reason (`evaluation/llm_rater/llm_filter.csv` lists all 26 with the decision).
10 rows were flagged; dolly-1950 was already rejected by the team, so **the LLM-assisted filter removed 9 rows**
(train 7, test 2):

| source_id | split | reason |
|---|---|---|
| dolly-12914 | test | changes the task: asks for "the colour mentioned" instead of what the song "Colour the World" is |
| dolly-4205 | test | adds facts: requires "historical relevance", not in the text, and dictates the answer's points (the one row whose faculty answer the LLM rater had seen) |
| dolly-257 | train | leaks the answer ("the lack of a permanent cure") |
| dolly-3986 | train | leaks the answer (quarterly review, ranking criteria) |
| dolly-7569 | train | leaks the answer (restricts water flow, supports other species) |
| dolly-3291 | train | impossible constraint: "no more than three words" for a multi-part colour answer |
| dolly-4384 | train | impossible constraint: "a single number" for the text's "more than 60" |
| dolly-8748 | train | adds facts: asserts a shift away from children that the text contradicts |
| dolly-9245 | train | changes the task: asks for counts; the question and reference list the regions |

**Not removed, recorded as limitations:** Q5, 23 rows where the LLM rater found the category label debatable (plain
questions labelled summarization or information_extraction: Dolly's label noise); Q2, 19 rows where the degraded
prompt is a near-verbatim copy of a short Dolly question. The filter only covered the 90 overlap rows; similar Q3
problems are likely in rows nobody rated.

## 5. Validation-split results (development, not held out)

`dev-val-n10`: 10 val rows per category from **v1.1** (the dataset at the time), target `openai/gpt-oss-120b` on Groq,
judge `qwen/qwen3.8-27b`. Stage B was tuned on these rows, so they are development numbers. 2 items with a wrong
reference answer are excluded for all variants (with them: stage_b quality 9.4, task success 93%).

| variant | n | quality (0-10) | task success | input tok | output tok | total tok | latency ms |
|---|---|---|---|---|---|---|---|
| degraded | 48 | 9.2 | 77% (26) | 230 | 546 | 776 | 1,168 |
| **stage_b** | 48 | **9.6** | **96% (26)** | 245 | 210 | **455** | 461 |
| dataset_target | 48 | 9.5 | 92% (26) | 253 | 178 | 432 | 396 |

Stage B cut total tokens per request by 41% against the degraded prompt (input +15 tokens, output -336) and
raised task success from 77% to 96% on the checkable items.

## 6. Test-split results (run once, offline, no API calls)

Stage A retrained on the final train split (4,509 rows -> 9,018 texts, plus 500 Dolly out-of-scope examples: 9,518), then the
482 test prompts run once through Stage A and Stage B. Full reports: `evaluation/stage_a_test.md`,
`evaluation/stage_b_test.md`.

**Stage A task category (degraded prompts): accuracy 74.7%, macro-F1 0.746** (5 categories)

| category | n | precision | recall | F1 |
|---|---|---|---|---|
| closed_qa | 99 | 56.7% | 76.8% | 0.652 |
| information_extraction | 93 | 73.2% | 55.9% | 0.634 |
| classification | 98 | 93.1% | 95.9% | 0.945 |
| summarization | 94 | 60.0% | 44.7% | 0.512 |
| coding | 98 | 99.0% | 98.0% | 0.985 |

| true \ predicted | closed_qa | information_extraction | classification | summarization | coding | other |
|---|---|---|---|---|---|---|
| closed_qa | 76 | 5 | 2 | 13 | 0 | 3 |
| information_extraction | 23 | 52 | 2 | 15 | 1 | 0 |
| classification | 2 | 0 | 94 | 0 | 0 | 2 |
| summarization | 33 | 14 | 2 | 42 | 0 | 3 |
| coding | 0 | 0 | 1 | 0 | 96 | 1 |

Most errors are between closed_qa, information_extraction and summarization, the three Dolly categories whose
labels are noisy (section 4); classification and coding are near 95-98%. Out-of-scope prompts (held-out Dolly
brainstorming/creative_writing): 68.5% classified as `other`.

**Stage C routing: 31 of 482 prompts (6.4%)**: task category unresolved 24, ambiguous reference 7 (per category:
closed_qa 4.0%, information_extraction 5.4%, classification 15.3%, summarization 5.3%, coding 2.0%). Recorded but not
routed: missing label set 27, missing output format 24.

**Stage B offline**

- Output format stated: degraded prompts 3.1% -> Stage B 95.0% (the dataset's LLM-written optimized prompts: 79.0%).
- Prompt length: 11.2 -> 22.0 words on average (dataset optimized prompts 26.3).
- Rules fired: B07 structure 99.8%, B03 output format 61.2%, B08 group fallback 30.9%, B04 length 16.8%, B06 labels
  13.3%, B05 language 8.3%, B01 filler 3.7%, B02 duplicates 0.2%.
- Additions made for the wrong category: 25 of 482 prompts (5.2%), partly Dolly label noise.
- Missing constraints left after Stage B (prompts not sent to Stage C): language 27.

## 7. Benchmark results (final, LLM)

`final-benchmark`, run 2026-09-28 20:24-21:20 (one pass; a second pass found nothing left to do): all 44 benchmark
rows of v1.2 final x 3 variants, target `cerebras/gpt-oss-120b` (temperature 0, max 2,048 tokens, reasoning low),
judge Groq `qwen/qwen3.8-27b`, blind to the variant. 132 of 132 items recorded, 0 judge failures, **no exclusions**
(no benchmark row is in `wrong_references.csv`). Full table: `evaluation/final_benchmark_summary.md`.

| variant | n | quality (0-10) | task success | input tok | output tok | total tok | latency ms |
|---|---|---|---|---|---|---|---|
| degraded | 44 | 8.2 | 67% (27) | 221 | 673 | 894 | 1,215 |
| **stage_b** | 44 | **9.0** | **85% (27)** | 235 | 151 | **386** | **773** |
| dataset_target | 44 | 9.0 | 81% (27) | 242 | 129 | 371 | 1,189 |

Stage B against the degraded prompt: quality +0.8, task success +18 points (on the 27 checkable items), total tokens
-57% (input +14, output -522), latency -36%. It matches the dataset's LLM-written optimized prompts on quality and
task success at almost the same token count.

Per category (quality; task success where checkable):

| category | n | degraded | stage_b | dataset_target |
|---|---|---|---|---|
| classification | 8 | 7.5; 43% | 10.0; 86% | 8.6; 57% |
| closed_qa | 10 | 8.6; 90% | 9.0; 90% | 8.8; 90% |
| coding | 10 | 8.0; 60% | 7.8; 80% | 8.9; 90% |
| information_extraction | 10 | 8.1 | 8.9 | 8.9 |
| summarization | 6 | 9.0 | 10.0 | 10.0 |

Caveats: 44 items, so per-category numbers (6-10 items each) are indicative only. In coding Stage B raises task
success (60% -> 80%) but its judge quality is slightly lower than the degraded prompt's (7.8 vs 8.0) and below the
dataset target's (8.9). One stand-in target model and one judge model; real GPT/Gemini/Claude runs come later.
