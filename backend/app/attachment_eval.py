"""Attachment rules (B09-B15) on a hand-made test set: 30 prompts, 5 per attachment type.

    python -m app.attachment_eval --out ../evaluation/attachment_test.md

The prompts (`evaluation/attachments/attachment_prompts.json`) were written by hand for this check and are not from
the dataset. Each goes through the real Stage A and Stage B with its attachment type (and the category given in the
file: "auto" or a user choice), then is rendered for all three targets. A rule fires correctly when:
* its own code fired, and no other attachment rule did;
* all of its requirement sentences are in the IR and in all three renderings, and so is the attachment note;
* no ambiguous reference is left unresolved (the attachment is what "this" / "the file" refers to).
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from app.config import BACKEND_DIR
from app.rendering import TARGETS, attachment_note, render_all
from app.stage_a.detector import FeatureDetector
from app.stage_b.ir import Attachment
from app.stage_b.optimizer import optimize
from app.stage_b.rules import ATTACHMENT_REQUIREMENTS, RULES

PROMPTS = BACKEND_DIR.parent / "evaluation" / "attachments" / "attachment_prompts.json"
RULE_FOR = {"image": "B09_ATTACHMENT_IMAGE", "pdf": "B10_ATTACHMENT_PDF", "pptx": "B11_ATTACHMENT_PPTX",
            "docx": "B12_ATTACHMENT_DOCX", "other": "B13_ATTACHMENT_OTHER", "spreadsheet": "B14_ATTACHMENT_SPREADSHEET",
            "code": "B15_ATTACHMENT_CODE"}
ATTACHMENT_CODES = set(RULE_FOR.values())
assert ATTACHMENT_CODES <= {code for code, _ in RULES}


def check(item: dict, f) -> dict:
    att = Attachment(type=item["type"], name=item["name"])
    out = optimize(item["prompt"], f, category=item["category"], attachment=att)
    rendered = render_all(out.ir)
    name = f" ({item['name']})" if item["name"] else ""
    reqs = [r.format(name=name) for r in ATTACHMENT_REQUIREMENTS[item["type"]]]
    note = attachment_note(out.ir)
    fired = set(out.rules_applied) & ATTACHMENT_CODES
    res = {
        "fired": RULE_FOR[item["type"]] in fired,
        "exclusive": fired <= {RULE_FOR[item["type"]]},
        "requirements": all(r in out.ir.requirements for r in reqs)
                        and all(r in rendered[t] for r in reqs for t in TARGETS),
        "note": note is not None and all(note in rendered[t] for t in TARGETS),
        "ref_flagged": bool(f.ambiguous_refs),
        "ref_resolved": not any(u.startswith("ambiguous reference") for u in out.unresolved),
    }
    res["correct"] = all(res[k] for k in ("fired", "exclusive", "requirements", "note", "ref_resolved"))
    res.update(rules=out.rules_applied, category=out.ir.category, stage_a=f.task_type, to_stage_c=out.needs_stage_c,
               reasons=out.stage_c_reasons, rendered=rendered)
    return res


def report(items: list[dict], results: list[dict]) -> str:
    lines = ["# Attachment rules on the hand-made test set\n",
             f"{len(items)} hand-written prompts (`evaluation/attachments/attachment_prompts.json`), 5 per attachment "
             "type, through the real Stage A + Stage B and all three renderers (`python -m app.attachment_eval`). "
             "Correct = the type's rule fired, no other attachment rule fired, its requirements and the attachment "
             "note are in all three renderings, and no ambiguous reference is left.\n",
             "| type | rule | fired correctly | own rule fired | only its rule | requirements in all 3 renderings | "
             "ambiguous refs found -> resolved |", "|---|---|---|---|---|---|---|"]
    for kind in ("image", "pdf", "pptx", "docx", "spreadsheet", "code"):
        rs = [r for i, r in zip(items, results) if i["type"] == kind]
        c = Counter(k for r in rs for k, v in r.items() if v is True)
        flagged = sum(r["ref_flagged"] for r in rs)
        resolved = sum(r["ref_flagged"] and r["ref_resolved"] for r in rs)
        lines.append(f"| {kind} | {RULE_FOR[kind]} | **{c['correct']}/{len(rs)}** | {c['fired']}/{len(rs)} | "
                     f"{c['exclusive']}/{len(rs)} | {c['requirements']}/{len(rs)} | {flagged} -> {resolved} |")
    total = sum(r["correct"] for r in results)
    lines += [f"\n**All: {total}/{len(results)} correct.** Prompts still sent to Stage C after the attachment rule: "
              f"{sum(r['to_stage_c'] for r in results)} (only for the task category; the attachment resolves "
              "ambiguous references).\n", "## Per prompt\n",
              "| id | prompt | category (Stage A) | rules applied | correct | Stage C |", "|---|---|---|---|---|---|"]
    for i, r in zip(items, results):
        cat = r["category"] + ("" if r["category"] == r["stage_a"] else f" ({r['stage_a']})")
        lines.append(f"| {i['id']} | {i['prompt']} | {cat} | {', '.join(x.split('_')[0] for x in r['rules'])} | "
                     f"{'yes' if r['correct'] else '**no**'} | {', '.join(x.split(':')[0] for x in r['reasons']) or '-'} |")
    ex = results[[i["id"] for i in items].index("pdf-2")]
    lines += ["\n## Example: `summarize this paper` + paper.pdf\n"]
    for t in TARGETS:
        lines += [f"**{t}**\n", "```", ex["rendered"][t], "```", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", type=Path, default=PROMPTS)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    items = json.loads(args.prompts.read_text(encoding="utf-8"))
    feats = FeatureDetector().detect_many([i["prompt"] for i in items])
    results = [check(i, f) for i, f in zip(items, feats)]
    text = report(items, results)
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
