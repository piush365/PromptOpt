# 10. Coding: generated tests and the sandbox

[Back to the index](README.md)

"Does the code the model writes actually work?" Code: `backend/app/coding/`; method note: `docs/CODING_TESTS.md`;
results: `evaluation/coding/coding_tests.md`. Added in finish phase 4 (after `final-for-test`); it measures, it changes
nothing in Stage A/B/C.

---

## 10.1 The sandbox (`coding/sandbox.py`)

All generated or reference code runs through `run_python(files, entry="main.py", stdin="", timeout=5.0)`, and nothing
else in the project executes it.

| layer | details | why |
|---|---|---|
| fresh temporary directory | the given files are written into `promptopt-run-*`; deleted afterwards | the code sees only its own files |
| interpreter | the **system** `/usr/bin/python3 -I -B` (isolated mode: no user site-packages, no `PYTHON*` variables; no `.pyc` files) | standard library only, not the project's venv |
| **bubblewrap** (`bwrap` 0.12.0) | `--unshare-all` (new user, pid, **network**, ipc, uts namespaces), `--die-with-parent`, `--new-session`, `/usr` read-only (plus `/bin`, `/lib`, `/lib64` symlinks), fresh `/proc` and `/dev`, private `/tmp`, the temp dir bound at `/work` (cwd), `--clearenv` with only `PATH=/usr/bin`, `HOME=/work`, `LANG=C.UTF-8` | **no network at all**; no home directory, no project files, no `.env` |
| resource limits (always) | address space **512 MB**; CPU time: soft limit ⌊timeout⌋ + 1 s, hard limit one second more; file size **4 MB** (stdout/stderr included); **64** open files; no core dumps; processes = the user's current tasks + **32** | memory bombs, CPU loops, disk filling, fork bombs |
| wall-clock timeout | default 5 s; 15 s for a test run; 3 s per individual test (SIGALRM inside the runner); 10 s for reference runs | hung code; the whole process group is killed (`SIGKILL`) |
| output | stdout/stderr go to files in the temp dir (capped by the 4 MB file limit), at most 20,000 characters returned | a print loop cannot fill memory |

*Why "user's tasks + 32" for the process limit:* `RLIMIT_NPROC` counts all of the user's processes and threads, not
just the sandboxed ones, so the limit is set relative to what is already running.

**Without bubblewrap** the runner **refuses** to run code (`SANDBOX_REQUIRE_BWRAP=1`, the default). With
`SANDBOX_REQUIRE_BWRAP=0` it runs with rlimits, timeout, temp dir and a cleared environment only — the code can then
reach the network and read the user's files — and every result is labelled `rlimits-only`. All reported numbers were
produced with bwrap.

**Result status:** `timeout` (timed out, or killed by SIGXCPU/SIGKILL after ≥ 90% of the timeout), `memory`
(MemoryError, or SIGSEGV/SIGABRT mentioning memory), `output_limit` (SIGXFSZ or "File too large"), otherwise `ok`
(exit 0) or `error`.

**Tested** in `backend/tests/test_coding.py`: timeout (busy loop and sleep), memory limit, no network, host files
invisible, output limit, fork limit, refusal without bwrap.

## 10.2 Which items can be tested (`coding/testgen.py`)

Only **Python** items: the CodeAlpaca reference parses as Python and the instruction asks for no other language
(`reference_check.language_asked`, `languages_seen`). Per item:

| mode | condition | test |
|---|---|---|
| **function** | the reference defines top-level functions | 3–6 assert tests, generated and validated (10.3) |
| **stdout** | no function, but the reference prints | "prints exactly what the reference prints" (trailing spaces ignored); the reference is run twice — different outputs, or imports of datetime/time/random/uuid/secrets, mean nondeterministic → untestable |
| **untestable** | third-party packages or network (`requests`, `sklearn`, `pandas` …: imports not in `sys.stdlib_module_names`), interactive (`input()`), or no function and no output (a bare value or fragment) | reported, not run |
| **reference suspect** | the reference does not import on its own, or no generated test passes on it after a retry, or a Python task whose reference does not parse | reported with the reason, **not dropped** |

