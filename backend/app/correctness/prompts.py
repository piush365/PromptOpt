"""The two prompts per case: the vague prompt as the user would send it, and PromptOpt's optimized prompt.

    python -m app.correctness.prompts          # in backend/.venv-gpu (Stage C on routed prompts); writes prompts.json

Exactly the app's path (app.pipeline.process_prompt, without the database), on the frozen v1.0 pipeline:
* vague      the vague prompt with the material pasted below it after a blank line (app.evaluation.variants.with_context,
             as Compare sends the original prompt)
* optimized  Stage A on (prompt, material) -> Stage B (category auto, material given separately) -> Stage C under the
             routing contract when Stage B routes the prompt (a rejected answer keeps Stage B's result) -> rendered
             for each target (GPT / Gemini / Claude) with the material placed as the Document. gpt-oss runs get the
             GPT rendering (the family Compare uses for it), Gemini the Gemini rendering.

Leak check: the optimizer must not put the gold answer into the prompt. The optimized REQUEST (the IR rendered
without the pasted material) is searched for every gold form; a hit that is not already in the vague prompt is a
leak (closed_qa: the answer's forms; extraction: the gold items; classification: an item id together with its
gold label; summarization: the key facts' evidence; coding: any line of the reference solution or any assert).
"""
import argparse
import json
from pathlib import Path

from app.correctness.cases import SUITE_DIR, load_cases
from app.correctness.checks import find, normalize
from app.evaluation.variants import with_context
from app.rendering import TARGETS, render_all
from app.stage_b.ir import render_plain
from app.stage_b.optimizer import optimize

PROMPTS = SUITE_DIR / "prompts.json"


def leaks(case: dict, request: str) -> list[str]:
    """Gold forms in the optimized request that the vague prompt did not already contain."""
    cat, g, chk, vague = case["category"], case["gold"], case["check"], case["vague_prompt"]

    def new(aliases: list[str]) -> bool:
        return bool(find(aliases, request)) and not find(aliases, vague)

    out = []
    if cat == "closed_qa" and new(chk["aliases"]):
        out.append(f"gold answer {g!r}")
    elif cat == "information_extraction":
        out += [f"gold item {i!r}" for i in g if new(chk["aliases"][i])]
    elif cat == "classification":
        for line in request.splitlines():
            for k, lab in g.items():
                if find(chk["items"][k], line) and find(chk["labels"][lab], line):
                    out.append(f"item {k} with its label {lab!r}")
    elif cat == "summarization":
        out += [f"key fact {k['fact']!r}" for k in g["key_facts"]
                if normalize(k["evidence"]) in normalize(request) and normalize(k["evidence"]) not in normalize(vague)]
    elif cat == "coding":
        lines = [ln.strip() for ln in g["reference"].splitlines() if len(ln.strip()) > 15] + g["tests"]
        out += [f"reference/assert line {ln!r}" for ln in lines if ln in request]
    return out


def build(case: dict, detector, stage_c=None) -> dict:
    from app.stage_c.contract import apply_stage_c
    material = case["material"]
    f = detector.detect(case["vague_prompt"], material)
    out = optimize(case["vague_prompt"], f, category="auto", separate_text=True)
    ir, c = out.ir, None
    if out.needs_stage_c and stage_c is not None:
        c = apply_stage_c(case["vague_prompt"], f, out, stage_c)
        if c.accepted:
            ir = c.ir
    request = render_plain(ir)
    return {
        "vague": with_context(case["vague_prompt"], material),
        "optimized": render_all(ir, context_text=material),
        "request": request,
        "stage_a": {"category": f.task_type, "confidence": round(f.confidence, 3)},
        "category_used": ir.category, "rules": [s["rule_code"] for s in out.steps],
        "routed": out.needs_stage_c, "stage_c_reasons": list(out.stage_c_reasons),
        "stage_c": None if c is None else {"used": c.used, "accepted": c.accepted, "fields": c.fields,
                                           "errors": c.errors, "category_status": c.category_status,
                                           "category_guess": c.category_guess},
        "leaks": leaks(case, request),
    }


def load_prompts(path: Path = PROMPTS) -> dict:
    if not path.exists():
        raise SystemExit(f"{path} not found: run `python -m app.correctness.prompts` (in backend/.venv-gpu) first")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-stage-c", action="store_true", help="A+B only (routed prompts keep Stage B's result)")
    ap.add_argument("--out", type=Path, default=PROMPTS)
    args = ap.parse_args()
    from app.stage_a.detector import FeatureDetector
    from app.stage_c import runtime
    detector = FeatureDetector()
    cases = load_cases()
    stage_c, model_name = None, None
    if not args.no_stage_c:
        if not runtime.available():
            raise SystemExit("Stage C adapter or ML packages missing: run in backend/.venv-gpu, or pass --no-stage-c")
        model = runtime.StageCModel.load()
        stage_c, model_name = model.generate, model.name
    built = {c["id"]: build(c, detector, stage_c) for c in cases}
    args.out.write_text(json.dumps({"stage_c_model": model_name, "targets": list(TARGETS), "cases": built},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    routed = [k for k, v in built.items() if v["routed"]]
    leaked = {k: v["leaks"] for k, v in built.items() if v["leaks"]}
    print(f"{len(built)} cases; routed to Stage C: {len(routed)} {routed}; "
          f"accepted: {sum(1 for k in routed if (built[k]['stage_c'] or {}).get('accepted'))}; leaks: {leaked or 'none'}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
