# 3. The dataset: sources, generation, repair, validation, splits

[Back to the index](README.md)

PromptOpt Dataset is a set of **pairs**: a *degraded prompt* (how a rushed, non-expert user types a request) and an
*optimized prompt* (the same task stated clearly, with an explicit output format and only helpful constraints), for the
five categories. Each row also keeps the source's original instruction, context and reference answer. This chapter
documents every step that produced the final version (v1.2 final, 5,184 rows), with the formulas, thresholds and
measurements behind each one. Short version: `docs/DATASET_CARD.md`.

The dataset is **not** in git and **never** in the database. It lives in `data/` (git-ignored) and on Google Drive.

---

## 3.1 Versions at a glance

| version | rows | what changed | built by |
|---|---|---|---|
| v1 | 2,265 | sampling, LLM generation, automatic checks, splits | Colab notebook `PromptOpt_Dataset_Preparation_v2.ipynb` (on Drive) |
| v1.1 | 2,256 | data the generator had dropped from the instruction put back; 9 rows without source data removed | `backend/app/dataset_repair.py` |
| v1.2 | 5,228 | v1.1 unchanged + 2,972 new rows from never-used source rows; test enlarged to 100 per category | `backend/app/dataset_expand.py` |
| **v1.2 final** | **5,184** | v1.2 minus 35 rows rejected by the human raters and 9 removed by the LLM-assisted filter | `python -m app.validation merge --drop-rejected --auto-filter ...` |

```
Dolly-15k (4 categories) ─┐                          ┌─ automatic checks ─ repair ─┐
                          ├─ clean ─ sample ─ LLM ───┤                             ├─ splits ─ human review ─ LLM filter ─ v1.2 final
CodeAlpaca-20k (coding) ──┘            writes pairs  └─────────────────────────────┘
```

## 3.2 Sources

| source | rows in the download | used for | licence / note |
|---|---|---|---|
| `databricks-dolly-15k.jsonl` (Dolly-15k) | 15,011 | closed_qa (1,773), information_extraction (1,506), classification (2,136), summarization (1,188); brainstorming + creative_writing as `other` examples for Stage A only | CC BY-SA 3.0 |
| `code_alpaca_20k.json` (CodeAlpaca-20k, `sahil2801/CodeAlpaca-20k` on Hugging Face) | 20,022 | coding | the reference answers contain errors (section 3.12) |

**`source_id`.** Every source row is identified by its row number in the original download: `dolly-{i}` and
`codealpaca-{i}`, assigned **before** any filtering. It never changes when the dataset is rebuilt (the dataset's own
`id` column, e.g. `PO-CQA-0123`, is renumbered on rebuilds and is never used as a key). `dataset_expand.check_source_ids`
aborts if more than 1% of v1.1 rows do not match their `source_id` in the source files, which would mean the files are
a different download.

CodeAlpaca's `input` field plays the role of Dolly's `context`.

## 3.3 Cleaning (notebook steps 1–5; ported in `dataset_expand.clean_pool`)

Sub-steps, in order:

1. **Category filter.** Dolly rows of the four categories with a non-empty instruction and response.
2. **De-duplication.** Key = normalized instruction + `" || "` + normalized context, where *normalized* means lower
   case with every whitespace run collapsed to one space. The first occurrence is kept.
3. **Response-length outliers (Dolly).** Per category, with $w_i$ the response word count:

   $$\text{cutoff}_c = \operatorname{median}_c(w) + 3\,\sigma_c(w), \qquad \text{drop row } i \text{ if } w_i > \text{cutoff}_c$$

   $\sigma$ is the sample standard deviation (`statistics.stdev`, divisor $n-1$). **Basis:** the median is a robust
   centre for right-skewed word counts, and "3 standard deviations" is the classical outlier tail; the rule removes the
   few extremely long reference answers that would dominate evaluation of summaries and extractions. Recomputed with
   the code on the source files:

   | category | rows after de-dup | median words | σ | cutoff | dropped |
   |---|---|---|---|---|---|
   | closed_qa | 1,759 | 17 | 48.3 | 162.0 | 36 |
   | information_extraction | 1,501 | 19 | 105.1 | 334.4 | 45 |
   | classification | 2,133 | 14 | 36.4 | 123.3 | 37 |
   | summarization | 1,186 | 54 | 154.5 | 517.5 | 10 |

