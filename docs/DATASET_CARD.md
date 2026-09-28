# PromptOpt Dataset: dataset card

Pairs of a **degraded prompt** (how a rushed, non-expert user types a request) and an **optimized prompt** (the same
task stated clearly, with an explicit output format and only helpful constraints), for five task categories:
closed_qa, information_extraction, classification, summarization (from Dolly-15k) and coding (from CodeAlpaca-20k).
Each row also keeps the source's original instruction, context and reference answer.

The dataset lives on Google Drive and in `data/` (git-ignored); it is never stored in the database.

## Versions

| version | rows | what changed | built by |
|---|---|---|---|
| v1 | 2,265 | first build: sampling, generation, automatic checks, splits | Colab notebook `PromptOpt_Dataset_Preparation_v2.ipynb` |
| v1.1 | 2,256 | data dropped from the instruction put back (349 optimized + 20 degraded prompts repaired, 75 dropped subjects restored, 9 rows without source data removed); see `docs/dataset_v1_1_repair_log.csv` | `backend/app/dataset_repair.py` |
| v1.2 | 5,228 (1,009-1,093 per category) | v1.1 unchanged, plus 2,972 new rows from never-used source rows | `backend/app/dataset_expand.py` |
| **v1.2 final** | **5,184** | v1.2 minus 35 rows the team rejected and 9 rows removed by an automatic LLM-assisted filter (not human); adds the validation columns. The dataset used for the final numbers | `python -m app.validation merge --drop-rejected --auto-filter ...` |

The final dataset is `data/promptopt_dataset_v1_2_final/promptopt_dataset_v1_2_final.csv` (every left-out row with
its reason: `merge_log.csv` next to it). `DATASET_DIR` points at that folder, but `app.dataset_io` still looks for a
file named `promptopt_dataset_v1_1.csv` there, so every command is given `--dataset <that csv>` explicitly.

## How the rows were generated (`generation_version`)

The dataset was built in phases, and every row says which one produced it. Report results with this in mind: the
v1 rows were generated with a different prompt from the v1.2 rows.

| generation_version | prompt | rows per call | provider / models (`model` column) | when | rows |
|---|---|---|---|---|---|
| `v1` | the notebook's prompt (no data rule) | 1 | Groq: gpt-oss-120b (1,054), gpt-oss-20b (858), qwen3.8-27b (344) | Sep 2026, before 26 Sep | 2,256 (all v1.1 rows) |
| `v1.2-single` | v1.2 prompt: the notebook's rules plus the data rule | 1 | Groq: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` | 26 Sep 2026, morning | 303 generated, 254 in v1.2 |
| `v1.2-batch5` | the same rules as `v1.2-single`, worded compactly for several items | 5 | `cerebras/gpt-oss-120b` first; Groq models when Cerebras' daily limit is used up | 26 Sep 2026 | 2,900 generated, 2,718 in v1.2 |

All phases use temperature 0.7, JSON output, reasoning effort "low" for gpt-oss ("none" for qwen), and context
truncated to 1,000 characters (1,500 in the first notebook runs).

**The data rule** (v1.2): data written inside the instruction (items to classify, lists, code, numbers,
expressions, quoted strings, the named subject) must appear verbatim in both prompts. v1 had no such rule, which is
why v1.1 had to repair it.

**Batching** (`v1.2-batch5`): the system prompt was about 60% of a one-row call, so five rows share one call. On a
10-row comparison (same rows, both setups, `data/promptopt_dataset_v1_2/prompt_comparison_10rows.json`) this cut
the cost from ~1,070 to ~400 tokens per row, with the automatic checks as good or better (old: 2 flags, 0 data
drops; new: 0 flags, 1 dropped item list, which the deterministic repair restores). Each item is sent with its
`source_id` and the reply must echo it; results are matched **only** by that id, never by position, so rows in one
call cannot be swapped. The first 40 batched rows were matched by position before this was added; all 40 were
checked (each output compared with every instruction in its call) and none was swapped.

