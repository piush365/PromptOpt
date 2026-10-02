"""Token evaluation on the FULL test split: degraded prompt vs PromptOpt (A+B, and A+B+C on routed prompts).

    python -m app.evaluation.tokens                    # run (resumable; stops at the daily budget, rerun later)
    python -m app.evaluation.tokens --report-only --out ../evaluation/token_test.md

A measurement on the frozen pipeline (Stage A/B at `final-for-test`, Stage C adapter as evaluated): nothing is tuned.
Target: cerebras/gpt-oss-120b, temperature 0, max 2048 tokens, reasoning "low", one user message: the settings of
the final benchmark run (app.evaluation.run). Every variant gets the row's context appended after a blank line
(app.evaluation.variants). Variants:
  degraded   the user's prompt as typed
  stage_b    A+B: Stage A + Stage B's optimized text (exactly the benchmark's `stage_b` variant)
  stage_c    A+B+C: for the prompts Stage B routes to Stage C, Stage C's patched text under the routing contract
             (a rejected answer keeps Stage B's text); run in backend/.venv-gpu so Stage C uses the GPU
No judge (to save quota): task success is reported where it can be checked without one (classification labels,
coding: a code block that parses). Answers are cached in data/evaluation/token-test.jsonl; calls stop before the
rolling 24-hour Cerebras usage passes BUDGET_FRACTION of the daily limit, so a run can span two days.
"""
import argparse
import random
import statistics
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from app.config import BACKEND_DIR, EVAL_DIR
from app.dataset_io import DEFAULT_CSV, load_rows
from app.evaluation.llm import DailyLimitReached
from app.evaluation.run import (CATEGORIES, TARGET_MAX_TOKENS, TARGET_REASONING, TARGETS, Cache, make_llm,
                                select_rows)
from app.evaluation.success import task_success
from app.evaluation.variants import build_variants, with_context

TARGET = TARGETS["cerebras"]
CACHE = EVAL_DIR / "token-test.jsonl"
BUDGET_FRACTION = 0.7
DAILY_TOKENS = 1_000_000
BOOTSTRAP = 10_000
SEED = 20261002


# ---------------------------------------------------------------- prompts
def stage_c_prompts(rows: list[dict], detector, log=print) -> dict[str, dict]:
    """A+B+C text for the routed rows (Stage C on the GPU if available), cached with the answers."""
    from app.stage_b import optimize
    from app.stage_c.contract import apply_stage_c
    from app.stage_c.runtime import StageCModel, available
    if not available():
        raise SystemExit("Stage C adapter or ML packages missing: run in backend/.venv-gpu")
    model, out = None, {}
    for r in rows:
        context = r.get("context") or None
        f = detector.detect(r["degraded_prompt"], context)
        res = optimize(r["degraded_prompt"], f)
        if not res.needs_stage_c:
            continue
        model = model or StageCModel.load()
        c = apply_stage_c(r["degraded_prompt"], f, res, model.generate)
        out[r["source_id"]] = {"prompt": with_context(c.optimized_text, context), "accepted": c.accepted,
                               "fields": c.fields, "errors": c.errors}
    log(f"Stage C: {len(out)} routed prompts, {sum(v['accepted'] for v in out.values())} answers accepted")
    return out


def used_today() -> int:
    from app.groq_budget import UsageLedger
    return UsageLedger(BACKEND_DIR.parent / "data" / "cerebras_usage.json").used(TARGET)["tokens"]


def run(rows: list[dict], log=print) -> dict:
    from app.stage_a.detector import FeatureDetector
    detector = FeatureDetector()
    cache = Cache(CACHE)
    sc = stage_c_prompts(rows, detector, log)
    llm = make_llm("cerebras")
    stats = defaultdict(int)
    try:
        for i, r in enumerate(rows, 1):
            sid = r["source_id"]
            built = build_variants(r, detector, ("degraded", "stage_b"))
            prompts = {v: built[v]["prompt"] for v in built}
            if sid in sc:
                prompts["stage_c"] = sc[sid]["prompt"]
            for v, prompt in prompts.items():
                rec = cache.get(sid, v)
                if rec.get("response") is not None and rec.get("prompt") == prompt:
                    stats["cached"] += 1
                    continue
                est = len(prompt) // 4 + TARGET_MAX_TOKENS
                if used_today() + est > BUDGET_FRACTION * DAILY_TOKENS:
                    raise DailyLimitReached(f"Cerebras usage over the last 24 h is near {BUDGET_FRACTION:.0%} of "
                                            f"{DAILY_TOKENS:,} tokens")
                c = llm.complete(TARGET, [{"role": "user", "content": prompt}], max_tokens=TARGET_MAX_TOKENS,
                                 temperature=0.0, reasoning_effort=TARGET_REASONING)
                extra = {"stage_c": sc[sid]} if v == "stage_c" else {}
                cache.add(sid, v, category=r["category"], prompt=prompt, response=c.content, target=asdict(c), **extra)
                stats["calls"] += 1
            if i % 10 == 0:
                log(f"[{i}/{len(rows)}] calls {stats['calls']}, cached {stats['cached']}, "
                    f"Cerebras 24 h tokens {used_today():,}")
    except DailyLimitReached as e:
        log(f"Stopped for today: {e}. Progress is cached; run the same command again later.")
        stats["stopped"] = 1
    return dict(stats)


