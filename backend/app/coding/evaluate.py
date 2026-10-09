"""Pass rate of the target model's code for degraded vs Stage B prompts, on the tested Python coding items.

    python -m app.coding.evaluate --out ../evaluation/coding/coding_tests.md      # after python -m app.coding.testgen

Target: cerebras/gpt-oss-120b, temperature 0, reasoning "low", max 2048 tokens, one user message: exactly the
settings of the final benchmark run (app.evaluation.run). pass@1 = the one answer passes every validated test.
Test split: the target is called here (cached in data/coding/target.jsonl). Benchmark split: the answers cached by the
final benchmark run (data/evaluation/final-benchmark.jsonl) are reused, nothing is called again.

Outcome per answer:
  pass          passes every test, calling the function the tests call
  naming-only   fails as asked only because the function has another name: passes once the tests' name is bound to
                the answer's single top-level function
  wrong         runs, but fails at least one test (also after renaming)
  error         the code does not import / crashes / times out
  ambiguous     several top-level functions, none with the tests' name: naming cannot be resolved automatically
                (could be a naming-only failure or a real one; not guessed)
  no function   Python code, but no function the tests could call (e.g. a bare snippet)
  no Python     no Python code in the answer (prose, another language)
"""
import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from app.coding.harness import extract_code, run_function_tests, run_stdout_test
from app.coding.sandbox import sandbox_kind
from app.coding.testgen import OUT_DIR, definitions_only
from app.config import BACKEND_DIR
from app.dataset_io import load_rows
from app.evaluation.run import TARGET_MAX_TOKENS, TARGET_REASONING, Cache
from app.evaluation.variants import build_variants

TARGET = "cerebras/gpt-oss-120b"
VARIANTS = ("degraded", "stage_b")
BENCHMARK_CACHE = BACKEND_DIR.parent / "data" / "evaluation" / "final-benchmark.jsonl"
OUTCOMES = ("pass", "naming-only", "wrong", "error", "ambiguous", "no function", "no Python")


def outcome(run) -> str:
    if run.status == "passed":
        return "naming-only" if run.renamed else "pass"
    if run.status == "failed":
        return "wrong"
    if run.status in ("import_error", "timeout", "crash"):
        return "error"
    if run.status == "ambiguous":
        return "ambiguous"
    return "no Python" if run.detail == "no code found" else "no function"


def judge_answer(item: dict, response: str) -> dict:
    if item["mode"] == "stdout":
        code = extract_code(response)
        run = run_stdout_test(code, item["expected_stdout"])
    else:
        code = extract_code(response, item["entry"])
        run = run_function_tests(definitions_only(code) if code else "", item["tests"], item["entry"])
    return {"outcome": outcome(run), "passed": run.passed, "total": run.total, "renamed": run.renamed,
            "status": run.status, "detail": run.detail[:200], "code_chars": len(code)}


def truncated(items: list[dict]) -> set[tuple[str, str]]:
    """(source_id, variant) whose answer stopped at the token limit (finish_reason "length")."""
    out = set()
    for path, split in ((OUT_DIR / "target.jsonl", "test"), (BENCHMARK_CACHE, "benchmark")):
        cache = Cache(path)
        for i in items:
            for v in VARIANTS:
                if i["split"] == split and (cache.get(i["source_id"], v).get("target") or {}).get("finish_reason") \
                        == "length":
                    out.add((i["source_id"], v))
    return out


