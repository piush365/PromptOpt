"""IR renderers (Claude / GPT / Gemini) and the pipeline that saves them.

The no-loss tests parse every rendering back into its sections and compare them with the IR, so a field that is
missing, moved into another section, or merged with another one fails the test.
"""
import itertools
import re

import pytest

from app.db import repository as repo
from app.pipeline import process_prompt
from app.rendering import RENDERERS, TARGETS, attachment_note, count_tokens, fence, render, render_all, token_counts
from app.stage_a.classifier import KeywordClassifier
from app.stage_a.detector import FeatureDetector
from app.stage_b.ir import Attachment, PromptIR
from app.stage_b.optimizer import optimize

DET = FeatureDetector(classifier=KeywordClassifier(), use_spacy=False)


# ---------------------------------------------------------------- parsers (the inverse of each renderer)
def _unfence(block: str) -> str:
    m = re.fullmatch(r"(`{3,})\n(.*)\n\1", block, re.S)
    assert m, f"not a fenced block: {block!r}"
    return m.group(2)


def _split_outside_fences(text: str, is_header) -> list[tuple[str, list[str]]]:
    """[(header line, body lines)], where header lines inside fenced blocks do not count."""
    out, fence_len = [], 0
    for line in text.split("\n"):
        m = re.match(r"^(`{3,})", line)
        if fence_len == 0 and is_header(line):
            out.append((line, []))
            continue
        if m:
            n = len(m.group(1))
            if fence_len == 0:
                fence_len = n
            elif n == fence_len and line == m.group(1):
                fence_len = 0
        out[-1][1].append(line)
    return out


def _items(body: str) -> tuple[str, ...]:
    lines = [x for x in body.split("\n") if x]
    assert all(x.startswith("- ") for x in lines), body
    return tuple(x[2:] for x in lines)


def _sections(text: str, labels: tuple[str, ...]) -> dict[str, str]:
    """{label: body} for lines starting with 'label:' outside fenced blocks ('Task: x' keeps x on the first line)."""
    sec = {}
    for head, body in _split_outside_fences("\0\n" + text, lambda x: x == "\0" or x.startswith(labels)):
        label, _, rest = head.partition(":")
        sec[label] = "\n".join(([rest.strip()] if rest.strip() else []) + body).strip("\n")
    sec.pop("\0", None)
    return sec


def _plain_context(body: str | None) -> dict:
    sec = _sections(body or "", ("Document:", "Input:", "Attachment:"))
    return {"context": _unfence(sec["Input"]) if "Input" in sec else None,
            "context_text": _unfence(sec["Document"]) if "Document" in sec else None,
            "attachment": sec.get("Attachment")}


def parse_claude(text: str) -> dict:
    top = dict(re.findall(r"^<(context|task|constraints|output_format)>\n(.*?)\n</\1>$", text, re.S | re.M))
    inner = dict(re.findall(r"<(document|input|attachment)>\n(.*?)\n</\1>", top.get("context", ""), re.S))
    return {"task": top.get("task"), "context": inner.get("input"), "context_text": inner.get("document"),
            "attachment": inner.get("attachment"), "constraints": _items(top.get("constraints", "")),
            "output_format": top.get("output_format")}


def parse_gpt(text: str) -> dict:
    sec = {h[4:]: "\n".join(b).strip("\n") for h, b in _split_outside_fences(text, lambda x: x.startswith("### "))}
    return {"task": sec.get("Task"), **_plain_context(sec.get("Context")),
            "constraints": _items(sec.get("Constraints", "")), "output_format": sec.get("Output format")}


GEMINI_LABELS = ("Task:", "Constraints:", "Output format:", "Context:")


def parse_gemini(text: str) -> dict:
    sec = _sections(text, GEMINI_LABELS)
    return {"task": sec.get("Task"), **_plain_context(sec.get("Context")),
            "constraints": _items(sec.get("Constraints", "")), "output_format": sec.get("Output format")}


PARSERS = {"claude": parse_claude, "gpt": parse_gpt, "gemini": parse_gemini}