# ---------------------------------------------------------------- statistics
def bootstrap_ci(values: list[float], rng: random.Random, n: int = BOOTSTRAP) -> tuple[float, float]:
    if len(values) < 2:
        return (float("nan"), float("nan"))
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def wilcoxon_p(before: list[int], after: list[int]) -> float | None:
    from scipy.stats import wilcoxon
    diffs = [a - b for a, b in zip(after, before)]
    if len(diffs) < 2 or not any(diffs):
        return None
    return float(wilcoxon(after, before).pvalue)


def reduction(before: int, after: int) -> float | None:
    """Per-item % reduction (positive = fewer tokens)."""
    return 100 * (before - after) / before if before else None


def pairs(cache: Cache, rows: list[dict], a: str, b: str) -> list[tuple[dict, dict, dict]]:
    out = []
    for r in rows:
        x, y = cache.get(r["source_id"], a), cache.get(r["source_id"], b)
        if x.get("response") is not None and y.get("response") is not None:
            out.append((r, x, y))
    return out


def tok(rec: dict, kind: str) -> int:
    t = rec["target"]
    return {"input": t["input_tokens"], "output": t["output_tokens"],
            "total": t["input_tokens"] + t["output_tokens"], "reasoning": t.get("reasoning_tokens") or 0}[kind]


def summary(ps: list, rng: random.Random) -> dict:
    out = {"n": len(ps)}
    for kind in ("input", "output", "total"):
        before = [tok(x, kind) for _, x, _ in ps]
        after = [tok(y, kind) for _, _, y in ps]
        red = [v for v in (reduction(b, a) for b, a in zip(before, after)) if v is not None]
        lo, hi = bootstrap_ci(red, rng)
        out[kind] = {"mean_before": sum(before) / len(ps), "mean_after": sum(after) / len(ps),
                     "aggregate_reduction": reduction(sum(before), sum(after)),
                     "mean_reduction": sum(red) / len(red) if red else None,
                     "median_reduction": statistics.median(red) if red else None, "ci": (lo, hi),
                     "p": wilcoxon_p(before, after)}
    out["reasoning"] = {"mean_before": sum(tok(x, "reasoning") for _, x, _ in ps) / len(ps),
                        "mean_after": sum(tok(y, "reasoning") for _, _, y in ps) / len(ps)}
    out["truncated"] = (sum(x["target"].get("finish_reason") == "length" for _, x, _ in ps),
                        sum(y["target"].get("finish_reason") == "length" for _, _, y in ps))
    succ = [(task_success(r["category"], r, x["response"], None), task_success(r["category"], r, y["response"], None))
            for r, x, y in ps]
    succ = [(a, b) for a, b in succ if a is not None and b is not None]
    out["success"] = (sum(a for a, _ in succ), sum(b for _, b in succ), len(succ))
    return out


def _f(x, d=1, pct=False) -> str:
    if x is None or x != x:
        return "-"
    return f"{x:.{d}f}%" if pct else f"{x:.{d}f}"


def _p(p) -> str:
    return "-" if p is None else ("< 0.001" if p < 0.001 else f"{p:.3f}")


def table(groups: list[tuple[str, dict]], before_name: str, after_name: str) -> list[str]:
    lines = [f"| set | n | tokens | {before_name} (mean) | {after_name} (mean) | reduction: aggregate | mean per item "
             "[95% CI] | median per item | Wilcoxon p |", "|---|---|---|---|---|---|---|---|---|"]
    for name, s in groups:
        for kind in ("input", "output", "total"):
            k = s[kind]
            lines.append(f"| {name if kind == 'input' else ''} | {s['n'] if kind == 'input' else ''} | {kind} | "
                         f"{k['mean_before']:.0f} | {k['mean_after']:.0f} | {_f(k['aggregate_reduction'], pct=True)} | "
                         f"**{_f(k['mean_reduction'], pct=True)}** [{_f(k['ci'][0], pct=True)}, {_f(k['ci'][1], pct=True)}] | "
                         f"{_f(k['median_reduction'], pct=True)} | {_p(k['p'])} |")
    return lines


