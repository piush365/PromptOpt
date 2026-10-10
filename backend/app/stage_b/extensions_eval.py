"""Measure the Stage B extensions (B16) on a split: what changes when the app runs them after the frozen rules.

    python -m app.stage_b.extensions_eval --split val --out ../evaluation/stage_b/extensions_val.md

For every prompt, Stage A + Stage B run twice (frozen rules; frozen rules + extensions), with Stage A's category
("auto", as in the evaluation) and, separately, with the dataset's category as if the user had picked it (how the
app is used when Stage A is unsure). Reported: how often B16 fires, how many prompts gain a label set, how many get
their items moved into the input block, the change in Stage C routing, and agreement with the dataset's optimized
prompt: a stated label "agrees" if it appears (case-insensitive) in that LLM-written target. Every changed prompt is
listed before/after for reading. Develop on val; the test split stays untouched.
"""
import argparse
from pathlib import Path

from app.dataset_io import DEFAULT_CSV, load_rows
from app.stage_a.detector import FeatureDetector
from app.stage_b.optimizer import optimize

LABEL_REQ = "Use only these labels: "


def labels_of(out) -> list[str]:
    import re
    req = next((r for r in out.ir.requirements if r.startswith(LABEL_REQ)), "")
    return re.findall(r'"([^"]+)"', req)


def run(rows, feats, use_label: bool) -> tuple[list[str], list[dict]]:
    changed, stats = [], {"n": 0, "fired": 0, "labels_added": 0, "labels_changed": 0, "items_moved": 0,
                          "routed_before": 0, "routed_after": 0, "label_total": 0, "label_agree": 0}
    for r, f in zip(rows, feats):
        cat = r["category"] if use_label else "auto"
        sep = bool(r["context"].strip())
        a = optimize(r["degraded_prompt"], f, category=cat, separate_text=sep)
        b = optimize(r["degraded_prompt"], f, category=cat, separate_text=sep, extensions=True)
        stats["n"] += 1
        stats["routed_before"] += a.needs_stage_c
        stats["routed_after"] += b.needs_stage_c
        if "B16_LABELS_WIDER" not in b.rules_applied:
            continue
        stats["fired"] += 1
        la, lb = labels_of(a), labels_of(b)
        stats["labels_added"] += bool(lb) and not la
        stats["labels_changed"] += bool(la) and la != lb
        stats["items_moved"] += b.ir.context is not None and a.ir.context is None
        target = r["optimized_prompt"].lower()
        stats["label_total"] += len(lb)
        stats["label_agree"] += sum(x.lower() in target for x in lb)
        changed.append(f"**{r['source_id']}** ({r['category']}, category {cat})\n\n```\n{a.optimized_text}\n```\n->\n"
                       f"```\n{b.optimized_text}\n```\nDataset target: {r['optimized_prompt'][:300]}\n")
    return changed, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val", choices=["train", "val"])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    rows = load_rows(DEFAULT_CSV, split=args.split)
    feats = FeatureDetector().detect_many([r["degraded_prompt"] for r in rows], [r["context"] or None for r in rows])
    lines = [f"# Stage B extensions (B16) on the `{args.split}` split\n",
             "Frozen rules vs frozen rules + extensions, same Stage A features. `auto` = Stage A's category (the "
             "evaluation setting); `dataset category` = the dataset's label as if the user had picked it. A stated label "
             "agrees when it appears in the dataset's LLM-written optimized prompt (a rough check: the target may use "
             "a synonym).\n",
             "| category choice | prompts | B16 fired | label set added | label set changed | items moved to input | "
             "routed to Stage C: before -> after | labels agreeing with the target |", "|---|---|---|---|---|---|---|---|"]
    details = []
    for use_label in (False, True):
        changed, s = run(rows, feats, use_label)
        name = "dataset category" if use_label else "auto"
        agree = f"{s['label_agree']}/{s['label_total']}" if s["label_total"] else "-"
        lines.append(f"| {name} | {s['n']} | {s['fired']} | {s['labels_added']} | {s['labels_changed']} | "
                     f"{s['items_moved']} | {s['routed_before']} -> {s['routed_after']} | {agree} |")
        details += [f"\n## Changed prompts ({name})\n", *changed] if changed else [f"\n## Changed prompts ({name})\n", "None."]
    text = "\n".join(lines + details) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
