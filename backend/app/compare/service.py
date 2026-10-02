"""Compare: the user's original prompt vs PromptOpt's optimized prompt on the same model.

    result = compare(original_prompt, optimized_prompt, model_id, target="gpt", context=pasted_text,
                     category="coding", judge=True)

Both variants: one user message, temperature 0, the same max tokens (and reasoning "low" for gpt-oss), exactly the
evaluation harness's settings. The original prompt gets the pasted text appended after a blank line, as the user
would paste it (app.evaluation.variants.with_context); the optimized prompt is the rendering for the chosen target,
which already places that text. Answers are cached (data/compare/cache.jsonl), so repeating a comparison costs no
quota.

Honest labels: `rendered_for` is the target the optimized prompt was written for, `answered_by` the model that ran
it; when they differ (a Gemini-rendered prompt run on gpt-oss) the result says it is a stand-in.

Coding prompts that are dataset items with validated tests (app.coding.app_tests): both answers are run against the
tests in the sandbox (app.coding.harness). Judge (optional): Groq qwen scores each answer 0-10 against the user's
ORIGINAL request, one answer at a time, never told which prompt produced it.
"""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from app.coding import app_tests
from app.coding.evaluate import judge_answer
from app.compare import providers
from app.config import BACKEND_DIR
from app.evaluation.judge import shorten_response
from app.evaluation.run import JUDGE_MODEL, TARGET_MAX_TOKENS, TARGET_REASONING, Cache
from app.evaluation.variants import with_context

CACHE = BACKEND_DIR.parent / "data" / "compare" / "cache.jsonl"
TARGET_LABELS = {"gpt": "GPT", "gemini": "Gemini", "claude": "Claude"}
FAMILY_OF_TARGET = {"gpt": "gpt", "gemini": "gemini", "claude": "claude"}

JUDGE_SYSTEM = """You are a strict, fair grader of answers written by an AI assistant.
You get the USER'S REQUEST (what the user originally typed, with any text they pasted) and one RESPONSE. There is
no reference answer. Score the RESPONSE from 0 to 10 for how well it does what the user wanted: correct (no invented
facts), relevant, complete, and in a sensible form. 10 = fully does what the user wanted; 0 = wrong, off-topic or
empty. Return ONLY a JSON object: {"score": <0-10>, "reason": "<one short sentence>"}"""


def _key(model_id: str, prompt: str) -> str:
    return hashlib.sha256(f"{model_id}\n{TARGET_MAX_TOKENS}\n{TARGET_REASONING}\n{prompt}".encode()).hexdigest()[:24]