def report(rows: list[dict]) -> tuple[str, dict]:
    cache = Cache(CACHE)
    rng = random.Random(SEED)
    ab = pairs(cache, rows, "degraded", "stage_b")
    overall = summary(ab, rng)
    per_cat = [(c, summary([p for p in ab if p[0]["category"] == c], rng)) for c in CATEGORIES
               if any(p[0]["category"] == c for p in ab)]
    t = overall["total"]
    headline = (f"Optimized prompts reduce total tokens by {t['mean_reduction']:.1f}% (95% CI {t['ci'][0]:.1f}-"
                f"{t['ci'][1]:.1f}%, n = {overall['n']})")
    i, o = overall["input"], overall["output"]
    lines = ["# Token evaluation on the full test split\n",
             f"**{headline}**: the mean of the per-prompt reductions in total tokens (input + output, output "
             f"including the model's hidden reasoning), degraded prompt vs PromptOpt (Stage A + B), on "
             f"`{TARGET}`.\n",
             f"**Input grows, the saving comes from output.** The optimized prompt is longer: input tokens "
             f"{i['mean_before']:.0f} -> {i['mean_after']:.0f} per prompt on average ({_f(-i['mean_reduction'], pct=True)} "
             f"per prompt). The answers are much shorter: output tokens {o['mean_before']:.0f} -> {o['mean_after']:.0f} "
             f"({_f(o['mean_reduction'], pct=True)} fewer per prompt), because a stated format and length stop the "
             "model from writing long, unrequested answers.\n",
             f"Setup: test split ({overall['n']} of {len(rows)} prompts with both answers), one run, temperature 0, max "
             f"{TARGET_MAX_TOKENS} tokens, reasoning \"{TARGET_REASONING}\", one user message, the row's context "
             "appended to every variant: the final benchmark's settings. Frozen pipeline (`final-for-test`); nothing "
             "tuned. No judge. Reduction = (degraded - optimized) / degraded, per prompt; CI = 10,000 bootstrap "
             "resamples of the per-prompt reductions; Wilcoxon signed-rank test on the paired token counts; "
             "aggregate = reduction of the summed tokens.\n",
             "## Degraded vs A+B (Stage A + Stage B)\n", *table([("all", overall), *per_cat], "degraded", "A+B"), "",
             f"Reasoning tokens (part of output): {overall['reasoning']['mean_before']:.0f} -> "
             f"{overall['reasoning']['mean_after']:.0f} per prompt. Answers cut off at the {TARGET_MAX_TOKENS}-token "
             f"limit: degraded {overall['truncated'][0]}, A+B {overall['truncated'][1]}.\n",
             "### Task success where it is checkable without a judge\n",
             "| category | degraded | A+B | n |", "|---|---|---|---|"]
    for c, s in per_cat:
        a, b, n = s["success"]
        if n:
            lines.append(f"| {c} | {a}/{n} ({100 * a / n:.0f}%) | {b}/{n} ({100 * b / n:.0f}%) | {n} |")
    lines += ["", "classification: every item gets the reference label; coding: a code block is present and Python "
                  "code in it parses (functional tests: `coding_tests.md`). closed_qa needs the judge and is not "
                  "checked here; extraction and summarization are not checkable automatically.\n"]
    routed = [r for r in rows if cache.get(r["source_id"], "stage_c").get("response") is not None]
    if routed:
        abc = pairs(cache, routed, "degraded", "stage_c")
        ab_r = pairs(cache, routed, "degraded", "stage_b")
        bc = pairs(cache, routed, "stage_b", "stage_c")
        acc = sum(cache.get(r["source_id"], "stage_c").get("stage_c", {}).get("accepted", False) for r in routed)
        lines += ["## Routed prompts: A+B vs A+B+C\n",
                  f"The {len(routed)} prompts Stage B sends to Stage C (Stage C's answer accepted for {acc}; rejected "
                  "ones keep Stage B's text). Small set: indicative only.\n",
                  *table([("degraded -> A+B", summary(ab_r, rng)), ("degraded -> A+B+C", summary(abc, rng)),
                          ("A+B -> A+B+C", summary(bc, rng))], "before", "after"), ""]
    return "\n".join(lines) + "\n", {"headline": headline, "overall": overall}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    rows = select_rows(load_rows(DEFAULT_CSV, split="test"), per_category=10_000)   # interleaved by category
    if not args.report_only:
        print(run(rows))
    text, _ = report(rows)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
