# Team input

Everything here needs a person to read, review or fill something in. The code only reads these files; results go
to `evaluation/`.

| folder / file | who | status | what to do | how it comes back |
|---|---|---|---|---|
| `correctness_review/cases_review.xlsx` (blank) · `cases_review_filled.xlsx` (filled) | the 3 team members, one sheet each | **done** (2026-10-10: 50 of 50 gold answers confirmed, 0 flagged) | For each case, tick "gold correct (Y/N)": is the gold answer the one correct answer to the vague prompt, given the material? Comment on every N. | `python -m app.correctness.review --import <filled.xlsx>` (in `backend/`) -> `evaluation/correctness_suite/human_review.md`; `RESULTS.md` then shows the result instead of "human review pending". |
| `attachment_blind_set/` (`blind_test.csv`, 15 rows, `INSTRUCTIONS.md`) | people outside the team | future work | Write prompts with an attachment type without looking at the code or rules. | `python -m app.attachment_eval --blind ../team_input/attachment_blind_set/blind_test.csv --out ../evaluation/attachments/attachment_blind_test.md` |
| `image_blind_set/` (`blind_test.csv`, 10 rows, `INSTRUCTIONS.md`) | people outside the team | future work | Write image prompts without looking at the code or rules. | `python -m app.image.evaluate --blind ../team_input/image_blind_set/blind_test.csv --out ../evaluation/image/image_blind_test.md` |
| `validation_guide.md` | dataset raters | done (reference) | The rating rules used for the dataset validation (3 x 170 rows + faculty 20). | Results: `evaluation/dataset/validation_report.md`, `evaluation/REVIEW_SUMMARY.md` |
