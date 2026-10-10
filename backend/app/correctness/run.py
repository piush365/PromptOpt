"""Run the correctness suite: vague vs optimized prompt on the same model, scored against the gold answers.

    python -m app.correctness.run                                   # all available models (cached, resumable)
    python -m app.correctness.run --models cerebras/gpt-oss-120b    # one model
    python -m app.correctness.run --report-only                     # no target calls: rescore the cache, write
                                                                    # results.json + RESULTS.md

Frozen pipeline (v1.0): the prompts come from evaluation/correctness_suite/prompts.json (app.correctness.prompts);
nothing here changes a rule because of a result.
Models: cerebras/gpt-oss-120b and groq/openai/gpt-oss-120b; gemini when GEMINI_API_KEY is set. Both prompts of a
case on the same model with Compare's settings (app.compare.service.run_variant): one user message, temperature 0,
max 2048 tokens (gpt-oss's reasoning included), reasoning "low" for gpt-oss. gpt-oss gets the GPT rendering,
Gemini the Gemini rendering. Answers are cached per provider in data/correctness_suite/; calls stay within 70% of
each free daily limit, so a run can stop and be resumed later.
Scoring: app.correctness.checks. Extractor/judge: Groq qwen (a different model from the target), blind, cached.
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

from app.compare import providers
from app.compare.service import run_variant
from app.config import BACKEND_DIR
from app.correctness import checks
from app.correctness.cases import CATEGORIES, SUITE_DIR, load_cases
from app.correctness.prompts import load_prompts
from app.evaluation.llm import DailyLimitReached
from app.evaluation.run import JUDGE_MODEL, TARGET_MAX_TOKENS, TARGET_REASONING, Cache

CACHE_DIR = BACKEND_DIR.parent / "data" / "correctness_suite"
RESULTS = SUITE_DIR / "results.json"
REPORT = SUITE_DIR / "RESULTS.md"
ANALYSIS = SUITE_DIR / "analysis.json"          # hand-written notes on cases where optimization hurt (optional)
HUMAN = SUITE_DIR / "human_review.json"         # written by app.correctness.review --import
# the first model is the primary one; a later model is reported as a replication once all its cases are answered
DEFAULT_MODELS = ["groq/openai/gpt-oss-120b", "cerebras/gpt-oss-120b", f"gemini/{providers.GEMINI_MODEL}"]
FUTURE_WORK = "future work: no API key, same as GPT and Claude"
VARIANTS = ("vague", "optimized")
JUDGE_DAILY_TOKENS = 200_000


def target_for(info: providers.ModelInfo) -> str:
    return "gemini" if info.family == "gemini" else "gpt"


def answer_cache(info: providers.ModelInfo) -> Cache:
    return Cache(CACHE_DIR / f"answers-{info.provider}.jsonl")


def make_llm_json(cache: Cache):
    """The blind extractor/judge: Groq qwen, JSON mode, temperature 0, cached by (system, user)."""
    def llm_json(system: str, user: str) -> dict | None:
        key = hashlib.sha256(f"{JUDGE_MODEL}\n{system}\n{user}".encode()).hexdigest()[:24]
        rec = cache.get(key, "llm_json")
        if "obj" in rec:
            return rec["obj"]
        from app.groq_budget import UsageLedger
        if UsageLedger().used(JUDGE_MODEL)["tokens"] > providers.BUDGET_FRACTION * JUDGE_DAILY_TOKENS:
            raise DailyLimitReached(f"Groq {JUDGE_MODEL}: 70% of the daily token limit used")
        info = providers.BY_ID["groq/openai/gpt-oss-120b"]
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for _ in range(3):
            c = providers.client(info).complete(JUDGE_MODEL, msgs, max_tokens=1024, temperature=0.0,
                                                reasoning_effort="none", json_mode=True)
            try:
                obj = json.loads(c.content)
            except ValueError:
                continue
            if isinstance(obj, dict):
                cache.add(key, "llm_json", obj=obj)
                return obj
        return None
    return llm_json


def run_model(info: providers.ModelInfo, cases: list[dict], prompts: dict, calls: bool, log=print) -> dict:
    """{case_id: {variant: answer + tokens + score}} for one model; missing answers are skipped (not called) when
    `calls` is False."""
    cache = answer_cache(info)
    llm_json = make_llm_json(Cache(CACHE_DIR / "judge.jsonl"))
    target = target_for(info)
    out = {}
    for i, case in enumerate(cases, 1):
        p = prompts[case["id"]]
        texts = {"vague": p["vague"], "optimized": p["optimized"][target]}
        row = {}
        for v, text in texts.items():
            if not calls and not cache.get(_key(info, text), "answer").get("response"):
                continue
            ans = run_variant(info, text, cache)
            row[v] = {**ans, **checks.score(case, ans["answer"], llm_json)}
        if len(row) == 2:
            out[case["id"]] = row
        if calls and i % 5 == 0:
            log(f"[{info.id}] {i}/{len(cases)}")
    return out


def _key(info: providers.ModelInfo, prompt: str) -> str:
    from app.compare.service import _key as key
    return key(info.id, prompt)


# ---------------------------------------------------------------- report
def pct_reduction(before: int, after: int) -> float | None:
    return round(100 * (before - after) / before, 1) if before else None


def summarize(rows: list[tuple[dict, dict]]) -> dict:
    """rows: (case, {"vague": ..., "optimized": ...})."""
    n = len(rows)
    both = sum(r["vague"]["correct"] and r["optimized"]["correct"] for _, r in rows)
    only_o = sum(r["optimized"]["correct"] and not r["vague"]["correct"] for _, r in rows)
    only_v = sum(r["vague"]["correct"] and not r["optimized"]["correct"] for _, r in rows)
    red = [pct_reduction(r["vague"]["total_tokens"], r["optimized"]["total_tokens"]) for _, r in rows]
    tot_v = sum(r["vague"]["total_tokens"] for _, r in rows)
    tot_o = sum(r["optimized"]["total_tokens"] for _, r in rows)
    return {"n": n, "vague": both + only_v, "optimized": both + only_o, "both": both, "only_optimized": only_o,
            "only_vague": only_v, "both_wrong": n - both - only_o - only_v,
            "mcnemar_p": checks.mcnemar_exact(only_o, only_v),
            "mean_reduction": round(sum(x for x in red if x is not None) / n, 1) if n else None,
            "aggregate_reduction": pct_reduction(tot_v, tot_o),
            "mean_tokens": {v: {k: round(sum(r[v][k] for _, r in rows) / n) for k in
                                ("input_tokens", "output_tokens", "total_tokens")} for v in VARIANTS} if n else {}}


def secondary(cat: str, rows: list[tuple[dict, dict]]) -> str:
    """The category's graded metric, vague -> optimized."""
    def mean(f, v):
        xs = [f(r[v]["detail"]) for _, r in rows]
        return sum(xs) / len(xs) if xs else 0
    if not rows:
        return ""
    if cat == "information_extraction":
        return (f"mean F1 {mean(lambda d: d.get('f1', 0), 'vague'):.2f} -> {mean(lambda d: d.get('f1', 0), 'optimized'):.2f}; "
                f"precision {mean(lambda d: d.get('precision', 0), 'vague'):.2f} -> {mean(lambda d: d.get('precision', 0), 'optimized'):.2f}; "
                f"recall {mean(lambda d: d.get('recall', 0), 'vague'):.2f} -> {mean(lambda d: d.get('recall', 0), 'optimized'):.2f}")
    if cat == "classification":
        return (f"per-item accuracy {100 * mean(lambda d: d.get('accuracy', 0), 'vague'):.1f}% -> "
                f"{100 * mean(lambda d: d.get('accuracy', 0), 'optimized'):.1f}%")
    if cat == "summarization":
        cov = lambda d: d.get("key_facts_covered", 0) / max(1, d.get("key_facts", 1))
        return (f"key-fact coverage {100 * mean(cov, 'vague'):.0f}% -> {100 * mean(cov, 'optimized'):.0f}%; "
                f"forbidden statements {int(mean(lambda d: len(d.get('forbidden_present', [])), 'vague') * len(rows))} -> "
                f"{int(mean(lambda d: len(d.get('forbidden_present', [])), 'optimized') * len(rows))}; "
                f"within the word limit {int(mean(lambda d: d.get('within_length', False), 'vague') * len(rows))}/{len(rows)} -> "
                f"{int(mean(lambda d: d.get('within_length', False), 'optimized') * len(rows))}/{len(rows)}; "
                f"mean words {mean(lambda d: d.get('words', 0), 'vague'):.0f} -> {mean(lambda d: d.get('words', 0), 'optimized'):.0f}")
    if cat == "coding":
        fr = lambda d: d.get("passed", 0) / max(1, d.get("total", 1))
        return f"asserts passed {100 * mean(fr, 'vague'):.0f}% -> {100 * mean(fr, 'optimized'):.0f}%"
    return ""


