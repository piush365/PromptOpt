"""Coding items and their tests: which items can be tested, LLM-generated assert tests, validation on the reference.

    python -m app.coding.testgen                 # test + benchmark Python items -> data/coding/items.json

Per Python coding item (CodeAlpaca reference parses as Python and the instruction asks for no other language; a
Python task whose reference does not parse is listed as a reference suspect):
* function  the reference defines top-level functions: Cerebras gpt-oss-120b writes 3-6 assert tests calling the
            function the instruction is about; every test runs against the reference in the sandbox and only tests
            that pass are kept. When none passes, one retry shows the model the failures and allows short
            multi-line tests. If the reference itself fails (does not import) or still no test passes on it, the
            item is flagged `reference_suspect` (reference and tests disagree: either may be wrong), never dropped
            silently.
* stdout    no function, but the reference prints: the test is "prints the same as the reference" (the reference is
            run twice; different outputs, or a reference that uses the clock or randomness = untestable). No LLM
            needed.
* untestable  third-party packages / network, interactive (input()), or no function and no output (a bare value
            or fragment).
LLM answers are cached in data/coding/testgen.jsonl, so reruns cost nothing.
"""
import argparse
import ast
import json
import sys
from pathlib import Path

from app.coding.harness import normalize_output, run_function_tests, top_level_functions
from app.coding.sandbox import run_python
from app.config import BACKEND_DIR
from app.dataset_io import load_rows
from app.reference_check import languages_seen, language_asked, strip_fences

OUT_DIR = BACKEND_DIR.parent / "data" / "coding"
GEN_MODEL = "cerebras/gpt-oss-120b"
GEN_MAX_TOKENS = 3000
MIN_TESTS, MAX_TESTS = 3, 6
BUDGET_FRACTION = 0.7                      # stay within this share of Cerebras' 1M tokens/day


# ---------------------------------------------------------------- which items, which mode
def is_python_item(row: dict[str, str]) -> bool:
    code = strip_fences(row["reference_response"])
    try:
        ast.parse(code)
    except SyntaxError:
        return False
    return language_asked(row["original_instruction"]) in (None, "python") and not (languages_seen(code) - {"python"})


def looks_like_python(row: dict[str, str]) -> bool:
    """A Python task whose reference does not parse: the instruction asks for Python, or names no language while the
    reference shows only Python signs."""
    asked = language_asked(row["original_instruction"])
    seen = languages_seen(strip_fences(row["reference_response"]))
    return asked == "python" or (asked is None and seen == {"python"})


def third_party(code: str) -> list[str]:
    mods = set()
    for n in ast.walk(ast.parse(code)):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            mods.add(n.module.split(".")[0])
    return sorted(m for m in mods if m not in sys.stdlib_module_names)


def calls(code: str, name: str) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name
               for n in ast.walk(ast.parse(code)))


def prints(code: str) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"
               for n in ast.walk(ast.parse(code)))


