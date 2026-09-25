"""Model-agnostic intermediate representation (IR) of a prompt.

Stage B rules read and return a PromptIR; they never edit a string in place, so each change is small, testable and
can be logged. `render_plain` turns the IR into the generic optimized text; per-LLM renderings (XML tags for Claude,
markdown for GPT) come later and use the same IR.
"""
from pydantic import BaseModel, ConfigDict

from app.stage_a.schema import Category


class PromptIR(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: Category
    task: str                                   # what to do, in the user's words (cleaned up)
    context: str | None = None                  # material that was embedded in the prompt (list, code), moved out by B07
    constraints: tuple[str, ...] = ()           # length, programming language, ...
    requirements: tuple[str, ...] = ()          # task-specific rules, e.g. the allowed labels
    output_format: str | None = None
    category_group: str | None = None           # set by B08 when only the category group is known, not the category
    unresolved: tuple[str, ...] = ()            # what Stage B could not fix; Stage C (or the user) has to


def render_plain(ir: PromptIR) -> str:
    """Task, then the input it works on, then requirements, constraints and output format in one short paragraph."""
    parts = [ir.task]
    if ir.context:
        parts.append("Input:\n" + ir.context)
    tail = " ".join([*ir.requirements, *ir.constraints, *([ir.output_format] if ir.output_format else [])])
    if tail:
        parts.append(tail)
    return "\n\n".join(p for p in parts if p)
