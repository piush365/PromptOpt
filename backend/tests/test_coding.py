"""Sandboxed runner, test harness and coding-item selection (no LLM calls)."""
import shutil

import pytest

from app.coding import sandbox
from app.coding.evaluate import outcome
from app.coding.harness import (TestRun, defines, extract_code, run_function_tests, run_stdout_test,
                                top_level_functions)
from app.coding.sandbox import run_python
from app.coding.testgen import classify, definitions_only, parse_generation

needs_bwrap = pytest.mark.skipif(shutil.which("bwrap") is None, reason="bubblewrap not installed")


# ---------------------------------------------------------------- sandbox
@needs_bwrap
def test_ok_and_error():
    assert run_python({"main.py": "print('hi')"}).stdout == "hi\n"
    r = run_python({"main.py": "1/0"})
    assert r.status == "error" and "ZeroDivisionError" in r.stderr and r.sandbox == "bwrap"


@needs_bwrap
@pytest.mark.parametrize("code", ["while True: pass", "import time\ntime.sleep(60)"])
def test_timeout_kills_the_run(code):
    r = run_python({"main.py": code}, timeout=1.5)
    assert r.status == "timeout" and r.seconds < 5


@needs_bwrap
def test_memory_limit():
    r = run_python({"main.py": "x = bytearray(2 * 1024 ** 3)\nprint('allocated')"}, memory_mb=256)
    assert r.status == "memory" and "allocated" not in r.stdout


@needs_bwrap
def test_no_network():
    code = ("import socket\ntry:\n    socket.create_connection(('1.1.1.1', 53), timeout=2)\n    print('OPEN')\n"
            "except OSError as e:\n    print('blocked', e.errno)")
    r = run_python({"main.py": code})
    assert r.ok and r.stdout.startswith("blocked") and "OPEN" not in r.stdout


@needs_bwrap
def test_host_files_are_not_visible():
    r = run_python({"main.py": "import os\nprint(sorted(os.listdir('/')))\nprint(os.path.exists('/home'))"})
    assert "False" in r.stdout and "home" not in r.stdout.splitlines()[0] and "mnt" not in r.stdout


@needs_bwrap
def test_output_limit_and_fork_limit():
    assert run_python({"main.py": "while True: print('x' * 1000)"}, file_mb=1).status == "output_limit"
    bomb = "import os\nn = 0\nwhile True:\n    try:\n        os.fork(); n += 1\n    except OSError:\n        break\n"
    r = run_python({"main.py": bomb}, timeout=5)
    assert r.status != "timeout"                       # the process limit stops it long before the timeout
    assert run_python({"main.py": "print(1)"}).ok        # and the machine is fine afterwards


def test_refuses_to_run_without_bwrap_by_default(monkeypatch):
    monkeypatch.setattr(sandbox, "BWRAP", None)
    monkeypatch.setattr(sandbox, "REQUIRE_BWRAP", True)
    with pytest.raises(RuntimeError, match="bubblewrap"):
        run_python({"main.py": "print(1)"})
    monkeypatch.setattr(sandbox, "REQUIRE_BWRAP", False)          # explicit opt-in: rlimits only, and labelled
    r = run_python({"main.py": "print(1)"})
    assert r.ok and r.sandbox == "rlimits-only"


# ---------------------------------------------------------------- harness
ADD_TESTS = ["assert add(1, 2) == 3", "assert add(-1, 1) == 0"]


@needs_bwrap
def test_function_tests_pass_and_fail_per_test():
    assert run_function_tests("def add(a, b):\n    return a + b", ADD_TESTS, "add").status == "passed"
    r = run_function_tests("def add(a, b):\n    return a - b", ADD_TESTS, "add")
    assert r.status == "failed" and r.passed == 0 and "AssertionError" in r.results[0]["error"]


@needs_bwrap
def test_naming_discovery_binds_the_single_top_level_function():
    r = run_function_tests("def plus(a, b):\n    return a + b", ADD_TESTS, "add")
    assert r.status == "passed" and r.renamed == "plus" and outcome(r) == "naming-only"
    r = run_function_tests("def plus(a, b):\n    return a * b", ADD_TESTS, "add")
    assert r.renamed == "plus" and outcome(r) == "wrong"
    assert run_function_tests("def a(x): pass\ndef b(x): pass", ADD_TESTS, "add").status == "ambiguous"
    assert run_function_tests("x = 1", ADD_TESTS, "add").status == "no_function"
    assert outcome(run_function_tests("add = lambda a, b: a + b", ADD_TESTS, "add")) == "pass"   # defined by assign