4. **PII scrubbing (Dolly).** Instruction, context and response go through the same email/phone patterns as the
   live app (`db/pii.py`, chapter 13.6).
5. **CodeAlpaca.** De-duplicated the same way; outputs under 3 words dropped (`MIN_CODING_OUTPUT_WORDS = 3`: one- or
   two-word "answers" are not code).
6. **Attributes** added to every row: `has_context`, `has_format_spec` (the notebook's own format regex,
   `dataset_expand.FORMAT_PATTERNS`, 14 patterns), instruction/context/response word counts, and
   **`complexity_bucket`**: the tertile of (instruction words + context words) **within the category**. With the rows
   of a category sorted by that length (ties by position), the row at 0-based rank $r$ out of $N$ gets

   $$\text{bucket} = (\text{short}, \text{medium}, \text{long})\big[\min(2, \lfloor 3r/N \rfloor)\big]$$

   so each bucket holds one third of the rows.

Pool after cleaning: closed_qa 1,723, information_extraction 1,456, classification 2,096, summarization 1,176,
coding 19,024 (CodeAlpaca is not down-sampled).

## 3.4 v1: the first generation (Colab)

* **Sampling.** 500 rows per category, stratified by complexity and context.
* **Generation.** One Groq call per row returned both prompts (JSON), temperature 0.7, reasoning effort "low" for
  gpt-oss and "none" for qwen, context truncated to 1,500 characters (1,000 later). Models (rows in v1.1):
  gpt-oss-120b 1,054, gpt-oss-20b 858, qwen3.8-27b 344.
* **Automatic checks** (section 3.6.5) dropped failing pairs, leaving **2,265** rows.
* **Splits** by original instruction (40 test rows per category at that time).

Survival rate per category, used later by the expansion plan (rows that survived into v1.1 ÷ rows sampled):
closed_qa 425/500 = 85.0%, information_extraction 449/500 = 89.8%, classification 474/500 = 94.8%,
summarization 436/500 = 87.2%, coding 472/500 = 94.4%.

## 3.5 v1 → v1.1: putting dropped data back (`dataset_repair.py`)

**The problem.** In v1 many prompts lost the literal data written into the original instruction:

```
original:  Identify which instrument is string or percussion: Sheker, Taishogoto
optimized: Classify each listed instrument as "string" or "percussion". Output a JSON object ...
```

The items are gone, so the optimized prompt cannot be answered. (The row's `context` is appended to every prompt at
evaluation time, so only data living in the instruction itself can be lost this way.)

**Per row:**

1. `extract_payload` finds the literal data in the original instruction. Classification: the item list (after the
   first colon, after the question, on the following lines, or the last comma-separated run). All categories: data on
   the lines after the first line (code, answer options) and arithmetic expressions (a regex for three or more numbers
   joined by operators).
2. `dropped` decides whether a prompt lost it:
   * optimized classification prompts: **any** item missing (items compared by word stems);
   * everything else (and degraded prompts, which may shorten items the way users do: "UK", "tux"): the share of the
     payload's content words still present is below `COVERAGE_MIN = 0.5`:

     $$\text{coverage} = \frac{|\text{content words}(\text{payload}) \cap \text{words}(\text{prompt})|}{|\text{content words}(\text{payload})|} < 0.5$$

     **Basis:** half the content words is a conservative "clearly lost" line; a prompt that paraphrases the data keeps
     more than half of its content words.
3. `repair_row` appends the payload **verbatim**: to degraded prompts as a user would paste it (after `": "` or a new
   line), to optimized prompts under a label (`Items: `, `Expression: `, or `Input:` + new line for multi-line data).
   Deterministic, no model involved.
4. Rows whose instruction points at data that exists nowhere ("sort these numbers" with no numbers anywhere) are
   **removed**: nothing can be restored (9 rows).
