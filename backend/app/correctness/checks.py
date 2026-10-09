"""Scoring one answer against one correctness-suite case, per category.

    score(case, answer, llm_json) -> {"correct": bool, "method": ..., "detail": {...}}

* closed_qa (normalized match): the answer is normalized (lower case, no markdown, no thousands separators, Unicode
  dashes and spaces unified) and searched for the gold answer's forms (`aliases`) and for known wrong values
  (`distractors`). Gold found and no distractor: correct. Gold not found: wrong. Both found (an answer that also
  mentions a wrong value, e.g. "10 Nov, moved to 17 Nov"): the blind extractor reads the answer's final value, which
  is then matched the same way.
* information_extraction (set P/R/F1, exact set): the material is a closed world, so every item the answer could
  wrongly include is listed as a distractor. No distractor mentioned: the predicted set is the gold items found.
  A distractor mentioned (it may be listed, or mentioned as excluded): the extractor lists the items the answer
  gives as its answer, and those are matched. Correct = exact set (precision = recall = 1).
* classification (per-item accuracy, all correct): each item's label is read from the lines that mention the item
  (or from the heading above them). Any item unread or with two labels: the extractor reads all of them.
  Correct = every item right.
* summarization (checklist): the blind judge marks each required key fact as covered or not and each forbidden
  statement as present or not; the word count is computed. Correct = all key facts, no forbidden statement, and
  within the word limit.
* coding (pass@1): the answer's code runs against the hidden asserts in the bubblewrap sandbox (app.coding.harness).
  Correct = every assert passes.

`llm_json(system, user) -> dict | None` is the extractor/judge (Groq qwen in app.correctness.run): blind, it sees
the user's request and one answer, never the gold answer or which prompt produced the answer.
"""
import math
import re
from typing import Callable

from app.coding.harness import extract_code, run_function_tests

LlmJson = Callable[[str, str], dict | None]

_SPACES = re.compile(r"[       ]")
_DASHES = re.compile(r"[‐‑‒–—−]")
_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})
_THOUSANDS = re.compile(r"(?<=\d),(?=\d)")
_BIG_O = re.compile(r"o\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)")


def unify(text: str) -> str:
    """Typography only: Unicode spaces, dashes and quotes made plain, markdown emphasis removed. `re:` aliases run here."""
    t = _SPACES.sub(" ", text or "")
    t = _DASHES.sub("-", t)
    t = t.translate(_QUOTES)
    return re.sub(r"[*_`]", "", t)


def normalize(text: str) -> str:
    t = unify(text).replace("₹", " ")
    t = _THOUSANDS.sub("", t)
    return t.lower()


def normalize_big_o(text: str) -> str:
    """'O(n log n)', 'O(N·log N)', 'O(log₂ n)', 'O(n²)', 'O(n**2)', 'O(n*n)' -> 'o(nlogn)', 'o(logn)', 'o(n^2)'.
    Runs on normalized text, where markdown's '*' and '_' are already gone ('n**2' -> 'n2', 'log_2' -> 'log2')."""
    def one(m: re.Match) -> str:
        inner = re.sub(r"[\s·×\\]|cdot", "", m.group(1).replace("²", "^2").replace("₂", "2").replace("^{2}", "^2"))
        inner = re.sub(r"log2?\(?n\)?", "logn", inner)
        if inner in ("n2", "nn", "n^2"):
            inner = "n^2"
        return f"o({inner})"
    return _BIG_O.sub(one, text)


def alias_regex(alias: str) -> re.Pattern:
    """`re:` aliases are regular expressions used as written (on the unified, un-lowered text); others are matched on the
    normalized text with word boundaries, and a number never matches inside a longer number ('5' not in '75', '2.5')."""
    if alias.startswith("re:"):
        return re.compile(alias[3:])
    a = re.escape(normalize(alias))
    start = r"(?<![\w.])" if re.match(r"\w", normalize(alias)) else ""
    end = r"(?!\w)(?!\.\d)" if re.search(r"\w$", normalize(alias)) else ""
    return re.compile(start + a + end)


