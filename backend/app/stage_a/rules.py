"""Stage A rule-based detectors (A02-A05). Each detector is a separate, pure, unit-tested function.

Every detector takes the prompt text and returns evidence (the matched strings), so Stage B and the
explanation UI can show *why* something was flagged.
"""
import re
from collections.abc import Iterable

_I = re.IGNORECASE


def _find_all(patterns: Iterable[re.Pattern], text: str) -> list[str]:
    """Matched substrings, in order of appearance, without duplicates (case-insensitive)."""
    hits: list[tuple[int, str]] = []
    for p in patterns:
        hits.extend((m.start(), m.group(0).strip()) for m in p.finditer(text))
    seen, out = set(), []
    for _, h in sorted(hits):
        if h and h.lower() not in seen:
            seen.add(h.lower())
            out.append(h)
    return out


_NUM = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|a single|a|single)"
_UNIT = r"(?:words?|sentences?|lines?|paragraphs?|bullet points?|bullets|items|points|characters|tokens)"

# ---------------------------------------------------------------- A02: output format
FORMAT_PATTERNS = [re.compile(p, _I) for p in (
    r"\b(?:json|yaml|csv|xml|markdown|html table)\b",
    r"\b(?:a|the|in a|as a|markdown) table\b",
    r"\b(?:bullet(?:ed)?|numbered|comma[- ]separated|ordered)\s+(?:list|points?)\b",
    r"\bbullet points?\b",
    r"\bcomma[- ]separated\b",
    r"\bseparated (?:by|with) (?:a )?(?:commas?|semicolons?|new ?lines?|line breaks?|spaces?|tabs?)\b",
    r"\bas a list\b",
    r"\b(?:one|each) (?:item|entry|name|answer) per line\b",
    r"\b(?:on (?:its|their) own lines?|on separate lines|one per line)\b",
    r"\bstart with the (?:direct )?answer\b",
    rf"\b(?:in|within|using|with|as|to) (?:exactly |at most |no more than |under |up to )?{_NUM} {_UNIT}\b",
    rf"\b{_NUM}[- ](?:word|sentence|line|paragraph) (?:answer|summary|response|description|explanation)\b",
    r"\b(?:respond|reply|answer|output|return|give|provide)\s+(?:with\s+)?only\b",
    r"\bonly (?:the|a|one) (?:label|name|number|answer|word|letter|category|class|code|function|result|value|list)\b",
    r"\b(?:yes|true) or (?:no|false)\b",
    r"\boutput (?:format|a|an|the|as|only|should)\b",
    r"\bformat(?:ted)? (?:as|in|like)\b",
    r"\bin the (?:following )?format\b",
    r"\bformat\s*:",
    r"\bcode block\b",
    r"\b(?:with|under|using) (?:clear |separate )?(?:headings|headers|sections)\b",
    r"\bkey[- ]value pairs?\b",
    r"\b(?:label|name|number|answer|word|date|value|category|title|term|code|letter|phrase)s? only\b",
    rf"\(\s*(?:max(?:imum)?\.?\s*|at most\s*|up to\s*)?{_NUM} {_UNIT}\s*\)",
    rf"\b(?:max(?:imum)?\.?|at most|no more than|under) \d+ {_UNIT}\b",
    r"[\"”'] format\b|\bformat only\b",
)]


def detect_format_spec(text: str) -> list[str]:
    """A02. Evidence that the prompt states an output format; empty list = format missing."""
    return _find_all(FORMAT_PATTERNS, text)