5. Optimized prompts that stopped naming the instruction's **subject** ("the temple" for "Doleshwor Mahadeva temple";
   subjects found with spaCy named entities) cannot be fixed by appending. `regenerate` asks Groq gpt-oss-120b (the
   model that made v1) for a minimal edit, 5 rows per call, and `accept_edit` keeps the edit only if it names every lost
   subject **and** is at most 12 words longer than before. Edits are cached in `regenerated.json`, so re-running is
   reproducible.

**Result:** 349 optimized and 20 degraded prompts repaired, 75 dropped subjects restored, 9 rows removed → **2,256**
rows. Every change: `docs/dataset_v1_1_repair_log.csv`.

## 3.6 v1.1 → v1.2: expansion to about 1,000 rows per category (`dataset_expand.py`)

### 3.6.1 How many rows to sample (the plan)

Only source rows never sent to a model before are used. For category $c$:

$$\text{needed}_c = \max(0,\ 1000 - \text{rows}_c^{v1.1}), \qquad
\text{rate}_c = \frac{\text{rows}_c^{v1.1}}{\text{sampled}_c^{v1}}, \qquad
\text{to\_sample}_c = \min\!\Big(\text{unused}_c,\ \Big\lceil \frac{\text{needed}_c}{\text{rate}_c} \times 1.05 \Big\rceil\Big)$$

**Basis of each term:** dividing by the v1 survival rate estimates how many rows must be generated so that enough
survive the same checks; `SAMPLE_MARGIN = 1.05` adds 5% so a category still reaches the target if this round's pass
rate is a little lower; the minimum caps it at the rows that exist. Recomputed with the code:

| category | v1.1 rows | rate | needed | unused source rows | to sample |
|---|---|---|---|---|---|
| closed_qa | 425 | 0.850 | 575 | 1,223 | ⌈575 / 0.850 × 1.05⌉ = **711** |
| information_extraction | 449 | 0.898 | 551 | 956 | ⌈551 / 0.898 × 1.05⌉ = **645** |
| classification | 474 | 0.948 | 526 | 1,596 | ⌈526 / 0.948 × 1.05⌉ = **583** |
| summarization | 436 | 0.872 | 564 | 676 | min(676, ⌈679.1⌉) = **676** (every unused row) |
| coding | 472 | 0.944 | 528 | 18,524 | ⌈528 / 0.944 × 1.05⌉ = **588** |
| **all** | | | | | **3,203** |

The sample is frozen in `sample.jsonl`, so every run works on the same rows.

### 3.6.2 Stratified sampling (largest-remainder allocation)

`stratified_pick(rows, n, strata=("complexity_bucket", "has_context"))` draws $n$ rows so each stratum keeps its
share. With $N$ candidate rows and $N_k$ in stratum $k$:

1. ideal allocation $a_k = n \cdot N_k / N$;
2. base allocation $b_k = \lfloor a_k \rfloor$;
3. the $n - \sum_k b_k$ remaining places go to the strata with the largest fractional parts $a_k - b_k$ (ties broken
   by the stratum key) — the **largest-remainder (Hamilton) method**, which never misses a stratum's ideal share by a
   full row;
4. within a stratum, rows are taken in a fixed pseudo-random order: the SHA-256 of `seed:salt:source_id` mapped to
   $[0, 1)$ (`_unit`), so the draw is reproducible without a random-number generator state.

*Example:* $n = 10$ from strata of 45, 35 and 20 rows ($N = 100$): $a = (4.5, 3.5, 2.0)$, $b = (4, 3, 2)$, 1 place
left, fractional parts $(0.5, 0.5, 0)$, the tie goes to the first key → $(5, 3, 2)$.

### 3.6.3 Generation

* **Prompt** (`SYSTEM_PROMPT`): the notebook's rules for both rewrites plus the **data rule**: data written inside the
  instruction (items to classify, lists, code, numbers, expressions, quoted strings, the named subject) must appear
  **verbatim** in both prompts. v1 had no such rule, which is why v1.1 had to repair it. Per-category requirements for
  the optimized prompt (closed_qa: answer only from the text and state the length; extraction: what to extract and the
  output structure; classification: list the labels, label only, end with `Items: ...`; summarization: a length and a
  focus; coding: name the language, behaviour, inputs/outputs, code in one block).
