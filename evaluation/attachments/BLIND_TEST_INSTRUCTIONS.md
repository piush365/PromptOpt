# Blind attachment test: instructions for the team

> **Status: future work.** Not collected for v1.0; results are on developer-written prompts only.

Please fill in `blind_test.csv` (15 rows) **without looking at the PromptOpt code, the rules or
`attachment_prompts.json`**. The point is to test the system on prompts its authors did not write.

For each row:

| column | what to write |
|---|---|
| `id` | leave as is (`blind-01` ... `blind-15`) |
| `prompt` | a request a real user might type when attaching a file. Mix short and vague ("what's in this?") with specific ones; typos and casual wording are fine |
| `attachment_type` | exactly one of: `image`, `pdf`, `pptx`, `docx`, `spreadsheet`, `code`. Please use each type 2-3 times |
| `attachment_name` | optional file name, e.g. `budget.xlsx` (leave empty if none) |
| `category` | `auto`, or the category a user would pick: `closed_qa`, `information_extraction`, `classification`, `summarization`, `coding`. Use `auto` for at least half of the rows |
| `expected_behaviour` | in your own words, what a good optimized prompt should say or ask the model to do with the file (e.g. "should tell the model to use only the attached sheet and say which column it used"). Write this **before** running anything |
| `author` | your initials |

Do not include personal data (real names, emails, phone numbers). When done, send the file back; results are
reported in `evaluation/attachment_blind_test.md`, separately from the 30 hand-made prompts.