**Prompt revisions** (`prompt_rev` in the generation checkpoint): after the first 225 batched rows, their
auto-check pass rate was compared with v1 per category. In closed_qa the optimized prompt often left out the
question itself (76% pass vs 85% in v1; those rows fail the drift check and are dropped), and in classification it
dropped the item list in 18 of 41 rows (restored by the repair). Revision 2 states both explicitly ("restate the
full question or request"; classification ends with "Items: " and every item). On 20 unseen rows it passed 20/20
with no dropped data. Rows from revision 1 stay in the dataset (after the checks and the repair). Outside
classification, a trailing "Items:" line that only repeats the question or subject is removed at build
(`dataset_repair.strip_redundant_items`; logged as `items_line_removed`).

**v1.2 build** (`data/promptopt_dataset_v1_2/build_report.md`): 3,203 rows generated, 2,983 passed the automatic
checks, 11 removed by the repair (no source data), 2,972 added. Generating models of the new rows:
cerebras/gpt-oss-120b 2,628, openai/gpt-oss-20b 154, openai/gpt-oss-120b 122, qwen/qwen3.8-27b 68.

**Splits (v1.2)**

| category | train | val | test | benchmark | total |
|---|---|---|---|---|---|
| closed_qa | 953 | 30 | 100 | 10 | 1,093 |
| information_extraction | 869 | 30 | 100 | 10 | 1,009 |
| classification | 908 | 30 | 100 | 10 | 1,048 |
| summarization | 928 | 30 | 101 | 10 | 1,069 |
| coding | 869 | 30 | 100 | 10 | 1,009 |
| **all** | 4,527 | 150 | 501 | 50 | 5,228 |

Test was 40 per category through v1.1 and is 100 from v1.2, so the final numbers rest on more rows. The extra rows
(292) come only from new v1.2 rows, which no tuning ever saw (Stage B was tuned on val only), picked stratified by
complexity. The 40 v1.1 test rows per category (49 in information_extraction, see below) are unchanged. Rows on a
rater sheet keep their split, and no row sharing an instruction with one was moved. The leakage guard still applies:
no instruction appears in two splits (summarization has 101 test rows because a picked instruction had a second
copy). In information_extraction 6 of the 49 test rows before the enlargement came from the leakage guard (new rows
repeating a v1.1 test instruction).

**Splits (v1.2 final)**, after the human rejections and the LLM-assisted filter

| category | train | val | test | benchmark | total |
|---|---|---|---|---|---|
| closed_qa | 951 | 29 | 99 | 10 | 1,089 |
| information_extraction | 867 | 30 | 93 | 10 | 1,000 |
| classification | 906 | 30 | 98 | 8 | 1,042 |
| summarization | 920 | 30 | 94 | 6 | 1,050 |
| coding | 865 | 30 | 98 | 10 | 1,003 |
| **all** | 4,509 | 149 | 482 | 44 | 5,184 |

The benchmark lost 6 rows to human rejections (summarization is down to 6, classification to 8); the per-category
benchmark numbers for those two rest on fewer items.

## Pipeline (v1.2 rows)

1. **Sources and cleaning** (as the notebook): 4 Dolly categories; no empty rows; no duplicate
   instruction + context; Dolly response-length outliers (> median + 3 std per category) dropped; emails and phone
   numbers scrubbed from Dolly; CodeAlpaca answers under 3 words dropped. `source_id` is the row number in the
   original download and is checked against v1.1 before use.
2. **Sampling**: only source rows never sent to a model before, per category
   (1,000 - v1.1 rows) / v1 pass rate x 1.05, stratified by complexity (prompt-length tertile) and context. Frozen in
   `sample.jsonl`.
3. **Generation** as in the table above; resumable checkpoint; each provider has its own usage ledger and daily
   budget (Groq's quota is kept mainly for the evaluation harness).
4. **Automatic checks** (as the notebook): degraded or optimized prompt drifted from the task (sentence-embedding
   similarity), degraded prompt keeps a format spec or is longer than the original, coding target is not about
   code, optimized prompt too long. A failing pair is dropped.
5. **Repair**: `dataset_repair` on every passing row (dropped data appended verbatim; rows whose data exists
   nowhere removed; dropped subjects restored by a cached model edit).
6. **Splits**, keyed by `source_id`: v1.1 rows keep their split and id. New rows go to train unless a held-out split
   of their category is short (benchmark 10, val 30, test 100 per category, filled in that order); rows on a rater
   sheet keep their split. A new row repeating a held-out
   instruction goes to that held-out split; a new row repeating any v1.1 instruction never fills a held-out split.

## Columns

`id`, `split`, `category`, `source_dataset`, `source_id`, `degraded_prompt`, `optimized_prompt`,
`original_instruction`, `context`, `reference_response`, `has_context`, `has_format_spec`,
`optimized_has_format_spec`, `complexity_bucket`, word counts, `sim_degraded_vs_original`,
`sim_optimized_vs_original`, `human_validated`, `model` (provider/model that generated the row),
`generation_version`.

## Human validation

Three team members rated 90 shared rows (18 per category) plus 60 extra and 20 v1.2 rows each (330 distinct rows);
the faculty rated 20 of the shared rows as an independent check. See `docs/validation_guide.md` and
`evaluation/REVIEW_SUMMARY.md` for the agreement statistics (Fleiss' Kappa, Gwet's AC1, PABAK, raw agreement,
prevalence).

Decision rule: shared rows by majority vote per question (2 of 3), accepted only if the majority says Y on all five
questions; the other rows by their single rater (all five Y). The faculty never decide a row. Result: 330 rows
validated, 295 accepted, 35 rejected and left out. Rows nobody rated (4,898) stay and rely on the automatic checks;
`human_validated` says which is which.

## LLM-assisted filter (automatic, not human)

After the team finished, an LLM rater (Claude, `claude-opus-5-5`) rated the 90 shared rows with the same five
questions, strictly, without seeing the human answers (prompt, inputs and outputs in
`data/validation/llm_rater/`). It never counts in the agreement statistics and never overrides a human answer. Of
the 26 shared rows where it answered N on Q3 (optimized prompt keeps the task), only those where the optimized
prompt adds facts, leaks the answer, sets an impossible constraint or changes the task were removed; an added
output format or length was not a reason. 10 rows were flagged (`llm_filter.csv`), 1 of them (dolly-1950) was
already rejected by the team, so the filter removed **9 rows** (7 train, 2 test). Its Q2 and Q5 disagreements
removed nothing; they are listed as limitations below.

## Known limitations

- Two prompt generations (v1 and v1.2) and three generation setups; compare results by `generation_version` where
  it matters.
- Dolly's category labels are noisy (many summarization / information_extraction rows are plain questions). The
  LLM rater called the label debatable on 23 of the 90 shared rows (the team accepted all of them); nothing was
  removed for this.
- Many Dolly degraded prompts are near-verbatim copies of the original question (the question was already short and
  vague). The LLM rater flagged 19 of the 90 shared rows on Q2 for this (the team accepted them); nothing was removed.
- The LLM-assisted filter looked only at the 90 shared rows; the same kinds of Q3 problems (answer leaked into the
  prompt, impossible length limits) are likely present at a similar rate in rows nobody rated.
- Some CodeAlpaca reference answers are wrong (e.g. `codealpaca-16240`: the "equal-sum" split it prints sums to 10
  and 18); task success on coding must not trust the reference blindly.
- Summarization is close to its source limit: v1.2 uses every unused Dolly summarization row.