* **Settings:** temperature 0.7 (variety in the degraded prompts), JSON output, reasoning "low" for gpt-oss and "none"
  for qwen (fewer hidden tokens), context truncated to 1,000 characters (`MAX_CONTEXT_CHARS`), a completion budget of
  $\max(1024,\ 400n + 300)$ tokens for a call with $n$ items (2,300 for a 5-item batch; basis: the visible JSON is about
  90 tokens per item plus 130–300 tokens of shared reasoning, so 400 per item leaves a wide margin), up to 3 calls per
  row if the JSON is unusable.
* **Batching** (`v1.2-batch5`): 5 rows per call. *Why and how it was estimated:* the system prompt was about 60% of a
  one-row call, so sending it once per 5 rows is the main saving. Measured on the same 10 rows with both set-ups
  (`data/promptopt_dataset_v1_2/prompt_comparison_10rows.json`): about **1,070 → 400 tokens per row**, with automatic
  checks as good or better (old: 2 flags, 0 data drops; new: 0 flags, 1 dropped item list, restored by the repair).
  Each item carries its `source_id` and the reply must echo it; results are matched **only** by id, never by position
  (the first 40 batched rows were matched by position before this was added; all 40 were checked, none was swapped).
* **Prompt revision 2:** after 225 batched rows, their pass rate was compared with v1 per category: in closed_qa the
  optimized prompt often left out the question (76% pass vs 85% in v1), in classification it dropped the items in 18 of
  41 rows. Revision 2 states both explicitly; on 20 unseen rows it passed 20/20 with no dropped data.
* **Providers:** Cerebras gpt-oss-120b first; Groq models when Cerebras' daily quota is used up (Groq's quota is kept
  mainly for the evaluation harness). Rows go round-robin over the categories so a partial run stays balanced.

### 3.6.4 Budget and pacing during generation

| rule | value | basis |
|---|---|---|
| Groq: share of each model's daily limit generation may use (its own tag) | `BUDGET_FRACTION = 0.5` | the other half stays for evaluation the same day |
| any model: total use by all tools never above | `GLOBAL_CAP = 0.95` of the daily limit | keeps a safety margin under the provider's hard stop |
| Cerebras: share for generation | `CEREBRAS_FRACTION = 0.95` | Cerebras was used for generation only |
| tokens per call (planning) | measured average of the last 200 rows once ≥ 20 rows exist (`MEASURE_AFTER`), else 1,050 (single) / 525 (batched) | 1,050 = input (cached included) + output per single call, measured 2026-09-26 |
| seconds between Groq calls | $\max\!\big(2.2,\ \tfrac{60 \cdot T}{0.9 \cdot 8000}\big)$ for $T$ tokens per call | stays under 90% of Groq's 8,000 tokens-per-minute; e.g. $T = 1{,}050$ → 8.75 s |

A call is allowed only if (own requests + 1) ≤ fraction × request limit, (own tokens + estimate) ≤ fraction × token
limit, and the same for the total of all tools against `GLOBAL_CAP` (`Budget.allows`). For Cerebras, the remaining
daily quota reported in the response headers is trusted when known.

### 3.6.5 Automatic quality checks (`quality_flags`)

Similarity is the cosine similarity of all-MiniLM-L6-v2 embeddings. The embeddings are L2-normalized, so

$$\text{sim}(a, b) = \cos\theta = \frac{\mathbf{e}_a \cdot \mathbf{e}_b}{\lVert\mathbf{e}_a\rVert\,\lVert\mathbf{e}_b\rVert} = \mathbf{e}_a \cdot \mathbf{e}_b \in [-1, 1].$$

A pair **fails** if any flag is true:

| flag | condition | why |
|---|---|---|
| `degraded_drifted` | sim(original, degraded) < **0.45** | the degraded prompt must still ask the same thing |
| `not_degraded` | (degraded = original after normalizing, or sim > 0.98) **and** the original stated a format | nothing was degraded |
| `degraded_keeps_format_spec` | the notebook's format regex matches the degraded prompt | a degraded prompt must have no format |
| `degraded_longer_than_original` | words(degraded) − words(kept data) > 1.25 × words(original) + 3 | degraded prompts are short |
| `optimized_drifted` | sim(original, optimized) < **0.35**, or (no shared key stem and sim < 0.50) | the optimized prompt must keep the task |
| `coding_target_not_code` | coding row whose optimized prompt has no code word (code, function, Python, SQL, ...) | — |
| `optimized_too_long` | words(optimized) − words(kept data) > 120 | over-specification |

