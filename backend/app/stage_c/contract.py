"""Stage C routing contract: what Stage C is asked, how its answer is validated, and how it patches the IR.

    result = apply_stage_c(prompt, features, stage_b_output, generate)     # generate(messages) -> str
    result.ir, result.accepted, result.errors

* Stage C is called only for the fields Stage B left unresolved (`natural_unresolved`), or for an explicit `fields`
  list (forced routing, evaluation only). Every other field is locked: Stage B's value is kept.
* The answer must be one JSON object with exactly the requested keys, and pass the same detectors as the rest of the
  pipeline (`validate`); otherwise the prompt keeps Stage B's result (fallback).
* Category policy (`category_decision`): when the prompt was routed for the task category, Stage C's category is
  accepted only if it is one of Stage A's top-2 categories, or Stage A's confidence is below 0.3 (Stage A knows too
  little to object). Otherwise the category is "uncertain": it stays unresolved, Stage C's guess is kept for the UI
  to pre-select, and the user is asked to pick. Stage C's other fields are applied either way.
* `c_only_input` builds the input for the C-only ablation (no Stage B: nothing filled, no requirements).
The same `model_input` / `to_messages` build the training data (app.stage_c.data), so training and inference match.
"""
import json
import time
from dataclasses import dataclass, field
from typing import Callable

from app.stage_a import rules as detect
from app.stage_a.schema import PromptFeatures
from app.stage_b.ir import PromptIR, render_plain
from app.stage_c.parse import is_format

FIELDS = ("task", "output_format", "constraints")
CATEGORY_TOP_K = 2                # Stage C's category must be among Stage A's top-k ...
CATEGORY_LOW_CONFIDENCE = 0.3     # ... unless Stage A's confidence is below this
CATEGORIES = ("closed_qa", "information_extraction", "classification", "summarization", "coding")
SYSTEM_PROMPT = (
    "You are Stage C of PromptOpt. You get a user's prompt and the structured version a rule-based optimizer made of "
    "it. Fields set to null and listed in \"unresolved\" could not be filled by the rules. Return a JSON object with "
    "exactly the unresolved keys and nothing else. \"task\": the instruction, clear and self-contained. "
    "\"output_format\": how the answer should be laid out, or null if no format is needed. \"constraints\": a list of "
    "short rules (length, language, tone, audience, use only the provided text), possibly empty. \"category\": one of "
    "closed_qa, information_extraction, classification, summarization, coding. Keep the user's intent; add no facts.")


def natural_unresolved(out) -> list[str]:
    """Fields Stage B left for Stage C, from its `unresolved` list (docs/STAGE_C_PLAN.md, section 1)."""
    fields = []
    for u in out.unresolved:
        if u == "task category":
            fields += ["output_format", "constraints", "category"]
        elif u.startswith("ambiguous reference"):
            fields.append("task")
        elif u == "output format":
            fields.append("output_format")
    return [f for f in ("task", "output_format", "constraints", "category") if f in fields]


def model_input(prompt: str, f: PromptFeatures, ir: PromptIR, unresolved: list[str]) -> dict:
    shown = {"task": ir.task, "output_format": ir.output_format, "constraints": list(ir.constraints),
             "requirements": list(ir.requirements), "category": ir.category}
    for k in unresolved:
        shown[k] = None
    return {"prompt": prompt,
            "category": {"value": f.task_type, "source": ir.category_source, "confidence": round(f.confidence, 2)},
            "has_context": f.has_context, "attachment": ir.attachment.type,
            "ir": shown, "unresolved": unresolved}


def c_only_input(prompt: str, f: PromptFeatures, ir: PromptIR) -> dict:
    """C-only ablation: Stage C fills task, output_format and constraints with no Stage B rules applied."""
    inp = model_input(prompt, f, ir, list(FIELDS))
    inp["ir"]["requirements"] = []
    return inp


def to_messages(inp: dict, tgt: dict | None = None) -> list[dict[str, str]]:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(inp, ensure_ascii=False)}]
    if tgt is not None:
        msgs.append({"role": "assistant", "content": json.dumps(tgt, ensure_ascii=False)})
    return msgs


def parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def validate(raw: str, fields: list[str], has_context: bool) -> tuple[dict | None, list[str]]:
    """(patch, []) if Stage C's answer may be used, else (None, reasons)."""
    obj = parse_json(raw)
    if obj is None:
        return None, ["not a JSON object"]
    errors = []
    if set(obj) != set(fields):
        errors.append(f"keys {sorted(obj)} != requested {sorted(fields)}")
    if "task" in fields:
        task = obj.get("task")
        if not isinstance(task, str) or len(task.split()) < 2:
            errors.append("task empty")
        elif refs := detect.detect_ambiguous_refs(task, has_context):
            errors.append(f"task has an ambiguous reference: {refs}")
    if "output_format" in fields:
        fmt = obj.get("output_format")
        if fmt is not None and not (isinstance(fmt, str) and (detect.detect_format_spec(fmt) or is_format(fmt))):
            errors.append("output_format states no format")
    if "constraints" in fields:
        cons = obj.get("constraints")
        if not isinstance(cons, list) or not all(isinstance(c, str) and c.strip() for c in cons):
            errors.append("constraints is not a list of strings")
    if "category" in fields and obj.get("category") not in CATEGORIES:
        errors.append(f"category {obj.get('category')!r} unknown")
    return (None, errors) if errors else (obj, [])


def patch_ir(ir: PromptIR, patch: dict) -> PromptIR:
    """Fill the requested fields; resolve the matching `unresolved` items. Nothing else changes."""
    update: dict = {}
    if "task" in patch:
        update["task"] = patch["task"].strip()
    if "output_format" in patch:
        update["output_format"] = patch["output_format"].strip() if patch["output_format"] else None
    if "constraints" in patch:
        update["constraints"] = tuple(c.strip() for c in patch["constraints"])
    if "category" in patch:
        update.update(category=patch["category"], category_source="stage_c")
    done = {"task category": "category" in patch, "ambiguous reference": "task" in patch,
            "output format": bool(patch.get("output_format"))}
    update["unresolved"] = tuple(u for u in ir.unresolved if not done.get(u.split(":")[0], False))
    return ir.model_copy(update=update)


def category_decision(guess: str, f: PromptFeatures) -> str:
    """'accepted' or 'uncertain' for Stage C's (valid) category guess, given Stage A's scores."""
    top = sorted(f.category_scores, key=f.category_scores.get, reverse=True)[:CATEGORY_TOP_K]
    return "accepted" if guess in top or f.confidence < CATEGORY_LOW_CONFIDENCE else "uncertain"


@dataclass
class StageCResult:
    used: bool                                   # Stage C was called
    accepted: bool                               # its answer passed validation and was applied
    ir: PromptIR                                 # final IR (Stage B's when not used or rejected)
    fields: list[str] = field(default_factory=list)
    raw: str | None = None
    errors: list[str] = field(default_factory=list)
    seconds: float = 0.0
    category_status: str | None = None           # "accepted" / "uncertain" when a category was requested
    category_guess: str | None = None            # Stage C's category (pre-selected in the UI when uncertain)

    @property
    def optimized_text(self) -> str:
        return render_plain(self.ir)

    @property
    def fallback(self) -> bool:
        return self.used and not self.accepted


def apply_stage_c(prompt: str, f: PromptFeatures, out, generate: Callable[[list[dict]], str],
                  fields: list[str] | None = None, inp: dict | None = None) -> StageCResult:
    """Run Stage C on the fields Stage B left unresolved (or `fields`); fall back to Stage B's IR on any failure.
    `inp` overrides the model input (C-only ablation)."""
    fields = natural_unresolved(out) if fields is None else list(fields)
    if not fields:
        return StageCResult(used=False, accepted=False, ir=out.ir)
    inp = inp or model_input(prompt, f, out.ir, fields)
    start = time.perf_counter()
    raw = generate(to_messages(inp))
    seconds = time.perf_counter() - start
    patch, errors = validate(raw, fields, f.has_context)
    if patch is None:
        return StageCResult(used=True, accepted=False, ir=out.ir, fields=fields, raw=raw, errors=errors,
                            seconds=seconds)
    status = guess = None
    if "category" in patch:
        guess = patch["category"]
        status = category_decision(guess, f)
        if status == "uncertain":                 # keep "task category" unresolved; the user picks
            patch = {k: v for k, v in patch.items() if k != "category"}
    return StageCResult(used=True, accepted=True, ir=patch_ir(out.ir, patch), fields=fields, raw=raw,
                        seconds=seconds, category_status=status, category_guess=guess)
