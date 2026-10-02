# Phase 2 freeze check: Stage B unchanged without an attachment

Phase 2 added attachment types `spreadsheet` and `code` with rules B14/B15 (2026-10-02), after `frozen-for-test`.
They may fire only when that attachment type is given. Checked two ways on the test split (482 prompts, no attachment),
offline, with the same category index:

1. **Report:** `python -m app.stage_b.evaluate --split test` regenerated `evaluation/stage_b_test.md`. The only
   difference from the frozen report is two new rows in the rules table, each fired on 0 prompts:
   ```
   > | B14_ATTACHMENT_SPREADSHEET | 0 | 0.0% |
   > | B15_ATTACHMENT_CODE | 0 | 0.0% |
   ```
2. **Per prompt:** the script below was run on a checkout of `frozen-for-test` and on the Phase 2 code. Both dumps
   (Stage A features, IR, optimized text, steps, Stage C routing, confidence for every prompt) are byte-identical:
   sha256 `35f7d4dcc929cbd8eee98474f5f941e8a5ef320dd117bdcfe774f3189713cb5e` for both.

Also unit-tested: `test_new_attachment_rules_never_fire_without_an_attachment` (backend/tests/test_stage_b.py).

```python
import hashlib, json, sys
from app.dataset_io import load_rows
from app.stage_a.detector import FeatureDetector
from app.stage_b.optimizer import optimize
rows = load_rows(sys.argv[2], split="test")
feats = FeatureDetector().detect_many([r["degraded_prompt"] for r in rows], [r["context"] or None for r in rows])
out = {}
for r, f in zip(rows, feats):
    o = optimize(r["degraded_prompt"], f)
    out[r["id"]] = {"text": o.optimized_text, "steps": o.steps, "ir": o.ir.model_dump(mode="json"),
                    "needs_c": o.needs_stage_c, "conf": o.confidence, "features": f.model_dump()}
json.dump(out, open(sys.argv[1], "w"), sort_keys=True)
print(len(out), hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest())
```
Run as `PYTHONPATH=. CATEGORY_INDEX_PATH=<backend/artifacts/category_index.npz> python dump_b.py out.json
<data/promptopt_dataset_v1_2_final/promptopt_dataset_v1_2_final.csv>` inside `backend/` of each checkout.

## Re-check after the gated B05 fix (2026-10-02)

B05 now gives a coding prompt with a data attachment (spreadsheet, PDF, image, pptx, docx, other) `Use Python.`
instead of `Keep the language of the given code.`; without an attachment it is unchanged. The check is now a command,
`python -m app.freeze_check` (same dump as above, run from a temporary worktree of the tag):

```
frozen-for-test: 35f7d4dcc929cbd8eee98474f5f941e8a5ef320dd117bdcfe774f3189713cb5e
current:          35f7d4dcc929cbd8eee98474f5f941e8a5ef320dd117bdcfe774f3189713cb5e
482 test prompts: BYTE-IDENTICAL
```
The regenerated `stage_b_test.md` still differs only by the two B14/B15 rows (0 prompts each). Attachment set: 30/30.
