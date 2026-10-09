"""The correctness suite's cases (evaluation/correctness_suite/cases.jsonl) and their automatic validation.

    python -m app.correctness.cases            # validate; writes evaluation/correctness_suite/validation.md

Automatic checks, per case (a case that fails any of them is reported; the suite is not run until all pass):
* schema: required fields; 10 cases per category; unique ids
* no duplicates: no two cases share a vague prompt, and no two materials are near-copies (word 5-gram overlap)
* new, not from the training data: no vague prompt equals a dataset prompt, and no material shares 3 or more word
  8-grams with the dataset's contexts, prompts or references (all 5,184 rows of v1.2 final, every split); the few
  shared 8-grams (code idioms) are listed in the report
* the gold answer is derivable from the material:
    closed_qa              evidence strings present; `compute` (arithmetic over the material's numbers) gives the
                           gold; otherwise a gold form appears in the material
    information_extraction every gold item's evidence and every distractor appear in the material (closed world)
    classification         every item appears in the material; gold labels are from the label set; `rule` (if any)
                           recomputes each label from `compute`
    summarization          every key fact's evidence appears in the material; 3-5 key facts, 2 forbidden, a limit
    coding                 the reference solution passes all of its own asserts in the sandbox; 5-8 asserts
* privacy: the material passes the app's PII scrubber unchanged (so the UI path stores exactly what was tested)
The leak check (the optimizer must not put the gold answer into the optimized prompt) needs the prompts:
app.correctness.prompts.
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

from app.config import BACKEND_DIR
from app.correctness.checks import find, normalize

SUITE_DIR = BACKEND_DIR.parent / "evaluation" / "correctness_suite"
CASES = SUITE_DIR / "cases.jsonl"
CATEGORIES = ["closed_qa", "information_extraction", "classification", "summarization", "coding"]
REQUIRED = ("id", "category", "scenario", "difficulty", "material", "vague_prompt", "gold", "check")
DIFFICULTIES = {"distractor", "calculation", "edge case", "ambiguous item", "open format"}
MAX_SHARED_8GRAMS = 3        # one or two shared 8-grams are idioms ("for i in range n for j in"), listed in the report
SAFE = {"min": min, "max": max, "round": round, "abs": abs, "ceil": math.ceil, "floor": math.floor}


def load_cases(path: Path = CASES) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def by_id(cases: list[dict]) -> dict[str, dict]:
    return {c["id"]: c for c in cases}


def _compute(expr: str, **names):
    return eval(expr, {"__builtins__": {}}, {**SAFE, **names})      # author-written expressions in a committed file


def _num(text: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", normalize(text))
    return float(m.group()) if m else None


def _in(s: str, material: str) -> bool:
    return normalize(s) in normalize(material)


def check_derivable(c: dict) -> list[str]:
    cat, chk, g, mat = c["category"], c["check"], c["gold"], c["material"]
    errs = []
    for ev in c.get("evidence", []) if isinstance(c.get("evidence"), list) else []:
        if not _in(ev, mat):
            errs.append(f"evidence not in material: {ev!r}")
    if cat == "closed_qa":
        if "compute" in chk:
            v = _compute(chk["compute"])
            ok = (v == g) if isinstance(v, str) else (_num(g) is not None and abs(_num(g) - v) < 1e-6)
            if not ok:
                errs.append(f"compute gives {v!r}, gold is {g!r}")
        elif not find(chk["aliases"], mat):
            errs.append("no gold form in the material and no compute")
        if not find(chk["aliases"], g):
            errs.append("gold does not match its own aliases")
        if find(chk["distractors"], g):
            errs.append("gold matches a distractor")
    elif cat == "information_extraction":
        for item in g:
            ev = (c.get("evidence") or {}).get(item)
            if not ev or not _in(ev, mat):
                errs.append(f"gold item {item!r}: evidence missing from material")
            if not find(chk["aliases"][item], item) and not find(chk["aliases"][item], ev or ""):
                errs.append(f"gold item {item!r}: aliases match neither the item nor its evidence")
        for d, al in chk["distractors"].items():
            if not find(al, mat):
                errs.append(f"distractor {d!r} not in material")
            if any(find(al, item) for item in g):
                errs.append(f"distractor {d!r} matches a gold item")
    elif cat == "classification":
        for k in g:
            if not any(find([a], mat) for a in chk["items"].get(k, [])):
                errs.append(f"item {k!r} not in material")
            if g[k] not in chk["labels"]:
                errs.append(f"item {k!r}: gold label {g[k]!r} not in the label set")
        if not 6 <= len(g) <= 10:
            errs.append(f"{len(g)} items (6-10 expected)")
        if "rule" in chk:
            for k, p in chk["compute"].items():
                lab = _compute(chk["rule"], p=p)
                if lab != g[k]:
                    errs.append(f"item {k!r}: rule gives {lab!r}, gold is {g[k]!r}")
    elif cat == "summarization":
        if not 3 <= len(g["key_facts"]) <= 5 or len(g["forbidden"]) != 2 or not g.get("max_words"):
            errs.append("needs 3-5 key facts, 2 forbidden statements and max_words")
        for k in g["key_facts"]:
            if not _in(k["evidence"], mat):
                errs.append(f"key fact evidence not in material: {k['evidence']!r}")
    elif cat == "coding":
        from app.coding.harness import run_function_tests
        if not 5 <= len(g["tests"]) <= 8:
            errs.append(f"{len(g['tests'])} asserts (5-8 expected)")
        if g["function"] not in mat:
            errs.append(f"function name {g['function']!r} not in the material")
        run = run_function_tests(g["reference"], g["tests"], g["function"])
        if not run.all_passed:
            errs.append(f"reference fails its own asserts: {run.status} {run.passed}/{run.total} {run.detail}")
    return errs


def _grams(text: str, n: int) -> set[tuple[str, ...]]:
    w = re.findall(r"\w+", normalize(text))
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def check_suite(cases: list[dict], dataset_rows: list[dict] | None = None) -> dict:
    """{"cases": {id: [errors]}, "suite": [errors], "overlap": {...}} for the whole suite."""
    from app.db.pii import scrub_pii
    per: dict[str, list[str]] = {}
    suite: list[str] = []
    ids = Counter(c.get("id") for c in cases)
    suite += [f"duplicate id {i}" for i, n in ids.items() if n > 1]
    cats = Counter(c.get("category") for c in cases)
    suite += [f"{cat}: {cats.get(cat, 0)} cases (10 expected)" for cat in CATEGORIES if cats.get(cat, 0) != 10]
    prompts = Counter(normalize(c["vague_prompt"]).strip() for c in cases)
    suite += [f"duplicate vague prompt {p!r}" for p, n in prompts.items() if n > 1]
    grams = {c["id"]: _grams(c["material"], 5) for c in cases}
    for i, a in enumerate(cases):
        for b in cases[i + 1:]:
            ga, gb = grams[a["id"]], grams[b["id"]]
            if ga and gb and len(ga & gb) / min(len(ga), len(gb)) > 0.5:
                suite.append(f"materials of {a['id']} and {b['id']} are near-duplicates")
    for c in cases:
        errs = [f"missing field {k}" for k in REQUIRED if k not in c]
        if errs:
            per[c.get("id", "?")] = errs
            continue
        if not set(c["difficulty"]) or not set(c["difficulty"]) <= DIFFICULTIES:
            errs.append(f"difficulty must be from {sorted(DIFFICULTIES)}")
        if scrub_pii(c["material"])[0] != c["material"] or scrub_pii(c["vague_prompt"])[0] != c["vague_prompt"]:
            errs.append("material or prompt changed by the PII scrubber")
        errs += check_derivable(c)
        per[c["id"]] = errs
    overlap = None
    if dataset_rows is not None:
        seen_prompts = {normalize(r["degraded_prompt"]).strip() for r in dataset_rows}
        ds_grams: set = set()
        for r in dataset_rows:
            for f in ("context", "degraded_prompt", "optimized_prompt", "reference_response", "original_instruction"):
                ds_grams |= _grams(r.get(f) or "", 8)
        overlap = {}
        for c in cases:
            g8 = _grams(c["material"] + "\n" + c["vague_prompt"], 8)
            shared = g8 & ds_grams
            overlap[c["id"]] = sorted(" ".join(g) for g in shared)
            if normalize(c["vague_prompt"]).strip() in seen_prompts:
                per[c["id"]].append("vague prompt is a dataset prompt")
            if len(shared) >= MAX_SHARED_8GRAMS:
                per[c["id"]].append(f"shares {len(shared)} word 8-gram(s) with the dataset, e.g. {' '.join(next(iter(shared)))!r}")
    return {"cases": per, "suite": suite, "overlap": overlap, "n_dataset_rows": len(dataset_rows or [])}


def validation_markdown(res: dict, cases: list[dict], leaks: dict | None) -> str:
    bad = {k: v for k, v in res["cases"].items() if v}
    leak_bad = {k: v for k, v in (leaks or {}).items() if v}
    lines = ["# Correctness suite: automatic validation\n",
             "Generated by `python -m app.correctness.cases` (leak check: `python -m app.correctness.prompts`).\n",
             f"- Cases: {len(cases)} ({', '.join(f'{c}: {sum(x['category'] == c for x in cases)}' for c in CATEGORIES)})",
             f"- Suite-level problems: {len(res['suite'])}" + "".join(f"\n  - {e}" for e in res["suite"]),
             f"- Cases failing a check: {len(bad)} of {len(cases)}"]
    if res["overlap"] is not None:
        lines.append(f"- Not from the training data: compared with all {res['n_dataset_rows']:,} rows of the dataset "
                     f"(every split): no vague prompt equals a dataset prompt; cases sharing any word 8-gram with the "
                     f"dataset: {sum(1 for v in res['overlap'].values() if v)}"
                     + "".join(f"\n  - {k}: " + "; ".join(repr(g) for g in v) for k, v in res["overlap"].items() if v))
    else:
        lines.append("- Not from the training data: NOT CHECKED (dataset CSV not found)")
    lines.append(f"- Leak check (gold answer in the optimized request but not in the vague prompt): "
                 + ("not run yet" if leaks is None else f"{len(leak_bad)} case(s) leak"))
    lines += ["", "| check | what it verifies |", "|---|---|",
              "| derivable | closed_qa: evidence present and `compute` gives the gold; extraction: every gold item and "
              "distractor is in the material; classification: items present, labels from the set, the attendance "
              "rule recomputed; summarization: every key fact's evidence present; coding: the reference passes all "
              "its own asserts in the bubblewrap sandbox |",
              "| duplicates | ids, vague prompts, materials (word 5-gram overlap > 50%) |",
              "| privacy | material and prompt unchanged by the app's PII scrubber |",
              "| leak | no gold form appears in the optimized request (the prompt without the pasted material) unless it "
              "was already in the vague prompt; Stage C's patch included |", ""]
    if bad or leak_bad:
        lines.append("## Problems\n")
        for k, v in {**bad, **{f'{k} (leak)': v for k, v in leak_bad.items()}}.items():
            lines += [f"- **{k}**: " + "; ".join(v)]
    else:
        lines.append("All automatic checks pass for all cases.")
    return "\n".join(lines) + "\n"


def main() -> None:
    import argparse
    from app.dataset_io import DEFAULT_CSV, load_rows
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=SUITE_DIR / "validation.md")
    args = ap.parse_args()
    cases = load_cases()
    rows = load_rows(DEFAULT_CSV) if DEFAULT_CSV.exists() else None
    res = check_suite(cases, rows)
    prompts = SUITE_DIR / "prompts.json"
    leaks = ({k: v["leaks"] for k, v in json.loads(prompts.read_text())["cases"].items()} if prompts.exists() else None)
    args.out.write_text(validation_markdown(res, cases, leaks), encoding="utf-8")
    bad = {k: v for k, v in res["cases"].items() if v}
    for k, v in bad.items():
        print(k, v)
    for e in res["suite"]:
        print("suite:", e)
    print(f"{len(cases)} cases, {len(bad)} failing, suite problems {len(res['suite'])}; wrote {args.out}")
    raise SystemExit(1 if bad or res["suite"] else 0)


if __name__ == "__main__":
    main()