def reason(case: dict, s: dict) -> str:
    """Why one answer was scored wrong, from the check's details."""
    d, cat = s["detail"], case["category"]
    if s["method"] == "unscored":
        return d.get("reason", "not scored")
    if cat == "closed_qa":
        return d.get("reason", "")
    if cat == "information_extraction":
        parts = ([f"missed {', '.join(d['missed'])}"] if d.get("missed") else []) + \
                ([f"also listed {', '.join(map(str, d['extra']))}"] if d.get("extra") else [])
        return "; ".join(parts)
    if cat == "classification":
        return "; ".join(f"{k}: {w['got'] or 'no label read'} (gold {w['gold']})" for k, w in d["wrong"].items())
    if cat == "summarization":
        parts = [f"missed: {m}" for m in d.get("missed", [])] + [f"stated: {f}" for f in d.get("forbidden_present", [])]
        if not d.get("within_length", True):
            parts.append(f"{d['words']} words > {d['max_words']}")
        return "; ".join(parts)
    if cat == "coding":
        if d["status"] not in ("passed", "failed"):
            return f"{d['status']}: {d.get('error', '')}"[:200]
        f = d["failed"][0] if d["failed"] else {}
        return f"{d['passed']}/{d['total']} asserts; first failure: `{f.get('test', '').splitlines()[-1]}` {f.get('error', '')}"[:240]
    return ""


