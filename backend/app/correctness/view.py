"""What the UI's "Test suite" view shows for one case: material, both prompts, both answers, gold, verdicts, tokens.

Results come from evaluation/correctness_suite/results.json (the reported run), so the demo works offline and from a
fresh clone; `live=True` runs the case on the chosen model now (cached, so a repeat costs no quota) and scores it
with the same checks.
"""
import json
from functools import lru_cache

from app.compare import providers
from app.correctness import checks
from app.correctness.cases import CATEGORIES, by_id, load_cases
from app.correctness.prompts import PROMPTS
from app.correctness.run import (CACHE_DIR, DEFAULT_MODELS, RESULTS, answer_cache, gold_text, make_llm_json,
                                 pct_reduction, reason, summarize, target_for)
from app.compare.service import run_variant
from app.evaluation.run import Cache


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> dict:
    return json.loads(open(path, encoding="utf-8").read())


def _json(path) -> dict | None:
    return _load(str(path), path.stat().st_mtime) if path.exists() else None


def overview() -> dict:
    cases = load_cases()
    results = _json(RESULTS) or {"models": {}}
    models = []
    for mid in DEFAULT_MODELS:
        info = providers.BY_ID[mid]
        res = results["models"].get(mid)
        s = summarize([(None, r) for r in res["cases"].values()]) if res else None
        models.append({"id": mid, "label": info.label, "available": info.available, "reason": info.reason,
                       "has_results": bool(res), "summary": s and {k: s[k] for k in (
                           "n", "vague", "optimized", "only_optimized", "only_vague", "mcnemar_p", "mean_reduction")}})
    return {"categories": CATEGORIES, "models": models, "generated": results.get("generated"),
            "cases": [{"id": c["id"], "category": c["category"], "scenario": c["scenario"]} for c in cases]}


def case_view(case_id: str, model_id: str, live: bool = False) -> dict:
    case = by_id(load_cases()).get(case_id)
    if case is None:
        raise KeyError(case_id)
    info = providers.BY_ID.get(model_id)
    if info is None:
        raise ValueError(f"unknown model {model_id!r}")
    prompts = (_json(PROMPTS) or {"cases": {}})["cases"].get(case_id)
    if prompts is None:
        raise LookupError("prompts.json is missing: run python -m app.correctness.prompts")
    target = target_for(info)
    texts = {"vague": prompts["vague"], "optimized": prompts["optimized"][target]}
    row = None
    if live:
        if not info.available:
            raise providers.ModelUnavailable(info.reason)
        llm_json = make_llm_json(Cache(CACHE_DIR / "judge.jsonl"))
        row = {}
        for v, text in texts.items():
            ans = run_variant(info, text, answer_cache(info))
            row[v] = {**ans, **checks.score(case, ans["answer"], llm_json)}
    else:
        res = ((_json(RESULTS) or {}).get("models") or {}).get(model_id)
        row = res["cases"].get(case_id) if res else None
    out = {"case": {k: case[k] for k in ("id", "category", "scenario", "difficulty", "material", "vague_prompt")},
           "gold": gold_text(case).replace("**", ""), "notes": case.get("notes", ""),
           "prompts": {"vague": texts["vague"], "optimized": texts["optimized"], "rendered_for": target},
           "pipeline": {k: prompts[k] for k in ("stage_a", "category_used", "rules", "routed", "stage_c")},
           "model": {"id": info.id, "label": info.label}, "live": live, "result": None}
    if row:
        out["result"] = {v: {"answer": row[v]["answer"], "correct": row[v]["correct"], "method": row[v]["method"],
                             "why": None if row[v]["correct"] else reason(case, row[v]),
                             **{k: row[v][k] for k in ("input_tokens", "output_tokens", "total_tokens", "latency_ms")}}
                         for v in ("vague", "optimized")}
        out["result"]["total_reduction_pct"] = pct_reduction(row["vague"]["total_tokens"],
                                                             row["optimized"]["total_tokens"])
    return out
