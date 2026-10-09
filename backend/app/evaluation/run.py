"""Evaluation harness: prompt variants -> target LLM -> judge -> task success -> evaluation_runs table.

    python -m app.evaluation.run --per-category 5                 # first dev run: 25 val prompts
    python -m app.evaluation.run --per-category 5 --summary-only  # print the summary again

Develop on val only. test and benchmark are the final held-out numbers: they need --final, once, at the end.

Resumable: every target call and judgment is appended to data/evaluation/<run>.jsonl as soon as it returns, and every
finished item is committed to the database. Re-running the same command skips what is in the database, reuses cached
calls, and only calls the API for what is missing. When Groq's daily limit is reached the run stops; run it again
later. Results are keyed by source_id (the dataset's `id` is renumbered on every rebuild).
"""
import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import EVAL_DIR
from app.db import repository as repo
from app.db.models import EvaluationRun
from app.dataset_io import DEFAULT_CSV, load_rows
from app.evaluation import judge
from app.groq_budget import UsageLedger
from app.evaluation.llm import Completion, DailyLimitReached, GroqChat, JSONGenerationFailed, ModelUnavailable
from app.evaluation.success import task_success
from app.evaluation.variants import VARIANTS, build_variants

CATEGORIES = ["closed_qa", "information_extraction", "classification", "summarization", "coding"]
TARGET_MODEL = "openai/gpt-oss-120b"
TARGET_MAX_TOKENS = 2048          # includes gpt-oss's hidden reasoning tokens; the same for every variant
TARGET_REASONING = "low"          # as in the dataset notebook; recorded, and the same for every variant
JUDGE_MODEL = "qwen/qwen3.8-27b"  # a different model from the target, so it does not favour its own answers
JUDGE_MAX_TOKENS = 512
JUDGE_REASONING = "none"          # skip qwen's thinking step (as in the notebook)
JUDGE_ATTEMPTS = 3                # retries when the judge returns unusable JSON
JUDGE_VERSION = 2                 # 2: long responses shown whole (up to 12,000 chars) or head + tail (judge.py)
OLD_JUDGE_RESPONSE_CHARS = 6000   # version 1 cut responses here; longer ones need a new judgment
JUDGE_GIVE_UP_RUNS = 2            # after this many runs with a failed judgment, the item is skipped (and reported)
SEED = "promptopt-eval-v1"
FINAL_SPLITS = {"test", "benchmark"}


def select_rows(rows: list[dict[str, str]], per_category: int) -> list[dict[str, str]]:
    """A fixed pseudo-random `per_category` rows per category, interleaved so a partial run stays balanced."""
    key = lambda r: hashlib.sha256(f"{SEED}:{r['source_id']}".encode()).hexdigest()  # noqa: E731
    picked = {c: sorted((r for r in rows if r["category"] == c), key=key)[:per_category] for c in CATEGORIES}
    return [picked[c][i] for i in range(per_category) for c in CATEGORIES if i < len(picked[c])]


def dataset_version(path: Path, rows: list[dict[str, str]]) -> str:
    return f"v1-{len(rows)}-{hashlib.sha256(Path(path).read_bytes()).hexdigest()[:8]}"