@needs_bwrap
def test_hanging_test_and_import_error_and_main_block():
    r = run_function_tests("def add(a, b):\n    while True: pass", ADD_TESTS[:1], "add")
    assert r.status == "failed" and "TimeoutError" in r.results[0]["error"]
    assert run_function_tests("import not_a_module\ndef add(a, b): return a + b", ADD_TESTS, "add").status == \
        "import_error"
    main_block = "def add(a, b):\n    return a + b\nif __name__ == '__main__':\n    print(input())"
    assert run_function_tests(main_block, ADD_TESTS, "add").status == "passed"
    prompt_no_newline = "def f():\n    input('Your move: ')\n"         # results marker after an input() prompt
    assert run_function_tests(prompt_no_newline, ["assert f() is None"], "f").status == "failed"


@needs_bwrap
def test_stdout_test():
    assert run_stdout_test("for i in range(3):\n    print(i)", "0\n1\n2\n").status == "passed"
    assert run_stdout_test("print(1)", "2").status == "failed"
    assert run_stdout_test("", "x").status == "no_function"


def test_extract_code_and_helpers():
    answer = "Here:\n```python\ndef f(x):\n    return x\n```\nUsage:\n```python\nprint(f(1))\n```"
    assert extract_code(answer, "f") == "def f(x):\n    return x"
    assert extract_code("```js\nconsole.log(1)\n```") == ""
    assert extract_code("def g():\n    return 1") == "def g():\n    return 1"
    assert top_level_functions("class A:\n    def m(self): pass\ndef f(): pass") == ["f"]
    assert defines("square = lambda x: x * x", "square") and not defines("print(1)", "square")
    assert definitions_only("import os\ndef f():\n    return 1\nprint(f())\nx = input()") == \
        "import os\n\ndef f():\n    return 1\nx = input()"


def test_parse_generation_keeps_only_compiling_asserts():
    content = '{"function": "add", "tests": ["assert add(1, 2) == 3", "print(1)", "assert add(", "assert add(0,0)==0"]}'
    assert parse_generation(content, ["add"]) == ("add", ["assert add(1, 2) == 3", "assert add(0,0)==0"])
    assert parse_generation("not json", ["add"]) == (None, [])
    assert parse_generation('{"function": "zzz", "tests": []}', ["add"])[0] == "add"   # single function: fixed
    multi = '{"function": "add", "tests": ["x = add(1, 1)\\nassert x == 2"]}'           # retry: set-up + assert
    assert parse_generation(multi, ["add"])[1] == ["x = add(1, 1)\nassert x == 2"]


def row(reference: str, instruction: str = "Write a function.") -> dict:
    return {"source_id": "x", "split": "test", "id": "x", "original_instruction": instruction, "context": "",
            "degraded_prompt": "write a function",
            "reference_response": reference}


@pytest.mark.parametrize("reference, mode", [
    ("def f(x):\n    return x", "function"),
    ("for i in range(3):\n    print(i)", "stdout"),
    ("result = [x * 2 for x in [1, 2]]", "untestable"),
    ("import requests\ndef f():\n    return requests.get('u')", "untestable"),
    ("def game():\n    move = input('move: ')\n    return move", "untestable"),
])
def test_classify(reference, mode):
    assert classify(row(reference))["mode"] == mode


def test_outcome_mapping():
    assert outcome(TestRun("passed")) == "pass"
    assert outcome(TestRun("passed", renamed="g")) == "naming-only"
    assert outcome(TestRun("failed")) == "wrong"
    assert outcome(TestRun("import_error")) == outcome(TestRun("timeout")) == "error"
    assert outcome(TestRun("ambiguous")) == "ambiguous"
    assert outcome(TestRun("no_function", detail="no code found")) == "no Python"
    assert outcome(TestRun("no_function", detail="`f` not defined; top-level functions: []")) == "no function"


def test_clock_based_script_is_untestable():
    from app.coding.testgen import validate_stdout_item
    item = classify(row("from datetime import datetime\nprint(datetime.now())"))
    assert item["mode"] == "stdout"
    assert validate_stdout_item(item)["mode"] == "untestable"
