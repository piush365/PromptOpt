"""Render one PromptIR for each target LLM family. The same fields, in the structure each provider recommends.

* Claude (Anthropic prompt engineering guide): XML tags separate the parts of a prompt; long material goes at the
  top in <document> tags, the instructions after it. Tags: <document>, <input>, <attachment>, <task>,
  <requirements>, <constraints>, <output_format>.
* GPT (OpenAI prompting guide for the GPT-4.1/GPT-5 family): markdown sections ("# Task", "# Instructions" with
  "## Requirements" / "## Constraints" sub-sections, "# Output Format", then "# Input" / "# Context"), with data in
  delimited blocks so it cannot be read as instructions.
* Gemini (Google's prompt design strategies): clearly labelled sections ("Task:", "Constraints:", "Output format:"),
  with the context first and the task and instructions at the end, after the data.

Every renderer includes every rendered field of the IR (see app.stage_b.ir): task, context, the separate text
(`context_text`, when context_ref is "separate" or the caller passes it), attachment, requirements, constraints and
output_format. Data blocks (inline input, separate text) are fenced with a fence longer than any backtick run inside
them, so code or markdown in the data survives unchanged.

    rendered = render_all(result.ir, context_text=pasted_text)
    repository.save_renderings(db, result_id, rendered)
"""
import re
from typing import Callable

from app.stage_b.ir import PromptIR, TargetLLM

TARGETS: tuple[TargetLLM, ...] = ("claude", "gpt", "gemini")
ATTACHMENT_LABELS = {"image": "an image", "pdf": "a PDF", "pptx": "a slide deck (PPTX)", "docx": "a Word document",
                     "other": "a file"}


def attachment_note(ir: PromptIR) -> str | None:
    """One sentence saying what is attached, or None."""
    a = ir.attachment
    if a.type == "none":
        return None
    return f"The user attached {ATTACHMENT_LABELS[a.type]}" + (f" named {a.name}." if a.name else ".")


def fence(text: str, info: str = "") -> str:
    """A fenced block that `text` cannot close early: the fence is longer than any backtick run inside it."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{info}\n{text}\n{ticks}"


def _bullets(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {x}" for x in items)


def render_claude(ir: PromptIR, context_text: str | None = None) -> str:
    parts = []
    if context_text:
        parts.append(f"<document>\n{context_text}\n</document>")
    if ir.context:
        parts.append(f"<input>\n{ir.context}\n</input>")
    if note := attachment_note(ir):
        parts.append(f"<attachment>\n{note}\n</attachment>")
    parts.append(f"<task>\n{ir.task}\n</task>")
    if ir.requirements:
        parts.append(f"<requirements>\n{_bullets(ir.requirements)}\n</requirements>")
    if ir.constraints:
        parts.append(f"<constraints>\n{_bullets(ir.constraints)}\n</constraints>")
    if ir.output_format:
        parts.append(f"<output_format>\n{ir.output_format}\n</output_format>")
    return "\n\n".join(parts)


def render_gpt(ir: PromptIR, context_text: str | None = None) -> str:
    parts = [f"# Task\n{ir.task}"]
    if ir.requirements or ir.constraints:
        sub = [f"## {name}\n{_bullets(items)}" for name, items in (("Requirements", ir.requirements),
                                                                   ("Constraints", ir.constraints)) if items]
        parts.append("# Instructions\n" + "\n\n".join(sub))
    if ir.output_format:
        parts.append(f"# Output Format\n{ir.output_format}")
    if note := attachment_note(ir):
        parts.append(f"# Attachment\n{note}")
    if ir.context:
        parts.append(f"# Input\n{fence(ir.context)}")
    if context_text:
        parts.append(f"# Context\n{fence(context_text)}")
    return "\n\n".join(parts)


def render_gemini(ir: PromptIR, context_text: str | None = None) -> str:
    parts = []
    if context_text:
        parts.append(f"Context:\n{fence(context_text)}")
    if ir.context:
        parts.append(f"Input:\n{fence(ir.context)}")
    if note := attachment_note(ir):
        parts.append(f"Attachment: {note}")
    parts.append(f"Task: {ir.task}")
    if ir.requirements:
        parts.append(f"Requirements:\n{_bullets(ir.requirements)}")
    if ir.constraints:
        parts.append(f"Constraints:\n{_bullets(ir.constraints)}")
    if ir.output_format:
        parts.append(f"Output format: {ir.output_format}")
    return "\n\n".join(parts)


RENDERERS: dict[str, Callable[[PromptIR, str | None], str]] = {
    "claude": render_claude, "gpt": render_gpt, "gemini": render_gemini}


def render(ir: PromptIR, target: TargetLLM | None = None, context_text: str | None = None) -> str:
    """Render for `target`, or for the IR's own target_llm."""
    target = target or ir.target_llm
    if target not in RENDERERS:
        raise ValueError(f"unknown target LLM {target!r}; expected one of {TARGETS}")
    return RENDERERS[target](ir, context_text)


def render_all(ir: PromptIR, context_text: str | None = None,
               targets: tuple[TargetLLM, ...] = TARGETS) -> dict[str, str]:
    """{target: rendered prompt}, the format repository.save_renderings takes."""
    return {t: RENDERERS[t](ir, context_text) for t in targets}
