"""Task success, where it can be checked without a human. None means "cannot be checked for this item".

* closed_qa:      the judge's yes/no verdict against the reference answer (see judge.py)
* classification: every item gets the same label as in the reference answer
* coding:         a code block is present, and Python code in it parses with ast.parse
* information_extraction, summarization: not checkable automatically (quality score only)
"""
import ast
import re

from app.stage_a.rules import detect_constraints
from app.stage_b.rules import extract_labels

_I = re.IGNORECASE
_SPACES = re.compile(r"[\u00a0\u2000-\u200b\u202f\u205f\u3000]")        # no-break / narrow spaces (gpt-oss uses them)
_DASHES = re.compile(r"[\u2010-\u2015\u2212]")


def normalize(text: str) -> str:
    """Unicode spaces and dashes to plain ones, so 'Black\u202fCat' matches 'Black Cat'."""
    return _DASHES.sub("-", _SPACES.sub(" ", text or ""))


# ---------------------------------------------------------------- classification
_BELONG = re.compile(r"\b(?:belong(?:s)? to|from|in|by)\s+(?:either\s+)?(?:the\s+|an?\s+)?(?P<a>[\w'-]+(?: [\w'-]+)?)"
                     r"\s+or\s+(?:the\s+|an?\s+)?(?P<b>[\w'-]+(?: [\w'-]+)?)\s*(?=[?:;.,]|$)", _I)
SHORT_ANSWER_WORDS = 8          # a reference this short that starts with yes/no is a yes/no answer
_YES_NO = re.compile(r"^\W*(yes|no)\b", _I)


def classification_labels(instruction: str, reference: str) -> list[str]:
    """The allowed labels: named in the instruction, or yes/no when the reference is a plain yes/no answer."""
    labels = extract_labels(instruction)
    if not labels and (m := _BELONG.search(instruction)):
        labels = [m["a"], m["b"]]
    if not labels and _YES_NO.match(reference) and len(reference.split()) <= SHORT_ANSWER_WORDS:
        labels = ["yes", "no"]
    return labels


def classification_items(instruction: str) -> list[str]:
    """The items to classify: the list after the last ':' or ';' (or after the question), split on commas and 'and'."""
    m = re.search(r"[:;]([^:;]*)$", instruction) or re.search(r"\?(.*)$", instruction, re.DOTALL)
    tail = m.group(1).strip().rstrip(".") if m else ""
    if not tail:
        return []
    items = [x.strip(" '\"") for x in re.split(r",|;|\n|\band\b", tail) if x.strip(" '\"")]
    return items if len(items) >= 2 or (items and len(items[0].split()) <= 5) else []


def _label_pattern(label: str) -> re.Pattern:
    words = label.split()
    alts = [re.escape(label)] + ([re.escape(words[0])] if len(words) > 1 and len(words[0]) >= 3 else [])
    return re.compile(rf"\b(?:{'|'.join(alts)})s?\b", _I)


def _labels_in(text: str, labels: list[str]) -> list[str]:
    """Labels mentioned in text, in order of first appearance."""
    hits = sorted((m.start(), lab) for lab in labels for m in [_label_pattern(lab).search(text)] if m)
    return [lab for _, lab in hits]


def _items_in(text: str, items: list[str]) -> list[str]:
    return [i for i in items if re.search(rf"(?<!\w){re.escape(i)}(?!\w)", text, _I)]


def assign_labels(text: str, items: list[str], labels: list[str]) -> dict[str, str]:
    """{item: label} as stated in a free-text answer. A sentence with one label gives it to every item in it; a
    sentence with several is read comma by comma, items waiting for the next label ('Golf, boxing and running are
    individual sports')."""
    out: dict[str, str] = {}
    for sentence in re.split(r"[.;\n]+", text):
        found = _labels_in(sentence, labels)
        if not found:
            continue
        if len(set(found)) == 1:
            for i in _items_in(sentence, items):
                out.setdefault(i, found[0])
            continue
        pending: list[str] = []
        for part in sentence.split(","):
            pending += _items_in(part, items)
            here = _labels_in(part, labels)
            if here:
                for i in pending:
                    out.setdefault(i, here[0])
                pending = []
    return out


def classification_success(instruction: str, reference: str, response: str) -> bool | None:
    instruction, reference, response = normalize(instruction), normalize(reference), normalize(response)
    labels = classification_labels(instruction, reference)
    if not labels:
        return None
    items = classification_items(instruction)
    if len(items) < 2:                                          # one decision: compare the first label mentioned
        gold, pred = _labels_in(reference, labels), _labels_in(response, labels)
        return (pred[:1] == gold[:1]) if gold else None
    gold = assign_labels(reference, items, labels)
    if not gold:
        return None
    pred = assign_labels(response, items, labels)
    return all(pred.get(i) == lab for i, lab in gold.items())


# ---------------------------------------------------------------- coding
_FENCE = re.compile(r"```[ \t]*([\w+#.-]*)[^\n]*\n(.*?)```", re.DOTALL)
_PYTHON_TAGS = {"python", "py", "python3"}


def coding_success(instruction: str, response: str) -> bool:
    """A code block is present, and every block that is Python (tagged python, or untagged when the instruction
    asks for Python) parses."""
    blocks = _FENCE.findall(response)
    if not blocks:
        return False
    named = [x.lower() for x in detect_constraints(instruction).get("language", [])]
    wants_python = any("python" in x for x in named)
    for tag, code in blocks:
        tag = tag.lower()
        if tag in _PYTHON_TAGS or (not tag and wants_python):
            try:
                ast.parse(code)
            except SyntaxError:
                return False
    return True


def task_success(category: str, row: dict[str, str], response: str, answers_correctly: bool | None) -> bool | None:
    if category == "closed_qa":
        return answers_correctly
    if category == "classification":
        return classification_success(row["original_instruction"], row["reference_response"], response)
    if category == "coding":
        return coding_success(row["original_instruction"], response)
    return None