# ---------------------------------------------------------------- cache
class Cache:
    """Append-only JSONL: one line per finished step (target call or judgment) of one (source_id, variant)."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.data[(rec["source_id"], rec["variant"])].update(rec)

    def get(self, source_id: str, variant: str) -> dict[str, Any]:
        return self.data.get((source_id, variant), {})

    def add(self, source_id: str, variant: str, **fields: Any) -> None:
        rec = {"source_id": source_id, "variant": variant, **fields}
        self.data[(source_id, variant)].update(rec)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- one item
def _judge(llm: GroqChat, category: str, request: str, context: str, reference: str, response: str) -> judge.Judgment:
    """Up to JUDGE_ATTEMPTS calls. When Groq could not finish the JSON (JSONGenerationFailed, usually the token
    limit), the next attempt gets twice the tokens."""
    last: Exception | None = None
    max_tokens = JUDGE_MAX_TOKENS
    for _ in range(JUDGE_ATTEMPTS):
        try:
            c = llm.complete(JUDGE_MODEL, judge.messages(category, request, context, reference, response),
                             max_tokens=max_tokens, temperature=0.0, reasoning_effort=JUDGE_REASONING, json_mode=True)
        except JSONGenerationFailed as e:
            last, max_tokens = e, max_tokens * 2
            continue
        try:
            return judge.parse(c.content, category)
        except ValueError as e:
            last = e
    raise ValueError(f"judge failed {JUDGE_ATTEMPTS} times: {last}")


def run(db: Session, rows: list[dict[str, str]], llm: Any, detector: Any, run_name: str, version: str,
        cache: Cache, variants: tuple[str, ...] = VARIANTS, max_tokens: int = TARGET_MAX_TOKENS,
        reasoning_effort: str | None = TARGET_REASONING, log: Callable[[str], None] = print,
        target_model: str = TARGET_MODEL, refresh: bool = False) -> dict[str, int]:
    """Evaluate every (row, variant) not yet in the database. Returns counters."""
    done = set(db.execute(select(EvaluationRun.dataset_item_id, EvaluationRun.variant)
                          .where(EvaluationRun.run_name == run_name, EvaluationRun.target_llm == target_model)).all())
    stats = {"recorded": 0, "skipped": 0, "target_calls": 0, "judge_calls": 0, "judge_failures": 0}
    if refresh:
        done -= _stale(db, rows, detector, variants, run_name, target_model, cache, done, stats, log)
    try:
        for i, row in enumerate(rows, start=1):
            sid, cat = row["source_id"], row["category"]
            todo = [v for v in variants if (sid, v) not in done]
            stats["skipped"] += len(variants) - len(todo)
            if not todo:
                continue
            built = build_variants(row, detector, tuple(todo))
            for v in todo:
                rec = cache.get(sid, v)
                b = built[v]
                if rec.get("response") is not None and rec.get("prompt") != b["prompt"]:
                    # the variant's prompt changed since it was cached (e.g. a Stage B fix): the old answer is stale
                    log(f"  {sid} {v}: prompt changed since cached, calling again")
                    cache.add(sid, v, response=None, judgment=None)
                    rec = cache.get(sid, v)
                if rec.get("response") is None:
                    c: Completion = llm.complete(target_model, [{"role": "user", "content": b["prompt"]}],
                                                 max_tokens=max_tokens, temperature=0.0,
                                                 reasoning_effort=reasoning_effort)
                    stats["target_calls"] += 1
                    cache.add(sid, v, category=cat, request=b["request"], prompt=b["prompt"], meta=b["meta"],
                              response=c.content, target=asdict(c), max_tokens=max_tokens,
                              reasoning_effort=reasoning_effort, judgment=None)
                    rec = cache.get(sid, v)
                if rec.get("judgment") is None:
                    if rec.get("judge_failed_runs", 0) >= JUDGE_GIVE_UP_RUNS:
                        stats["judge_given_up"] = stats.get("judge_given_up", 0) + 1
                        log(f"  {sid} {v}: judge failed in {JUDGE_GIVE_UP_RUNS} runs, skipped (not recorded)")
                        continue
                    try:
                        j = _judge(llm, cat, rec["request"], row.get("context", ""), row["reference_response"],
                                   rec["response"])
                    except ValueError as e:
                        stats["judge_failures"] += 1
                        cache.add(sid, v, judge_failed_runs=rec.get("judge_failed_runs", 0) + 1)
                        log(f"  {sid} {v}: {e}")
                        continue
                    stats["judge_calls"] += 1
                    cache.add(sid, v, judgment=asdict(j), judge_version=JUDGE_VERSION)
                    rec = cache.get(sid, v)
                j = rec["judgment"]
                t = rec["target"]
                ok = task_success(cat, row, rec["response"], j.get("answers_correctly"))
                repo.record_evaluation(db, run_name, version, sid, cat, v, target_model, t["input_tokens"],
                                       t["output_tokens"], t["latency_ms"], j["score"], ok)
                db.commit()
                stats["recorded"] += 1
            log(f"[{i}/{len(rows)}] {sid} ({cat}) done")
    except (DailyLimitReached, ModelUnavailable) as e:
        log(f"Stopped: {type(e).__name__}: {str(e)[:200]}\nProgress is saved; run the same command again later.")
        stats["stopped"] = 1
    return stats


def _stale(db: Session, rows: list[dict[str, str]], detector: Any, variants: tuple[str, ...], run_name: str,
           target_model: str, cache: Cache, done: set, stats: dict, log: Callable[[str], None]) -> set:
    """--refresh: recorded items that are out of date. A changed prompt (a Stage B fix) is called and judged again; a
    response longer than the old judge's cut, judged by an older judge version, is judged again from the cached
    response (no target call). Their records are deleted so the run redoes them. Returns the (sid, variant) keys."""
    stale = set()
    for row in rows:
        sid = row["source_id"]
        keys = [v for v in variants if (sid, v) in done]
        if not keys:
            continue
        built = build_variants(row, detector, tuple(keys))
        for v in keys:
            rec = cache.get(sid, v)
            if rec.get("prompt") is not None and rec.get("prompt") != built[v]["prompt"]:
                stats["refreshed_prompt"] = stats.get("refreshed_prompt", 0) + 1
            elif (len(rec.get("response") or "") > OLD_JUDGE_RESPONSE_CHARS
                  and rec.get("judge_version", 1) < JUDGE_VERSION):
                cache.add(sid, v, judgment=None)
                stats["rejudged_long"] = stats.get("rejudged_long", 0) + 1
            else:
                continue
            repo.delete_evaluation(db, run_name, sid, v, target_model)
            stale.add((sid, v))
            log(f"  {sid} {v}: out of date, redone")
    db.commit()
    return stale


# ---------------------------------------------------------------- summary
def _fmt(x: Any, digits: int = 1) -> str:
    return "-" if x is None else f"{float(x):.{digits}f}"


def summary(db: Session, run_name: str, cache: Cache, target_model: str = TARGET_MODEL,
            wrong_references: dict[str, str] | None = None) -> str:
    """The results table. Items excluded after the run are not counted as failures: an item whose reference answer is
    wrong (evaluation/dataset/wrong_references.csv) or that the judge could not score for some variant is left out for ALL
    variants (so every variant is compared on the same items), listed with its reason, and the headline numbers are
    shown with and without the exclusions, with a warning when an exclusion moves one by more than 1 point."""
    from app.reference_check import load_wrong_references

    wrong = load_wrong_references() if wrong_references is None else wrong_references
    in_run = {sid for (sid, _v) in cache.data}
    excluded = {sid: f"wrong reference: {reason}" for sid, reason in wrong.items() if sid in in_run}
    for (sid, v), rec in sorted(cache.data.items()):
        if (sid not in excluded and rec.get("judgment") is None
                and rec.get("judge_failed_runs", 0) >= JUDGE_GIVE_UP_RUNS):
            excluded[sid] = f"judge could not score the {v} response"
    rows = repo.evaluation_summary(db, run_name, exclude_ids=excluded)
    if not rows:
        return f"No results for run `{run_name}` yet."
    extra = defaultdict(lambda: {"reasoning": [], "truncated": 0})
    for (sid, v), rec in cache.data.items():
        if sid in excluded:
            continue
        t = rec.get("target")
        if t:
            key = (rec.get("category"), v)
            if t.get("reasoning_tokens") is not None:
                extra[key]["reasoning"].append(t["reasoning_tokens"])
            extra[key]["truncated"] += t.get("finish_reason") == "length"

    def line(cat: str, v: str, rs: list[dict]) -> str:
        n = sum(r["n"] for r in rs)
        w = lambda k: sum(float(r[k] or 0) * r["n"] for r in rs) / n  # noqa: E731
        checked = sum(r["n_success_checked"] for r in rs)
        succ = (sum(float(r["task_success_rate"] or 0) * r["n_success_checked"] for r in rs) / checked) if checked else None
        cats = CATEGORIES if cat == "all" else [cat]
        reasoning = [x for c in cats for x in extra[(c, v)]["reasoning"]]
        trunc = sum(extra[(c, v)]["truncated"] for c in cats)
        return (f"| {cat} | {v} | {n} | {_fmt(w('avg_quality'))} | "
                f"{'-' if succ is None else f'{100 * succ:.0f}% ({checked})'} | {_fmt(w('avg_input_tokens'), 0)} | "
                f"{_fmt(w('avg_output_tokens'), 0)} | {_fmt(sum(reasoning) / len(reasoning) if reasoning else None, 0)} | "
                f"{_fmt(w('avg_total_tokens'), 0)} | {_fmt(w('avg_latency_ms'), 0)} | {trunc} |")

    out = [f"# Evaluation run `{run_name}`\n",
           f"Target `{target_model}` (temperature 0, max {TARGET_MAX_TOKENS} tokens, reasoning {TARGET_REASONING}); "
           f"judge `{JUDGE_MODEL}`, blind to the variant. Quality 0-10. Task success over checkable items "
           f"(count in brackets). Output tokens include the model's hidden reasoning tokens (shown separately).\n",
           "| category | variant | n | quality | task success | input tok | output tok | of which reasoning | "
           "total tok | latency ms | truncated |", "|" + "---|" * 11]
    by_variant = defaultdict(list)
    for r in rows:
        out.append(line(r["category"], r["variant"], [r]))
        by_variant[r["variant"]].append(r)
    for v in VARIANTS:
        if by_variant.get(v):
            out.append(line("all", v, by_variant[v]).replace("| all |", "| **all** |", 1))
    if excluded:
        out += ["", f"**Excluded after the run** ({len(excluded)} items, left out for ALL variants; not counted above):"]
        out += [f"- `{sid}`: {reason}" for sid, reason in sorted(excluded.items())]
        out += ["", *headline_comparison(repo.evaluation_summary(db, run_name, exclude_ids=excluded),
                                         repo.evaluation_summary(db, run_name))]
    return "\n".join(out) + "\n"


QUALITY_WARN = 0.1        # quality is 0-10: 0.1 is 1 point on a 0-100 scale
SUCCESS_WARN = 0.01       # task success: 1 percentage point


def headline(rows: list[dict]) -> dict[str, dict[str, float | None]]:
    """Per variant over all categories: n, quality, task success, total tokens, latency (weighted like the table)."""
    out = {}
    for v in VARIANTS:
        rs = [r for r in rows if r["variant"] == v]
        n = sum(r["n"] for r in rs)
        if not n:
            continue
        w = lambda k: sum(float(r[k] or 0) * r["n"] for r in rs) / n  # noqa: E731
        checked = sum(r["n_success_checked"] for r in rs)
        succ = sum(float(r["task_success_rate"] or 0) * r["n_success_checked"] for r in rs) / checked if checked else None
        out[v] = {"n": n, "quality": w("avg_quality"), "success": succ, "total_tokens": w("avg_total_tokens"),
                  "latency": w("avg_latency_ms")}
    return out


def headline_comparison(with_ex: list[dict], without_ex: list[dict]) -> list[str]:
    a, b = headline(with_ex), headline(without_ex)
    lines = ["**Headline numbers with and without the exclusions** (all categories)", "",
             "| variant | n with / without | quality with / without | task success with / without | "
             "total tok with / without | latency ms with / without |", "|---|---|---|---|---|---|"]
    warnings = []
    pct = lambda x: "-" if x is None else f"{100 * x:.0f}%"  # noqa: E731
    for v in VARIANTS:
        if v not in b:
            continue
        x, y = a.get(v, {}), b[v]
        lines.append(f"| {v} | {x.get('n', 0)} / {y['n']} | {_fmt(x.get('quality'))} / {_fmt(y['quality'])} | "
                     f"{pct(x.get('success'))} / {pct(y['success'])} | {_fmt(x.get('total_tokens'), 0)} / "
                     f"{_fmt(y['total_tokens'], 0)} | {_fmt(x.get('latency'), 0)} / {_fmt(y['latency'], 0)} |")
        if x.get("quality") is not None and abs(x["quality"] - y["quality"]) > QUALITY_WARN:
            warnings.append(f"{v} quality {y['quality']:.2f} -> {x['quality']:.2f}")
        if x.get("success") is not None and y["success"] is not None and abs(x["success"] - y["success"]) > SUCCESS_WARN:
            warnings.append(f"{v} task success {100 * y['success']:.1f}% -> {100 * x['success']:.1f}%")
    lines.append("")
    if warnings:
        lines.append("**Warning: the exclusions change headline numbers by more than 1 point** (quality: more than "
                     "0.1 on the 0-10 scale; task success: more than 1 percentage point): " + "; ".join(warnings) + ".")
    else:
        lines.append("The exclusions change no headline number by more than 1 point (quality: 0.1 on the 0-10 scale; "
                     "task success: 1 percentage point).")
    return lines


# ---------------------------------------------------------------- CLI
TARGETS = {"groq": TARGET_MODEL, "cerebras": "cerebras/gpt-oss-120b"}


def check_final_once(db: Session, run_name: str, version: str) -> None:
    """A final run may be resumed (same dataset version), never repeated on another dataset version."""
    versions = set(db.scalars(select(EvaluationRun.dataset_version).where(EvaluationRun.run_name == run_name)))
    if versions and versions != {version}:
        raise SystemExit(f"{run_name} already has results for dataset {sorted(versions)}; the final numbers are "
                         f"run once. Current dataset: {version}.")


def make_llm(target: str) -> Any:
    """Groq for the judge (and the target unless target is "cerebras"), all recorded in the usage ledgers."""
    from app.llm_router import Router

    groq = GroqChat(ledger=UsageLedger(), tag="evaluation")
    if target != "cerebras":
        return groq
    from app.cerebras import CerebrasChat
    from app.config import BACKEND_DIR

    return Router(groq, CerebrasChat(ledger=UsageLedger(BACKEND_DIR.parent / "data" / "cerebras_usage.json"),
                                     tag="evaluation"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dataset", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--split", default="val", choices=["val", "test", "benchmark"])
    ap.add_argument("--final", action="store_true", help="required for test/benchmark (final numbers, run once)")
    ap.add_argument("--per-category", type=int, default=5)
    ap.add_argument("--run-name", help="default: dev-<split>-n<per-category>")
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=list(VARIANTS))
    ap.add_argument("--max-tokens", type=int, default=TARGET_MAX_TOKENS)
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--refresh", action="store_true",
                    help="redo recorded items whose prompt changed, and re-judge long responses judged by an older "
                         "judge version (dev runs only)")
    ap.add_argument("--target", choices=["groq", "cerebras"], default="groq",
                    help="provider of the target gpt-oss-120b (same model); the judge is always Groq's qwen")
    args = ap.parse_args()
    if args.split in FINAL_SPLITS and not args.final:
        raise SystemExit(f"{args.split} is held out for the final numbers; develop on val (or pass --final, once).")
    if args.refresh and args.final:
        raise SystemExit("--refresh is for dev runs; final numbers are run once")
    target_model = TARGETS[args.target]

    from app.db.base import SessionLocal

    run_name = args.run_name or (f"final-{args.split}" if args.final else f"dev-{args.split}-n{args.per_category}")
    cache = Cache(EVAL_DIR / f"{run_name}.jsonl")
    with SessionLocal() as db:
        if not args.summary_only:
            from app.stage_a.detector import FeatureDetector

            all_rows = load_rows(args.dataset)
            version = dataset_version(args.dataset, all_rows)
            if args.final:
                check_final_once(db, run_name, version)
            rows = select_rows([r for r in all_rows if r["split"] == args.split], args.per_category)
            print(f"Run {run_name}: {len(rows)} prompts x {len(args.variants)} variants on {args.split}, "
                  f"target {target_model}")
            llm = make_llm(args.target)
            stats = run(db, rows, llm, FeatureDetector(), run_name, version, cache, tuple(args.variants),
                        args.max_tokens, target_model=target_model, refresh=args.refresh)
            print("Stats:", stats)
        text = summary(db, run_name, cache, target_model)
    print(text)
    (EVAL_DIR / f"{run_name}_summary.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
