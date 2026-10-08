"""Per-rule accuracy of Stage B (B01-B08) on a dataset split. Measurement only: no rule is changed.

    python -m app.stage_b.rule_accuracy --out ../evaluation/stage_b_rule_accuracy.md     # test split

For each rule, "expected" = the dataset's optimized prompt (the target) fixes the defect the rule is for, while the
degraded prompt has it. Defects are found with the Stage A detectors, so expected and fired use the same yardstick:

  B01 filler          degraded has filler (A04), target has none
  B02 repetition      degraded has a repeated sentence or doubled word (A04), target has none
  B03 output format   target states a format (A02), degraded does not
  B04 length          target states a length (A03), degraded does not
  B05 language        target names a programming language (A03), degraded does not
  B06 labels          target lists the allowed labels explicitly ("X" or "Y", {a, b}, "labels:"), degraded does not
  B07 structure       degraded carries its data inline on one line, target puts it in its own block
  B08 grounding       target says to answer from the provided text, degraded does not

"Fired" = the rule's entry in Stage B's change log (`OptimizationOutput.rules_applied`). B07's log entry also
covers pure tidying (capital letter, final '.'), so a second row counts B07 as fired only when it moved data into
the IR context. The targets were written by an LLM, so "expected" is the LLM's choice, not a human gold label.
"""
import argparse
import re
from pathlib import Path

from app.dataset_io import DEFAULT_CSV, load_rows
from app.stage_a import rules as detect
from app.stage_a.detector import FeatureDetector
from app.stage_b.optimizer import optimize
from app.stage_b.rules import _ALREADY_GROUNDED

_I = re.IGNORECASE
_QUOTED_LABELS = re.compile(r"[\"“'][^\"“”'\n]{1,40}[\"”']\s*(?:,\s*(?:or\s+|and\s+)?|\s+or\s+|\s+and\s+)[\"“']", _I)
_SET_LABELS = re.compile(r"\{[^{}\n]+,[^{}\n]+\}")
_NAMED_LABELS = re.compile(r"\b(?:labels?|categories|classes)\s*:", _I)
_GROUNDED = re.compile(r"\b(?:using|from|in|on) (?:the |this )?(?:provided|given|supplied|attached) "
                       r"(?:text|passage|context|paragraph|article|reference)\b", _I)
_DATA_BLOCK = re.compile(r"\n|```")


def lists_labels(text: str) -> bool:
    return bool(_QUOTED_LABELS.search(text) or _SET_LABELS.search(text) or _NAMED_LABELS.search(text))


def grounded(text: str) -> bool:
    return bool(_ALREADY_GROUNDED.search(text) or _GROUNDED.search(text))


def _repeats(text: str) -> bool:
    return bool(detect.detect_repetition(text))


def _length(text: str) -> bool:
    return "length" in detect.detect_constraints(text)


def _language(text: str) -> bool:
    return "language" in detect.detect_constraints(text)


def expected(degraded: str, target: str) -> dict[str, bool]:
    """Which of B01-B08 the target says are needed for this degraded prompt."""
    return {
        "B01": bool(detect.detect_filler(degraded)) and not detect.detect_filler(target),
        "B02": _repeats(degraded) and not _repeats(target),
        "B03": bool(detect.detect_format_spec(target)) and not detect.detect_format_spec(degraded),
        "B04": _length(target) and not _length(degraded),
        "B05": _language(target) and not _language(degraded),
        "B06": lists_labels(target) and not lists_labels(degraded),
        "B07": (detect.detect_embedded_context(degraded) and not _DATA_BLOCK.search(degraded.strip())
                and bool(_DATA_BLOCK.search(target.strip()))),
        "B08": grounded(target) and not grounded(degraded),
    }


RULE_NAMES = {"B01": "B01_REMOVE_FILLER", "B02": "B02_REMOVE_DUPLICATES", "B03": "B03_ADD_OUTPUT_FORMAT",
              "B04": "B04_ADD_LENGTH", "B05": "B05_ADD_LANGUAGE", "B06": "B06_ADD_LABELS",
              "B07": "B07_STANDARDIZE_STRUCTURE", "B08": "B08_GROUP_FALLBACK"}


