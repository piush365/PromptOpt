"""Parse a free-text optimized prompt (the dataset's `optimized_prompt`) into IR fields: task, output_format,
constraints, plus the embedded data block (context). Stage C's training targets come from here.

It reuses Stage A's detectors (A02 output format, A03 constraints) and B08's grounding pattern to label sentences; no
Stage A/B code is changed. One sentence goes to exactly one field, so the fields together keep every sentence.

* The first paragraph is the instruction; later paragraphs ("Items: ...", "Input: ...", code) are context.
* The first sentence is the task (after a lone grounding sentence, which is a constraint). Clauses of a few fixed shapes are cut out of it (see `split_first`): a grounding
  clause ("Answer only from the provided text: ..."), a length ("... in two sentences", "limiting the response to 15
  words"), a trailing format
  clause ("..., and output them as a JSON array") or a format phrase ("in 3 bullet points"). Anything else that
  states a format or constraint inside the first sentence stays in the task.
* A later sentence goes to output_format when it states a structure (list, JSON, code block, one per line, only the
  label, ...); to constraints when it states a length, tone, audience, programming language or grounding ("using
  only the provided text"); otherwise it stays with the task.
* A sentence right after a format sentence that only describes the elements ("Each element has ...") is format too.
"""
import re

from pydantic import BaseModel

from app.stage_a import rules as detect
from app.stage_b.rules import _ALREADY_GROUNDED

_I = re.IGNORECASE
_PARAGRAPH = re.compile(r"\n\s*\n")
_ABBREV = re.compile(r"\b(?:e\.g|i\.e|etc|vs|approx|Mr|Mrs|Ms|Dr|St|No|U\.S|U\.K)\.$", _I)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[A-Z0-9])")

# A02 patterns that only state a length ("in 3 sentences", "(max 50 words)"): a length is a constraint, as in
# Stage B (B04 puts it in constraints). Indices into detect.FORMAT_PATTERNS.
_LENGTH_ONLY = {10, 11, 23, 24}
# Plus a few layouts A02 misses (A02 itself is frozen): "on a separate line", "one per line", "Output each item ..."
_STRUCTURE = [p for i, p in enumerate(detect.FORMAT_PATTERNS) if i not in _LENGTH_ONLY] + [re.compile(p, _I) for p in (
    r"\bon (?:a )?(?:separate|new) lines?\b",
    r"\b(?:one|each) [\w-]+(?: [\w-]+)? per line\b",
    r"^(?:output|list|print|return|write) (?:each|every|one)\b",
)]
_FORMAT_FOLLOW_UP = re.compile(r"^(?:each|every|separate|the (?:array|list|object|output|table|json)|use (?:the )?"
                               r"(?:keys?|fields?|columns?)|include (?:the )?(?:keys?|fields?|columns?))\b", _I)


class ParsedPrompt(BaseModel):
    task: str
    output_format: str | None = None
    constraints: list[str] = []
    context: str | None = None


def split_sentences(text: str) -> list[str]:
    """Sentences of one paragraph; does not split after 'e.g.', 'vs.', 'U.S.' or inside a number ('3.5')."""
    out: list[str] = []
    for piece in _SENTENCE_END.split(" ".join(text.split())):
        if out and _ABBREV.search(out[-1]):
            out[-1] += " " + piece
        else:
            out.append(piece)
    return [s.strip() for s in out if s.strip()]


def is_format(sentence: str) -> bool:
    return any(p.search(sentence) for p in _STRUCTURE)


def is_constraint(sentence: str) -> bool:
    return bool(detect.detect_constraints(sentence)) or bool(_ALREADY_GROUNDED.search(sentence)) or bool(
        detect.detect_format_spec(sentence))          # a length-only A02 match ("in 3 sentences")