def find(aliases: list[str], text: str) -> list[int]:
    """Start positions of every alias match (typography-unified text for `re:` aliases, normalized text otherwise)."""
    norm = normalize(text)
    hits = []
    for a in aliases:
        hits += [m.start() for m in alias_regex(a).finditer(unify(text) if a.startswith("re:") else norm)]
    return hits


def matches(aliases: list[str], text: str) -> bool:
    return bool(find(aliases, text))


# ---------------------------------------------------------------- closed_qa
QA_SYSTEM = """You read an AI assistant's RESPONSE to a QUESTION and report the final answer the RESPONSE gives.
Copy the answer value exactly as the RESPONSE states it (a number with its unit, a date, a name, a plan code ...),
without explanation. If the RESPONSE gives no single final answer, use null.
Return ONLY a JSON object: {"answer": "<the final answer>" or null}"""


def score_closed_qa(case: dict, answer: str, llm_json: LlmJson | None) -> dict:
    chk = case["check"]
    gold, dist = matches(chk["aliases"], answer), matches(chk["distractors"], answer)
    if not gold:
        return {"correct": False, "method": "deterministic", "detail": {"reason": "gold answer not in the response"}}
    if not dist:
        return {"correct": True, "method": "deterministic", "detail": {}}
    if llm_json is None:
        return {"correct": False, "method": "unscored", "detail": {"reason": "gold and a distractor both present; no extractor"}}
    out = llm_json(QA_SYSTEM, f"QUESTION:\n{case['vague_prompt']}\n\nRESPONSE:\n{answer.strip()}") or {}
    final = str(out.get("answer") or "")
    ok = matches(chk["aliases"], final) and not matches(chk["distractors"], final)
    return {"correct": ok, "method": "extractor", "detail": {"extracted": final,
            **({} if ok else {"reason": f"final answer read as {final!r}"})}}


# ---------------------------------------------------------------- information_extraction
IE_SYSTEM = """You read an AI assistant's RESPONSE to a REQUEST and list the items the RESPONSE gives as its answer.
Include only items the RESPONSE presents as part of the answer; leave out items it mentions as excluded, not
applicable or for comparison. One entry per item; copy each item in full as the RESPONSE writes it (the whole list
line or table row, with any name, date or amount it gives), without notes in brackets.
Return ONLY a JSON object: {"items": ["<item>", ...]}"""


def prf(tp: int, n_pred: int, n_gold: int) -> dict:
    p = tp / n_pred if n_pred else (1.0 if not n_gold else 0.0)
    r = tp / n_gold if n_gold else 1.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def score_information_extraction(case: dict, answer: str, llm_json: LlmJson | None) -> dict:
    chk = case["check"]
    gold = {g: matches(chk["aliases"][g], answer) for g in case["gold"]}
    dist = sorted(d for d, al in chk["distractors"].items() if matches(al, answer))
    if not dist:
        found = [g for g, ok in gold.items() if ok]
        m = prf(len(found), len(found), len(gold))
        return {"correct": len(found) == len(gold), "method": "deterministic",
                "detail": {**m, "found": found, "missed": [g for g, ok in gold.items() if not ok], "extra": []}}
    if llm_json is None:
        return {"correct": False, "method": "unscored", "detail": {"reason": f"distractors mentioned: {dist}"}}
    out = llm_json(IE_SYSTEM, f"REQUEST:\n{case['vague_prompt']}\n\nRESPONSE:\n{answer.strip()}") or {}
    items = [str(i) for i in (out.get("items") or []) if str(i).strip()]
    found, extra = set(), []
    for it in items:
        hit = [g for g in case["gold"] if matches(chk["aliases"][g], it)]
        bad = [d for d, al in chk["distractors"].items() if matches(al, it)]
        if hit and (not bad or len(hit) == 1):      # one gold item with a side note ("14 Oct (was 7 Oct)") counts
            found.update(hit)
        else:                                       # no gold item, or several lumped with a wrong one
            extra.append(it)
    m = prf(len(found), len(found) + len(extra), len(gold))
    return {"correct": len(found) == len(gold) and not extra, "method": "extractor",
            "detail": {**m, "found": sorted(found), "missed": [g for g in case["gold"] if g not in found],
                       "extra": extra, "extracted": items}}


