"""Evaluate Stage A on a dataset split and print a markdown report.

    python -m app.stage_a.evaluate                 # test split (final numbers)
    python -m app.stage_a.evaluate --split val     # use val while tuning; never tune on test
    python -m app.stage_a.evaluate --out ../evaluation/stage_a_test.md

Inputs are the *degraded* prompts, because those are what real users type. The dataset's own labels are used as
references: `category`, and `has_format_spec` / `optimized_has_format_spec` (computed by the dataset notebook's
regex, so agreement there measures consistency between two regex detectors, not ground truth).
"""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

from app.config import TASK_CATEGORIES
from app.dataset_io import DEFAULT_CSV, load_rows
from app.stage_a.build_index import DEFAULT_DOLLY, dolly_other
from app.stage_a.detector import FeatureDetector


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def category_report(gold: list[str], pred: list[str]) -> str:
    labels = [c for c in TASK_CATEGORIES if c in set(gold) | set(pred)]
    rows = []
    for c in labels:
        tp = sum(g == p == c for g, p in zip(gold, pred))
        n_pred, n_gold = pred.count(c), gold.count(c)
        prec = tp / n_pred if n_pred else 0.0
        rec = tp / n_gold if n_gold else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        rows.append([c, n_gold, _pct(prec), _pct(rec), f"{f1:.2f}"])
    acc = sum(g == p for g, p in zip(gold, pred)) / len(gold)
    conf = Counter(zip(gold, pred))
    cm = [[g] + [conf[(g, p)] for p in labels] for g in labels if g in gold]
    return (f"Accuracy: **{_pct(acc)}** on {len(gold)} prompts\n\n"
            + _table(["category", "n", "precision", "recall", "F1"], rows)
            + "\n\nConfusion matrix (rows = true, columns = predicted)\n\n"
            + _table(["true \\ pred"] + labels, cm))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--split", default="test", choices=["train", "val", "test", "benchmark"])
    ap.add_argument("--out", type=Path, help="also write the report to this file")
    ap.add_argument("--dump", type=Path, help="write per-prompt features as JSONL (for error analysis)")
    args = ap.parse_args()

    rows = load_rows(args.dataset, split=args.split)
    det = FeatureDetector()
    start = time.perf_counter()
    feats = det.detect_many([r["degraded_prompt"] for r in rows], [r["context"] for r in rows])
    ms = 1000 * (time.perf_counter() - start) / len(rows)
    opt = det.detect_many([r["optimized_prompt"] for r in rows], [r["context"] for r in rows])
    orig = det.detect_many([r["original_instruction"] for r in rows], [r["context"] for r in rows])

    out = [f"# Stage A evaluation: `{args.split}` split\n",
           f"Classifier: `{feats[0].classifier}`. Mean time per prompt: {ms:.1f} ms (CPU, batched).\n",
           "## A01 Task category (degraded prompts)\n",
           category_report([r["category"] for r in rows], [f.task_type for f in feats])]

    if det.classifier.__class__.__name__ == "EmbeddingClassifier" and DEFAULT_DOLLY.exists():
        held = dolly_other(DEFAULT_DOLLY, held_out=True)
        ofeats = det.detect_many(held)
        hit = sum(f.task_type == "other" for f in ofeats) / len(held)
        out.append(f"\nOut-of-scope prompts (held-out Dolly brainstorming/creative_writing, never in the index): "
                   f"**{_pct(hit)}** classified as `other` ({len(held)} prompts).")

    def agree(fs, key):
        return sum(f.has_format_spec == (r[key] == "True") for f, r in zip(fs, rows)) / len(rows)

    n = len(rows)
    out += ["\n## A02 Output format",
            _table(["prompt", "flagged as having a format", "agreement with dataset label"], [
                ["original instruction", _pct(sum(f.has_format_spec for f in orig) / n), _pct(agree(orig, "has_format_spec"))],
                ["degraded prompt", _pct(sum(f.has_format_spec for f in feats) / n), "(no label)"],
                ["optimized prompt", _pct(sum(f.has_format_spec for f in opt) / n), _pct(agree(opt, "optimized_has_format_spec"))],
            ]),
            "\nA good detector flags few degraded prompts and most optimized prompts."]

    by_cat: dict[str, list] = {}
    for f, fo, r in zip(feats, opt, rows):
        by_cat.setdefault(r["category"], []).append((f, fo))
    cons = []
    for cat, pairs in sorted(by_cat.items()):
        for c in ("length", "tone", "audience", "language"):
            d = sum(c in f.constraints_present for f, _ in pairs) / len(pairs)
            o = sum(c in fo.constraints_present for _, fo in pairs) / len(pairs)
            if d or o:
                cons.append([cat, c, _pct(d), _pct(o)])
    out += ["\n## A03 Constraints stated (degraded vs optimized)", _table(["category", "constraint", "degraded", "optimized"], cons),
            "\nMissing relevant constraints in degraded prompts: "
            + ", ".join(f"{k} {v}" for k, v in Counter(c for f in feats for c in f.missing_constraints).most_common())]

    red_d = sum(bool(f.redundant_phrases) for f in feats) / n
    red_o = sum(bool(f.redundant_phrases) for f in opt) / n
    top = Counter(p.lower() for f in feats for p in f.redundant_phrases).most_common(8)
    out += ["\n## A04 Redundancy",
            f"Prompts with filler or repetition: degraded {_pct(red_d)}, optimized {_pct(red_o)}.",
            "Most common in degraded prompts: " + ", ".join(f"'{p}' ({c})" for p, c in top)]

    no_ctx = [(f, r) for f, r in zip(feats, rows) if not r["context"].strip()]
    ctx = [(f, r) for f, r in zip(feats, rows) if r["context"].strip()]
    amb_no = sum(bool(f.ambiguous_refs) for f, _ in no_ctx) / max(len(no_ctx), 1)
    # Same prompts, but pretend the context was dropped: how many would then be flagged?
    dropped = det.detect_many([r["degraded_prompt"] for _, r in ctx])
    amb_drop = sum(bool(f.ambiguous_refs) for f in dropped) / max(len(ctx), 1)
    out += ["\n## A05 Ambiguous references",
            f"Degraded prompts whose source had no context ({len(no_ctx)}): {_pct(amb_no)} flagged "
            f"(these are mostly false alarms).",
            f"Degraded prompts whose source HAD a context, run without it ({len(ctx)}): {_pct(amb_drop)} flagged "
            f"(a reference to a missing passage is exactly what A05 should catch)."]

    report = "\n".join(out) + "\n"
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    if args.dump:
        with open(args.dump, "w", encoding="utf-8") as fh:
            for f, r in zip(feats, rows):
                fh.write(json.dumps({"id": r["id"], "category": r["category"], "prompt": r["degraded_prompt"],
                                     **f.model_dump()}) + "\n")


if __name__ == "__main__":
    main()