def run_variant(info: providers.ModelInfo, prompt: str, cache: Cache) -> dict:
    """One answer (cached). Reasoning effort "low" applies to gpt-oss; other models ignore it."""
    key = _key(info.id, prompt)
    rec = cache.get(key, "answer")
    if not rec.get("response"):
        providers.check_budget(info, len(prompt) // 4 + TARGET_MAX_TOKENS)
        c = providers.complete(info, [{"role": "user", "content": prompt}], max_tokens=TARGET_MAX_TOKENS,
                               temperature=0.0, reasoning_effort=TARGET_REASONING if info.family == "gpt-oss" else None)
        cache.add(key, "answer", model=info.id, response=c.content, target=asdict(c))
        rec = cache.get(key, "answer")
        rec["cached"] = False
    else:
        rec["cached"] = True
    t = rec["target"]
    return {"answer": rec["response"], "input_tokens": t["input_tokens"], "output_tokens": t["output_tokens"],
            "reasoning_tokens": t.get("reasoning_tokens"), "total_tokens": t["input_tokens"] + t["output_tokens"],
            "latency_ms": t["latency_ms"], "finish_reason": t.get("finish_reason"), "cached": rec["cached"]}


def _change(before: int, after: int) -> float | None:
    return round(100 * (after - before) / before, 1) if before else None


def judge(original_request: str, answer: str, cache: Cache) -> dict | None:
    """Blind, reference-free score of one answer against the user's original request (Groq qwen)."""
    key = hashlib.sha256(f"judge\n{JUDGE_MODEL}\n{original_request}\n{answer}".encode()).hexdigest()[:24]
    rec = cache.get(key, "judge")
    if "score" not in rec:
        info = providers.BY_ID["groq/openai/gpt-oss-120b"]
        if not info.available:
            return None
        from app.groq_budget import UsageLedger
        if UsageLedger().used(JUDGE_MODEL)["tokens"] > providers.BUDGET_FRACTION * 200_000:
            return {"score": None, "reason": "judge skipped: Groq daily budget for the judge model reached"}
        msgs = [{"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": f"USER'S REQUEST:\n{original_request.strip()}\n\nRESPONSE:\n"
                                            f"{shorten_response(answer.strip() or '(empty response)')}"}]
        c = providers.client(info).complete(JUDGE_MODEL, msgs, max_tokens=1024, temperature=0.0,
                                            reasoning_effort="none", json_mode=True)
        try:
            obj = json.loads(c.content)
            cache.add(key, "judge", score=float(obj["score"]), reason=str(obj.get("reason", ""))[:300])
        except (ValueError, KeyError, TypeError):
            return {"score": None, "reason": "judge returned no usable score"}
        rec = cache.get(key, "judge")
    return {"score": rec["score"], "reason": rec["reason"]}


def compare(original_prompt: str, optimized_prompt: str, model_id: str, target: str, context: str | None = None,
            category: str | None = None, judge_answers: bool = False, cache_path: Path = CACHE) -> dict:
    info = providers.BY_ID.get(model_id)
    if info is None:
        raise ValueError(f"unknown model {model_id!r}; choose one of {list(providers.BY_ID)}")
    if not info.available:
        raise providers.ModelUnavailable(info.reason)
    cache = Cache(cache_path)
    original_text = with_context(original_prompt, context)
    out = {v: run_variant(info, text, cache) for v, text in (("original", original_text),
                                                             ("optimized", optimized_prompt))}
    o, p = out["original"], out["optimized"]
    stand_in = FAMILY_OF_TARGET.get(target) != info.family
    result = {
        "rendered_for": target, "answered_by": info.id, "answered_by_label": info.label, "stand_in": stand_in,
        "label": (f"{TARGET_LABELS.get(target, target)}-rendered prompt, answered by {info.label}"
                  + (f" (a stand-in: {TARGET_LABELS.get(target, target)} itself is not available here)"
                     if stand_in else "")),
        "settings": {"temperature": 0.0, "max_tokens": TARGET_MAX_TOKENS,
                     "reasoning_effort": TARGET_REASONING if info.family == "gpt-oss" else None},
        "original": {**o, "prompt": original_text}, "optimized": {**p, "prompt": optimized_prompt},
        "change_pct": {k: _change(o[k], p[k]) for k in ("input_tokens", "output_tokens", "total_tokens")},
        "latency_change_pct": _change(o["latency_ms"], p["latency_ms"]),
        "tests": None, "judge": None,
    }
    if category == "coding" or app_tests.lookup(original_prompt):
        item = app_tests._items().get(app_tests._norm(original_prompt))
        if item is not None:
            result["tests"] = {"item": item["source_id"], "validated": True, "mode": item["mode"],
                               **{v: judge_answer(item, out[v]["answer"]) for v in ("original", "optimized")}}
        else:
            result["tests"] = {"validated": False, "note": "No validated tests for this prompt (it is not a dataset "
                                                         "coding item); generate tests in the panel above to see them."}
    if judge_answers:
        result["judge"] = {"model": JUDGE_MODEL, "blind": True,
                           **{v: judge(original_text, out[v]["answer"], cache) for v in ("original", "optimized")}}
    return result
