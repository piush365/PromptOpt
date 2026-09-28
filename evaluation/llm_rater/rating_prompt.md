# LLM rater (Claude): rating prompt

Rater label: **LLM rater (Claude)**. Model: `claude-opus-5-5`, rating inside a Claude Code session (no API call;
the rows were read from `inputs.jsonl` and rated in one pass, in file order).

This rater is NOT a team rater. Its answers are never counted in Fleiss' Kappa and never used to accept or reject a
row. They are compared with the team's majority vote only, and rows where it says N but the team accepted go on a
"for human re-check" list.

Inputs: the 90 overlap records (`role == overlap` in `assignment.csv`), text columns only (`source_id, category,
split, original_instruction, context, degraded_prompt, optimized_prompt`), taken from the v1.2 dataset CSV and
checked to be identical to the text in the team's sheets. No human or faculty answers, notes or reports were read
for this pass.

---

You are a strict reviewer of a prompt-rewriting dataset. Each record has an ORIGINAL instruction (with an optional
CONTEXT passage) from Dolly-15k or CodeAlpaca-20k, which is the ground truth for the task; a DEGRADED prompt (a
vaguer version a user might type); an OPTIMIZED prompt (the clear rewrite); and a CATEGORY label, one of
closed_qa, information_extraction, classification, summarization, coding.

Follow `docs/validation_guide.md` and answer each question Y or N. Apply every question literally and strictly:

1. **Q1_degraded_same_task**: does the degraded prompt ask for the same task as the original instruction?
   N if it changes the task even slightly: a different question, a dropped or changed object of the task, a changed
   category, or a narrower/broader scope. (The degraded prompt may omit the context passage and output details;
   that is the point of degradation. It may use "this"/"that" to refer to the passage.)
2. **Q2_degraded_realistic**: is it a realistic vaguer version a real user might type?
   N if it is broken, nonsense, a copy of the original, or artificially garbled.
3. **Q3_optimized_same_intent**: does the optimized prompt keep the same task and intent?
   N if it adds any requirement, fact or constraint the original did not imply (a format or length limit counts
   only if it changes what an acceptable answer is, e.g. forces a specific number of items, a specific library,
   or content the original did not ask for), includes the answer, or drops any item or data from the original
   instruction or context (items to classify, code, the subject, the passage).
4. **Q4_optimized_better**: is the optimized prompt clearer and better specified than the degraded one (explicit
   output format, sensible constraints, no filler)? N if it is not an improvement.
5. **Q5_category_correct**: is the category label right? N if the label is wrong OR debatable (e.g. a plain
   question labelled summarization or information_extraction, an extraction labelled closed_qa); put the better
   category in the note.

Two rules fixed during the pass (after the first 60 rows, then applied to all 90 so the rows are rated the same way;
no human answers had been read at that point):
- Q2 = N when the degraded prompt is a near-verbatim copy of the original: differs only in case, punctuation, a
  contraction, a filler word, or a single word.
- Q5 = N when the record is labelled information_extraction or summarization but the instruction is a plain
  question (not an "extract ..." or "summarize ..." instruction): closed_qa is at least as fitting, so the label is
  debatable.

Known contamination: before this pass the rater had seen the faculty's answers for dolly-4205 (N on Q1, Q3, Q5)
and aggregate counts from the validation report, but no team member's answer for any record. dolly-4205 is marked
in its note.

For every N write a one-line reason in `notes` (prefix with the question, e.g. "Q3: adds a 3-item limit").
A record is accepted only if all five answers are Y.

Output one CSV row per record: `source_id, Q1..Q5 (Y/N), notes`.
