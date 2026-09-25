"""Stage B entry point: `optimize(prompt, features) -> OptimizationOutput`.

    from app.stage_a import detect_features
    from app.stage_b import optimize
    f = detect_features(text)
    out = optimize(text, f)
    repository.save_optimization(db, prompt.id, out.optimized_text, out.ir.model_dump(mode="json"),
                                 out.confidence, out.steps)

Every rule that changes the text is logged as a step (rule code, text before, text after) for the explanation UI
and the `transformations` table. Rules can be switched off with `disabled` for the ablation study.
"""
from pydantic import BaseModel, Field

from app.stage_a.schema import PromptFeatures
from app.stage_b.ir import PromptIR, render_plain
from app.stage_b.rules import CATEGORY_MIN_CONFIDENCE, RULES

# Stage C (LoRA) runs only when confidence is below this. Starting value; tune it on the val split.
STAGE_C_THRESHOLD = 0.7
# Confidence = Stage A's category confidence (the category decides what gets added), minus a penalty for each
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
    def rules_applied(self) -> list[str]:
        return [s["rule_code"] for s in self.steps]


def initial_ir(prompt: str, f: PromptFeatures) -> PromptIR:
    """The prompt as it came in, plus the problems Stage A found that no Stage B rule can fix."""
    unresolved = []
    if f.task_type == "other" or f.confidence < CATEGORY_MIN_CONFIDENCE:
        unresolved.append("task category")
    if f.ambiguous_refs:
        unresolved.append("ambiguous reference: " + ", ".join(f"'{r}'" for r in f.ambiguous_refs))
    return PromptIR(category=f.task_type, task=prompt.strip(), unresolved=tuple(unresolved))


def confidence(ir: PromptIR, f: PromptFeatures) -> float:
    base = OTHER_CONFIDENCE if ir.category == "other" else f.confidence
    return round(min(1.0, max(0.0, base - UNRESOLVED_PENALTY * len(ir.unresolved))), 4)


def optimize(prompt: str, f: PromptFeatures, disabled: frozenset[str] | set[str] = frozenset(),
             threshold: float = STAGE_C_THRESHOLD) -> OptimizationOutput:
    unknown = set(disabled) - set(RULE_CODES)
    if unknown:
        raise ValueError(f"unknown rule codes: {sorted(unknown)}")
    ir = initial_ir(prompt, f)
    steps = []
    for code, rule in RULES:
        if code in disabled:
            continue
        new = rule(ir, f)
        before, after = render_plain(ir), render_plain(new)
        if after != before:
            steps.append({"rule_code": code, "before": before, "after": after})
        ir = new
    conf = confidence(ir, f)
    return OptimizationOutput(original=prompt, optimized_text=render_plain(ir), ir=ir, steps=steps,
                              confidence=conf, needs_stage_c=conf < threshold)