def answers(items: list[dict], llm, detector, log=print) -> dict[tuple[str, str], str]:
    """{(source_id, variant): response}. Test: called (cached); benchmark: from the final benchmark cache."""
    out = {}
    bench = Cache(BENCHMARK_CACHE)
    cache = Cache(OUT_DIR / "target.jsonl")
    rows = {r["source_id"]: r for s in ("test", "benchmark") for r in load_rows(split=s)}
    for i, item in enumerate(items, 1):
        row = rows[item["source_id"]]
        built = build_variants(row, detector, VARIANTS)
        for v in VARIANTS:
            src = bench if item["split"] == "benchmark" else cache
            rec = src.get(item["source_id"], v)
            if rec.get("response") is not None and rec.get("prompt") != built[v]["prompt"]:
                raise SystemExit(f"{item['source_id']} {v}: cached prompt differs from today's; Stage B changed?")
            if rec.get("response") is None:
                if item["split"] == "benchmark":
                    raise SystemExit(f"{item['source_id']} {v}: not in the final benchmark cache")
                if llm is None:
                    from app.coding.testgen import make_llm
                    llm = make_llm()
                c = llm.complete(TARGET, [{"role": "user", "content": built[v]["prompt"]}],
                                 max_tokens=TARGET_MAX_TOKENS, temperature=0.0, reasoning_effort=TARGET_REASONING)
                cache.add(item["source_id"], v, prompt=built[v]["prompt"], response=c.content, target=asdict(c))
                rec = cache.get(item["source_id"], v)
            out[(item["source_id"], v)] = rec["response"]
        log(f"[{i}/{len(items)}] {item['source_id']} answers ready")
    return out


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.1f}%)" if b else "-"