For function items only the **definitions** of the reference and of each candidate (imports, functions, classes,
assignments: `definitions_only` via the AST) are imported, so unguarded demo code (prints, `input()`, loops) does not
run — the same for both.

## 10.3 Test generation and validation

1. **Generate:** Cerebras `gpt-oss-120b`, temperature 0, JSON mode, reasoning "low", ≤ 3,000 tokens. The prompt gives
   the task, the input, the reference solution and the candidate function names, and asks for 3–6 one-line assert
   tests calling that function by name: behaviour the task describes (not quirks of the reference), at least one edge
   case, deterministic, standard library only, no I/O, floats compared with `round()`.
2. **Parse:** keep strings containing `assert` that compile; the function name must be one of the reference's (or the
   only one).
3. **Validate on the reference:** run every test against the reference's definitions in the sandbox; **keep only the
   tests that pass**.
4. **Retry once** if none passes: show the model its failing tests with the errors and allow short multi-line tests
   (set-up lines, then asserts), e.g. to build a linked list.
5. If the reference itself fails, or still nothing passes → reference suspect.

Answers are cached (`data/coding/testgen.jsonl`), so re-runs cost nothing. Generation stops before Cerebras usage
passes 70% of its 1,000,000-token daily limit.

*Bias note:* the test writer is the same model as the target. Validating every test on an **independent** reference
(CodeAlpaca) limits, but does not remove, the bias of a model testing its own style of solution.

## 10.4 Running a candidate (`coding/harness.py`)

1. `extract_code(answer, function)`: the fenced Python block that defines the function, else the longest Python
   block, else the whole answer if it parses as Python, else "" (no code).
2. **Naming:** if the code does not define the tests' function name and has exactly **one** top-level function, the
   tests' name is bound to it (`renamed`); with none → `no_function`; with several → `ambiguous` (never guessed).
3. A runner script imports `solution.py` (so its `if __name__ == "__main__"` block does not run), executes each test
   in its own namespace under a 3-second alarm, and prints the results after a unique marker
   (`@@PROMPTOPT_RESULTS@@`), which is searched anywhere in stdout (an `input()` prompt may precede it).
4. Script items: run as a program; normalized stdout must equal the reference's.

**Outcome per answer:** `pass` · `naming-only` (passes only after binding the name) · `wrong` (runs, fails a test) ·
`error` (does not import, crashes, times out) · `ambiguous` · `no function` · `no Python`.

**pass@1** = the single answer (temperature 0) passes every validated test:
* **strict** — calling the function by the tests' name;
* **lenient** — also counting `naming-only` as a pass.

## 10.5 Evaluation (`coding/evaluate.py`)

Target `cerebras/gpt-oss-120b`, temperature 0, reasoning "low", max 2,048 tokens, one user message: the settings of
the final benchmark. Test answers are generated here (cached in `data/coding/target.jsonl`); benchmark answers are
reused from the final benchmark cache (nothing re-called). If a cached prompt differs from today's, the run aborts
("Stage B changed?").

Results (chapter 9.5): strict 6/29 → **10/29**, lenient 11/29 → 12/29; only Stage B passes 4 items, only degraded 0
(sign test p = 0.125). Failures split into naming-only / undetermined / real: degraded 5 / 5 / 13, Stage B 2 / 1 / 16.

## 10.6 In the app

For a coding prompt (Stage B category, Stage A's category or Stage C's guess = coding) the UI shows a "Tests for this
coding prompt" panel:
* the prompt is a dataset coding item (same degraded prompt as a test/benchmark item): its **validated** tests, offline;
* otherwise: "Generate unvalidated tests" (Cerebras, 3–6 asserts for the optimized prompt, cached per prompt, needs
  `CEREBRAS_API_KEY`), clearly marked **UNVALIDATED** (no reference to check them against), shown for reading only.

Compare runs a dataset item's validated tests on both answers in the sandbox (chapter 12).
