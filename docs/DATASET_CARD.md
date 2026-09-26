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
| v1.2 | ~5,100 (about 1,000 per category) | v1.1 unchanged, plus new rows from never-used source rows | `backend/app/dataset_expand.py` |

## How the rows were generated (`generation_version`)

The dataset was built in phases, and every row says which one produced it. Report results with this in mind: the
v1 rows were generated with a different prompt from the v1.2 rows.

| generation_version | prompt | rows per call | provider / models (`model` column) | when | rows |
|---|---|---|---|---|---|
| `v1` | the notebook's prompt (no data rule) | 1 | Groq: gpt-oss-120b (1,054), gpt-oss-20b (858), qwen3.8-27b (344) | Sep 2026, before 26 Sep | 2,256 (all v1.1 rows) |
| `v1.2-single` | v1.2 prompt: the notebook's rules plus the data rule | 1 | Groq: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` | 26 Sep 2026, morning | 303 generated |
| `v1.2-batch5` | the same rules as `v1.2-single`, worded compactly for several items | 5 | `cerebras/gpt-oss-120b` first; Groq models when Cerebras' daily limit is used up | from 26 Sep 2026 | the rest |

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
   of their category is short (benchmark 10, test 40, val 30 per category). A new row repeating a held-out
   instruction goes to that held-out split; a new row repeating any v1.1 instruction never fills a held-out split.

## Columns

`id`, `split`, `category`, `source_dataset`, `source_id`, `degraded_prompt`, `optimized_prompt`,
`original_instruction`, `context`, `reference_response`, `has_context`, `has_format_spec`,
`optimized_has_format_spec`, `complexity_bucket`, word counts, `sim_degraded_vs_original`,
`sim_optimized_vs_original`, `human_validated`, `model` (provider/model that generated the row),
`generation_version`.

## Human validation

Three team members rate 90 shared rows (18 per category, Fleiss' Kappa) plus 60 rows each; the faculty rate 20 of
the shared rows as an independent check (percent agreement and Cohen's kappa against the team's majority).
See `docs/validation_guide.md`.

## Known limitations

- Two prompt generations (v1 and v1.2) and three generation setups; compare results by `generation_version` where
  it matters.
- Dolly's category labels are noisy (many summarization / information_extraction rows are plain questions).
- Some CodeAlpaca reference answers are wrong (e.g. `codealpaca-16240`: the "equal-sum" split it prints sums to 10
  and 18); task success on coding must not trust the reference blindly.
- Summarization is close to its source limit: v1.2 uses every unused Dolly summarization row.
