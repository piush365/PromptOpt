"""The prompt variants sent to the target LLM for one dataset row.

* degraded:       the user's prompt as typed (the dataset's degraded_prompt)
* stage_b:        PromptOpt's output for that prompt (Stage A + Stage B, no Stage C yet)
* dataset_target: the dataset's optimized prompt, written by an LLM; an upper bound, not something PromptOpt produces

Every variant gets the row's context appended after a blank line, exactly as a user would paste the text (or the code
to edit) below their request. Without it, prompts like "summarize that text" or "edit this function" would be
unanswerable. The same context is appended to all three variants, so it adds the same tokens to each.
"""
from typing import Any

from app.stage_b import optimize

VARIANTS = ("degraded", "stage_b", "dataset_target")


def with_context(prompt: str, context: str | None) -> str:
    context = (context or "").strip()
    return f"{prompt.strip()}\n\n{context}" if context else prompt.strip()


def build_variants(row: dict[str, str], detector: Any, variants: tuple[str, ...] = VARIANTS) -> dict[str, dict]:
    """{variant: {"request": the prompt without the context, "prompt": full text sent to the LLM, "meta": {...}}}."""
    context = row.get("context") or None
    out = {}
    if "degraded" in variants:
        out["degraded"] = {"request": row["degraded_prompt"].strip(), "meta": {}}
    if "stage_b" in variants:
        f = detector.detect(row["degraded_prompt"], context)
        res = optimize(row["degraded_prompt"], f)
        out["stage_b"] = {"request": res.optimized_text,
                          "meta": {"stage_a_category": f.task_type, "stage_a_confidence": f.confidence,
                                   "rules_applied": res.rules_applied, "needs_stage_c": res.needs_stage_c,
                                   "stage_c_reasons": res.stage_c_reasons}}
    if "dataset_target" in variants:
        out["dataset_target"] = {"request": row["optimized_prompt"].strip(), "meta": {}}
    for v in out.values():
        v["prompt"] = with_context(v["request"], context)
    return out