# ---------------------------------------------------------------- A03: constraints
CONSTRAINT_PATTERNS: dict[str, list[re.Pattern]] = {
    "length": [re.compile(p, _I) for p in (
        rf"\b(?:\d+\s*(?:-|to)\s*)?{_NUM} {_UNIT}\b",
        r"\b(?:brief(?:ly)?|concise(?:ly)?|succinct(?:ly)?|short|in detail|detailed|thorough(?:ly)?|tl;?dr|one-liner)\b",
        r"\b(?:at most|no more than|at least|maximum of|max\.?|up to|fewer than|less than|under|within)\s+\d+\b",
        r"\bonly (?:the|a|one) (?:label|name|number|answer|word|letter|category|class|result|value)\b",
        r"\b(?:single|one)[- ](?:word|sentence|line|paragraph)\b",
    )],
    "tone": [re.compile(p, _I) for p in (
        r"\b(?:formal|informal|casual|friendly|professional|neutral|polite|humou?rous|serious|enthusiastic|"
        r"persuasive|objective|academic|conversational|warm|empathetic|witty|playful)\s+(?:tone|style|manner|voice|register|language)\b",
        r"\b(?:formally|informally|casually|professionally|politely|objectively|neutrally)\b",
        r"\btone\b",
    )],
    "audience": [re.compile(p, _I) for p in (
        r"\b(?:explain\w*|describe\w*|write|summari[sz]e\w*|rewrite|present|simplif\w+|tailor\w*|aimed|suitable|intended|"
        r"targeted|geared|pitch\w*|understandable|accessible|make it)\b[^.?!]{0,60}?"
        r"\b(?:for|to) (?:a |an |the |my )?(?:complete |total |absolute )?(?:beginners?|novices?|kids?|children|child|"
        r"\d+[- ]year[- ]olds?|students?|experts?|non-?technical (?:\w+ )?(?:people|readers?|audience|users?|staff)|"
        r"laypersons?|lay(?:men| readers?| audience)|general (?:audience|public|reader)|developers?|engineers?|"
        r"executives?|managers?|customers?|investors?|scientists?|researchers?|teenagers?|adults?|stakeholders?)\b",
        r"\baudience\b",
        r"\bexplain (?:it )?like i'?m\b|\beli5\b",
        r"\bin (?:layman'?s|simple|plain) (?:terms|english|language|words)\b",
    )],
    "language": [re.compile(p, _I) for p in (
        r"\b(?:python|java|javascript|typescript|c\+\+|c#|golang|rust|ruby|php|swift|kotlin|scala|perl|sql|"
        r"mysql|postgres(?:ql)?|sqlite|html|css|bash|shell script|powershell|matlab|haskell|lua|dart|node\.?js|"
        r"react|jquery|django|flask|pandas|numpy|objective-c|assembly|fortran|cobol|julia|elixir|clojure|"
        r"visual basic|vba|groovy|js|ts)(?![\w+#])",
        r"\bin (?:go|r|c)\b(?![+#\w])",
        r"\b(?:go|r|c) (?:code|program|script|function|language)\b",
    )],
}

# Constraints worth asking for, per category. Stage B only adds the missing ones listed here.
RELEVANT_CONSTRAINTS: dict[str, tuple[str, ...]] = {
    "closed_qa": ("length",),
    "information_extraction": (),
    "classification": (),
    "summarization": ("length", "audience", "tone"),
    "coding": ("language",),
    "other": ("length", "audience", "tone"),
}


def detect_constraints(text: str) -> dict[str, list[str]]:
    """A03. {constraint: evidence} for each constraint the prompt states."""
    found = {}
    for name, patterns in CONSTRAINT_PATTERNS.items():
        hits = _find_all(patterns, text)
        if hits:
            found[name] = hits
    return found


def missing_constraints(text: str, category: str) -> list[str]:
    """A03. Constraints relevant to `category` that the prompt does not state."""
    present = detect_constraints(text)
    return [c for c in RELEVANT_CONSTRAINTS.get(category, ()) if c not in present]


# ---------------------------------------------------------------- A04: redundancy
FILLER_PATTERNS = [re.compile(p, _I) for p in (
    r"^\s*(?:hey|hi|hello|dear)(?: there)?\b",
    r"\bplease\b",
    r"\bkindly\b",
    r"\b(?:could|can|would|will) you (?:please |kindly )?(?:(?:be able to|mind|help me(?: to)?)\s)?",
    r"\bi (?:was|am|'m) (?:just )?wondering (?:if|whether)(?: you could)?\b",
    r"\bi(?: would|'d) (?:like|love|want) (?:for )?you to\b",
    r"\bi (?:want|need) you to\b",
    r"\b(?:if (?:it'?s |it is )?possible|if you (?:can|could|don'?t mind))\b",
    r"\bif (?:it'?s|it is) not too much (?:trouble|to ask)\b",
    r"\bthank(?:s| you)(?: (?:so|very) much| in advance| a lot)?\b",
    r"\b(?:basically|literally|actually|honestly)\b",
    r"\bjust\b(?! (?:in time|now|like|as|because))",
    r"(?<!what )(?<!which )(?<!what's )\b(?:sort|kind) of\b(?! (?:\w+ )?(?:is|are|was|were|does|do)\b)",
    r"\byou know\b",
    r"\bquick question\b",
    r"\bfor me\b",
    r"\bas an ai(?: language model)?\b",
)]

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_REPEATED_WORD = re.compile(r"\b(\w+)(\s+\1\b)+", _I)
_ALLOWED_DOUBLES = {"that", "had", "is", "no", "bye", "very", "so"}


