"""Model-agnostic intermediate representation (IR) of a prompt.

Stage B rules read and return a PromptIR; they never edit a string in place, so each change is small, testable and
can be logged. `render_plain` turns the IR into the generic optimized text; app.rendering renders the same IR for a
target LLM (XML tags for Claude, markdown sections for GPT, labelled sections for Gemini).

Fields the target LLM sees: task, context (+ the separate text context_ref points at), requirements, constraints,
output_format, attachment. Metadata for the pipeline and the explanation UI, never rendered: category,
category_source, category_group, target_llm, unresolved.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.stage_a.schema import Category

AttachmentType = Literal["none", "image", "pdf", "pptx", "docx", "spreadsheet", "code", "other"]
TargetLLM = Literal["gpt", "gemini", "claude"]
# Where the material the task works on is:
#   none        there is none
#   inline      it was written in the prompt; B07 moved it into `context`
#   separate    text supplied next to the prompt (pasted passage, starter code); not stored in the IR
#   attachment  an attached file (see `attachment`)
ContextRef = Literal["none", "inline", "separate", "attachment"]


class Attachment(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: AttachmentType = "none"
    name: str | None = None                     # file name, if the user gave one


class PromptIR(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: Category
    task: str                                   # what to do, in the user's words (cleaned up)
    context: str | None = None                  # material that was embedded in the prompt (list, code), moved out by B07
    context_ref: ContextRef = "none"
    constraints: tuple[str, ...] = ()           # length, programming language, ...
    requirements: tuple[str, ...] = ()          # task-specific rules, e.g. the allowed labels, how to use an attachment
    output_format: str | None = None
    attachment: Attachment = Attachment()
    target_llm: TargetLLM | None = None         # chosen by the user; None = plain text only
    category_source: Literal["stage_a", "user", "stage_c"] = "stage_a"
    category_group: str | None = None           # set by B08 when only the category group is known, not the category
    unresolved: tuple[str, ...] = ()            # what Stage B could not fix; Stage C (or the user) has to


def context_ref_for(context: str | None, separate_text: bool, attachment: Attachment) -> ContextRef:
    """Attachment beats separate text beats inline material."""
    if attachment.type != "none":
        return "attachment"
    if separate_text:
        return "separate"
    return "inline" if context else "none"


def render_plain(ir: PromptIR) -> str:
    """Task, then the input it works on, then requirements, constraints and output format in one short paragraph."""
    parts = [ir.task]
    if ir.context:
        parts.append("Input:\n" + ir.context)
    tail = " ".join([*ir.requirements, *ir.constraints, *([ir.output_format] if ir.output_format else [])])
    if tail:
        parts.append(tail)
    return "\n\n".join(p for p in parts if p)
