"""Render one PromptIR for each target LLM family. The same content in all three, in the structure each provider
recommends, with four sections: task, context, constraints, output format.

* Claude (Anthropic prompt engineering guide): XML tags. Long material goes at the top, so <context> comes first
  (with <document>, <input> and <attachment> inside it), then <task>, <constraints>, <output_format>.
* GPT (OpenAI prompting guide for the GPT-4.1/GPT-5 family): markdown sections "### Task", "### Context",
  "### Constraints", "### Output format", with data in delimited blocks so it cannot be read as instructions.
* Gemini (Google's prompt design strategies): clearly labelled sections in plain text, the instruction first and the
  context after it: "Task:", "Constraints:", "Output format:", then "Context:".

Section contents (the same for every target):
* task          ir.task
* context       the separate text (`context_text`: a pasted passage, labelled Document), the material that was in the
                prompt (ir.context, labelled Input) and the attachment note (labelled Attachment), each when present
* constraints   ir.requirements, then ir.constraints, one bullet each
* output format ir.output_format
Data blocks (Input, Document) are fenced with a fence longer than any backtick run inside them, so code or markdown
in the data survives unchanged. Metadata (category, unresolved, ...) is never rendered.

    rendered = render_all(result.ir, context_text=pasted_text)
    repository.save_renderings(db, result_id, rendered)
    token_counts(rendered)      # {"gpt": {"tokens": 41, "method": "tiktoken o200k_base", "exact": True}, ...}
"""
import re
from functools import lru_cache
from typing import Callable

from app.stage_b.ir import PromptIR, TargetLLM

TARGETS: tuple[TargetLLM, ...] = ("claude", "gpt", "gemini")
ATTACHMENT_LABELS = {"image": "an image", "pdf": "a PDF", "pptx": "a slide deck (PPTX)", "docx": "a Word document",
                     "spreadsheet": "a spreadsheet", "code": "a code file", "other": "a file"}


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


def constraint_items(ir: PromptIR) -> tuple[str, ...]:
    """Requirements (task-specific rules, attachment use) first, then constraints (length, language, ...)."""
    return (*ir.requirements, *ir.constraints)


def _context_parts(ir: PromptIR, context_text: str | None) -> list[tuple[str, str]]:
    """[(label, text)] for the context section: Document (separate text), Input (from the prompt), Attachment."""
    parts = []
    if context_text:
        parts.append(("Document", context_text))
    if ir.context:
        parts.append(("Input", ir.context))
    if note := attachment_note(ir):
        parts.append(("Attachment", note))
    return parts


def _plain_context(parts: list[tuple[str, str]]) -> str:
    """Labelled context for GPT and Gemini: data fenced, the attachment note on one line."""
    return "\n\n".join(f"{label}: {text}" if label == "Attachment" else f"{label}:\n{fence(text)}"
                       for label, text in parts)


def render_claude(ir: PromptIR, context_text: str | None = None) -> str:
    out = []
    if parts := _context_parts(ir, context_text):
        inner = "\n".join(f"<{label.lower()}>\n{text}\n</{label.lower()}>" for label, text in parts)
        out.append(f"<context>\n{inner}\n</context>")
    out.append(f"<task>\n{ir.task}\n</task>")
    if items := constraint_items(ir):
        out.append(f"<constraints>\n{_bullets(items)}\n</constraints>")
    if ir.output_format:
        out.append(f"<output_format>\n{ir.output_format}\n</output_format>")
    return "\n\n".join(out)


def render_gpt(ir: PromptIR, context_text: str | None = None) -> str:
    out = [f"### Task\n{ir.task}"]
    if parts := _context_parts(ir, context_text):
        out.append(f"### Context\n{_plain_context(parts)}")
    if items := constraint_items(ir):
        out.append(f"### Constraints\n{_bullets(items)}")
    if ir.output_format:
        out.append(f"### Output format\n{ir.output_format}")
    return "\n\n".join(out)


def render_gemini(ir: PromptIR, context_text: str | None = None) -> str:
    out = [f"Task: {ir.task}"]
    if items := constraint_items(ir):
        out.append(f"Constraints:\n{_bullets(items)}")
    if ir.output_format:
        out.append(f"Output format: {ir.output_format}")
    if parts := _context_parts(ir, context_text):
        out.append(f"Context:\n{_plain_context(parts)}")
    return "\n\n".join(out)


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


# ---------------------------------------------------------------- input token counts
# GPT: exact, with tiktoken's o200k_base (the GPT-4o / GPT-4.1 / GPT-5 encoding). Claude and Gemini tokenizers are
# not available offline, so their counts are approximate (characters / 4, the rule of thumb both providers give for
# English) and labelled as such. tiktoken missing, or its encoding file not downloadable: GPT is approximate too.
CHARS_PER_TOKEN = 4
APPROX = "approx. (characters / 4)"


@lru_cache(maxsize=1)
def _gpt_encoding():
    try:
        import tiktoken
        return tiktoken.get_encoding("o200k_base")
    except Exception:                                   # not installed, or offline on first use
        return None


def count_tokens(text: str, target: TargetLLM) -> dict:
    """{"tokens": n, "method": how it was counted, "exact": bool}."""
    if target == "gpt" and (enc := _gpt_encoding()) is not None:
        return {"tokens": len(enc.encode(text)), "method": "tiktoken o200k_base", "exact": True}
    return {"tokens": max(1, round(len(text) / CHARS_PER_TOKEN)) if text else 0, "method": APPROX, "exact": False}


def token_counts(rendered: dict[str, str]) -> dict[str, dict]:
    """Input tokens of each rendering, counted the way its target counts them (see count_tokens)."""
    return {t: count_tokens(text, t) for t, text in rendered.items()}
