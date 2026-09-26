"""Stage B rules (B01-B13). Each rule is a separate, pure function `(ir, features) -> PromptIR`.

A rule returns the IR unchanged when it does not apply, so the optimizer can tell which rules fired. Rules only add
content for the five known categories, and only when Stage A is confident about the category
(CATEGORY_MIN_CONFIDENCE); when it is only confident about the group of text-based categories, B08 adds group-level
rules instead; otherwise they only clean up. Anything a rule cannot fix deterministically is recorded in
`ir.unresolved` for Stage C.
"""
import re

from app.stage_a import rules as detect
from app.stage_a.schema import PromptFeatures
from app.stage_b.ir import PromptIR, render_plain

_I = re.IGNORECASE

# Category-specific rules (B03-B06) apply only at or above this Stage A category confidence. On val, Stage A is right
# 77-96% of the time above 0.6 and 47-59% of the time between 0.4 and 0.6: a wrong format is worse than none.
CATEGORY_MIN_CONFIDENCE = 0.6
KNOWN_CATEGORIES = {"closed_qa", "information_extraction", "classification", "summarization", "coding"}


def category_is_reliable(ir: PromptIR, f: PromptFeatures) -> bool:
    return ir.category in KNOWN_CATEGORIES and f.confidence >= CATEGORY_MIN_CONFIDENCE


# ---------------------------------------------------------------- shared text clean-up
_QUESTION_START = re.compile(
    r"^(?:what|what's|who|who's|whom|whose|which|when|where|why|how|is|are|was|were|do|does|did|can|could|should|"
    r"would|will|has|have|had)\b", _I)
_BEFORE_I = {"do", "does", "did", "can", "could", "should", "would", "will", "have", "am", "was", "if", "when", "so",
             "and", "but", "that", "what", "how", "where", "why", "then", "because"}
_VERBS_AFTER_I = {"am", "was", "have", "had", "need", "want", "would", "will", "do", "did", "can", "think", "know",
                  "mean", "use", "got", "tried", "make", "get", "create", "write", "find", "add", "fix", "see", "run",
                  "remove", "convert", "check", "sort", "change", "turn", "set", "print", "read", "call", "compute",
                  "calculate", "implement", "should", "could"}


def _capital_i(text: str) -> str:
    """'how do i sort' -> 'how do I sort', but leave a loop variable alone ('for i in range')."""
    words = text.split(" ")
    for k, w in enumerate(words):
        if re.fullmatch(r"i'(?:m|d|ve|ll)", w):
            words[k] = "I" + w[1:]
        elif w == "i":
            prev = words[k - 1].lower() if k else ""
            nxt = words[k + 1].lower() if k + 1 < len(words) else ""
            if prev in _BEFORE_I or nxt in _VERBS_AFTER_I or (k == 0 and nxt.isalpha() and nxt != "in"):
                words[k] = "I"
    return " ".join(words)


def tidy(text: str) -> str:
    """Collapse whitespace, fix spacing around punctuation, capitalise, and end with '.' or '?'."""
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(r"\s+([,.;:?!])", r"\1", t)
    t = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", t)                # ", ," left behind by removals
    t = re.sub(r"^[\s,.;:!-]+|[\s,;:-]+$", "", t)
    t = re.sub(r",\s*([.?!])$", r"\1", t)
    t = _capital_i(t)
    if not t:
        return t
    t = t[0].upper() + t[1:]
    question = _QUESTION_START.match(t) and "?" not in t
    if t[-1] not in ".?!":
        t += "?" if question else "."
    elif question and t.endswith(".") and not t.endswith(".."):         # "hey, which one is ..." lost its greeting
        t = t[:-1] + "?"
    return t


# ---------------------------------------------------------------- B07: structure
DATA_CATEGORIES = {"classification", "information_extraction", "summarization", "coding"}
_FENCE = re.compile(r"```.*?```", re.S)
_COLON = re.compile(r":(?=\s)")