*Key stems* are the first 5 characters of words longer than 2 characters that are not stop words.
**Basis of the thresholds:** 0.45 and 0.35 come from the v1 notebook. The optimized threshold is deliberately lower
because the optimized prompt adds format and constraint sentences that dilute the similarity to the bare instruction,
while the degraded prompt is a paraphrase of it; the "no shared stem and < 0.50" clause catches prompts that keep the
general topic but none of the instruction's key words. The +3 words and the 1.25 factor allow for casual filler
("hey can you ...") in a short prompt.

Rows that pass are repaired (section 3.5) and a trailing `Items:` line that only repeats the question is removed
outside classification (`strip_redundant_items`, logged as `items_line_removed`).

**v1.2 build result** (`data/promptopt_dataset_v1_2/build_report.md`):

| category | generated | passed checks | rows repaired | subjects regenerated | removed (no source data) | added |
|---|---|---|---|---|---|---|
| closed_qa | 711 | 668 | 1 | 21 | 0 | 668 |
| information_extraction | 645 | 560 | 0 | 9 | 0 | 560 |
| classification | 583 | 582 | 59 | 10 | 8 | 574 |
| summarization | 676 | 633 | 0 | 2 | 0 | 633 |
| coding | 588 | 540 | 2 | 1 | 3 | 537 |
| **all** | **3,203** | **2,983** | | | **11** | **2,972** |

Flags hit (one row can hit several): the most common were `degraded_keeps_format_spec` in information_extraction (73)
and `optimized_drifted` in closed_qa (35). Generating models of the 2,972 new rows: cerebras/gpt-oss-120b 2,628,
openai/gpt-oss-20b 154, openai/gpt-oss-120b 122, qwen/qwen3.8-27b 68.

### 3.6.6 Splits (`assign_splits`)

1. v1.1 rows keep their split and id.
2. New rows on a rater sheet keep the split they had when assigned.
3. New rows go to `train`, unless a held-out split of their category is short of its size, filled **in this order**:
   benchmark 10, val 30, test 100 per category (so val never waits on test). Rows to fill a held-out split are chosen
   by `stratified_pick` by complexity bucket.
4. **Leakage guard:** a new row repeating a held-out instruction goes to that held-out split; a new row repeating any
   v1.1 instruction is never used to fill a held-out split; copies of an instruction a new row just took into a
   held-out split go with it. Hence no instruction appears in two splits.
5. New ids continue each category's numbering (`PO-CQA-…`, `PO-IE-…`, `PO-CLS-…`, `PO-SUM-…`, `PO-COD-…`).

Test was 40 per category through v1.1 and is 100 from v1.2. The extra 60 per category come only from new v1.2 rows,
which no tuning had seen (Stage B was tuned on val). Summarization has 101 test rows because a picked instruction had
a second copy (the leakage guard moved it along).

| v1.2 | train | val | test | benchmark | total |
|---|---|---|---|---|---|
| closed_qa | 953 | 30 | 100 | 10 | 1,093 |
| information_extraction | 869 | 30 | 100 | 10 | 1,009 |
| classification | 908 | 30 | 100 | 10 | 1,048 |
| summarization | 928 | 30 | 101 | 10 | 1,069 |
| coding | 869 | 30 | 100 | 10 | 1,009 |
| **all** | **4,527** | **150** | **501** | **50** | **5,228** |

## 3.7 Generation versions (`generation_version` column)

| value | prompt | rows per call | rows in v1.2 |
|---|---|---|---|
| `v1` | the notebook's prompt (no data rule) | 1 | 2,256 |
| `v1.2-single` | v1.2 prompt with the data rule | 1 | 254 |
| `v1.2-batch5` | the same rules worded compactly | 5 | 2,718 |

## 3.8 Human validation (`validation.py`, `team_input/validation_guide.md`)

### 3.8.1 Design

