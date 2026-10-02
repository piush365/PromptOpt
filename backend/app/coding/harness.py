"""Run a candidate solution against assert-style tests (function items) or a reference output (script items), always
in the sandbox (app.coding.sandbox).

    run_function_tests(code, ["assert add(1, 2) == 3"], function="add")   -> TestRun
    run_stdout_test(code, expected_stdout)                                  -> TestRun

Function items: the candidate is saved as `solution.py` and imported (so its `if __name__ == "__main__":` block does
not run); each test runs in its own namespace with everything the solution defines, under a per-test alarm. Naming:
when the candidate does not define the function the tests call, and it has exactly ONE top-level function, the tests'
name is bound to that function (`renamed`); with none or several, the item fails as `no_function` / `ambiguous`.
"""
import ast
import json
import re
from dataclasses import dataclass, field

from app.coding.sandbox import RunResult, run_python

PER_TEST_SECONDS = 3
RUN_TIMEOUT = 15.0
MARKER = "@@PROMPTOPT_RESULTS@@"

RUNNER = r'''
import json, os, signal, sys, traceback
sys.path.insert(0, os.getcwd())          # python -I leaves the script's directory off sys.path
MARKER, PER_TEST = {marker!r}, {per_test}
cfg = json.load(open("tests.json"))
def _alarm(*_):
    raise TimeoutError("test took longer than %d s" % PER_TEST)
signal.signal(signal.SIGALRM, _alarm)
try:
    import solution
except BaseException as e:
    print(MARKER + json.dumps({{"import_error": "".join(traceback.format_exception_only(type(e), e)).strip()}}))
    sys.exit(0)
ns = {{k: v for k, v in vars(solution).items() if not k.startswith("__")}}
if cfg["alias"]:
    ns[cfg["function"]] = getattr(solution, cfg["alias"])
results = []
for t in cfg["tests"]:
    signal.alarm(PER_TEST)
    try:
        exec(compile(t, "<test>", "exec"), dict(ns))
        results.append({{"ok": True}})
    except BaseException as e:
        results.append({{"ok": False, "error": "".join(traceback.format_exception_only(type(e), e)).strip()[:300]}})
    finally:
        signal.alarm(0)
print(MARKER + json.dumps({{"results": results}}))
'''


@dataclass
class TestRun:
    __test__ = False                  # not a pytest test class
    status: str                       # passed | failed | import_error | no_function | ambiguous | timeout | crash
    passed: int = 0
    total: int = 0
    renamed: str | None = None        # the candidate's function the tests' name was bound to
    results: list[dict] = field(default_factory=list)
    detail: str = ""
    sandbox: str = ""

    @property
    def all_passed(self) -> bool:
        return self.status == "passed"


def top_level_functions(code: str) -> list[str]:
    """Names of top-level `def`s (not methods), in order; [] if the code does not parse."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    return [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def defines(code: str, name: str) -> bool:
    """`name` is defined at top level: a def, a class, or an assignment (`square = lambda x: ...`)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name:
            return True
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
            return True
    return False


_FENCE = re.compile(r"```[ \t]*([\w+-]*)[^\n]*\n(.*?)```", re.S)


def extract_code(response: str, function: str | None = None) -> str:
    """The Python code in an LLM answer: the fenced block that defines `function` (else the longest Python block);
    the whole answer if it has no fences and parses as Python; "" otherwise."""
    blocks = [(lang.lower(), body.strip()) for lang, body in _FENCE.findall(response or "")]
    py = [b for lang, b in blocks if lang in ("python", "py", "python3", "")]
    if function:
        for b in py:
            if defines(b, function):
                return b
    if py:
        return max(py, key=len)
    try:
        ast.parse(response)
        return response.strip()
    except (SyntaxError, ValueError):
        return ""


def _status_from(res: RunResult) -> tuple[str, str]:
    if res.status == "timeout":
        return "timeout", "the whole run timed out"
    return "crash", (res.stderr.strip().splitlines() or [res.status])[-1][:300]


def run_function_tests(code: str, tests: list[str], function: str) -> TestRun:
    if not code.strip():
        return TestRun("no_function", total=len(tests), detail="no code found")
    alias = None
    if not defines(code, function):
        funcs = top_level_functions(code)
        if len(funcs) == 1:
            alias = funcs[0]
        else:
            return TestRun("no_function" if not funcs else "ambiguous", total=len(tests),
                           detail=f"`{function}` not defined; top-level functions: {funcs}")
    cfg = json.dumps({"tests": tests, "function": function, "alias": alias})
    res = run_python({"solution.py": code, "tests.json": cfg,
                      "main.py": RUNNER.format(marker=MARKER, per_test=PER_TEST_SECONDS)}, timeout=RUN_TIMEOUT)
    # the marker may follow output without a newline (an input() prompt), so look for it anywhere
    if MARKER not in res.stdout:
        status, detail = _status_from(res)
        return TestRun(status, total=len(tests), renamed=alias, detail=detail, sandbox=res.sandbox)
    data = json.loads(res.stdout.rsplit(MARKER, 1)[1].splitlines()[0])
    if "import_error" in data:
        return TestRun("import_error", total=len(tests), renamed=alias, detail=data["import_error"][:300],
                       sandbox=res.sandbox)
    results = data["results"]
    passed = sum(r["ok"] for r in results)
    return TestRun("passed" if passed == len(tests) else "failed", passed, len(tests), alias, results,
                   sandbox=res.sandbox)


def normalize_output(text: str) -> str:
    """Trailing spaces and blank lines at the end ignored; everything else must match."""
    return "\n".join(line.rstrip() for line in (text or "").strip().splitlines())


def run_stdout_test(code: str, expected: str, stdin: str = "") -> TestRun:
    """Script items: run the candidate as a program; its output must equal the reference's (normalized)."""
    if not code.strip():
        return TestRun("no_function", total=1, detail="no code found")
    res = run_python({"main.py": code}, stdin=stdin, timeout=RUN_TIMEOUT)
    if res.status != "ok":
        status, detail = _status_from(res) if res.status != "error" else ("import_error", res.stderr.strip()[-300:])
        return TestRun(status, total=1, detail=detail, sandbox=res.sandbox)
    ok = normalize_output(res.stdout) == normalize_output(expected)
    return TestRun("passed" if ok else "failed", int(ok), 1, results=[{"ok": ok, "stdout": res.stdout[:500]}],
                   sandbox=res.sandbox)
