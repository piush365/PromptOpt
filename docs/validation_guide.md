# PromptOpt Dataset v1: validation guide for raters

Each record is a pair: a **degraded** prompt (vague, the way a real user might type it) and an **optimized**
prompt (the clear version PromptOpt should learn to produce). The **original instruction** and **context** come
from Dolly-15k / CodeAlpaca-20k and are the ground truth for what the task is.

## Who rates what

| rater | records |
|---|---|
| Lab assistants (`lab_assistants.xlsx`) | 20: 4 per category, from the benchmark split used in the live A/B test |
| Each student (`<name>.xlsx`) | about a third of the rest, plus a shared overlap set |
| Overlap (in all three student sheets) | about 6% of the student records, rated independently by all three for Fleiss' Kappa |

Do not discuss overlap records before all three have rated them; the agreement score is only meaningful if the
ratings are independent. Row order is shuffled so categories are mixed.

## The five questions (answer Y or N from the drop-down)

1. **Q1_degraded_same_task**: does the degraded prompt ask for the same task as the original instruction?
   N if it asks a different question, drops the object of the task, or changes the category.
2. **Q2_degraded_realistic**: is it a realistic vaguer version a real user might type?
   N if it is broken, nonsense, a copy of the original, or artificially garbled.
3. **Q3_optimized_same_intent**: does the optimized prompt keep the same task and intent?
   N if it adds facts, includes the answer, or adds requirements the user clearly did not want.
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
| which one is string or percussion: tombak, cizhonghlu | Classify each listed instrument as "string" or "percussion". Output a JSON object with the instrument names as keys and the label as values. | Y Y Y Y Y | same task, realistic, clear format |
| who gets a dowry? (category: summarization) | ... | ... Q5 = N | this is a plain question (closed_qa), not a summary |
| summarize it | Summarize the passage about the Eiffel Tower in 3 bullet points. | Q3 = N | the optimized prompt invents a topic the user never gave |

## Workflow

1. Open your `.xlsx` in Excel, LibreOffice or Google Sheets (File > Import keeps the drop-downs).
2. Rate in any order; save often. Blank = not done yet.
3. Send the file back (or put it in the shared Drive folder `validation/`) under the same file name.
4. The team runs `python -m app.validation report` to see progress and agreement, and `merge` at the end.

Target: Fleiss' Kappa above 0.6 ("substantial" agreement) on the overlap set. If it is lower, meet, discuss the
disagreements, clarify this guide, and re-rate the overlap set.
