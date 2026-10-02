"""Stage C evaluation on the val split (docs/STAGE_C_PLAN.md, section 4). Run in backend/.venv-gpu:

    python -m app.stage_c.evaluate --adapter artifacts/stage_c_adapter --out ../evaluation/stage_c_eval.md

(a) base model vs LoRA on every val example (routed, forced subsets, forced_all): JSON validity, exact keys, field
    accuracy vs the target.
(b) ablation A+B vs A+B+C vs C-only on the routed subset AND with forced routing of all val prompts: intent
    similarity to the original instruction, format-stated rate, fallback rate, JSON validity, field accuracy,
    latency; plus Stage C's category vs Stage A's on routed prompts.
(c) latency per prompt on GPU and CPU (batch 1, greedy).
Named cases (evaluation/stage_c/named_cases.json) are run through the full pipeline and reported by name.
Never run on test: the test split is used once, at the very end.
"""
import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from app.config import BACKEND_DIR, SENTENCE_MODEL
from app.dataset_io import DEFAULT_CSV, load_rows
from app.stage_a import rules as detect
from app.stage_a.classifier import sentence_encoder
from app.stage_a.detector import FeatureDetector
from app.stage_b.ir import Attachment, render_plain
from app.stage_b.optimizer import RULE_CODES, optimize
from app.stage_c.contract import FIELDS, apply_stage_c, c_only_input, parse_json, validate
from app.stage_c.data import OUT_DIR
from app.stage_c.parse import is_format
from app.stage_c.runtime import StageCModel

NAMED = BACKEND_DIR.parent / "evaluation" / "stage_c" / "named_cases.json"


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{100 * x:.1f}%"