def scores(pairs: list[tuple[bool, bool]]) -> dict:
    """TP/FP/FN/TN, precision, recall, F1 from (expected, fired) pairs. Undefined ratios are None."""
    tp = sum(e and f for e, f in pairs)
    fp = sum(f and not e for e, f in pairs)
    fn = sum(e and not f for e, f in pairs)
    tn = len(pairs) - tp - fp - fn
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": p, "recall": r, "f1": f1}


def _f(x: float | None) -> str:
    return "-" if x is None else f"{x:.3f}"


def report(rows: list[dict[str, str]], outs: list, split: str) -> str:
    exp = [expected(r["degraded_prompt"], r["optimized_prompt"]) for r in rows]
    table, macro = [], []
    for code, name in RULE_NAMES.items():
        s = scores([(e[code], name in o.rules_applied) for e, o in zip(exp, outs)])
        macro.append(s)
        table.append([code, name, s["tp"], s["fp"], s["fn"], _f(s["precision"]), _f(s["recall"]), _f(s["f1"])])
    moved = scores([(e["B07"], "B07_STANDARDIZE_STRUCTURE" in o.rules_applied and o.ir.context is not None)
                    for e, o in zip(exp, outs)])
    def mean(k: str, ss: list[dict] = macro) -> float | None:
        vals = [s[k] for s in ss if s[k] is not None]
        return sum(vals) / len(vals) if vals else None

    alt = [moved if code == "B07" else s for code, s in zip(RULE_NAMES, macro)]
    lines = [f"# Stage B per-rule accuracy: `{split}` split\n",
             f"{len(rows)} degraded prompts through Stage A + Stage B (frozen rules; measurement only). Expected = the "
             "dataset's optimized prompt fixes the rule's defect while the degraded prompt has it, judged with the "
             "Stage A detectors (definitions in `app/stage_b/rule_accuracy.py`); fired = the rule's change-log entry. "
             "**The targets are LLM-written**, so expected is the LLM's choice, not a human gold label: a rule that "
             "adds what the LLM left out counts as a false positive, and a target that adds what Stage B "
             "deliberately does not (e.g. a format below the 0.6 confidence gate) counts as a false negative.\n",
             "| rule | change-log code | TP | FP | FN | precision | recall | F1 |", "|---|---|---|---|---|---|---|---|",
             *("| " + " | ".join(str(c) for c in t) + " |" for t in table),
             f"| **macro (B01-B08)** | | | | | **{_f(mean('precision'))}** | **{_f(mean('recall'))}** | "
             f"**{_f(mean('f1'))}** |",
             f"| B07, data moved only (not in macro) | B07 fired and set `context` | {moved['tp']} | {moved['fp']} | "
             f"{moved['fn']} | {_f(moved['precision'])} | {_f(moved['recall'])} | {_f(moved['f1'])} |",
             f"| macro, with B07 = data moved | | | | | {_f(mean('precision', alt))} | {_f(mean('recall', alt))} | "
             f"{_f(mean('f1', alt))} |", "",
             "Macro = unweighted mean over the rules where the value is defined (B02 has no expected prompt, so its "
             "recall and F1 are undefined and left out). B01's expected uses the same filler detector the rule uses, "
             "so its perfect score shows consistency, not independent accuracy. Rules share defects (a length can "
             "come from B04 or from B08), so a defect fixed by another rule counts as a false negative here.\n"]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--split", default="test", choices=["train", "val", "test", "benchmark"])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    rows = load_rows(args.dataset, split=args.split)
    feats = FeatureDetector().detect_many([r["degraded_prompt"] for r in rows], [r["context"] or None for r in rows])
    outs = [optimize(r["degraded_prompt"], f) for r, f in zip(rows, feats)]       # as in app.stage_b.evaluate
    text = report(rows, outs, args.split)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