def expected(ir: PromptIR, context_text: str | None) -> dict:
    return {"task": ir.task, "context": ir.context, "context_text": context_text, "attachment": attachment_note(ir),
            "constraints": (*ir.requirements, *ir.constraints), "output_format": ir.output_format}


# ---------------------------------------------------------------- IRs to test with
FULL = PromptIR(category="classification", task="Classify each instrument as string or percussion.",
                context="tombak, cizhonghlu", context_ref="attachment",
                requirements=("Use the attached PDF (a.pdf) as the source.", 'Use only these labels: "string", "percussion".'),
                constraints=("Answer in at most two sentences.",), output_format='For each item, output "item: label".',
                attachment=Attachment(type="pdf", name="a.pdf"), target_llm="claude", unresolved=("label set",))
MINIMAL = PromptIR(category="other", task="Tell me a joke.")
TRICKY = PromptIR(
    category="coding", task="Fix the bug in this code.",
    context="```python\ndef f(x):\n    return x +\n```\n# Output Format\nTask: not a label\n</input>\n````",
    requirements=("Keep the language of the given code.",), output_format="Return only the code, in a single code block.")
TRICKY_TEXT = "Some pasted text.\n\n# Task\nContext: fake label\n```\nnested fence\n```"

PROMPTS = [
    ("which instrument is string or percussion: tombak, cizhonghlu", "auto", None, None),
    ("summarize this", "summarization", None, "The Eiffel Tower is in Paris. It opened in 1889."),
    ("write a function that reverses a string", "coding", None, None),
    ("what does this say", "auto", Attachment(type="image"), None),
    ("summarize the attached report pls", "summarization", Attachment(type="pdf", name="q3 report.pdf"), None),
    ("could you please list the dates", "information_extraction", Attachment(type="docx"), "Signed 3 May 2021."),
    ("make notes from these slides", "auto", Attachment(type="pptx", name="deck.pptx"), None),
    ("who is the author", "closed_qa", Attachment(type="other", name="data.bin"), None),
    ("fix this ```def f(x): return x +``` please", "coding", None, None),
]


def pipeline_irs():
    for text, cat, att, ctx in PROMPTS:
        f = DET.detect(text, ctx)
        yield optimize(text, f, category=cat, attachment=att, separate_text=ctx is not None).ir, ctx


CASES = [(FULL, None), (FULL, "A passage."), (MINIMAL, None), (TRICKY, TRICKY_TEXT), *pipeline_irs()]


# ---------------------------------------------------------------- no field lost
@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("case", range(len(CASES)))
def test_every_field_survives_every_renderer(target, case):
    ir, text = CASES[case]
    rendered = RENDERERS[target](ir, text)
    if target == "claude" and ir is TRICKY:          # "</input>" in the data: Claude's tags are not escaped
        for value in (ir.task, ir.context, text, *ir.requirements, ir.output_format):
            assert value in rendered
        return
    assert PARSERS[target](rendered) == expected(ir, text)


@pytest.mark.parametrize("target", TARGETS)
def test_metadata_is_not_rendered(target):
    rendered = render(FULL, target)
    for meta in ("label set", "classification", "category"):
        assert meta not in rendered


def test_same_meaning_in_every_format():
    """All three renderings of one IR carry identical field values."""
    for ir, text in CASES:
        if ir is TRICKY:
            continue
        parsed = [PARSERS[t](RENDERERS[t](ir, text)) for t in TARGETS]
        assert parsed[0] == parsed[1] == parsed[2]


# ---------------------------------------------------------------- format details
def test_claude_uses_xml_tags_with_the_context_first():
    out = render(FULL, "claude", "A passage.")
    assert out.startswith("<context>\n<document>\nA passage.\n</document>\n<input>")
    tags = re.findall(r"^<(\w+)>$", out, re.M)
    assert tags == ["context", "document", "input", "attachment", "task", "constraints", "output_format"]


def test_gpt_uses_markdown_sections():
    out = render(FULL, "gpt", "A passage.")
    heads = [x for x in out.split("\n") if x.startswith("#")]
    assert heads == ["### Task", "### Context", "### Constraints", "### Output format"]