def b07_standardize_structure(ir: PromptIR, f: PromptFeatures) -> PromptIR:
    """Move material embedded in the prompt (a code block, or a list/passage after 'task:') into the IR context,
    so the task, the input, the constraints and the output format each end up in their own place; tidy the task.
    Runs first, so the other rules never edit the user's data."""
    task, context = ir.task, ir.context
    if context is None:
        fences = _FENCE.findall(task)
        if fences:
            context, task = "\n\n".join(fences), _FENCE.sub(" ", task)
        elif ir.category in DATA_CATEGORIES and (m := _COLON.search(task)):
            head, tail = task[:m.start()], task[m.end():].strip()
            if ("\n" not in head and len(head.split()) <= 25 and not tail.endswith("?")
                    and (len(tail.split()) >= 8 or "," in tail or "\n" in tail)):
                task, context = head, tail
    task = tidy(task)
    if (task, context) == (ir.task, ir.context):
        return ir
    return ir.model_copy(update={"task": task, "context": context})


# ---------------------------------------------------------------- B01: filler
_MODAL_START = re.compile(r"^\s*(?:(?:hey|hi|hello)\W*\s*)?(?:could|can|would|will) you\b", _I)
# 'print please enter your name': words right after these are content (the text to print), not filler
_CONTENT_VERB = re.compile(r"\b(?:print|prints|printing|say|says|saying|display|displays|output|outputs|echo|alert|"
                           r"prompt|prompts|show|shows|write out)\b", _I)
_QUOTE_MARK = re.compile(r"[\"“”]|(?<!\w)'|'(?!\w)")


def _is_content(text: str, start: int) -> bool:
    """True if a filler match at `start` is inside quotes or within 4 words after a content verb."""
    before = text[:start]
    if len(_QUOTE_MARK.findall(before)) % 2 == 1:
        return True
    return bool(_CONTENT_VERB.search(" ".join(before.split()[-4:])))


def b01_remove_filler(ir: PromptIR, f: PromptFeatures) -> PromptIR:
    """Delete politeness and filler ('hey', 'could you please', 'I was wondering if', 'just', 'for me').
    Uses the same phrase list as detector A04. 'Can you ...?' becomes an instruction ending in '.'. Filler inside
    quotes or right after a content verb ('print please enter your name') is part of the content and is kept."""
    task = ir.task
    for p in detect.FILLER_PATTERNS:
        task = p.sub(lambda m: m.group(0) if _is_content(m.string, m.start()) else " ", task)
    if len(task.split()) < 2:                                   # nothing but filler: leave it for Stage C
        return ir
    if _MODAL_START.match(ir.task) and task.rstrip().endswith("?") and not _QUESTION_START.match(task.strip()):
        task = task.rstrip()[:-1]
    task = tidy(task)
    return ir if task == ir.task else ir.model_copy(update={"task": task})


# ---------------------------------------------------------------- B02: repetition
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def b02_remove_duplicates(ir: PromptIR, f: PromptFeatures) -> PromptIR:
    """Drop accidental doubled words ('the the') and sentences that repeat an earlier one (3+ words)."""
    task = detect._REPEATED_WORD.sub(
        lambda m: m.group(1) if m.group(1).lower() not in detect._ALLOWED_DOUBLES and not m.group(1).isdigit()
        else m.group(0), ir.task)
    seen, kept = set(), []
    for s in _SENTENCE.split(task):
        key = detect._norm(s)
        if len(key.split()) >= 3 and key in seen:
            continue
        seen.add(key)
        kept.append(s)
    task = tidy(" ".join(kept))
    return ir if task == ir.task else ir.model_copy(update={"task": task})


# ---------------------------------------------------------------- B08: category group fallback
# Stage A often cannot tell these apart (a degraded summarization or extraction prompt reads like a question), but is
# much surer that the prompt is one of them. All three work on attached text and want a short, grounded answer.
TEXT_GROUP = ("closed_qa", "information_extraction", "summarization")
TEXT_GROUP_NAME = "text_based"
GROUP_BOTH = "Answer from the provided text in at most three sentences."
GROUP_GROUNDED = "Answer from the provided text."
GROUP_LENGTH = "Answer in at most three sentences."
_ALREADY_GROUNDED = re.compile(r"\bfrom (?:the|this) (?:provided|given|attached) (?:text|passage|context)\b|"
                               r"\b(?:only|solely) (?:use |using |on |from )?(?:the|this) (?:provided |given |attached )?"
                               r"(?:text|passage|context|article)\b|\b(?:based on|according to) (?:the|this)\b", _I)


