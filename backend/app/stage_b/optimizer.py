"""Stage B entry point: `optimize(prompt, features) -> OptimizationOutput`.

    from app.stage_a import detect_features
    from app.stage_b import optimize
    f = detect_features(text)
    out = optimize(text, f)
    repository.save_optimization(db, prompt.id, out.optimized_text, out.ir.model_dump(mode="json"),
                                 out.confidence, out.steps)

Every rule that changes the text is logged as a step (rule code, text before, text after) for the explanation UI
and the `transformations` table. Rules can be switched off with `disabled` for the ablation study.

Category choice: `category="auto"` uses Stage A's classifier; one of the five categories overrides it (the user knows
what they asked). Which one was used is logged and stored in `ir.category_source`. An attachment (image, PDF, ...) is a
modifier handled by rules B09-B15, not a category. `target_llm` is recorded in the IR for app.rendering.

A prompt goes to Stage C only when something is still unresolved that Stage C can fix: the task category (after
the single-category gate and the B08 group fallback) or an ambiguous reference. A missing label set or output
format is recorded in `ir.unresolved` for the explanation UI but does not send the prompt to Stage C by itself.
"""
import logging

from pydantic import BaseModel, Field

from app.stage_a import rules as detect
from app.stage_a.schema import PromptFeatures
from app.stage_b.ir import Attachment, PromptIR, TargetLLM, context_ref_for, render_plain
from app.stage_b.rules import CATEGORY_MIN_CONFIDENCE, KNOWN_CATEGORIES, RULES

log = logging.getLogger(__name__)

# Unresolved items that send a prompt to Stage C.
STAGE_C_REASONS = ("task category", "ambiguous reference")
# Confidence (stored with the result, not used for routing) = Stage A's category confidence, minus a penalty for each
# problem Stage B could not fix. `other` prompts get nothing category-specific, so they start low.
UNRESOLVED_PENALTY = 0.2
OTHER_CONFIDENCE = 0.3
RULE_CODES = [code for code, _ in RULES]


class OptimizationOutput(BaseModel):
    original: str
    optimized_text: str
    ir: PromptIR
    steps: list[dict[str, str]] = Field(description="applied changes, in the format repository.save_optimization takes")
    confidence: float = Field(ge=0.0, le=1.0)
    needs_stage_c: bool

    @property
    def unresolved(self) -> tuple[str, ...]:
        return self.ir.unresolved

    @property
    def stage_c_reasons(self) -> list[str]:
        return [u for u in self.ir.unresolved if u.startswith(STAGE_C_REASONS)]

    @property
    def rules_applied(self) -> list[str]:
        return [s["rule_code"] for s in self.steps]


def apply_category_choice(f: PromptFeatures, category: str) -> tuple[PromptFeatures, str]:
    """Features for Stage B and where the category came from. "auto": Stage A's, unchanged. A category: the user's
    choice replaces Stage A's with full confidence, and the constraints relevant to it are re-derived."""
    if category == "auto":
        return f, "stage_a"
    if category not in KNOWN_CATEGORIES:
        raise ValueError(f"unknown category {category!r}; expected 'auto' or one of {sorted(KNOWN_CATEGORIES)}")
    missing = [c for c in detect.RELEVANT_CONSTRAINTS[category] if c not in f.constraints_present]
    return f.model_copy(update={"task_type": category, "confidence": 1.0, "category_scores": {category: 1.0},
                                "missing_constraints": missing}), "user"


def initial_ir(prompt: str, f: PromptFeatures, attachment: Attachment = Attachment(),
               target_llm: TargetLLM | None = None, category_source: str = "stage_a") -> PromptIR:
    """The prompt as it came in, plus the problems Stage A found that no Stage B rule can fix."""
    unresolved = []
    if f.task_type == "other" or f.confidence < CATEGORY_MIN_CONFIDENCE:
        unresolved.append("task category")
    if f.ambiguous_refs:
        unresolved.append("ambiguous reference: " + ", ".join(f"'{r}'" for r in f.ambiguous_refs))
    return PromptIR(category=f.task_type, task=prompt.strip(), unresolved=tuple(unresolved), attachment=attachment,
                    target_llm=target_llm, category_source=category_source)


def confidence(ir: PromptIR, f: PromptFeatures) -> float:
    base = OTHER_CONFIDENCE if ir.category == "other" else f.confidence
    return round(min(1.0, max(0.0, base - UNRESOLVED_PENALTY * len(ir.unresolved))), 4)


def optimize(prompt: str, f: PromptFeatures, disabled: frozenset[str] | set[str] = frozenset(),
             category: str = "auto", attachment: Attachment | None = None, target_llm: TargetLLM | None = None,
             separate_text: bool = False) -> OptimizationOutput:
    """`separate_text`: text was supplied next to the prompt (a pasted passage), which the renderers place for the
    target LLM. An attachment counts as material to work on, like supplied text."""
    unknown = set(disabled) - set(RULE_CODES)
    if unknown:
        raise ValueError(f"unknown rule codes: {sorted(unknown)}")
    attachment = attachment or Attachment()
    stage_a_category = f.task_type
    f, source = apply_category_choice(f, category)
    log.info("category %s from %s (Stage A said %s)", f.task_type, source, stage_a_category)
    if attachment.type != "none" and not f.has_context:
        f = f.model_copy(update={"has_context": True})
    ir = initial_ir(prompt, f, attachment, target_llm, source)
    steps = []
    for code, rule in RULES:
        if code in disabled:
            continue
        new = rule(ir, f)
        before, after = render_plain(ir), render_plain(new)
        if after != before:
            steps.append({"rule_code": code, "before": before, "after": after})
        ir = new
    ir = ir.model_copy(update={"context_ref": context_ref_for(ir.context, separate_text, ir.attachment)})
    return OptimizationOutput(original=prompt, optimized_text=render_plain(ir), ir=ir, steps=steps,
                              confidence=confidence(ir, f),
                              needs_stage_c=any(u.startswith(STAGE_C_REASONS) for u in ir.unresolved))