def test_gemini_puts_the_instruction_first_and_the_context_after_it():
    out = render(FULL, "gemini", "A passage.")
    assert out.startswith("Task: Classify each instrument")
    assert out.index("Task:") < out.index("Constraints:") < out.index("Output format:") < out.index("Context:")
    assert "<" not in out and "#" not in out                     # plain text, no tags or markdown headings


def test_requirements_come_before_constraints():
    for t in TARGETS:
        out = render(FULL, t)
        assert out.index("Use the attached PDF") < out.index("Use only these labels") < out.index("at most two")


def test_token_counts_gpt_exact_others_labelled_approximate(monkeypatch):
    rendered = render_all(FULL, "A passage.")
    counts = token_counts(rendered)
    assert set(counts) == set(TARGETS)
    for t in ("claude", "gemini"):
        assert counts[t] == {"tokens": round(len(rendered[t]) / 4), "method": "approx. (characters / 4)",
                             "exact": False}
    assert counts["gpt"]["tokens"] > 0
    if counts["gpt"]["exact"]:
        assert counts["gpt"]["method"] == "tiktoken o200k_base"
    import app.rendering as r
    monkeypatch.setattr(r, "_gpt_encoding", lambda: None)            # tiktoken unavailable: approximate, labelled
    assert count_tokens("abcdefgh", "gpt") == {"tokens": 2, "method": "approx. (characters / 4)", "exact": False}


def test_fence_is_longer_than_any_backtick_run():
    assert fence("a") == "```\na\n```"
    assert fence("x ```` y").startswith("`````\n")


def test_render_uses_the_ir_target_and_rejects_unknown():
    assert render(FULL) == render(FULL, "claude")
    with pytest.raises(ValueError):
        render(MINIMAL)                               # no target anywhere
    assert set(render_all(MINIMAL)) == {"claude", "gpt", "gemini"}


def test_attachment_note():
    assert attachment_note(MINIMAL) is None
    assert attachment_note(FULL) == "The user attached a PDF named a.pdf."
    ir = MINIMAL.model_copy(update={"attachment": Attachment(type="image")})
    assert attachment_note(ir) == "The user attached an image."


# ---------------------------------------------------------------- pipeline + repository
@pytest.mark.parametrize("category, att, target", list(itertools.product(
    ["auto", "summarization"], [None, Attachment(type="pdf", name="r.pdf")], [None, "gpt"])))
def test_pipeline_saves_features_ir_steps_and_renderings(db, category, att, target):
    ctx = "Mail me at jo@example.com. The report covers Q3 revenue."
    out = process_prompt(db, "summarize this for me please", DET, category=category, attachment=att,
                         target_llm=target, context=ctx)
    db.commit()
    hist = repo.get_prompt_history(db, out.prompt_id)
    (res,) = hist["results"]
    assert set(res["renderings"]) == {"claude", "gpt", "gemini"}
    assert all("[EMAIL]" in r and "jo@example.com" not in r for r in res["renderings"].values())
    assert res["ir"]["category_source"] == ("user" if category != "auto" else "stage_a")
    assert res["ir"]["target_llm"] == target
    assert res["ir"]["context_ref"] == ("attachment" if att else "separate")
    assert hist["features"]["task_type"] == out.features.task_type          # Stage A's own answer is kept
    if att:
        assert "B10_ATTACHMENT_PDF" in [s["rule"] for s in res["steps"]]
        assert "r.pdf" in res["renderings"]["claude"]


@pytest.mark.parametrize("category, disagree", [("auto", False), ("summarization", False), ("coding", True)])
def test_pipeline_keeps_stage_a_and_flags_a_user_category_that_disagrees(db, category, disagree):
    out = process_prompt(db, "summarize this article in a few bullet points", DET, category=category,
                         context="The article text.")
    db.commit()
    assert out.stage_a_category == "summarization"                     # keyword classifier, stable
    assert out.category == (out.stage_a_category if category == "auto" else category)
    assert out.category_disagreement is disagree
    assert repo.get_prompt_history(db, out.prompt_id)["features"]["task_type"] == "summarization"
    assert set(out.token_counts) == set(TARGETS) and all(c["tokens"] > 0 for c in out.token_counts.values())
