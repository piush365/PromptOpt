"""Spelling suggestions for the prompt the user typed. Suggestions only: nothing is changed unless the user clicks one,
and Stage A/B/C never see this module (the frozen pipeline is unchanged).

    suggest("frm the list tell me prog lang or animal panda pythom java sanke bunny")
    -> [{"word": "frm", "start": 0, "end": 3, "suggestions": ["from", "form", "firm"]}, ... pythom -> python,
        sanke -> snake]

Dictionary: pyspellchecker's English word-frequency list (offline; Norvig's method: candidates within edit distance
2, ranked by frequency). Two adjustments, because prompts are not plain English text:
* ranking: a candidate with exactly the same letters (a swapped pair, "sanke" -> "snake") comes first, then a
  candidate at edit distance 1, then by word frequency. Swapped letters are the most common typing slip, and plain
  frequency would prefer "sake".
* what is never flagged: British spellings whose American form is known ("summarise", "colour"), technical words (programming languages, formats, common tech terms), words inside code
  fences, backticks or quotes, URLs and emails, words with digits, underscores, dots or inner capitals (identifiers),
  ALL-CAPS words, capitalized words not at the start of a sentence (names), words of fewer than 3 letters, and words
  that also occur in the pasted text (a name from the passage is not a typo).
Without pyspellchecker installed, `suggest` returns [] (the feature is optional).
"""
import re
from functools import lru_cache

MAX_SUGGESTIONS = 3
MIN_LENGTH = 3

# Words a general English dictionary does not know but prompts use all the time.
TECH_WORDS = frozenset("""
api apis app apps ascii async auth backend bash boolean bool cli cpu css csv dataframe dataset datasets db dict dicts
dns docx dom eli5 enum env faq fastapi frontend func gpu gpt gpts html http https ide iframe int ints io ip js json jsx
jquery jpeg jpg kotlin lambda llm llms lstm matplotlib md ml mysql nlp nodejs nosql npm numpy oop os pandas pdf php png
postgres postgresql pptx ppt pytorch py qa readme regex repo repos rgb sdk scipy sklearn spacy sql sqlite stdin stdout
str svg tcp tensorflow tldr todo ts tsx tuple tuples txt ui ul url urls usb utf ux vba vscode webpage wifi xlsx xml yaml
yml ai gemini claude chatgpt openai anthropic groq cerebras dalle midjourney
""".split())

_FENCE = re.compile(r"```.*?```", re.S)
_INLINE = re.compile(r"`[^`\n]*`|\"[^\"\n]*\"|“[^”\n]*”")
_URL_OR_EMAIL = re.compile(r"\b(?:https?://|www\.)\S+|\S+@\S+")
_WORD = re.compile(r"[A-Za-z][A-Za-z']*[A-Za-z]|[A-Za-z]")
_SENTENCE_START = re.compile(r"(?:^|[.!?\n]\s*)$")


@lru_cache(maxsize=1)
def _checker():
    try:
        from spellchecker import SpellChecker
    except ImportError:
        return None
    return SpellChecker(distance=2)


def available() -> bool:
    return _checker() is not None


def _masked(text: str) -> str:
    """The text with code, quotes, URLs and emails blanked out (same length, so offsets stay valid)."""
    for rx in (_FENCE, _INLINE, _URL_OR_EMAIL):
        text = rx.sub(lambda m: " " * len(m.group(0)), text)
    return text


# British spellings are not typos: "summarise", "colour", "analyse", "centre" are accepted when the American form is known
_BRITISH = ((r"is(e|ed|es|ing|ation|ations)$", r"iz\1"), (r"our(s|ed|ing)?$", r"or\1"), (r"ys(e|ed|es|ing)$", r"yz\1"),
            (r"tre(s)?$", r"ter\1"), (r"ogue(s)?$", r"og\1"), (r"ll(ed|ing|er)$", r"l\1"))


def _british(word: str, sp) -> bool:
    return any((alt := re.sub(pat, rep, word)) != word and alt in sp for pat, rep in _BRITISH)


def _ignored(word: str, start: int, text: str, context_words: set[str]) -> bool:
    if len(word) < MIN_LENGTH or "'" in word:
        return True
    low = word.lower()
    if low in TECH_WORDS or low in context_words:
        return True
    if word.isupper():                                        # acronym
        return True
    if any(c.isupper() for c in word[1:]):                    # camelCase / PascalCase identifier
        return True
    if word[0].isupper() and not _SENTENCE_START.search(text[:start]):     # a name mid-sentence
        return True
    end = start + len(word)
    neighbours = text[max(0, start - 1):start] + text[end:end + 1]
    return bool(re.search(r"[\d_./\\@#$<>=-]", neighbours))   # part of an identifier, path, number, tag


def _rank(word: str, candidates: set[str], sp) -> list[str]:
    def key(c: str):
        same_letters = sorted(c) == sorted(word)
        return (not same_letters, _distance(word, c), -sp.word_usage_frequency(c), c)
    return sorted(candidates, key=key)


def _distance(a: str, b: str) -> int:
    """Damerau-Levenshtein distance (optimal string alignment): insert, delete, replace, swap adjacent letters."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = a[i - 1] != b[j - 1]
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def suggest(text: str, context: str | None = None) -> list[dict]:
    """Likely typos in `text` with up to MAX_SUGGESTIONS corrections each, in order of appearance."""
    sp = _checker()
    if sp is None or not text:
        return []
    context_words = {w.lower() for w in _WORD.findall(context or "")}
    masked = _masked(text)
    out = []
    for m in _WORD.finditer(masked):
        word = m.group(0)
        if _ignored(word, m.start(), text, context_words) or word.lower() in sp or _british(word.lower(), sp):
            continue
        candidates = (sp.candidates(word.lower()) or set()) - {word.lower()}
        if not candidates:
            continue
        ranked = _rank(word.lower(), candidates, sp)[:MAX_SUGGESTIONS]
        if word[0].isupper():
            ranked = [c[:1].upper() + c[1:] for c in ranked]
        out.append({"word": word, "start": m.start(), "end": m.end(), "suggestions": ranked})
    return out


def apply(text: str, fixes: list[tuple[int, int, str]]) -> str:
    """Replace the spans (start, end, replacement); used by the tests and by any caller that applies all at once."""
    for start, end, new in sorted(fixes, reverse=True):
        text = text[:start] + new + text[end:]
    return text