# ---------------------------------------------------------------- classification
CLS_SYSTEM = """You read an AI assistant's RESPONSE that assigns a label to each of several items, and report the
label it gives each item. Use exactly one of the ALLOWED LABELS per item, or null if the RESPONSE gives that item
no label (or more than one).
Return ONLY a JSON object: {"labels": {"<item id>": "<label>" or null, ...}}"""


def _labels_in(text: str, chk: dict) -> set[str]:
    """Labels mentioned in one line (longest alias first, so 'non-veg' is not also read as 'veg')."""
    t = normalize(text)
    if chk.get("normalize") == "big_o":
        t = normalize_big_o(t)
    found = set()
    pairs = sorted(((a, lab) for lab, al in chk["labels"].items() for a in al), key=lambda p: -len(p[0]))
    for a, lab in pairs:
        rx = re.compile(r"(?<![\w-])" + re.escape(normalize(a)) + r"(?![\w-])")
        if rx.search(t):
            found.add(lab)
            t = rx.sub(" ", t)
    return found


def read_labels(case: dict, answer: str) -> dict[str, str | None]:
    """Per item: the one label on the lines mentioning it (the item's own text masked), else the label of the nearest
    heading above it (a line with exactly one label and no item); None if unreadable or contradictory."""
    chk = case["check"]
    items = chk["items"]
    item_rx = {k: [alias_regex(a) for a in al] for k, al in items.items()}
    heading, per_item = None, {k: set() for k in items}
    for raw in (answer or "").splitlines():
        if not raw.strip():
            continue
        norm = normalize(raw)
        here = [k for k, rxs in item_rx.items() if any(rx.search(norm) for rx in rxs)]
        masked = norm
        for k in here:
            for rx in item_rx[k]:
                masked = rx.sub(" ", masked)
        labs = _labels_in(masked, chk)
        if not here:
            heading = next(iter(labs)) if len(labs) == 1 else (None if labs else heading)
            continue
        for k in here:
            if len(here) > 1 and len(labs) > 1:
                per_item[k].add("?")
            elif labs:
                per_item[k] |= labs
            elif heading:
                per_item[k].add(heading)
    return {k: (next(iter(v)) if len(v) == 1 and "?" not in v else None) for k, v in per_item.items()}


def score_classification(case: dict, answer: str, llm_json: LlmJson | None) -> dict:
    chk = case["check"]
    got, method = read_labels(case, answer), "deterministic"
    if any(v is None for v in got.values()) and llm_json is not None:
        user = (f"ALLOWED LABELS: {', '.join(chk['labels'])}\nITEM IDS: {', '.join(chk['items'])}\n\n"
                f"REQUEST:\n{case['vague_prompt']}\n\nRESPONSE:\n{answer.strip()}")
        out = (llm_json(CLS_SYSTEM, user) or {}).get("labels") or {}
        method = "extractor"
        for k in got:
            v = out.get(k)
            labs = _labels_in(str(v), chk) if v else set()
            got[k] = next(iter(labs)) if len(labs) == 1 else None
    right = [k for k in case["gold"] if got.get(k) == case["gold"][k]]
    wrong = {k: {"gold": case["gold"][k], "got": got.get(k)} for k in case["gold"] if k not in right}
    return {"correct": not wrong, "method": method,
            "detail": {"accuracy": round(len(right) / len(case["gold"]), 3), "right": len(right),
                       "items": len(case["gold"]), "wrong": wrong}}