def definitions_only(code: str) -> str:
    """Top-level imports, functions, classes and assignments only: demo code (prints, input(), loops) is dropped, so
    importing the code for the tests does not run it. Applied to reference and candidates alike."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    keep = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign,
            ast.AnnAssign)
    tree.body = [n for n in tree.body if isinstance(n, keep)]
    return ast.unparse(tree)


def classify(row: dict[str, str]) -> dict:
    code = strip_fences(row["reference_response"])
    item = {"source_id": row["source_id"], "split": row["split"], "id": row["id"],
            "instruction": row["original_instruction"], "degraded_prompt": row["degraded_prompt"],
            "context": row["context"], "reference": code,
            "functions": top_level_functions(code)}
    if mods := third_party(code):
        return {**item, "mode": "untestable", "reason": "needs packages outside the standard library: " + ", ".join(mods)}
    if calls(code, "input"):
        return {**item, "mode": "untestable", "reason": "interactive: the reference reads input()"}
    if item["functions"]:
        return {**item, "mode": "function"}
    if prints(code):
        return {**item, "mode": "stdout"}
    return {**item, "mode": "untestable", "reason": "no function and no printed output (a value or fragment)"}


# ---------------------------------------------------------------- test generation
SYSTEM = ("You write unit tests for small Python coding tasks. Answer with JSON only: "
          '{"function": "<name of the function to test>", "tests": ["assert ...", ...]}.')


def gen_messages(item: dict) -> list[dict[str, str]]:
    ctx = f"\nInput given with the task:\n{item['context']}\n" if item["context"].strip() else ""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": (
        f"Task: {item['instruction']}\n{ctx}\nReference solution:\n```python\n{item['reference']}\n```\n\n"
        f"Write {MIN_TESTS} to {MAX_TESTS} tests for the function the task asks for (one of: "
        f"{', '.join(item['functions'])}). Rules: each test is ONE line starting with `assert` and calling that "
        "function by name; test the behaviour the task describes (not quirks of the reference); include at least "
        "one edge case; deterministic; standard library only; no printing, files, input() or network; compare "
        "floats with round() or math.isclose (import math inside the line is not allowed, so prefer round()); if "
        "the function prints instead of returning, test only what it returns.")}]


def retry_messages(item: dict, first: dict) -> list[dict[str, str]]:
    """Second attempt when no first-attempt test passed on the reference: show the failures, allow short multi-line
    tests (set-up lines, then asserts), e.g. to build a linked list or call a function that writes a file."""
    failures = "\n".join(f"- {d['test'][:300]}\n  -> {d['error'][:200]}" for d in first.get("dropped", [])[:MAX_TESTS])
    msgs = gen_messages(item)
    msgs[1]["content"] += (
        f"\n\nA first attempt produced tests that all fail on the reference solution:\n{failures}\n\nWrite new "
        "tests that check the task's behaviour through the reference's actual interface (its parameters, return "
        "value, or the object it changes in place). Each test may now be a short snippet of several lines (set-up "
        "statements, then one or more asserts), as one JSON string with \\n line breaks; it must still contain an "
        "assert and must not read input or use the network.")
    return msgs


def parse_generation(content: str, functions: list[str]) -> tuple[str | None, list[str]]:
    try:
        obj = json.loads(content)
    except json.JSONDecodeError:
        return None, []
    fn = obj.get("function") if isinstance(obj, dict) else None
    fn = fn if fn in functions else (functions[0] if len(functions) == 1 else None)
    tests = [t.strip() for t in (obj.get("tests") or []) if isinstance(t, str) and "assert" in t]
    tests = [t for t in tests if _compiles(t)]
    return fn, tests[:MAX_TESTS]


def _compiles(src: str) -> bool:
    try:
        compile(src, "<test>", "exec")
        return True
    except SyntaxError:
        return False


class GenCache:
    def __init__(self, path: Path):
        self.path, self.data = path, {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.data[rec["source_id"]] = rec

    def add(self, rec: dict) -> None:
        self.data[rec["source_id"]] = rec
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def make_llm():
    from app.cerebras import CerebrasChat
    from app.groq_budget import UsageLedger
    from app.llm_router import Router
    return Router(None, CerebrasChat(ledger=UsageLedger(BACKEND_DIR.parent / "data" / "cerebras_usage.json"),
                                     tag="coding"))


def within_budget() -> bool:
    from app.groq_budget import UsageLedger
    used = UsageLedger(BACKEND_DIR.parent / "data" / "cerebras_usage.json").used(GEN_MODEL)["tokens"]
    return used < BUDGET_FRACTION * 1_000_000


def generate(item: dict, llm, cache: GenCache, retry_of: dict | None = None) -> dict:
    """One cached generation; `retry_of` (the first attempt's validation) makes it the second attempt."""
    key = item["source_id"] + ("#retry" if retry_of else "")
    if key not in cache.data:
        if not within_budget():
            raise SystemExit(f"Cerebras usage would exceed {BUDGET_FRACTION:.0%} of the daily limit; rerun later "
                             "(cached items are kept).")
        msgs = retry_messages(item, retry_of) if retry_of else gen_messages(item)
        c = llm.complete(GEN_MODEL, msgs, max_tokens=GEN_MAX_TOKENS, temperature=0.0, reasoning_effort="low",
                         json_mode=True)
        cache.add({"source_id": key, "content": c.content, "model": c.model,
                   "input_tokens": c.input_tokens, "output_tokens": c.output_tokens})
    return cache.data[key]


# ---------------------------------------------------------------- validation on the reference
def validate_function_item(item: dict, content: str) -> dict:
    fn, tests = parse_generation(content, item["functions"])
    out = {**item, "entry": fn, "generated": tests}
    if fn is None:
        return {**out, "tests": [], "reference_suspect": True, "suspect_reason": "no usable function name/tests"}
    ref = definitions_only(item["reference"])
    run = run_function_tests(ref, tests, fn)
    if run.status == "import_error" or run.status in ("timeout", "crash"):
        return {**out, "tests": [], "reference_suspect": True,
                "suspect_reason": f"reference fails on its own: {run.detail}"}
    kept = [t for t, r in zip(tests, run.results) if r["ok"]]
    dropped = [{"test": t, "error": r.get("error", "")} for t, r in zip(tests, run.results) if not r["ok"]]
    out.update(tests=kept, dropped=dropped)
    if not kept:
        out.update(reference_suspect=True, suspect_reason="no generated test passes on the reference")
    else:
        out.update(reference_suspect=False)
    return out


NONDETERMINISTIC = {"datetime", "time", "random", "uuid", "secrets"}


def imports(code: str) -> set[str]:
    mods = set()
    for n in ast.walk(ast.parse(code)):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    return mods


def validate_stdout_item(item: dict) -> dict:
    if clock := imports(item["reference"]) & NONDETERMINISTIC:
        return {**item, "mode": "untestable",
                "reason": f"output depends on the clock or randomness ({', '.join(sorted(clock))})"}
    runs = [run_python({"main.py": item["reference"]}, timeout=10) for _ in range(2)]
    if runs[0].status != "ok":
        return {**item, "reference_suspect": True, "tests": [],
                "suspect_reason": f"reference fails on its own: {(runs[0].stderr.strip().splitlines() or [runs[0].status])[-1][:200]}"}
    a, b = normalize_output(runs[0].stdout), normalize_output(runs[1].stdout)
    if a != b:
        return {**item, "mode": "untestable", "reason": "nondeterministic output (differs between two runs)"}
    if not a:
        return {**item, "mode": "untestable", "reason": "the reference prints nothing"}
    return {**item, "reference_suspect": False, "expected_stdout": runs[0].stdout, "tests": ["stdout == reference"]}


def build(splits=("test", "benchmark"), llm=None) -> list[dict]:
    rows = [r for s in splits for r in load_rows(split=s) if r["category"] == "coding"]
    cache = GenCache(OUT_DIR / "testgen.jsonl")
    items = []
    for r in rows:
        if not is_python_item(r) and looks_like_python(r):
            items.append({"source_id": r["source_id"], "split": r["split"], "id": r["id"], "mode": "unparsed",
                          "instruction": r["original_instruction"], "degraded_prompt": r["degraded_prompt"],
                          "reference_suspect": True, "tests": [],
                          "suspect_reason": "a Python task whose reference does not parse as Python"})
            print(f"{r['source_id']:18} unparsed   SUSPECT: reference does not parse as Python", flush=True)
            continue
        if not is_python_item(r):
            items.append({"source_id": r["source_id"], "split": r["split"], "id": r["id"], "mode": "not_python",
                          "language": language_asked(r["original_instruction"])
                          or (sorted(languages_seen(strip_fences(r["reference_response"]))) or ["?"])[0]})
            continue
        item = classify(r)
        if item["mode"] == "function":
            llm = llm or make_llm()
            first = validate_function_item(item, generate(item, llm, cache)["content"])
            if not first["tests"] and not first.get("suspect_reason", "").startswith("reference fails on its own"):
                second = validate_function_item(item, generate(item, llm, cache, retry_of=first)["content"])
                second["attempts"] = 2
                item = second if second["tests"] else {**second, "first_attempt_dropped": first.get("dropped")}
            else:
                item = {**first, "attempts": 1}
        elif item["mode"] == "stdout":
            item = validate_stdout_item(item)
        items.append(item)
        print(f"{item['source_id']:18} {item['mode']:10} tests={len(item.get('tests', []))} "
              f"{'SUSPECT: ' + item['suspect_reason'] if item.get('reference_suspect') else item.get('reason', '')}",
              flush=True)
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", nargs="+", default=["test", "benchmark"])
    args = ap.parse_args()
    items = build(tuple(args.splits))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "items.json").write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT_DIR / 'items.json'} ({len(items)} items)")


if __name__ == "__main__":
    main()