def group_applies(f: PromptFeatures) -> bool:
    """No single category reaches the confidence gate, but the text-based group does, and text is attached."""
    scores = f.category_scores
    return (bool(scores) and max(scores.values()) < CATEGORY_MIN_CONFIDENCE and f.has_context
            and sum(scores.get(c, 0.0) for c in TEXT_GROUP) >= CATEGORY_MIN_CONFIDENCE)


def b08_group_fallback(ir: PromptIR, f: PromptFeatures) -> PromptIR:
    """closed_qa / information_extraction / summarization, but unclear which: ask for an answer grounded in the
    provided text and a concise length (unless already stated). No category-specific format. Resolves the category
    at group level, so the prompt does not need Stage C for it."""
    if not group_applies(f):
        return ir
    ground, length = not _ALREADY_GROUNDED.search(ir.task), "length" not in f.constraints_present
    added = {(True, True): (GROUP_BOTH,), (True, False): (GROUP_GROUNDED,), (False, True): (GROUP_LENGTH,)}.get(
        (ground, length), ())
    return ir.model_copy(update={"constraints": (*ir.constraints, *added), "category_group": TEXT_GROUP_NAME,
                                 "unresolved": tuple(u for u in ir.unresolved if u != "task category")})


# ---------------------------------------------------------------- B06: labels
_LABEL = r"[\w'-]+(?: [\w'-]+){0,3}"
_END = r"(?=\s*(?:[.?!:,;]|$))"
LABEL_PATTERNS = [re.compile(p, _I) for p in (
    # "classify these as X, Y or Z", "sort them into X and Y"
    rf"\b(?:as|into)\s+(?:either\s+)?(?:an?\s+|the\s+)?(?P<labels>{_LABEL}(?:,\s*{_LABEL})*,?\s+(?:or|and)\s+"
    rf"(?:an?\s+)?{_LABEL}){_END}",
    # "which are X and which are Y"
    # (up to two words between "which" and "is/are": "which of these are X and which are Y", val dolly-7818)
    rf"\bwhich (?:\w+ ){{0,2}}(?:is|are) (?:an?\s+)?(?P<a>{_LABEL}),? and which (?:\w+ ){{0,2}}(?:is|are) (?:an?\s+)?"
    rf"(?P<b>{_LABEL}){_END}",
    # "which one is string or percussion", "is it a fruit or a vegetable"
    rf"\b(?:is|are)\s+(?:(?:it|this|each|they|these)\s+)?(?:an?\s+|the\s+)?(?P<labels>{_LABEL}\s+or\s+(?:an?\s+)?"
    rf"{_LABEL}){_END}",
)]
# "which of these ski resorts are in utah" (no alternatives given): a yes/no decision per item
# never for two groups ("which ... are X and which are Y"): that names the labels, it is not a yes/no question
_YES_NO = re.compile(r"^(?!.*\band which\b)which (?:of )?(?:these|the following|the|those)\b(?:(?! or ).)*\b(?:is|are|was|were|can|could|"
                     r"has|have)\b(?:(?! or ).)*$", _I)
_ARTICLE = re.compile(r"^(?:an?|the)\s+", _I)
_LABELS_GIVEN = re.compile(r"\b(?:labels?|categories|classes)\s*:", _I)       # already optimized, or user listed them