# ---------------------------------------------------------------- summarization
SUM_SYSTEM = """You check a SUMMARY of a SOURCE TEXT against a checklist. The SUMMARY was written by an AI assistant.
For each REQUIRED fact (K1, K2, ...), answer true if the SUMMARY states it (in any wording), false if it is missing
or stated wrongly. For each FORBIDDEN statement (F1, F2), answer true if the SUMMARY makes that statement, false if
it does not. Judge only what the SUMMARY says; the SOURCE TEXT is for reference.
Return ONLY a JSON object: {"K1": true|false, ..., "F1": true|false, "F2": true|false, "reason": "<one short sentence>"}"""


def word_count(text: str) -> int:
    """Words of the answer as a reader sees them: markdown symbols and bullets are not words."""
    t = re.sub(r"[#*_`>|]", " ", text or "")
    return len([w for w in re.split(r"\s+", t) if re.search(r"\w", w)])


def score_summarization(case: dict, answer: str, llm_json: LlmJson | None) -> dict:
    g = case["gold"]
    words = word_count(answer)
    detail = {"words": words, "max_words": g["max_words"], "within_length": words <= g["max_words"]}
    if llm_json is None:
        return {"correct": False, "method": "unscored", "detail": {**detail, "reason": "no judge"}}
    keys = "\n".join(f"K{i}: {k['fact']}" for i, k in enumerate(g["key_facts"], 1))
    forb = "\n".join(f"F{i}: {f['fact']}" for i, f in enumerate(g["forbidden"], 1))
    out = llm_json(SUM_SYSTEM, f"SOURCE TEXT:\n{case['material']}\n\nREQUIRED:\n{keys}\n\nFORBIDDEN:\n{forb}\n\n"
                               f"SUMMARY:\n{answer.strip() or '(empty)'}")
    if not out:
        return {"correct": False, "method": "unscored", "detail": {**detail, "reason": "judge returned no usable JSON"}}
    covered = [bool(out.get(f"K{i}")) for i in range(1, len(g["key_facts"]) + 1)]
    forbidden = [bool(out.get(f"F{i}")) for i in range(1, len(g["forbidden"]) + 1)]
    detail.update({"key_facts_covered": sum(covered), "key_facts": len(covered),
                   "missed": [g["key_facts"][i]["fact"] for i, c in enumerate(covered) if not c],
                   "forbidden_present": [g["forbidden"][i]["fact"] for i, f in enumerate(forbidden) if f],
                   "judge_reason": str(out.get("reason", ""))[:300]})
    ok = all(covered) and not any(forbidden) and detail["within_length"]
    return {"correct": ok, "method": "judge", "detail": detail}


# ---------------------------------------------------------------- coding
def score_coding(case: dict, answer: str, llm_json: LlmJson | None = None) -> dict:
    g = case["gold"]
    run = run_function_tests(extract_code(answer, g["function"]), g["tests"], g["function"])
    failed = [{"test": t, "error": r.get("error", "")} for t, r in zip(g["tests"], run.results) if not r["ok"]]
    return {"correct": run.all_passed, "method": "sandbox",
            "detail": {"status": run.status, "passed": run.passed, "total": run.total, "renamed": run.renamed,
                       "failed": failed[:4], "error": run.detail, "sandbox": run.sandbox}}


SCORERS = {"closed_qa": score_closed_qa, "information_extraction": score_information_extraction,
           "classification": score_classification, "summarization": score_summarization, "coding": score_coding}


def score(case: dict, answer: str, llm_json: LlmJson | None) -> dict:
    return SCORERS[case["category"]](case, answer or "", llm_json)


# ---------------------------------------------------------------- statistics
def mcnemar_exact(only_optimized: int, only_vague: int) -> float:
    """Two-sided exact McNemar test (binomial on the discordant pairs); 1.0 when there are none."""
    n = only_optimized + only_vague
    if n == 0:
        return 1.0
    k = min(only_optimized, only_vague)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, p)
