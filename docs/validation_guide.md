# PromptOpt Dataset v1.1: validation guide for raters

Each record is a pair: a **degraded** prompt (vague, the way a real user might type it) and an **optimized**
prompt (the clear version PromptOpt should learn to produce). The **original instruction** and **context** come
from Dolly-15k / CodeAlpaca-20k and are the ground truth for what the task is.

## Who rates what

The team: **Nirzara Manade** (`Nirzara_Manade.xlsx`), **Siddhi Bolaikar** (`Siddhi_Bolaikar.xlsx`) and
**Piush Gogi** (`Piush_Gogi.xlsx`).

| rater | records |
|---|---|
| Every team member | the **overlap set**: 90 records (18 per category), rated by all three for Fleiss' Kappa |
| Each team member, alone | 60 **extra** records, to filter out bad pairs |
| Faculty (`faculty.xlsx`) | 20 records (4 per category) taken **from the overlap set**, benchmark and test split first |

So each team sheet has 150 rows and the faculty sheet has 20. Records nobody rates stay in the dataset and rely on
the automatic checks.

The faculty rate records the team also rates, so the report can compare the faculty's answers with the team's
majority vote on those 20 records (percent agreement and Cohen's kappa). This is an independent check on the
team's ratings; the faculty answers do not change the final decision on any record.

The extra records are picked by usefulness, in this order: the benchmark and test splits first (they are the
evaluation data), then pairs whose similarity scores only just passed the automatic checks, then summarization and
information_extraction (Dolly's labels are noisiest there), then the rest. They are dealt out in turn, so every
team member gets an equally useful share.

The overlap and faculty records are not marked in any sheet, and rows are shuffled so categories are mixed. Do not
discuss any record with each other or with the faculty until every sheet is done; the agreement scores are only
meaningful if the ratings are independent.

## Which ID to use

Refer to a record by its `source_id` (for example `dolly-10657` or `codealpaca-1234`), never by the dataset's
`id` column, which is renumbered every time the dataset is rebuilt and is not in the sheets.
`source_id` is the row number in the original download, assigned in Step 1 of the notebook before any filtering
(`dolly-{i}` for Dolly-15k, `codealpaca-{i}` for CodeAlpaca-20k), so it never changes.

The choice of records is frozen in `assignment.csv`. When the dataset grows, `assign` keeps every record already
chosen and only tops up; if a pair is regenerated, its answers are cleared and its note says `REGENERATED`.

## The five questions (answer Y or N from the drop-down)

1. **Q1_degraded_same_task**: does the degraded prompt ask for the same task as the original instruction?
   N if it asks a different question, drops the object of the task, or changes the category.
2. **Q2_degraded_realistic**: is it a realistic vaguer version a real user might type?
   N if it is broken, nonsense, a copy of the original, or artificially garbled.
3. **Q3_optimized_same_intent**: does the optimized prompt keep the same task and intent?
   N if it adds facts, includes the answer, adds requirements the user clearly did not want, or drops data
   from the original instruction (the items to classify, the code, the subject the question is about).
4. **Q4_optimized_better**: is the optimized prompt clearer and better specified than the degraded one
   (explicit output format, sensible constraints, no filler)? N if it is not an improvement.
5. **Q5_category_correct**: is the category label right? Dolly's labels are noisy: many "summarization" and
   "information_extraction" records are really plain questions. Answer N when the label is wrong and write the
   right category in `notes`.

A record is **accepted** only if all five answers are Y. Write a short reason in `notes` for every N.
Never edit the prompt columns; suggest fixes in `notes`.

## Examples

| degraded | optimized | answers | why |
|---|---|---|---|
| which one is string or percussion: tombak, cizhonghlu | Classify each listed instrument as "string" or "percussion". Output a JSON object with the instrument names as keys and the label as values.<br><br>Items: Tombak, Cizhonghlu | Y Y Y Y Y | same task, realistic, clear format, items kept |
| (same degraded prompt) | the same optimized prompt without the `Items:` line | Q3 = N | the instruments are gone, so the prompt cannot be answered |
| who gets a dowry? (category: summarization) | ... | ... Q5 = N | this is a plain question (closed_qa), not a summary |
| summarize it | Summarize the passage about the Eiffel Tower in 3 bullet points. | Q3 = N | the optimized prompt invents a topic the user never gave |

## Workflow

1. Open your `.xlsx` in Excel, LibreOffice or Google Sheets (File > Import keeps the drop-downs).
2. Rate in any order; save often. Blank = not done yet.
3. Send the file back (or put it in the shared Drive folder `validation/`) under the same file name.
4. The team runs `python -m app.validation report` to see progress, agreement and the faculty check, and `merge`
   at the end. Final answers: majority vote of the team on the overlap set, the single rater on extra records.

Targets: Fleiss' Kappa above 0.6 ("substantial" agreement) among the team on the 90 overlap records, and Cohen's
kappa above 0.6 between the faculty and the team's majority vote on the 20 faculty records. If either is lower, meet,
discuss the disagreements, clarify this guide, and re-rate the overlap set.

To recreate the sheets from scratch (for example after the dataset changes before anyone has rated), run
`python -m app.validation assign --reset` inside `backend/`. Answers already in a sheet are never deleted.