def mark(ok: bool) -> str:
    return "✅" if ok else "❌"


def _p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def human_status(cases: list[dict]) -> list[str]:
    if not HUMAN.exists():
        return ["Gold answers: **auto-validated; human review pending**.", "Human review: **pending**. `team_input/correctness_review/cases_review.xlsx` (3 sheets, one per team member) asks each reviewer "
                "to tick \"gold correct Y/N\"; import it with `python -m app.correctness.review --import <file>`. "
                "Until then the gold answers are checked automatically only (`validation.md`)."]
    h = json.loads(HUMAN.read_text())
    lines = [f"Gold answers: **auto-validated and human-reviewed** ({h['yes']} of {h['total']} confirmed correct).",
             f"Human review ({h['file']}, imported {h['imported']}): {h['yes']} Y, {h['no']} N, {h['blank']} not "
             f"answered, of {h['total']} cases; results per sheet in `human_review.md`."]
    if h["flagged"]:
        lines.append("**Flagged (a reviewer ticked N; their results below should be read with care):** "
                     + ", ".join(f"{f['id']} ({f['sheet']}: {f.get('comment') or 'no comment'})" for f in h["flagged"]))
    return lines


def git_rev() -> str:
    try:
        return subprocess.run(["git", "describe", "--tags", "--always", "--dirty"], capture_output=True, text=True,
                              cwd=BACKEND_DIR).stdout.strip()
    except OSError:
        return "?"


