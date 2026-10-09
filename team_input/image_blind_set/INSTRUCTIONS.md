# Blind image-prompt test: instructions for the team

> **Status: future work.** Not collected for v1.0; results are on developer-written prompts only.

Fill in `blind_test.csv` (10 rows) **without looking at the PromptOpt code, the image rules or
`image_prompts.json`**, so the image mode is tested on prompts its authors did not write.

| column | what to write |
|---|---|
| `id` | leave as is |
| `prompt` | a vague image request a real user might type ("a cat", "make me a poster for our fest", "logo for my cafe pls"). Mix very short ones with ones that already give a style, a ratio or something to leave out ("no text") |
| `target_model` | `dalle`, `nano_banana` or `stable_diffusion` |
| `expected_behaviour` | in your own words, written **before** running anything: what a good optimized prompt must keep and what it could add (e.g. "must keep 'Sunrise' as the bakery name; should not add a style I did not ask for") |
| `author` | your initials |

No personal data. Results are reported in `evaluation/image/image_blind_test.md`, separately from the 40 hand-written
prompts (`python -m app.image.evaluate --blind ../team_input/image_blind_set/blind_test.csv`).