def extract_labels(task: str) -> list[str]:
    """Allowed labels named in a classification prompt, or [] if none can be found reliably.

    When the labels run to the end of the prompt with no punctuation ('is string or percussion agung bell'), the
    item is glued onto the last label, so the last label is cut to the length of the longest other label."""
    for p in LABEL_PATTERNS:
        m = p.search(task)
        if not m:
            continue
        raw = [m["a"], m["b"]] if "a" in m.groupdict() else re.split(r",\s*(?:or\s+|and\s+)?|\s+or\s+|\s+and\s+",
                                                                      m["labels"])
        labels = [_ARTICLE.sub("", x.strip()).strip(" '\"") for x in raw if x and x.strip(" '\"")]
        if len(labels) >= 2 and not task[m.end():].strip():
            longest = max(len(x.split()) for x in labels[:-1])
            labels[-1] = " ".join(labels[-1].split()[:longest])
        if 2 <= len(labels) <= 8 and len({x.lower() for x in labels}) == len(labels):
            return labels
    return []


def b06_add_labels(ir: PromptIR, f: PromptFeatures) -> PromptIR:
    """Classification: state the allowed labels explicitly. If the prompt names none, a 'which of these ... are X'
    question becomes a yes/no decision per item; otherwise the label set is left to Stage C."""
    if ir.category != "classification" or not category_is_reliable(ir, f) or _LABELS_GIVEN.search(render_plain(ir)):
        return ir
    labels = extract_labels(ir.task.rstrip(".?!"))
    if labels:
        req = "Use only these labels: " + ", ".join(f'"{x}"' for x in labels) + "."
    elif _YES_NO.match(ir.task.rstrip(".?!")):
        req = 'Use only these labels: "yes", "no".'
    else:
        return ir.model_copy(update={"unresolved": (*ir.unresolved, "label set")})
    return ir.model_copy(update={"requirements": (*ir.requirements, req)})


# ---------------------------------------------------------------- B05: programming language
DEFAULT_LANGUAGE = "Python"
KEEP_LANGUAGE = "Keep the language of the given code."


def b05_add_language(ir: PromptIR, f: PromptFeatures) -> PromptIR:
    """Coding prompts that name no language get the default one, unless code was supplied: then the language is
    whatever that code is written in, which a regex cannot safely tell."""
    if ir.category != "coding" or not category_is_reliable(ir, f) or "language" not in f.missing_constraints:
        return ir
    rule = KEEP_LANGUAGE if f.has_context else f"Use {DEFAULT_LANGUAGE}."
    return ir.model_copy(update={"constraints": (*ir.constraints, rule)})


# ---------------------------------------------------------------- B04: length
LENGTH_DEFAULTS = {
    "closed_qa": "Answer in at most two sentences.",
    "summarization": "Keep it under 100 words.",
}


def b04_add_length(ir: PromptIR, f: PromptFeatures) -> PromptIR:
    """Add the category's default length limit when the prompt states none (only where length matters)."""
    if ir.category not in LENGTH_DEFAULTS or not category_is_reliable(ir, f) or "length" not in f.missing_constraints:
        return ir
    return ir.model_copy(update={"constraints": (*ir.constraints, LENGTH_DEFAULTS[ir.category])})


# ---------------------------------------------------------------- B03: output format
FORMAT_DEFAULTS = {
    "closed_qa": "Start with the direct answer.",
    "information_extraction": 'List each extracted item on its own line; if the text does not contain it, reply '
                              '"Not found".',
    "classification": 'For each item, output "item: label" on its own line.',
    "summarization": "Use bullet points.",
    "coding": "Return only the code, in a single code block.",
}
SINGLE_LABEL_FORMAT = "Output only the label."
# One item only when the prompt asks a yes/no-style question about one thing ("Is a tomato a fruit or a vegetable?")
# and nothing hints at more. Classification prompts almost always list several items, often glued onto the question
# without punctuation ("which instrument is string or percussion lummi stick timple"): on val, the old rule (single
# unless "these/each/list/...") picked the single-label format for 8 prompts, all with 2+ items.
_ONE_ITEM_START = re.compile(r"^(?:is|was|does|do)\b", _I)
_SEVERAL = re.compile(r"[,;]|\band\b|\b(?:these|following|each|every|all|list|items|them|which)\b", _I)


def _single_item(ir: PromptIR) -> bool:
    return not ir.context and bool(_ONE_ITEM_START.match(ir.task)) and not _SEVERAL.search(ir.task)


