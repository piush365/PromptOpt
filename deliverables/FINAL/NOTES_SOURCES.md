# Final report and deck: sources and how to rebuild

Not part of the report text. Built after the LA-2 review feedback (one example through every stage, simpler deck,
LA-1 + LA-2 merged, longer report organised by SDLC, no run dates, research paper only in the end matter).

| Numbers | Source |
|---|---|
| Review example: Stage A scores (k-NN 0.69 classification, head 0.858 summarization, final 0.52), Stage B steps (B07, B01), Stage C answer (`Provide only the label.`, category classification, status uncertain), GPT rendering 50 tokens | the real pipeline (`app.pipeline.process_prompt` with the Stage C adapter) and the app's Optimize screen |
| Review example Compare: 104/166/270 vs 121/41/162 tokens, 353 vs 97 ms, answers "Mixed..." vs "good" | Compare on `groq/openai/gpt-oss-120b` (app Compare screen, same cached run) |
| Tokens per category (input, output, total), -39.2%, CI, Wilcoxon | `evaluation/tokens/token_test.md` |
| Stage A/B/C, benchmark, ablation | `evaluation/FINAL_RESULTS.md`, `docs/documentation/04-06, 08` |
| Dataset numbers, formulas, kappa / AC1 worked example | `docs/documentation/03_dataset.md` |
| Correctness suite per case and per category tokens | `evaluation/correctness_suite/RESULTS.md` (per-category means computed from its case table) |
| Tests per module (798) | `python -m pytest --collect-only -q` in `backend/` |
| Unit test cases TC01-TC40 | real tests in `backend/tests/` and `frontend/e2e/app.spec.ts` |
| Survey, gap table | LA-1 deck |

All output-token numbers are from OpenAI's GPT model gpt-oss-120b (Groq / Cerebras free tiers); Claude and Gemini were
not run.

## Rebuild

Python with python-pptx, python-docx, Pillow, matplotlib; LibreOffice (`soffice`) for the PDFs.

```
cd deliverables/FINAL/src
python diagrams.py ../figures          # block diagrams (diag_* for the report, deck_* for the deck)
python charts.py ../figures            # charts
python build_report.py ../MP1_Report_PromptOpt_Final.docx      # report on the college template, two passes for the TOC
SKILL_SCRIPTS=<pptx skill>/scripts python build_deck.py "<LA-1 Canva export>.pptx" ../PromptOpt_Final.pptx
```

Screenshots of the review example: run a throw-away instance of the app (own SQLite file, `python -m app.init_db` first)
on port 8765 and `node frontend/scripts/story_shots.mjs <outdir>`; copy `story_*.png` into `figures/`.
