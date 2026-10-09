"""Evaluate Stage B on a dataset split and print a markdown report.

    python -m app.stage_b.evaluate --split val     # while tuning; never tune on test
    python -m app.stage_b.evaluate --out ../evaluation/stage_b/stage_b_test.md

Inputs are the *degraded* prompts run through the real Stage A. This measures what Stage B does on its own (which
rules fire, what reaches Stage C, whether format and constraints end up stated, how many words it adds), not whether
the LLM answers get better; that is the job of the evaluation harness with real LLMs.
"""
import argparse
from collections import Counter
from pathlib import Path

from app.dataset_io import DEFAULT_CSV, load_rows
from app.stage_a import rules as detect
from app.stage_a.detector import FeatureDetector
from app.stage_b.optimizer import RULE_CODES, optimize
from app.stage_b.rules import CATEGORY_MIN_CONFIDENCE, TEXT_GROUP

CATS = ["closed_qa", "information_extraction", "classification", "summarization", "coding"]


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _words(text: str) -> int:
    return len(text.split())


def report(rows: list[dict[str, str]], feats: list, outs: list, split: str) -> str:
    n = len(rows)
    lines = [f"# Stage B evaluation: `{split}` split\n",
             f"{n} degraded prompts through Stage A + Stage B. Category-specific rules need Stage A confidence "
             f">= {CATEGORY_MIN_CONFIDENCE}; B08 applies the text-group rules below that.\n"]

    fired = Counter(code for o in outs for code in o.rules_applied)
    lines += ["## Rules applied\n", _table(["rule", "prompts", "share"],
                                           [[c, fired[c], _pct(fired[c] / n)] for c in RULE_CODES]), ""]

    to_c = [o for o in outs if o.needs_stage_c]
    reasons = Counter(u.split(":")[0] for o in to_c for u in o.stage_c_reasons)
    other = Counter(u.split(":")[0] for o in outs for u in o.unresolved if u not in o.stage_c_reasons)
    lines += ["## Routed to Stage C\n", f"**{len(to_c)}** of {n} ({_pct(len(to_c) / n)}). Reasons:\n",
              _table(["reason", "prompts"], [[r, c] for r, c in reasons.most_common()]), "",
              "Recorded but not routed: " + (", ".join(f"{r} {c}" for r, c in other.most_common()) or "none"), ""]

    specific = {"B03_ADD_OUTPUT_FORMAT", "B04_ADD_LENGTH", "B05_ADD_LANGUAGE", "B06_ADD_LABELS"}
    cat_touched = [(r, f) for r, f, o in zip(rows, feats, outs) if set(o.rules_applied) & specific]
    grp_touched = [r for r, o in zip(rows, outs) if "B08_GROUP_FALLBACK" in o.rules_applied]
    wrong_cat = sum(r["category"] != f.task_type for r, f in cat_touched)
    wrong_grp = sum(r["category"] not in TEXT_GROUP for r in grp_touched)
    wrong = wrong_cat + wrong_grp
    lines += ["## Additions for the wrong category\n",
              f"Category-specific additions (B03-B06): {len(cat_touched)} prompts, {wrong_cat} where Stage A's category "
              f"disagrees with the dataset label. Group additions (B08): {len(grp_touched)} prompts, {wrong_grp} whose "
              f"label is outside {', '.join(TEXT_GROUP)}.\n",
              f"**Wrong-category additions: {wrong} of {n} prompts ({_pct(wrong / n)})**; some are Dolly label noise, "
              f"not Stage A errors.\n"]

    rows_out = []
    for c in CATS + ["all"]:
        idx = [i for i, r in enumerate(rows) if c == "all" or r["category"] == c]
        if not idx:
            continue
        k = len(idx)
        fmt = [sum(bool(detect.detect_format_spec(t)) for t in ts) / k for ts in (
            [rows[i]["degraded_prompt"] for i in idx], [outs[i].optimized_text for i in idx],
            [rows[i]["optimized_prompt"] for i in idx])]
        words = [sum(_words(t) for t in ts) / k for ts in (
            [rows[i]["degraded_prompt"] for i in idx], [outs[i].optimized_text for i in idx],
            [rows[i]["optimized_prompt"] for i in idx])]
        stage_c = sum(outs[i].needs_stage_c for i in idx) / k
        rows_out.append([c, k, *(_pct(x) for x in fmt), *(f"{x:.1f}" for x in words), _pct(stage_c)])
    lines += ["## Output format stated and prompt length\n",
              "Format = A02 finds an explicit output format. Words = mean word count. "
              "`dataset` = the dataset's optimized prompt (written by an LLM), for reference.\n",
              _table(["category", "n", "format: degraded", "format: Stage B", "format: dataset",
                      "words: degraded", "words: Stage B", "words: dataset", "to Stage C"], rows_out), ""]

    still = Counter()
    for o, f in zip(outs, feats):
        present = detect.detect_constraints(o.optimized_text)
        for c in detect.RELEVANT_CONSTRAINTS.get(o.ir.category, ()):
            if c in ("length", "language") and c not in present and not o.needs_stage_c and not o.ir.category_group:
                still[c] += 1
    lines += ["## Missing constraints left after Stage B (prompts not routed to Stage C)\n",
              ", ".join(f"{c} {k}" for c, k in still.items()) or "none", ""]

    lines += ["## Examples\n"]
    for c in CATS:
        for r, o in [(r, o) for r, o in zip(rows, outs) if r["category"] == c and o.steps and not o.needs_stage_c][:2]:
            lines += [f"**{c}** ({', '.join(o.rules_applied)})\n", "```", r["degraded_prompt"], "->",
                      o.optimized_text, "```", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--split", default="test", choices=["train", "val", "test", "benchmark"])
    ap.add_argument("--out", type=Path, help="also write the report to this file")
    args = ap.parse_args()

    rows = load_rows(args.dataset, split=args.split)
    feats = FeatureDetector().detect_many([r["degraded_prompt"] for r in rows], [r["context"] or None for r in rows])
    outs = [optimize(r["degraded_prompt"], f) for r, f in zip(rows, feats)]
    text = report(rows, feats, outs, args.split)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