| who | rows | purpose |
|---|---|---|
| all three team members | **overlap set**: 90 rows (18 per category), fixed pseudo-random pick | inter-rater agreement |
| each team member alone | 60 **extra** rows | filtering bad pairs |
| each team member alone | 20 **v1.2** rows (4 per category) | so the new rows are human-checked too |
| the faculty guide | 20 of the overlap rows (4 per category; benchmark and test split first) | independent check, never decides a row |

Distinct rows rated: $90 + 3 \times 60 + 3 \times 20 = 330$. Each team sheet has 170 rows ($90 + 60 + 20$).

**Extra rows were chosen by usefulness** (`extra_priority`): evaluation splits (benchmark, test) first; then
*borderline* rows, whose similarity check passed by less than 0.10 (sim_degraded < 0.55 or sim_optimized < 0.45);
then the categories with noisy Dolly labels (summarization, information_extraction); then a fixed pseudo-random
order. They were dealt out in turn so every rater got an equally useful share. Overlap and faculty rows are not marked
in the sheets and rows are shuffled; raters did not discuss rows until all sheets were done.

### 3.8.2 The five questions (Y/N)

1. **Q1** the degraded prompt asks for the same task as the original instruction;
2. **Q2** the degraded prompt is a realistic vaguer version a real user might type;
3. **Q3** the optimized prompt keeps the task and intent, without adding facts, answers or unwanted requirements, and
   without dropping data;
4. **Q4** the optimized prompt is clearer and better specified than the degraded one;
5. **Q5** the category label is correct.

A row is **accepted** only if all five are Y.

### 3.8.3 Decision rule

* Overlap rows: per question, **majority vote** (at least 2 of 3 matching answers); accepted only if the majority is
  Y on all five. (A tie cannot occur with three raters and two answers.)
* Extra and v1.2 rows: the single rater's answers.
* The faculty never decides a row.

**Result:** 330 validated, **295 accepted, 35 rejected** (left out of the final dataset). Accepted per category:
classification 48, closed_qa 56, coding 53, information_extraction 72, summarization 66. Per sheet: Nirzara 152 of
170 accepted, Piush 150, Siddhi 138; faculty 19 of 20. The 4,898 rows nobody rated rely on the automatic checks; the
column `human_validated` says which is which.

## 3.9 Agreement statistics: definitions, derivations, worked example

All statistics are computed in `validation.py` on the 90 overlap rows, per question, from a table with one row per
item: $n_{iY}$, $n_{iN}$ = how many of the $n = 3$ raters answered Y / N on item $i$; $I = 90$ items.

### 3.9.1 Observed agreement

Per item, the share of agreeing rater **pairs**:

$$P_i = \frac{\sum_j n_{ij}(n_{ij} - 1)}{n(n-1)} = \frac{\sum_j n_{ij}^2 - n}{n(n-1)}, \qquad \bar P = \frac{1}{I}\sum_i P_i$$

With three raters, an item with 3 equal answers has $P_i = (9 - 3)/6 = 1$; an item split 2–1 has
$P_i = (4 + 1 - 3)/6 = 1/3$. **Raw agreement** (reported separately) is the share of items where all raters agree.

### 3.9.2 Fleiss' kappa (Fleiss 1971)

Kappa corrects $\bar P$ for the agreement expected by chance if raters answered at random with the observed answer
frequencies $p_j = \frac{1}{I n}\sum_i n_{ij}$:

$$P_e = \sum_j p_j^2, \qquad \kappa = \frac{\bar P - P_e}{1 - P_e}$$

$\kappa = 1$ is perfect agreement, $0$ is chance level, negative is below chance. Landis & Koch (1977) bands, used in
the report (`interpret_kappa`): ≤ 0 poor, ≤ 0.2 slight, ≤ 0.4 fair, ≤ 0.6 moderate, ≤ 0.8 substantial, above that
almost perfect. The validation guide's target was $\kappa > 0.6$.

### 3.9.3 Gwet's AC1 (Gwet 2008) and PABAK

For two answer categories, AC1 uses a different chance term that does **not** go to 1 when one answer dominates:

$$\pi = p_Y, \qquad P_e^{AC1} = 2\pi(1-\pi), \qquad AC1 = \frac{\bar P - P_e^{AC1}}{1 - P_e^{AC1}}$$

