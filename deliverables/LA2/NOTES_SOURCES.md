# Working notes: where every number comes from

Not part of the report text. All numbers in the report, deck and demo plan were copied from these files or runs.

| Numbers | Source |
|---|---|
| Tokens -39.2% (CI 35.9-42.5%), per-category token table, 87/482 cost more | `evaluation/FINAL_RESULTS.md` section 9a (`evaluation/tokens/token_test.md`) |
| Stage A 74.7%, per-category P/R/F1 | `evaluation/FINAL_RESULTS.md` sections 1, 3 |
| Stage B format 3.1% -> 95.0%, 6.4% routed, per-rule accuracy B01-B08 | `evaluation/FINAL_RESULTS.md` sections 4, 4.1 |
| Benchmark 8.2 -> 9.0, 67% -> 85%, tokens 894 -> 386 | `evaluation/FINAL_RESULTS.md` section 4 |
| Stage C 5.0% vs 98.2%, ablation, latency 0.74 s, training (val loss 0.7047, 51 min) | `evaluation/FINAL_RESULTS.md` section 5 |
| Kappa / AC1, 295 of 330 accepted, faculty 19/20, 9 LLM-filtered rows | `evaluation/FINAL_RESULTS.md` section 2a |
| Attachments 30/30, coding pass@1 20.7% -> 34.5%, image CLIP 33.08 / 30.78 / 32.77 | `evaluation/FINAL_RESULTS.md` sections 6-8 |
| Compare -67.7% / +17.2% | `evaluation/FINAL_RESULTS.md` section 9; live re-run in the app on 14 Oct 2026 (768 -> 248) |
| Correctness 37/50 vs 42/50, -29.6%, per category, McNemar 0.267, Cerebras 43 vs 41, failures cls-09, sum-06, sum-10, cod-10 | `evaluation/correctness_suite/RESULTS.md` |
| Dataset sizes, v1.1 repair counts | `docs/DATASET_CARD.md`, `docs/PROJECT_REPORT.md` |
| Tables / repository / retention / endpoints | `docs/documentation/13_backend_api_database.md`, `backend/app/db/` |
| 798 tests (per-file counts) | `python -m pytest -q` and `--collect-only` in `backend/`, 14 Oct 2026: 798 passed in 24.6 s |
| 13/13 UI tests | `npx playwright test` in `frontend/`, 14 Oct 2026 |
| Freeze check byte-identical (35f7d4dc...) | `python -m app.freeze_check`, 14 Oct 2026 |
| Git: 92 commits, branches, tags, authors, per-month counts | `git rev-list --all --count`, `git branch -a`, `git tag`, `git shortlog -sne --all` |
| GitHub: release v1.0, no Issues/PRs, contributors | `gh release list`, `gh issue list`, `gh pr list`, repo page screenshots (14 Oct 2026) |
| Customer survey percentages, guide name, PRNs, gap table | LA-1 deck `PromptOpt_PPT.pdf` |

Regenerate: `src/charts.py` (charts/diagrams), `src/build_report.py` (report on top of the college template, two-pass TOC),
`src/fill_la2.py` (deck: built on the LA-1 Canva deck exported as PPTX, slides duplicated with the pptx skill's `add_slide.py`, then filled with python-pptx; same backgrounds, logo and embedded fonts as LA-1). Screenshots: `frontend/scripts/screenshots.mjs` against the running app.