def _mean(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _table(header: list[str], rows: list[list]) -> str:
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
                     + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


class Similarity:
    """Cosine similarity with the Stage A sentence encoder (the dataset's sim_* columns use the same model)."""

    def __init__(self):
        self.enc, self.cache = sentence_encoder(SENTENCE_MODEL), {}

    def __call__(self, a: str, b: str) -> float:
        missing = [t for t in (a, b) if t not in self.cache]
        if missing:
            self.cache.update(zip(missing, self.enc(missing)))
        return float(np.dot(self.cache[a], self.cache[b]))


def _text(v) -> str:
    """Any JSON value as text (models sometimes return lists of objects where strings were asked for)."""
    if v is None:
        return ""
    if isinstance(v, list):
        return " ".join(_text(x) for x in v)
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def field_scores(pred: dict | None, target: dict, sim: Similarity) -> dict:
    """Per requested field: category exact; others null/empty agreement and, when both have text, similarity."""
    out = {}
    for k, t in target.items():
        p = None if pred is None else pred.get(k)
        if k == "category":
            out["category_acc"] = float(p == t)
            continue
        out[f"{k}_presence"] = float(bool(_text(p).strip()) == bool(_text(t).strip()))
        if _text(p).strip() and _text(t).strip():
            out[f"{k}_sim"] = sim(_text(p), _text(t))
    return out


def summarize(scores: list[dict]) -> dict:
    keys = sorted({k for s in scores for k in s})
    return {k: _mean([s.get(k) for s in scores]) for k in keys}


# ---------------------------------------------------------------- (a) base vs LoRA
def generate_all(name: str, model: StageCModel, examples: list[dict], preds: dict) -> None:
    """Model output for every example, cached in `preds[name]`."""
    outs = preds.setdefault(name, {})
    for e in examples:
        key = f"{e['id']}/{e['kind']}"
        if key not in outs:
            start = time.perf_counter()
            outs[key] = {"raw": model.generate(e["messages"][:-1]), "seconds": time.perf_counter() - start}


def models_table(names: list[str], examples: list[dict], sim: Similarity, preds: dict) -> str:
    rows, kinds = [], ["routed", "forced", "forced_all", "all"]
    for name in names:
        outs = preds[name]
        for kind in kinds:
            sub = [e for e in examples if kind == "all" or e["kind"] == kind]
            parsed = [parse_json(outs[f"{e['id']}/{e['kind']}"]["raw"]) for e in sub]
            valid = _mean([float(p is not None) for p in parsed])
            keys = _mean([float(p is not None and set(p) == set(e["target"])) for p, e in zip(parsed, sub)])
            passes = _mean([float(validate(outs[f"{e['id']}/{e['kind']}"]["raw"], list(e["target"]),
                                           e["input"]["has_context"])[0] is not None) for e in sub])
            s = summarize([field_scores(p, e["target"], sim) for p, e in zip(parsed, sub)])
            rows.append([name, kind, len(sub), _pct(valid), _pct(keys), _pct(passes), _pct(s.get("category_acc")),
                         _pct(s.get("task_presence")), f"{s['task_sim']:.3f}" if s.get("task_sim") else "-",
                         _pct(s.get("output_format_presence")),
                         f"{s['output_format_sim']:.3f}" if s.get("output_format_sim") else "-",
                         _pct(s.get("constraints_presence")),
                         f"{s['constraints_sim']:.3f}" if s.get("constraints_sim") else "-"])
    return _table(["model", "examples", "n", "JSON valid", "exact keys", "passes validation", "category acc.",
                   "task present", "task sim.", "format null/non-null agree", "format sim.",
                   "constraints empty/non-empty agree", "constraints sim."], rows)


# ---------------------------------------------------------------- (b) ablation
def ablation(model: StageCModel, rows: list[dict], feats: list, targets: dict, sim: Similarity) -> tuple[str, str, dict]:
    """Returns (ablation table, category table, raw results)."""
    bare_rules = frozenset(RULE_CODES)
    res: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r, f in zip(rows, feats):
        sep = bool(r["context"].strip())
        out = optimize(r["degraded_prompt"], f, separate_text=sep)
        bare = optimize(r["degraded_prompt"], f, disabled=bare_rules, separate_text=sep)
        sets = ["forced"] + (["routed"] if out.needs_stage_c else [])
        for s in sets:
            systems = {"A+B": None,
                       "A+B+C": apply_stage_c(r["degraded_prompt"], f, out, model.generate,
                                              fields=None if s == "routed" else list(FIELDS)),
                       "C-only": apply_stage_c(r["degraded_prompt"], f, bare, model.generate, fields=list(FIELDS),
                                               inp=c_only_input(r["degraded_prompt"], f, bare.ir))}
            for name, c in systems.items():
                text = out.optimized_text if c is None else (c.optimized_text if c.accepted else
                                                             (out.optimized_text if name == "A+B+C" else
                                                              render_plain(bare.ir)))
                item = {"id": r["id"], "text": text, "intent": sim(text, r["original_instruction"]),
                        "format": bool(detect.detect_format_spec(text)) or is_format(text),
                        "category_gold": r["category"], "stage_a": f.task_type}
                if c is not None:
                    item.update(used=c.used, accepted=c.accepted, fallback=c.fallback, errors=c.errors,
                                seconds=c.seconds, raw=c.raw, json_valid=parse_json(c.raw or "") is not None)
                    kind = "routed" if s == "routed" and name == "A+B+C" else "forced_all"
                    tgt = targets.get((r["id"], kind))
                    if c.used and tgt is not None:
                        item["fields"] = field_scores(parse_json(c.raw or ""), tgt, sim)
                    if c.accepted:
                        item["category_c"] = c.ir.category if "category" in c.fields else None
                res[s][name].append(item)
        res["reference"]["dataset optimized"].append(
            {"intent": sim(r["optimized_prompt"], r["original_instruction"]),
             "format": bool(detect.detect_format_spec(r["optimized_prompt"]))})
        res["reference"]["degraded"].append(
            {"intent": sim(r["degraded_prompt"], r["original_instruction"]),
             "format": bool(detect.detect_format_spec(r["degraded_prompt"]))})

    table = []
    for s in ("routed", "forced"):
        for name in ("A+B", "A+B+C", "C-only"):
            items = res[s][name]
            if not items:
                continue
            c_items = [i for i in items if "used" in i]
            fs = summarize([i["fields"] for i in c_items if "fields" in i])
            secs = [i["seconds"] for i in c_items if i["used"]]
            table.append([s, name, len(items), f"{_mean([i['intent'] for i in items]):.3f}",
                          _pct(_mean([float(i['format']) for i in items])),
                          _pct(_mean([float(i["json_valid"]) for i in c_items])) if c_items else "-",
                          _pct(_mean([float(i["fallback"]) for i in c_items])) if c_items else "-",
                          _pct(fs.get("category_acc")) if fs else "-",
                          f"{fs['task_sim']:.3f}" if fs.get("task_sim") else "-",
                          _pct(fs.get("output_format_presence")) if fs else "-",
                          f"{statistics.median(secs):.2f}" if secs else "-"])
    for name, items in res["reference"].items():
        table.append(["reference", name, len(items), f"{_mean([i['intent'] for i in items]):.3f}",
                      _pct(_mean([float(i['format']) for i in items])), "-", "-", "-", "-", "-", "-"])
    ab = _table(["set", "system", "n", "intent sim.", "format stated", "JSON valid", "fallback", "category acc.",
                 "task sim.", "format null/non-null agree", "median s (GPU)"], table)

    routed_c = [i for i in res["routed"]["A+B+C"] if i.get("category_c")]
    routed_all = res["routed"]["A+B+C"]
    cat = _table(["", "n", "correct"], [
        ["Stage A category (routed prompts)", len(routed_all),
         _pct(_mean([float(i["stage_a"] == i["category_gold"]) for i in routed_all]))],
        ["Stage C category (accepted answers)", len(routed_c),
         _pct(_mean([float(i["category_c"] == i["category_gold"]) for i in routed_c]))],
        ["Stage C category, same prompts: Stage A", len(routed_c),
         _pct(_mean([float(i["stage_a"] == i["category_gold"]) for i in routed_c]))]])
    return ab, cat, res


# ---------------------------------------------------------------- named cases
def named_cases(model: StageCModel, det: FeatureDetector) -> str:
    rows = []
    for case in json.loads(NAMED.read_text(encoding="utf-8")):
        att = Attachment(**case["attachment"]) if case.get("attachment") else None
        f = det.detect(case["prompt"])
        out = optimize(case["prompt"], f, category=case["category"], attachment=att)
        c = apply_stage_c(case["prompt"], f, out, model.generate)
        got = c.ir.category if c.accepted and "category" in c.fields else None
        verdict = "not routed" if not c.used else ("rejected: " + "; ".join(c.errors) if not c.accepted else
                                                   ("right" if got == case["expected_category"] else "wrong"))
        rows.append([case["id"], f"`{case['prompt']}`", f"{f.task_type} ({f.confidence:.2f})", got or "-",
                     case["expected_category"], f"**{verdict}**", f"`{(c.raw or '').strip()}`"])
    return _table(["case", "prompt", "Stage A", "Stage C category", "expected", "result", "Stage C output"], rows)


# ---------------------------------------------------------------- (c) latency
def latency(model: StageCModel, examples: list[dict], n: int) -> dict:
    secs = []
    model.generate(examples[0]["messages"][:-1])                   # warm-up
    for e in examples[:n]:
        start = time.perf_counter()
        model.generate(e["messages"][:-1])
        secs.append(time.perf_counter() - start)
    secs.sort()
    return {"device": model.device, "n": len(secs), "median": statistics.median(secs),
            "p95": secs[min(len(secs) - 1, int(0.95 * len(secs)))], "max": secs[-1]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", type=Path, required=True)
    ap.add_argument("--data", type=Path, default=OUT_DIR)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--preds", type=Path, help="cache of model outputs (resumable)")
    ap.add_argument("--limit", type=int, help="first N val examples / prompts only (smoke test)")
    ap.add_argument("--cpu-n", type=int, default=20, help="prompts for the CPU latency measurement (0 = skip)")
    ap.add_argument("--device", default="auto")
    args = ap.parse_args()

    examples = [json.loads(x) for x in open(args.data / "val.jsonl", encoding="utf-8")][:args.limit]
    targets = {(e["id"], e["kind"]): e["target"] for e in examples}
    rows = load_rows(DEFAULT_CSV, split="val")[:args.limit]
    preds = json.loads(args.preds.read_text()) if args.preds and args.preds.exists() else {}
    sim = Similarity()
    det = FeatureDetector()
    feats = det.detect_many([r["degraded_prompt"] for r in rows], [r["context"] or None for r in rows])

    base = StageCModel.load(adapter=None, device=args.device)
    generate_all("zero-shot base", base, examples, preds)
    lat_base = latency(base, [e for e in examples if e["kind"] == "forced_all"], 20)
    del base
    lora = StageCModel.load(adapter=args.adapter, device=args.device)
    generate_all("LoRA", lora, examples, preds)
    t_models = models_table(["zero-shot base", "LoRA"], examples, sim, preds)
    if args.preds:
        args.preds.write_text(json.dumps(preds, indent=1))
    ab, cat, res = ablation(lora, rows, feats, targets, sim)
    named = named_cases(lora, det)
    lat = {"GPU" if lora.device == "cuda" else lora.device: latency(lora, [e for e in examples
                                                                         if e["kind"] == "forced_all"], 40)}
    del lora
    if args.cpu_n:
        cpu = StageCModel.load(adapter=args.adapter, device="cpu")
        lat["CPU"] = latency(cpu, [e for e in examples if e["kind"] == "forced_all"], args.cpu_n)

    lat_rows = [[k, v["n"], f"{v['median']:.2f}", f"{v['p95']:.2f}", f"{v['max']:.2f}"] for k, v in lat.items()]
    lat_rows.append([f"zero-shot base ({lat_base['device']})", lat_base["n"], f"{lat_base['median']:.2f}",
                     f"{lat_base['p95']:.2f}", f"{lat_base['max']:.2f}"])
    gpu = lat.get("GPU")
    text = "\n".join([
        "# Stage C evaluation (val split)\n",
        f"Adapter `{args.adapter}`; base `Qwen/Qwen2.5-0.5B-Instruct`; greedy decoding, batch 1. Val only "
        f"({len(rows)} prompts, {len(examples)} Stage C examples); the test split is not used. Plan: "
        "`docs/STAGE_C_PLAN.md`. Field targets come from the dataset's optimized prompts via the parser "
        "(known limitations in the plan). Similarities: cosine, all-MiniLM-L6-v2.\n",
        "## (a) Zero-shot base vs LoRA\n",
        "Kinds: `routed` = Stage B's real unresolved fields; `forced` = a random subset of task/output_format/"
        "constraints; `forced_all` = all three. `passes validation` = the answer would be used by the pipeline "
        "(contract in the plan, section 5).\n", t_models, "",
        "## (b) Ablation\n",
        "`routed` = val prompts Stage B actually sends to Stage C (too few on their own); `forced` = every val prompt "
        "with task, output_format and constraints requested. A+B = current pipeline; A+B+C = Stage C fills the "
        "requested fields, Stage B's other fields locked, rejected answers fall back to Stage B; C-only = Stage C "
        "fills all three fields with no Stage B rules (rejected -> the raw prompt). Intent sim. = final prompt vs "
        "the dataset's original instruction; format stated = A02 (or the parser's layouts) finds a format.\n",
        ab, "", "### Category on routed prompts: Stage C vs Stage A (against the dataset label)\n", cat, "",
        "## Named cases\n", named, "",
        "## (c) Latency per prompt (Stage C call only, batch 1, greedy)\n",
        _table(["device", "n", "median s", "p95 s", "max s"], lat_rows), "",
        f"Requirement: under 3 s per prompt on the laptop GPU (median): **"
        f"{'met' if gpu and gpu['median'] < 3 else 'NOT met' if gpu else 'not measured'}**"
        + (f" ({gpu['median']:.2f} s)." if gpu else "."),
    ])
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    raw = BACKEND_DIR.parent / "data" / "stage_c_runs" / "eval_details.json"
    raw.write_text(json.dumps({k: dict(v) for k, v in res.items()}, indent=1, default=str))


if __name__ == "__main__":
    main()