PABAK (prevalence- and bias-adjusted kappa) fixes chance agreement at 0.5 for two categories:

$$\text{PABAK} = \frac{\bar P - 0.5}{1 - 0.5} = 2\bar P - 1$$

### 3.9.4 Worked example: Q1 ("degraded prompt asks for the same task")

Exact counts from the rater sheets: 81 items answered Y by all three, 8 items split 2 Y / 1 N, 1 item split
1 Y / 2 N; Y answers 260 of 270.

* $\bar P = (81 \cdot 1 + 9 \cdot \tfrac{1}{3}) / 90 = 84/90 = 0.9333$
* raw agreement $= 81/90 = 0.900$
* $p_Y = 260/270 = 0.9630$, $p_N = 0.0370$ → $P_e = 0.9630^2 + 0.0370^2 = 0.9287$
* $\kappa = (0.9333 - 0.9287)/(1 - 0.9287) = 0.0047/0.0713 = \mathbf{0.065}$
* $P_e^{AC1} = 2 \times 0.9630 \times 0.0370 = 0.0713$ → $AC1 = (0.9333 - 0.0713)/(1 - 0.0713) = \mathbf{0.928}$
* $\text{PABAK} = 2 \times 0.9333 - 1 = \mathbf{0.867}$

These are exactly the reported values (`evaluation/dataset/validation_report.md`).

### 3.9.5 Why kappa is near zero although raters agree (the kappa paradox)

When almost every answer is Y, $P_e = p_Y^2 + p_N^2 \to 1$, so the denominator $1 - P_e$ becomes tiny and a handful
of disagreements decides the value: here $1 - P_e = 0.071$, and the 9 split items move $\bar P$ by $0.067$ below 1,
which is about the whole denominator. Kappa then says "near chance" even though the raters agreed on 90% of the items.
AC1's chance term $2\pi(1-\pi)$ goes to 0 instead, so AC1 stays near the observed agreement. This is a known
property of kappa under high prevalence (Feinstein & Cicchetti 1990), and why the project reports kappa **and** AC1,
PABAK, raw agreement and prevalence together.

**All questions** (team, 90 overlap rows):

| question | % Y | raw (all 3 agree) | Fleiss' κ | Gwet's AC1 | PABAK | rating distribution (3Y / 2Y1N / 1Y2N / 0Y) |
|---|---|---|---|---|---|---|
| Q1 degraded same task | 96.3% | 90.0% | 0.065 | 0.928 | 0.867 | 81 / 8 / 1 / 0 |
| Q2 degraded realistic | 96.3% | 88.9% | −0.038 | 0.920 | 0.852 | 80 / 10 / 0 / 0 |
| Q3 optimized same intent | 96.3% | 90.0% | 0.065 | 0.928 | 0.867 | 81 / 8 / 1 / 0 |
| Q4 optimized better | 98.1% | 94.4% | −0.019 | 0.962 | 0.926 | 85 / 5 / 0 / 0 |
| Q5 category correct | 98.1% | 94.4% | −0.019 | 0.962 | 0.926 | 85 / 5 / 0 / 0 |
| accept (all five Y) | 86.3% | 67.8% | 0.092 | 0.719 | 0.570 | 60 / 24 / 5 / 1 |

Agreement on the combined accept decision is clearly lower: one differing answer on any of five questions splits the
raters. The kappa target (> 0.6) is not met, for the reason above.

### 3.9.6 Faculty check (Cohen's kappa)

The faculty's 20 answers are compared with the team's **majority** answer per row (two "raters"):

