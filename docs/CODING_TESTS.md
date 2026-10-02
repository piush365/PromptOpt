# Coding test cases and the sandboxed runner

Phase 4 of the finish plan. Measures whether the code a target LLM writes actually works, for degraded vs Stage B
prompts. Stage A/B/C are frozen at `final-for-test`; this only adds evaluation and an app panel. Results:
`evaluation/coding_tests.md`.

## Sandbox (`backend/app/coding/sandbox.py`)

All generated or reference code runs through `run_python`, and nothing else in the project executes it.

| layer | what it does |
|---|---|
| subprocess in a fresh temp dir | the code sees only its own files; the dir is deleted afterwards |
| **bubblewrap** (`bwrap`, installed here: 0.12.0) | new user/pid/net/ipc/uts namespaces (`--unshare-all`): **no network**; `/usr` read-only, private `/tmp`, the temp dir at `/work`, no home directory, no project files, no `.env`; environment cleared; dies with its parent |
| rlimits | address space 512 MB (memory), CPU seconds, file size 4 MB (stdout/stderr included), 64 open files, no core dumps, number of processes (user's current tasks + 32, so a fork bomb stops at once) |
| timeout | wall clock (5 s by default, 15 s for a test run, 3 s per test); the whole process group is killed |
| interpreter | the system `/usr/bin/python3 -I -B` (isolated mode, standard library only), not the project venv |

**Without bubblewrap**, the runner refuses to run code (`SANDBOX_REQUIRE_BWRAP=1`, the default). With
`SANDBOX_REQUIRE_BWRAP=0` it runs with rlimits, timeout, temp dir and a cleared environment only: the code **can
then reach the network and read the user's files**, and every result is labelled `rlimits-only`. All numbers in
`evaluation/coding_tests.md` were produced with bwrap.

Tested in `backend/tests/test_coding.py`: timeout (busy loop and sleep), memory limit, no network, host files
invisible, output limit, fork limit, refusal without bwrap.

## Which items are tested (`backend/app/coding/testgen.py`)

Python items only (the reference parses as Python and the instruction asks for no other language). Per item:

* **function**: the reference defines a top-level function. Cerebras `gpt-oss-120b` (temperature 0, JSON) writes 3-6
  assert tests for it. Each test runs against the reference in the sandbox; only passing tests are kept. If none
  passes, one retry shows the model the failures and allows short multi-line tests (set-up, then asserts).
* **stdout**: no function, but the reference prints. The test is "prints exactly what the reference prints"
  (trailing spaces ignored). The reference runs twice; different outputs mean nondeterministic, so untestable.
* **untestable** (reported, not run): third-party packages or network (`requests`, `sklearn`, `pandas`), interactive
  (`input()`), or no function and no output (a bare value or fragment, e.g. `result = [x*2 for x in list]`).
* **reference suspect**: the reference does not import on its own, or still no test passes on it after the retry.
  The reference and the tests disagree, and either may be wrong; the item is listed with the reason, not dropped.

For function items only the definitions (imports, functions, classes, assignments) of the reference and of each
candidate answer are imported, so unguarded demo code (prints, `input()`) does not run, the same for both.

The test generator is the same model as the target. Tests are validated on an independent reference (CodeAlpaca),
which limits but does not remove the bias of a model testing its own style of solution.

## Naming (`backend/app/coding/harness.py`)

Tests call the function by the reference's name. When an answer does not define that name:

* exactly **one** top-level function: the tests' name is bound to it and the tests run again. Passing this way is a
  **naming-only** failure (the code works; the prompt did not fix the name);
* none, or several: `no code` / `ambiguous` (no guessing among several functions).

pass@1 is reported **strict** (as asked) and **lenient** (naming-only failures counted as passes).

## Outcomes per answer

`pass`, `naming-only`, `wrong` (runs, fails a test), `error` (does not import, crashes, times out), `no code` (no
Python code, or no / several functions under another name).

## In the app

For a coding prompt the UI shows a "Tests for this coding prompt" panel:
* the prompt is a dataset item: its validated tests (offline);
* otherwise: "Generate tests (Cerebras)" writes 3-6 tests for the optimized prompt, marked **UNVALIDATED** (no
  reference to check them against); needs `CEREBRAS_API_KEY`, cached per prompt.
"Run tests on the LLM's answer" is disabled until the Compare feature has API keys for the target LLMs.

## Commands (inside `backend/`)

```
python -m app.coding.testgen                                    # items + validated tests -> data/coding/items.json
python -m app.coding.evaluate --out ../evaluation/coding_tests.md
python -m pytest -q tests/test_coding.py
```