def report(all_items: list[dict], tested: list[dict], results: dict, cut: set | None = None) -> str:
    cut = cut or set()
    lines = ["# Coding test cases and pass rate\n",
             f"Sandbox: **{sandbox_kind()}** (`app/coding/sandbox.py`). Target `{TARGET}` (temperature 0, reasoning "
             f"\"{TARGET_REASONING}\", max {TARGET_MAX_TOKENS} tokens), the settings of the final benchmark run. Test "
             "generator: the same model (`app/coding/testgen.py`), every test validated on the CodeAlpaca reference. "
             "Stage A/B are frozen at `final-for-test`.\n"]
    # scope
    lines += ["## 1. Scope\n", "| split | coding items | Python | of which tested | reference suspect | untestable |",
              "|---|---|---|---|---|---|"]
    for split in ("test", "benchmark"):
        its = [i for i in all_items if i["split"] == split]
        py = [i for i in its if i["mode"] != "not_python"]
        t = [i for i in tested if i["split"] == split]
        sus = [i for i in py if i.get("reference_suspect")]
        unt = [i for i in py if i["mode"] == "untestable"]
        lines.append(f"| {split} | {len(its)} | {len(py)} | {len(t)} | {len(sus)} | {len(unt)} |")
    langs = Counter(i.get("language", "?") for i in all_items if i["mode"] == "not_python" and i["split"] == "test")
    lines += ["", "Other languages on test (not run): " + ", ".join(f"{k} {v}" for k, v in langs.most_common()) + ".\n"]
    modes = Counter(i["mode"] for i in tested)
    ntests = [len(i["tests"]) for i in tested if i["mode"] == "function"]
    lines += [f"Tested items: {modes.get('function', 0)} function items ({sum(ntests)} validated asserts, "
              f"{min(ntests, default=0)}-{max(ntests, default=0)} per item) and {modes.get('stdout', 0)} script "
              "items (output must equal the reference's).\n"]
    # pass rate
    lines += ["## 2. Pass rate (pass@1)\n",
              "`strict` = passes calling the function by the name the tests use; `lenient` = also counts answers that "
              "pass once the tests' name is bound to the answer's single top-level function (naming-only "
              "failures).\n", "| split | variant | n | pass@1 strict | pass@1 lenient | " + " | ".join(OUTCOMES) + " |",
              "|---|---|---|---|---|" + "---|" * len(OUTCOMES)]
    for split in ("test", "benchmark"):
        ids = [i["source_id"] for i in tested if i["split"] == split]
        for v in VARIANTS:
            oc = Counter(results[(sid, v)]["outcome"] for sid in ids)
            n = len(ids)
            lines.append(f"| {split} | {v} | {n} | **{_pct(oc['pass'], n)}** | {_pct(oc['pass'] + oc['naming-only'], n)} "
                         "| " + " | ".join(str(oc[o]) for o in OUTCOMES) + " |")
    test_ids = [i["source_id"] for i in tested if i["split"] == "test"]
    both = Counter((results[(s, 'degraded')]["outcome"] == "pass", results[(s, 'stage_b')]["outcome"] == "pass")
                   for s in test_ids)
    for split in ("test", "benchmark"):
        ids = [i["source_id"] for i in tested if i["split"] == split]
        parts = []
        for v in VARIANTS:
            hit = [sid for sid in ids if (sid, v) in cut]
            if hit:
                detail = ", ".join(f"{sid} -> {results[(sid, v)]['outcome']}" for sid in hit)
                parts.append(f"{v} {len(hit)} ({detail})")
        if parts:
            lines.append(f"\n{split.capitalize()}: answers cut off at the {TARGET_MAX_TOKENS}-token limit (it "
                         "includes the model's hidden reasoning; the same limit as the benchmark run): "
                         + "; ".join(parts) + ".")
    lines += ["", f"Test, paired (strict): both pass {both[(True, True)]}, only Stage B passes {both[(False, True)]}, "
              f"only degraded passes {both[(True, False)]}, neither {both[(False, False)]}.\n"]
    # naming
    count = lambda v, o: sum(results[(s, v)]["outcome"] == o for s in test_ids)  # noqa: E731
    lines += ["### Failures: naming-only vs real (test)\n",
              "`real` = wrong + error + no function + no Python; `undetermined` = ambiguous (several functions under "
              "other names; not guessed).\n",
              "| variant | failures (strict) | naming-only | undetermined | real |", "|---|---|---|---|---|"]
    for v in VARIANTS:
        fails = sum(results[(s, v)]["outcome"] != "pass" for s in test_ids)
        real = sum(count(v, o) for o in ("wrong", "error", "no function", "no Python"))
        lines.append(f"| {v} | {fails} | {count(v, 'naming-only')} | {count(v, 'ambiguous')} | {real} |")
    # per item
    lines += ["", "## 3. Per item\n", "| split | item | mode | tests | degraded | Stage B | instruction |",
              "|---|---|---|---|---|---|---|"]
    for i in tested:
        cells = []
        for v in VARIANTS:
            r = results[(i["source_id"], v)]
            cells.append(f"{r['outcome']} ({r['passed']}/{r['total']})" + (f", as `{r['renamed']}`" if r["renamed"]
                                                                          else ""))
        lines.append(f"| {i['split']} | {i['source_id']} | {i['mode']} | {len(i['tests'])} | {cells[0]} | {cells[1]} | "
                     f"{i['instruction'][:70].replace('|', '/')} |")
    # suspects and untestable
    lines += ["", "## 4. Reference suspects (kept and reported, not dropped)\n", "| split | item | reason | instruction |",
              "|---|---|---|---|"]
    lines += [f"| {i['split']} | {i['source_id']} | {i['suspect_reason'][:120].replace('|', '/')} | "
              f"{i['instruction'][:70].replace('|', '/')} |" for i in all_items if i.get("reference_suspect")]
    lines += ["", "## 5. Untestable Python items\n", "| split | item | reason |", "|---|---|---|"]
    lines += [f"| {i['split']} | {i['source_id']} | {i['reason']} |" for i in all_items if i["mode"] == "untestable"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    from app.stage_a.detector import FeatureDetector
    all_items = json.loads((OUT_DIR / "items.json").read_text(encoding="utf-8"))
    tested = [i for i in all_items if i["mode"] in ("function", "stdout") and i.get("tests")
              and not i.get("reference_suspect")]
    resp = answers(tested, None, FeatureDetector())
    results = {k: judge_answer(next(i for i in tested if i["source_id"] == k[0]), r) for k, r in resp.items()}
    (OUT_DIR / "results.json").write_text(json.dumps({f"{k[0]}/{k[1]}": v for k, v in results.items()}, indent=1),
                                          encoding="utf-8")
    text = report(all_items, tested, results, truncated(tested))
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