$$p_o = \frac{\#\text{agreements}}{N}, \qquad p_e = \sum_{c \in \{Y, N\}} p_{1c}\, p_{2c}, \qquad \kappa_{Cohen} = \frac{p_o - p_e}{1 - p_e}$$

where $p_{1c}$, $p_{2c}$ are each side's share of answer $c$. Undefined ("n/a") when both sides always gave the same
single answer ($p_e = 1$). Results: percent agreement 90–100% per question, accept 85% (17 of 20); Cohen's kappa
around 0 for the same prevalence reason; the faculty accepted 19 of 20 rows (the one rejection, `dolly-4205`, was
accepted by the team majority and later removed by the LLM-assisted filter).

## 3.10 LLM-assisted filter (automatic, not human)

After the team finished, an LLM rater (Claude, `claude-opus-5-5`) rated the 90 overlap rows with the same five
questions, as a strict reviewer, without seeing the human answers (prompt and outputs in
`data/validation/llm_rater/`, summary in `evaluation/llm_rater/`). It never counts in any agreement statistic and never
overrides a human answer. It accepted 38 of 90 rows (team majority: 88 of 90).

**Filter rule:** only rows where it answered N on Q3 (26) were considered, and only those where the optimized prompt
**adds facts, leaks the answer, sets an impossible constraint or changes the task** were removed; an added output
format or length was not a reason. 10 rows were flagged; one (`dolly-1950`) was already rejected by the team, so the
filter removed **9 rows** (train 7, test 2). Each is listed with its reason in `evaluation/REVIEW_SUMMARY.md` §4.

## 3.11 The final dataset (v1.2 final)

**Reconciliation:** $5{,}228 - 35 \text{ (human)} - 9 \text{ (LLM filter)} = 5{,}184$.

| split | v1.2 | human rejections | LLM filter | v1.2 final |
|---|---|---|---|---|
| train | 4,527 | −11 | −7 | **4,509** |
| val | 150 | −1 | 0 | **149** |
| test | 501 | −17 | −2 | **482** |
| benchmark | 50 | −6 | 0 | **44** |
| **all** | 5,228 | −35 | −9 | **5,184** |

| v1.2 final | train | val | test | benchmark | total |
|---|---|---|---|---|---|
| closed_qa | 951 | 29 | 99 | 10 | 1,089 |
| information_extraction | 867 | 30 | 93 | 10 | 1,000 |
| classification | 906 | 30 | 98 | 8 | 1,042 |
| summarization | 920 | 30 | 94 | 6 | 1,050 |
| coding | 865 | 30 | 98 | 10 | 1,003 |
| **all** | **4,509** | **149** | **482** | **44** | **5,184** |

File: `data/promptopt_dataset_v1_2_final/promptopt_dataset_v1_2_final.csv` (default `DATASET_DIR`); every left-out row
with its reason: `merge_log.csv` next to it and `evaluation/dataset/final_dataset_merge_log.csv`.

**Columns:** `id`, `split`, `category`, `source_dataset`, `source_id`, `degraded_prompt`, `optimized_prompt`,
`original_instruction`, `context`, `reference_response`, `has_context`, `has_format_spec`, `optimized_has_format_spec`,
`complexity_bucket`, `instruction_word_count`, `degraded_word_count`, `optimized_word_count`, `context_word_count`,
`response_word_count`, `sim_degraded_vs_original`, `sim_optimized_vs_original`, `human_validated`, `model`,
`generation_version` (plus the validation columns added by the merge).

## 3.12 Known limitations of the dataset

* Optimized prompts are **LLM-written**; only 330 rows were rated by humans, and the LLM filter covered only the 90
  overlap rows. Similar problems (leaked answers, impossible lengths) are likely in unrated rows at a similar rate.
* Two prompt generations (v1 and v1.2) and three set-ups; compare by `generation_version` where it matters.
* Dolly's category labels are noisy: many summarization / information_extraction rows are plain questions (the LLM
  rater called the label debatable on 23 of 90 rows; nothing was removed for this). This caps Stage A's measurable
  accuracy in the text group (chapter 4).
* Many Dolly degraded prompts are near-copies of an already short question (19 of 90 flagged on Q2 by the LLM rater).
* Some CodeAlpaca references are wrong (e.g. `codealpaca-16240`: the "equal-sum" split it prints sums to 10 and 18;
  `codealpaca-12152` claims the maximum depth of a binary tree with n nodes is log₂ n). Wrong references found on val
  are listed in `evaluation/dataset/wrong_references.csv` and excluded from evaluation summaries for all variants;
  static checks (`reference_check.py`) list suspects (does not parse, wrong language, no code, a named function missing).
* Summarization is at its source limit: v1.2 uses every unused Dolly summarization row.