_NUMBER = r"(?:\d+(?:\s*[-–]\s*\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|a single|single)"
# "..., and output it as JSON ...": the tail clause, if it states a structure, becomes its own format sentence
_FORMAT_TAIL = re.compile(r"(?:,\s*|\s+)(?:and\s+|then\s+)+(?=(?:output|return|present|format|list|give|provide|"
                          r"respond|reply|show|display|put|write|separate|number)\b)", _I)
# "Summarize X in 3 bullet points, focusing on Y": the format phrase is cut out of the task
_FORMAT_PHRASE = re.compile(
    rf"\s*,?\s*\b(?P<prep>in|as|using|with|into)\s+(?P<np>(?:a\s+|an\s+)?(?:(?:up to |at most |exactly )?{_NUMBER}\s+)?"
    r"(?:(?:concise|short|brief|clear|single|separate)\s+)?(?:bullet(?:ed)? points?|bullets|bullet(?:ed)? list|"
    r"numbered list|comma[- ]separated list|JSON(?: array| object| list)?|(?:markdown )?table|code block|"
    r"key[- ]value pairs?))\b", _I)
# "Answer only from the provided text: why ...", "..., using only the provided text."
_GROUND = (r"(?:(?:answer|respond)\s+(?:the (?:following )?question\s+)?)?(?:only\s+|solely\s+)?(?:using|from|"
           r"based (?:only |solely )?on|according to)\s+(?:only\s+|solely\s+)?(?:(?:the )?information (?:from|in)\s+)?"
           r"the (?:provided|given) (?:text|passage|context)")
_GROUND_HEAD = re.compile(rf"^(?P<c>{_GROUND})\s*[:,]\s*", _I)
_GROUND_TAIL = re.compile(rf"\s*,?\s+(?P<c>(?:using|based (?:only |solely )?on)\s+(?:only\s+)?the (?:provided|given) "
                          rf"(?:text|passage|context))(?P<end>[.?!]?)$", _I)
# "... in two sentences, focusing on ...", "..., limiting the response to 15 words or fewer."
_LENGTH_PHRASE = re.compile(rf"\s*,?\s+(?P<c>(?:in|within|using|under) (?:at most |no more than |under |up to |exactly )?"
                            rf"{_NUMBER} (?:words?|sentences?|paragraphs?|lines?)(?: or (?:fewer|less))?)\b", _I)
_LIMIT_PHRASE = re.compile(rf"\s*,?\s+(?P<c>(?:limiting|limit|keeping|keep) (?:the |your )?(?:response|answer|summary|"
                           rf"output|it) (?:to|under|within) (?:at most |no more than |under |up to )?{_NUMBER} "
                           rf"(?:words?|sentences?|paragraphs?|lines?)(?: or (?:fewer|less))?)\b", _I)
_GROUND_ONLY = re.compile(rf"^{_GROUND}\.?$", _I)
# only a restrictive clause is a constraint; "From the provided text, extract X" names the source and stays in the task
_RESTRICTS = re.compile(r"\b(?:only|solely)\b", _I).search


def _sentence(text: str) -> str:
    t = re.sub(r"\s+([,.;:?!])", r"\1", re.sub(r"\s+", " ", text)).strip(" ,;:")
    t = re.sub(r",\s*([.?!])$", r"\1", t)
    if not t:
        return t
    t = t[0].upper() + t[1:]
    return t if t[-1] in ".?!" else t + "."


def _grounding(clause: str) -> str:
    """'using only the provided text' -> 'Answer using only the provided text.'"""
    return _sentence(("Answer " if re.match(r"(?:using|based|according|from)\b", clause, _I) else "") + clause)