def b03_add_output_format(ir: PromptIR, f: PromptFeatures) -> PromptIR:
    """Add the category's default output format when the prompt states none."""
    if f.has_format_spec or ir.output_format or ir.category_group:
        return ir
    if not category_is_reliable(ir, f):
        return ir.model_copy(update={"unresolved": (*ir.unresolved, "output format")})
    fmt = FORMAT_DEFAULTS[ir.category]
    if ir.category == "classification":
        fmt = SINGLE_LABEL_FORMAT if _single_item(ir) else fmt
    return ir.model_copy(update={"output_format": fmt})


# ---------------------------------------------------------------- B09-B13: attachment modifier
# The attachment is a modifier, not a category: these rules add how to use the attached file, whatever the task. One
# rule per type, so the ablation can switch each off. An attachment is also what a vague "this"/"that file" points
# at, so the rule resolves Stage A's ambiguous-reference finding.
ATTACHMENT_REQUIREMENTS = {
    "image": ("Use what is visible in the attached image{name}; describe the parts you rely on.",
              "If something is not visible or not readable in the image, say so instead of guessing."),
    "pdf": ("Use the attached PDF{name} as the source.",
            "Cite the page or section numbers for the information you use.",
            "If the PDF does not contain the answer, say so."),
    "pptx": ("Use the attached slide deck{name} as the source.",
             "Refer to slides by their number.",
             "If the slides do not contain the answer, say so."),
    "docx": ("Use the attached Word document{name} as the source.",
             "Cite the section headings for the information you use.",
             "If the document does not contain the answer, say so."),
    "other": ("Use the attached file{name} as the source.",
              "If you cannot open or read the file, say so instead of guessing."),
}


def _attachment_rule(kind: str):
    def rule(ir: PromptIR, f: PromptFeatures) -> PromptIR:
        if ir.attachment.type != kind:
            return ir
        name = f" ({ir.attachment.name})" if ir.attachment.name else ""
        reqs = tuple(r.format(name=name) for r in ATTACHMENT_REQUIREMENTS[kind])
        unresolved = tuple(u for u in ir.unresolved if not u.startswith("ambiguous reference"))
        return ir.model_copy(update={"requirements": (*reqs, *ir.requirements), "unresolved": unresolved})

    rule.__name__ = f"b_attachment_{kind}"
    rule.__doc__ = (f"{kind} attachment: {' '.join(ATTACHMENT_REQUIREMENTS[kind])} Resolves an ambiguous reference "
                    f"(the attachment is what it refers to).")
    return rule


b09_attachment_image = _attachment_rule("image")
b10_attachment_pdf = _attachment_rule("pdf")
b11_attachment_pptx = _attachment_rule("pptx")
b12_attachment_docx = _attachment_rule("docx")
b13_attachment_other = _attachment_rule("other")


# ---------------------------------------------------------------- registry
# Application order: structure first (so later rules never touch embedded data), then clean-up, then the attachment
# (its instructions come first among the requirements), then the other additions.
RULES = [
    ("B07_STANDARDIZE_STRUCTURE", b07_standardize_structure),
    ("B01_REMOVE_FILLER", b01_remove_filler),
    ("B02_REMOVE_DUPLICATES", b02_remove_duplicates),
    ("B09_ATTACHMENT_IMAGE", b09_attachment_image),
    ("B10_ATTACHMENT_PDF", b10_attachment_pdf),
    ("B11_ATTACHMENT_PPTX", b11_attachment_pptx),
    ("B12_ATTACHMENT_DOCX", b12_attachment_docx),
    ("B13_ATTACHMENT_OTHER", b13_attachment_other),
    ("B08_GROUP_FALLBACK", b08_group_fallback),
    ("B06_ADD_LABELS", b06_add_labels),
    ("B05_ADD_LANGUAGE", b05_add_language),
    ("B04_ADD_LENGTH", b04_add_length),
    ("B03_ADD_OUTPUT_FORMAT", b03_add_output_format),
]
