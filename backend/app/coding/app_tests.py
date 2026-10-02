"""Tests shown in the app for coding prompts. Running them on a real LLM's answer waits for Compare (API keys).

* The prompt is a dataset coding item (same degraded prompt as a test/benchmark item): its tests, validated on the
  CodeAlpaca reference (data/coding/items.json, from `python -m app.coding.testgen`). Works offline.
* Otherwise, on request: Cerebras gpt-oss-120b writes 3-6 asserts for the optimized prompt. There is no reference
  solution to check them against, so they are marked UNVALIDATED. Needs CEREBRAS_API_KEY; cached per prompt
  (data/coding/app_tests.jsonl) so a repeated request costs nothing.
"""
import hashlib
import json
import os
import re
from functools import lru_cache

from app.coding.testgen import GEN_MAX_TOKENS, GEN_MODEL, MAX_TESTS, MIN_TESTS, OUT_DIR, GenCache, _compiles


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


@lru_cache(maxsize=1)
def _items() -> dict[str, dict]:
    path = OUT_DIR / "items.json"
    if not path.exists():
        return {}
    items = json.loads(path.read_text(encoding="utf-8"))
    return {_norm(i["degraded_prompt"]): i for i in items
            if i.get("degraded_prompt") and i.get("tests") and not i.get("reference_suspect")}


def lookup(prompt: str) -> dict | None:
    """Validated tests of the dataset item with this prompt, or None."""
    item = _items().get(_norm(prompt))
    if item is None:
        return None
    return {"source": "dataset", "validated": True, "item": item["source_id"], "mode": item["mode"],
            "function": item.get("entry"), "tests": item["tests"],
            "expected_stdout": item.get("expected_stdout"),
            "note": "Validated: every test passes on the dataset's reference solution."}


def can_generate() -> bool:
    return bool(os.getenv("CEREBRAS_API_KEY"))


def _messages(optimized_prompt: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": "You write unit tests for small Python coding tasks. Answer with JSON only: "
                                          '{"function": "<function name>", "signature": "<def line>", '
                                          '"tests": ["assert ...", ...]}.'},
            {"role": "user", "content": f"Task given to a coding assistant:\n{optimized_prompt}\n\nChoose the "
             f"function name and signature a solution should have (use the name the task gives, if any), then "
             f"write {MIN_TESTS} to {MAX_TESTS} one-line assert tests calling it: the behaviour the task asks for, "
             "at least one edge case, deterministic, standard library only, no I/O."}]


def generate(optimized_prompt: str, llm=None) -> dict:
    """Unvalidated tests for an arbitrary coding prompt (one Cerebras call, cached)."""
    key = hashlib.sha256(optimized_prompt.encode()).hexdigest()[:16]
    cache = GenCache(OUT_DIR / "app_tests.jsonl")
    if key not in cache.data:
        if llm is None:
            from app.coding.testgen import make_llm
            llm = make_llm()
        c = llm.complete(GEN_MODEL, _messages(optimized_prompt), max_tokens=GEN_MAX_TOKENS, temperature=0.0,
                         reasoning_effort="low", json_mode=True)
        cache.add({"source_id": key, "content": c.content, "model": c.model})
    try:
        obj = json.loads(cache.data[key]["content"])
    except json.JSONDecodeError:
        obj = {}
    tests = [t.strip() for t in obj.get("tests") or [] if isinstance(t, str) and t.strip().startswith("assert")
             and _compiles(t.strip())][:MAX_TESTS]
    return {"source": "generated", "validated": False, "mode": "function", "function": obj.get("function"),
            "signature": obj.get("signature"), "tests": tests,
            "note": "UNVALIDATED: generated from the optimized prompt; there is no reference solution to check them "
                    "against. Running them on the LLM's answer needs the Compare feature (API keys)."}