def _norm(s: str) -> str:
    return re.sub(r"[^\w\s]", "", s.lower()).strip()


def detect_filler(text: str) -> list[str]:
    """A04. Politeness and filler phrases that add tokens but no information."""
    return _find_all(FILLER_PATTERNS, text)


def detect_repetition(text: str, sentences: list[str] | None = None) -> list[str]:
    """A04. Sentences that repeat an earlier sentence, and accidental doubled words ('the the')."""
    out = []
    seen = set()
    for s in sentences if sentences is not None else _SENT_SPLIT.split(text):
        key = _norm(s)
        if len(key.split()) >= 3:
            if key in seen:
                out.append(s.strip())
            seen.add(key)
    for m in _REPEATED_WORD.finditer(text):
        if m.group(1).lower() not in _ALLOWED_DOUBLES and not m.group(1).isdigit():
            out.append(m.group(0))
    return out


# ---------------------------------------------------------------- A05: ambiguous references
_REF_NOUN_LIST = (
    "text", "passage", "paragraph", "article", "document", "essay", "story", "email", "letter", "code", "function",
    "snippet", "program", "script", "data", "dataset", "table", "file", "report", "content", "excerpt", "section",
    "information", "context", "sentence", "image", "picture", "link", "url", "video", "poem", "review", "transcript",
    "conversation", "chat", "message", "book", "chapter", "page", "query", "output", "error", "log", "pdf", "slide",
    "spreadsheet", "reference text", "reference",
)
_REF_NOUNS = "|".join(re.escape(n) for n in _REF_NOUN_LIST)
AMBIGUOUS_PATTERNS = [re.compile(p, _I) for p in (
    rf"\b(?:this|that|these|those|above|below|following|given|provided|attached|previous|said)\s+(?:{_REF_NOUNS})s?\b",
    # "the text" only when the noun phrase ends there ("summarize the article."), not "returns the page content"
    rf"\bthe\s+(?:{_REF_NOUNS})s?(?=\s*(?:[.,;:?!)]|$)|\s+(?:and|or|but|to|in|on|about|below|above|for|into|so|"
    rf"that|which|with|by|at|please|i|you|mean)\b)",
    r"\b(?:the |as )?(?:above|aforementioned|mentioned above|stated above|discussed (?:above|earlier))\b",
    r"\b(?:summari[sz]e|explain|fix|translate|rewrite|shorten|improve|check|review|debug|classify|analy[sz]e|"
    r"describe|simplify|correct|edit|proofread|paraphrase|refactor|optimi[sz]e)\s+(?:it|this|that|these|those|them)\b(?!\s+\w+ing\b)",
)]
_DANGLING_PRONOUNS = {"it", "this", "that", "these", "those", "they", "them"}


def detect_ambiguous_refs(text: str, has_context: bool, doc=None) -> list[str]:
    """A05. References to material that is not there ('summarize this', 'the passage' with no passage).

    Only flagged when no context was supplied. `doc` is an optional spaCy Doc of `text`; when given, a pronoun
    that appears before any noun it could refer to is also flagged (e.g. 'what does it mean?').
    """
    if has_context:
        return []
    hits = _find_all(AMBIGUOUS_PATTERNS, text)
    if doc is not None:
        seen_noun = False
        for tok in doc:
            if tok.pos_ in ("NOUN", "PROPN", "NUM"):
                seen_noun = True
            elif (not seen_noun and tok.pos_ == "PRON" and tok.lower_ in _DANGLING_PRONOUNS
                  and tok.dep_ not in ("expl", "mark") and tok.head.dep_ != "relcl" and not _covered(tok.text, hits)):
                hits.append(tok.text)
    return hits


def _covered(word: str, hits: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", h, _I) for h in hits)


# ---------------------------------------------------------------- context
_CODE_HINT = re.compile(r"```|^\s{4,}\S|[{};]\s*$|\bdef \w+\(|\bfunction \w+\(|<\w+>", re.MULTILINE)
_QUOTED = re.compile(r"[\"“'']([^\"”'']{40,})[\"”'']")


def detect_embedded_context(text: str) -> bool:
    """True when the prompt itself carries material to work on (passage, code, quoted text, a list of items)."""
    if _CODE_HINT.search(text) or _QUOTED.search(text) or text.count(",") >= 2:
        return True
    head, sep, tail = text.partition(":")
    if sep and len(head.split()) <= 25 and (len(tail.split()) >= 8 or tail.count(",") >= 1):
        return True
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 2 and sum(len(ln.split()) for ln in lines[1:]) >= 8:
        return True
    return len(text.split()) >= 60