def report(results: dict, cases: list[dict], prompts: dict) -> str:
    byid = {c["id"]: c for c in cases}
    analysis = json.loads(ANALYSIS.read_text()) if ANALYSIS.exists() else {}
    routed = [k for k, v in prompts["cases"].items() if v["routed"]]
    L = ["# Correctness suite: vague vs optimized prompts\n",
         "Are optimized prompts not just shorter but **correct**? 50 new, hand-written cases (10 per category) with "
         "one verifiable answer each, run as the user's vague prompt and as PromptOpt's optimized prompt on the same "
         "model. The pipeline is frozen at v1.0: no rule was changed because of these results.\n",
         f"- Cases: `cases.jsonl` (new; not from the dataset, checked in `validation.md`). Prompts: `prompts.json` "
         f"(A+B; A+B+C for the {len(routed)} prompts Stage B routes to Stage C: {', '.join(routed)}). "
         "No case leaks its gold answer into the optimized prompt (leak check in `validation.md`).",
         f"- Settings: one user message, temperature 0, max {TARGET_MAX_TOKENS} tokens (gpt-oss's reasoning included), "
         f"reasoning \"{TARGET_REASONING}\" for gpt-oss; both prompts get the same material (vague: pasted below the "
         "prompt; optimized: the GPT rendering's Document). Tokens are the provider's counts (input + output, "
         "reasoning included in output).",
         "- Scoring (`app/correctness/checks.py`): closed_qa normalized match; extraction exact set (P/R/F1 shown); "
         "classification all items right (per-item accuracy shown); summarization all key facts + no forbidden "
         "statement + within the word limit (blind checklist judge); coding all hidden asserts pass in the bubblewrap "
         f"sandbox. Extractor/judge: Groq `{JUDGE_MODEL}`, blind (never sees the gold answer or which prompt was used), "
         "used only where a deterministic check cannot decide (see the method column).",
         "- McNemar: exact two-sided test on the discordant cases (only optimized right vs only vague right).",
         f"- Code: `{git_rev()}`; generated {results['generated']}.",
         *[f"- {x}" for x in human_status(cases)], ""]
    if not results["models"]:
        return "\n".join(L + ["No results yet."]) + "\n"
    missing = [m for m in DEFAULT_MODELS if m not in results["models"]]
    if missing:
        L.append("Not run: " + "; ".join(
            f"`{m}` ({FUTURE_WORK if m.startswith('gemini/') else providers.BY_ID[m].reason or 'incomplete'})"
            for m in missing) + ".\n")
    partial = {m: len(r["cases"]) for m, r in results["models"].items() if len(r["cases"]) < len(cases)}
    if partial:
        L.append("In progress (reported once every case is answered): " + "; ".join(
            f"`{m}` {k}/{len(cases)}" for m, k in partial.items()) + ".\n")
    complete = [m for m in results["models"] if m not in partial]
    if len(complete) > 1:
        L += ["## Summary across models\n",
              "| model | vague correct | optimized correct | only optimized | only vague | McNemar p | total tokens (aggregate) |",
              "|---|---|---|---|---|---|---|"]
        for i, mid in enumerate(complete):
            s = summarize([(None, r) for r in results["models"][mid]["cases"].values()])
            L.append(f"| {results['models'][mid]['label']}{' (primary)' if i == 0 else ''} | {s['vague']}/{s['n']} | "
                     f"{s['optimized']}/{s['n']} | {s['only_optimized']} | {s['only_vague']} | {_p(s['mcnemar_p'])} | "
                     f"{-s['aggregate_reduction']:+.1f}% |")
        L.append("")
    for i, mid in enumerate(complete):
        res = results["models"][mid]
        rows = [(byid[k], r) for k, r in res["cases"].items()]
        role = "Primary model" if i == 0 else "Second-model replication"
        L += [f"## {role}: {res['label']}\n",
              f"{len(rows)} of {len(cases)} cases answered with both prompts.\n",
              "| category | n | vague correct | optimized correct | both | only optimized | only vague | both wrong "
              "| McNemar p | total tokens: mean reduction per case | aggregate |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for cat in CATEGORIES + ["overall"]:
            sub = rows if cat == "overall" else [x for x in rows if x[0]["category"] == cat]
            if not sub:
                continue
            s = summarize(sub)
            name = f"**{cat}**" if cat == "overall" else cat
            L.append(f"| {name} | {s['n']} | {s['vague']}/{s['n']} ({100 * s['vague'] / s['n']:.0f}%) | "
                     f"{s['optimized']}/{s['n']} ({100 * s['optimized'] / s['n']:.0f}%) | {s['both']} | "
                     f"{s['only_optimized']} | {s['only_vague']} | {s['both_wrong']} | {_p(s['mcnemar_p'])} | "
                     f"{s['mean_reduction']:+.1f}% | {s['aggregate_reduction']:+.1f}% |")
        s = summarize(rows)
        L += ["", "2x2 (all cases):\n", "| | optimized correct | optimized wrong |", "|---|---|---|",
              f"| **vague correct** | {s['both']} | {s['only_vague']} |",
              f"| **vague wrong** | {s['only_optimized']} | {s['both_wrong']} |", "",
              f"Mean tokens per case, vague -> optimized: input {s['mean_tokens']['vague']['input_tokens']} -> "
              f"{s['mean_tokens']['optimized']['input_tokens']}, output {s['mean_tokens']['vague']['output_tokens']} -> "
              f"{s['mean_tokens']['optimized']['output_tokens']}, total {s['mean_tokens']['vague']['total_tokens']} -> "
              f"{s['mean_tokens']['optimized']['total_tokens']} (reduction: positive = fewer tokens).\n",
              "Graded metrics, vague -> optimized:\n"]
        for cat in CATEGORIES[1:]:
            L.append(f"- {cat}: " + secondary(cat, [x for x in rows if x[0]["category"] == cat]))
        hurt = [(c, r) for c, r in rows if r["vague"]["correct"] and not r["optimized"]["correct"]]
        fixed = [(c, r) for c, r in rows if r["optimized"]["correct"] and not r["vague"]["correct"]]
        L += ["", f"### Where optimization hurt correctness ({len(hurt)})\n"]
        if not hurt:
            L.append("None.")
        for c, r in hurt:
            p = prompts["cases"][c["id"]]
            note = analysis.get(f"{mid}|{c['id']}") or analysis.get(c["id"])
            L.append(f"- **{c['id']}** ({c['category']}; Stage A said {p['stage_a']['category']} "
                     f"{p['stage_a']['confidence']:.2f}; rules {', '.join(x.split('_')[0] for x in p['rules']) or '-'}"
                     f"{'; Stage C' if p['routed'] else ''}): {reason(c, r['optimized'])}."
                     + (f" *Why:* {note}" if note else ""))
        L += ["", f"### Where optimization fixed a wrong answer ({len(fixed)})\n"]
        if not fixed:
            L.append("None.")
        for c, r in fixed:
            L.append(f"- **{c['id']}** ({c['category']}): vague was wrong: {reason(c, r['vague'])}.")
        L += ["", "### Per case\n",
              "| case | category | vague | optimized | tokens in vague -> opt | out | total | total reduction | scored by |",
              "|---|---|---|---|---|---|---|---|---|"]
        for c, r in rows:
            v, o = r["vague"], r["optimized"]
            routed_mark = " (C)" if prompts["cases"][c["id"]]["routed"] else ""
            red = pct_reduction(v["total_tokens"], o["total_tokens"])
            L.append(f"| {c['id']}{routed_mark} | {c['category']} | {mark(v['correct'])} | {mark(o['correct'])} | "
                     f"{v['input_tokens']} -> {o['input_tokens']} | {v['output_tokens']} -> {o['output_tokens']} | "
                     f"{v['total_tokens']} -> {o['total_tokens']} | {red:+.1f}% | "
                     f"{v['method']} / {o['method']} |")
        L += ["", "(C) = routed to Stage C (A+B+C). Reduction: positive = the optimized prompt used fewer tokens.", "",
              "### Answers\n"]
        for c, r in rows:
            L.append(f"<details><summary><b>{c['id']}</b> {c['scenario']}: vague {mark(r['vague']['correct'])}, "
                     f"optimized {mark(r['optimized']['correct'])}</summary>\n")
            L.append(f"Vague prompt: `{c['vague_prompt']}`  \nGold: {gold_text(c)}\n")
            for v in VARIANTS:
                why = "" if r[v]["correct"] else f" ({reason(c, r[v])})"
                L += [f"**{v}** {mark(r[v]['correct'])}{why}:\n", "```text", r[v]["answer"].strip().replace("```", "'''"),
                      "```", ""]
            L.append("</details>\n")
    return "\n".join(L) + "\n"


def gold_text(c: dict) -> str:
    g, cat = c["gold"], c["category"]
    if cat == "closed_qa":
        return f"**{g}**"
    if cat == "information_extraction":
        return ", ".join(f"**{x}**" for x in g)
    if cat == "classification":
        return "; ".join(f"{k}: **{v}**" for k, v in g.items())
    if cat == "summarization":
        return ("must state: " + "; ".join(k["fact"] for k in g["key_facts"]) + " | must not: "
                + "; ".join(f["fact"] for f in g["forbidden"]) + f" | at most {g['max_words']} words")
    return f"`{g['function']}` passes {len(g['tests'])} hidden asserts"


def collect(models: list[str], cases: list[dict], prompts: dict, calls: bool, log=print) -> dict:
    results = {"generated": datetime.now().isoformat(timespec="minutes"),
               "settings": {"temperature": 0.0, "max_tokens": TARGET_MAX_TOKENS, "reasoning_effort": TARGET_REASONING,
                            "judge": JUDGE_MODEL},
               "models": {}}
    for mid in models:
        info = providers.BY_ID[mid]
        if not info.available:
            log(f"skip {mid}: {info.reason}")
            continue
        try:
            got = run_model(info, cases, prompts, calls, log)
        except DailyLimitReached as e:
            log(f"Stopped {mid}: {e}. Answers so far are cached; run again later.")
            got = run_model(info, cases, prompts, False, log)
        if got:
            results["models"][mid] = {"label": f"{info.label} (prompt rendered for {target_for(info).upper()})",
                                      "target_rendering": target_for(info), "cases": got}
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--report-only", action="store_true", help="no target calls: score cached answers, write reports")
    ap.add_argument("--no-write", action="store_true", help="run (fill the cache) without writing results/report")
    ap.add_argument("--cases", nargs="+", help="only these case ids (implies --no-write)")
    args = ap.parse_args()
    cases = load_cases()
    if args.cases:
        cases, args.no_write = [c for c in cases if c["id"] in args.cases], True
    prompts = load_prompts()
    results = collect(args.models, cases, prompts["cases"], calls=not args.report_only)
    if args.no_write:
        for mid, res in results["models"].items():
            for k, r in res["cases"].items():
                print(mid, k, {v: (r[v]["correct"], r[v]["method"], r[v]["total_tokens"]) for v in VARIANTS})
        return
    if not args.report_only or args.models != DEFAULT_MODELS:
        # a partial run never overwrites the full report: rescore everything from the cache
        results = collect(DEFAULT_MODELS, cases, prompts["cases"], calls=False)
    text = report(results, cases, prompts)      # before writing: the report records `git describe`
    RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    REPORT.write_text(text, encoding="utf-8")
    for mid, res in results["models"].items():
        s = summarize([(None, r) for r in res["cases"].values()])
        print(f"{mid}: vague {s['vague']}/{s['n']}, optimized {s['optimized']}/{s['n']}, only-opt {s['only_optimized']}, "
              f"only-vague {s['only_vague']}, McNemar p {_p(s['mcnemar_p'])}, tokens {s['mean_reduction']:+.1f}% per case")
    print(f"wrote {RESULTS} and {REPORT}")


if __name__ == "__main__":
    main()