def split_first(sentence: str) -> tuple[str, list[str], list[str]]:
    """The first sentence -> (task, format clauses, constraint clauses). Clauses are cut out only when the task left
    over still has 3+ words; the text of each clause is kept (only capitalised and given a full stop, and a bare
    format phrase gets a verb: 'in 3 bullet points' -> 'Use 3 bullet points.')."""
    task, fmt, cons = sentence, [], []

    def keep(rest: str) -> bool:
        return len(rest.split()) >= 3

    if (m := _LIMIT_PHRASE.search(task)) and keep(task[:m.start()] + task[m.end():]):
        cons.append(_sentence(m["c"].replace("limiting", "limit").replace("keeping", "keep")))
        task = task[:m.start()] + task[m.end():]
    elif (m := _LENGTH_PHRASE.search(task)) and keep(task[:m.start()] + task[m.end():]):
        cons.append(_sentence("Keep it " + m["c"]))
        task = task[:m.start()] + task[m.end():]
    if (m := _GROUND_HEAD.match(task)) and _RESTRICTS(m["c"]) and keep(task[m.end():]):
        cons.append(_grounding(m["c"]))
        task = task[m.end():]
    if (m := _GROUND_TAIL.search(task)) and _RESTRICTS(m["c"]) and keep(task[:m.start()]):
        cons.append(_grounding(m["c"]))
        task = task[:m.start()] + m["end"]
    for m in _FORMAT_TAIL.finditer(task):
        tail = task[m.end():]
        if is_format(tail) and keep(task[:m.start()]):
            fmt.append(_sentence(tail))
            task = task[:m.start()]
            break
    if not fmt and (m := _FORMAT_PHRASE.search(task)) and keep(task[:m.start()] + task[m.end():]):
        verb = "Output as" if m["prep"].lower() == "as" else "Use"
        fmt.append(_sentence(f"{verb} {m['np']}"))
        task = task[:m.start()] + task[m.end():]
    return _sentence(task), fmt, cons


def parse_optimized(text: str) -> ParsedPrompt:
    paragraphs = [p.strip() for p in _PARAGRAPH.split(text.strip()) if p.strip()]
    instruction, data = paragraphs[0], paragraphs[1:]
    sentences = split_sentences(instruction)
    lead = []
    while len(sentences) > 1 and _GROUND_ONLY.match(sentences[0]) and _RESTRICTS(sentences[0]):     # "Answer only from the provided text. How ...?"
        lead.append(sentences.pop(0))
    first, fmt, cons = split_first(sentences[0])
    cons = lead + cons
    task = [first]
    prev_format = False
    for s in sentences[1:]:
        if is_format(s) or (prev_format and _FORMAT_FOLLOW_UP.search(s)):
            fmt.append(s)
            prev_format = True
            continue
        prev_format = False
        (cons if is_constraint(s) else task).append(s)
    return ParsedPrompt(task=" ".join(task), output_format=" ".join(fmt) or None, constraints=cons,
                        context="\n\n".join(data) or None)


def states_format(text: str) -> bool:
    """The instruction states an output structure somewhere (also inside the first sentence)."""
    return is_format(_PARAGRAPH.split(text.strip())[0])


def states_constraint(text: str) -> bool:
    """The instruction states a length, tone, audience, language or grounding somewhere."""
    instruction = _PARAGRAPH.split(text.strip())[0]
    return any(is_constraint(s) for s in split_sentences(instruction))


_ONLY_GROUNDED = re.compile(r"\b(?:only|solely)\b[^.]{0,30}\b(?:provided|given) (?:text|passage|context)", _I)


def constraint_cues(text: str, ignore_language: bool = False) -> set[str]:
    """Constraint kinds stated in `text`: A03's length/tone/audience/language, a length-only A02 match, and grounding
    that restricts the source ("only the provided text"; a plain "from the provided text" is part of the task).
    `ignore_language`: a programming language named in a coding task ("Write a Python function") is part of the task."""
    cues = set(detect.detect_constraints(text))
    if _ONLY_GROUNDED.search(text):
        cues.add("grounding")
    if detect.detect_format_spec(text) and not is_format(text):
        cues.add("length")
    if ignore_language:
        cues.discard("language")
    return cues
