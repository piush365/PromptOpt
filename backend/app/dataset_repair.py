"""Dataset v1 -> v1.1 repair: put back data that the generator dropped from the instruction.

In v1, many prompts lost the literal data written into the original instruction. A typical case:
    original:  Identify which instrument is string or percussion: Sheker, Taishogoto
    optimized: Classify each listed instrument as "string" or "percussion". Output a JSON object ...
The items are gone, so the optimized prompt cannot be answered. (The row's `context` is appended to every prompt at
evaluation time, so only data that lives in the instruction itself can be lost this way.)

Per row:
1. `extract_payload` finds the literal data in the original instruction. Classification: the item list (after the
   first colon, after the question, on the following lines, or the last comma-separated run). All categories: data on the lines
   after the first line (code, answer options) and arithmetic expressions.
2. `dropped`: in classification, a prompt dropped the data if any item is missing; elsewhere, if it keeps less than
   COVERAGE_MIN of the payload's content words. `repair_row` then appends the payload verbatim (deterministic).
3. Rows whose instruction points at data that exists nowhere ("these numbers" with no numbers) are removed: nothing
   can be restored.
4. Optimized prompts that no longer name the instruction's subject ("the temple" for "Doleshwor Mahadeva temple")
   cannot be fixed by appending; `regenerate` asks Groq for a minimal edit, several rows per call, and keeps the edit
   only if it passes `accept_edit`. Results are cached in regenerated.json, so re-running is reproducible.

    python -m app.dataset_repair                          # report only
    python -m app.dataset_repair --write                  # write data/promptopt_dataset_v1_1/
    python -m app.dataset_repair --write --max-calls 60   # also regenerate subject drops with Groq
"""
import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR

V1_CSV = BACKEND_DIR.parent / "data" / "promptopt_dataset_v1" / "promptopt_dataset_v1.csv"
V11_DIR = BACKEND_DIR.parent / "data" / "promptopt_dataset_v1_1"
V11_CSV = V11_DIR / "promptopt_dataset_v1_1.csv"
SPLITS = ("train", "val", "test", "benchmark")
COVERAGE_MIN = 0.5
REGEN_MODEL = "openai/gpt-oss-120b"   # the model that generated v1
ROWS_PER_CALL = 5
REWRITE_INSTRUCTION = ("Rewrite the user's prompt into a clear, well-specified prompt for an LLM. "
                       "Keep the same task and intent.")

# Words that carry no data: function words and the instruction words a rewrite is free to change.
STOPWORDS = frozenset("""
a an the and or of to in on for with from by as at is are be was were it its this that these those which what who
whom whose how why when where whether each every all any some one following below above given list listed items
item into either not vs versus than then there their them they please me you your i my we our can could would
should will tell identify classify categorize sort group label based if else
""".split())

# The instruction says the data follows ("these numbers", "the following function").
_REFERS_TO_DATA = re.compile(r"\b(these|those|the following|following|below|this)\s+(?!(is|was)\b)"
                             r"(\w+\s+){0,2}?(are|is|code|function|snippet|program|list|array|string|sentence|expression|"
                             r"words?|numbers?|items?|data|table|json|html|query|animals?|things|countries|cities|movies|"
                             r"books|foods?|people|names|objects|characters|sports|rivers|brands|companies)\b"
                             r"|\b(each|all|which|any) of (these|those|the following)\b", re.I)
_NUM = r"\(?-?\d+(?:\.\d+)?\)?"
_EXPRESSION = re.compile(rf"(?<![\w.]){_NUM}(?:(?:\s*[+*/%^]\s*|\s+-\s+){_NUM}){{2,}}")
_COMMA_LIST = re.compile(r"(?:[^,.:;?!\n]{1,40},\s*){2,}(?:(?:and|or)\s+)?[^,.:;?!\n]{1,40}")
# A line that describes the answer format rather than holding data: "[Name]: [Significance]", "And sort the list".
_FORMAT_LINE = re.compile(r"[\[{][A-Za-z][^\]}]{0,30}[\]}]|^(and|then|also|sort|use|output|return|format|please|make)\b",
                          re.I)
SUBJECT_ENTITY_LABELS = frozenset({"PERSON", "ORG", "GPE", "LOC", "FAC", "WORK_OF_ART", "EVENT", "PRODUCT", "NORP",
                                   "LAW"})


@dataclass(frozen=True)
class Payload:
    kind: str   # "items" | "lines" | "expression" | "after_question" | "list"
    text: str


def words(text: str) -> list[str]:
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = re.sub("[–-―]", " ", re.sub("[‐-‒]", "-", text))   # dashes split, hyphens join
    found = re.findall(r"[a-z0-9À-ɏ]+(?:['.+#-][a-z0-9À-ɏ]+)*", text)
    return [w[:-2] if w.endswith("'s") else w for w in found]


def content_words(text: str) -> set[str]:
    return {w for w in words(text) if w not in STOPWORDS}


def _data_colon(text: str) -> int:
    """Index of the first colon that introduces data (not in a URL or a time), or -1."""
    for m in re.finditer(":", text):
        i = m.start()
        if text[i + 1:i + 3] == "//" or (i > 0 and text[i - 1].isdigit() and text[i + 1:i + 2].isdigit()):
            continue
        return i
    return -1


def _data_lines(rest: str) -> str | None:
    lines = [ln.strip() for ln in rest.splitlines() if ln.strip()]
    data = [ln for ln in lines if not _FORMAT_LINE.search(ln)]
    return "\n".join(data) if data and any(content_words(ln) for ln in data) else None


def _items_after_colon(s: str) -> str | None:
    """Classification: the item list after the first colon (or an earlier question mark) of the first line, including
    continuation lines."""
    first = s.partition("\n")[0]
    i = _data_colon(first)
    q = first.find("?")
    if 0 <= q < len(first) - 1 and (i < 0 or q < i):   # "Which were nominated? "Avatar: The Way of Water", ..."
        i = q
    if i < 0:
        return None
    tail = s[i + 1:].strip()
    if first[i + 1:].strip():   # the list starts on the colon's line: later lines continue it
        tail = " ".join(ln.strip() for ln in tail.splitlines() if ln.strip())
    else:                       # "...:\ngoat\nsnake": one item per line
        tail = "\n".join(ln.strip() for ln in tail.splitlines() if ln.strip())
    # Labels first, then the items: "... either: 'A', 'B', 'C'. item1, item2" -> keep the part after the labels.
    parts = [p for p in re.split(r"(?<=[.?!])\s+", tail) if p.strip()]
    if len(parts) > 1 and "," in parts[-1]:
        tail = parts[-1]
    tail = tail.rstrip(" .")
    return tail if content_words(tail) and (len(words(tail)) >= 2 or "," in tail) else None


def _trim_lead(text: str) -> str:
    """'What ages are considered newborn, toddler, child' -> 'newborn, toddler, child': cut the first item down to
    the length of the longest other item."""
    first, _, rest = text.partition(",")
    others = [re.sub(r"^(and|or)\s+", "", p.strip()).split() for p in rest.split(",") if p.strip()]
    longest = max((len(o) for o in others), default=0)
    lead = first.split()
    if others and len(lead) > longest + 2:
        first = " ".join(lead[-longest:])
    return f"{first},{rest}"


def extract_payload(instruction: str, category: str) -> Payload | None:
    """The literal data written into an instruction, or None if it has none."""
    s = instruction.strip()
    if category == "classification":
        tail = _items_after_colon(s)
        if tail:
            return Payload("items", tail)
    lines = _data_lines(s.partition("\n")[2])
    if lines:
        return Payload("lines", lines)
    m = _EXPRESSION.search(s)
    if m:
        return Payload("expression", m.group(0).strip())
    if category != "classification":
        return None
    q = s.rfind("?")
    if 0 <= q < len(s) - 1 and content_words(s[q + 1:]):
        return Payload("after_question", s[q + 1:].strip().rstrip("."))
    lists = _COMMA_LIST.findall(s)
    if lists:   # the items usually come after the labels, so take the last list
        return Payload("list", _trim_lead(lists[-1].strip().rstrip(".")))
    return None


def items(payload: Payload) -> list[str]:
    if payload.kind == "expression":
        return [payload.text]
    parts = re.split(r"[,;\n]", payload.text)
    return [re.sub(r"^(and|or)\s+", "", p.strip(), flags=re.I) for p in parts if p.strip()]


def coverage(payload: Payload, prompt: str) -> float:
    need = content_words(payload.text)
    if not need:
        return 1.0
    return len(need & set(words(prompt))) / len(need)


def _stem(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def _item_present(item: str, have: set[str]) -> bool:
    need = {_stem(w) for w in content_words(item)}
    return not need or len(need & {_stem(w) for w in have}) / len(need) >= COVERAGE_MIN


def dropped(payload: Payload | None, prompt: str, category: str, degraded: bool = False) -> bool:
    """Optimized classification prompts: any item missing. Otherwise (and for degraded prompts, which may shorten
    items the way users do: "UK", "tux"): less than COVERAGE_MIN of the payload's content words left."""
    if payload is None:
        return False
    if category == "classification" and not degraded:
        have = set(words(prompt))
        return not all(_item_present(it, have) for it in items(payload))
    return coverage(payload, prompt) < COVERAGE_MIN


def append_payload(prompt: str, payload: Payload, degraded: bool) -> str:
    prompt = prompt.rstrip()
    multiline = "\n" in payload.text
    if degraded:   # a user pastes the data after the request
        sep = "\n" if multiline else (" " if prompt.endswith(":") else ": ")
        return f"{prompt}{sep}{payload.text}"
    if multiline:
        label = "Input:\n"
    else:
        label = "Expression: " if payload.kind == "expression" else "Items: "
    return f"{prompt}\n\n{label}{payload.text}"


def missing_source_data(row: dict[str, str]) -> bool:
    """The instruction says the data follows, but neither the instruction nor the context contains it."""
    if (row.get("context") or "").strip():
        return False
    s = row["original_instruction"]
    if not _REFERS_TO_DATA.search(s) or extract_payload(s, row["category"]) is not None:
        return False
    i = _data_colon(s)
    has_inline = re.search(r'"[^"]+"|“[^”]+”', s) or (i >= 0 and content_words(s[i + 1:]))
    return not has_inline


@dataclass
class RowResult:
    row: dict[str, str]
    action: str                         # "ok" | "repaired" | "removed"
    fixed_fields: tuple[str, ...] = ()
    payload: Payload | None = None


def _recount(row: dict[str, str]) -> None:
    row["degraded_word_count"] = str(len(row["degraded_prompt"].split()))
    row["optimized_word_count"] = str(len(row["optimized_prompt"].split()))


def repair_row(row: dict[str, str]) -> RowResult:
    if missing_source_data(row):
        return RowResult(dict(row), "removed")
    payload = extract_payload(row["original_instruction"], row["category"])
    out, fixed = dict(row), []
    for name, is_degraded in (("degraded_prompt", True), ("optimized_prompt", False)):
        if dropped(payload, row[name], row["category"], is_degraded):
            out[name] = append_payload(row[name], payload, is_degraded)
            fixed.append(name)
    if not fixed:
        return RowResult(out, "ok", payload=payload)
    _recount(out)
    return RowResult(out, "repaired", tuple(fixed), payload)


# ---- Subject drops: detected with spaCy NER, fixed by a minimal Groq edit

def _named(entity: str, have: set[str]) -> bool:
    """The prompt names the entity: one of its words, or a derived form ("Albania" -> "Albanian")."""
    return any(w in have or (len(w) >= 5 and any(h.startswith(w[:5]) for h in have)) for w in content_words(entity))


def _vocab(text: str) -> set[str]:
    """words(), plus the parts of hyphenated words ("EPA-rated" -> "epa", "rated")."""
    ws = words(text)
    return set(ws) | {p for w in ws for p in w.split("-") if p}


def lost_subjects(instruction: str, optimized: str, context: str, nlp: Any) -> list[str]:
    """Named entities of the instruction (people, places, works, ...) that the optimized prompt no longer names.
    Skipped: the first word (usually a verb spaCy mislabels), acronyms of three letters or fewer, and, when the row
    has a context, entities the context never mentions (a source like "Wikipedia", not the subject)."""
    have = _vocab(optimized)
    ctx = _vocab(context) if context.strip() else None
    lost = []
    for ent in nlp(instruction).ents:
        if ent.start == 0 or ent.label_ not in SUBJECT_ENTITY_LABELS or ent.text in lost:
            continue
        if not content_words(ent.text) or len(re.sub(r"[^A-Za-z]", "", ent.text)) <= 3:
            continue
        if ctx is not None and not _named(ent.text, ctx):
            continue
        if not _named(ent.text, have):
            lost.append(ent.text)
    return lost


def accept_edit(old: str, new: str, subjects: list[str]) -> bool:
    """Keep a regenerated prompt only if it names every lost subject and stays close in length."""
    new = (new or "").strip()
    if not new:
        return False
    have = _vocab(new)
    if not all(_named(s, have) for s in subjects):
        return False
    return len(new.split()) <= len(old.split()) + 12


REGEN_SYSTEM = """You fix optimized prompts in a prompt-rewriting dataset. Each optimized prompt stopped naming the \
subject of the original request (for example "the temple" instead of "Doleshwor Mahadeva temple").
For each item, return the optimized prompt with the listed subjects put back, changing as few words as possible.
Keep the task, the constraints and the output format exactly as they are. Do not answer the prompt.
Return JSON: {"items": [{"id": "...", "optimized_prompt": "..."}]}"""


def regen_messages(batch: list[dict[str, Any]]) -> list[dict[str, str]]:
    items = [{"id": b["id"], "original_request": b["original_instruction"], "optimized_prompt": b["optimized_prompt"],
              "subjects_to_restore": b["subjects"]} for b in batch]
    return [{"role": "system", "content": REGEN_SYSTEM},
            {"role": "user", "content": json.dumps({"items": items}, ensure_ascii=False)}]


def regenerate(candidates: list[dict[str, Any]], llm: Any, cache: dict[str, str], max_calls: int,
               model: str = REGEN_MODEL) -> int:
    """Fill `cache` {id: new optimized prompt} for candidates not in it yet. Returns the number of calls made."""
    todo = [c for c in candidates if c["id"] not in cache]
    calls = 0
    for i in range(0, len(todo), ROWS_PER_CALL):
        if calls >= max_calls:
            break
        batch = todo[i:i + ROWS_PER_CALL]
        calls += 1
        try:
            c = llm.complete(model, regen_messages(batch), max_tokens=4000, reasoning_effort="low", json_mode=True)
            items = json.loads(c.content).get("items", [])
        except (ValueError, AttributeError):
            continue
        got = {it.get("id"): it.get("optimized_prompt", "") for it in items if isinstance(it, dict)}
        for b in batch:
            cache[b["id"]] = got.get(b["id"], "")   # "" = tried, rejected; not retried
    return calls


# ---- Run

@dataclass
class Report:
    rows: list[dict[str, str]] = field(default_factory=list)
    log: list[dict[str, str]] = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)


def _load(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def run(rows: list[dict[str, str]], nlp: Any = None, cache: dict[str, str] | None = None) -> Report:
    """Deterministic repairs, then (if `cache` is given) the accepted subject edits from it."""
    rep = Report()
    for row in rows:
        res = repair_row(row)
        cat = row["category"]
        rep.counts[(cat, "total")] += 1
        if res.action == "removed":
            rep.counts[(cat, "removed")] += 1
            rep.log.append({"id": row["id"], "split": row["split"], "category": cat, "action": "removed",
                            "field": "", "before": row["optimized_prompt"], "after": ""})
            continue
        for name in res.fixed_fields:
            rep.counts[(cat, f"repaired_{name.split('_')[0]}")] += 1
            rep.log.append({"id": row["id"], "split": row["split"], "category": cat, "action": "repaired",
                            "field": name, "before": row[name], "after": res.row[name]})
        if res.fixed_fields:
            rep.counts[(cat, "rows_repaired")] += 1
        out = res.row
        if nlp is not None:
            subjects = lost_subjects(out["original_instruction"], out["optimized_prompt"], out["context"], nlp)
            if subjects:
                rep.counts[(cat, "subject_dropped")] += 1
                new = (cache or {}).get(out["id"])
                if new is not None and accept_edit(out["optimized_prompt"], new, subjects):
                    rep.counts[(cat, "regenerated")] += 1
                    rep.log.append({"id": out["id"], "split": out["split"], "category": cat,
                                    "action": "regenerated", "field": "optimized_prompt",
                                    "before": out["optimized_prompt"], "after": new.strip()})
                    out = dict(out, optimized_prompt=new.strip())
                    _recount(out)
                elif new is not None:
                    rep.counts[(cat, "regen_rejected")] += 1
        rep.rows.append(out)
    return rep


def subject_candidates(rows: list[dict[str, str]], nlp: Any) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        res = repair_row(row)
        if res.action == "removed":
            continue
        subjects = lost_subjects(res.row["original_instruction"], res.row["optimized_prompt"],
                                 res.row["context"], nlp)
        if subjects:
            out.append({**res.row, "subjects": subjects})
    # Evaluation splits first, so a partial run fixes what gets measured.
    order = {"benchmark": 0, "test": 1, "val": 2, "train": 3}
    return sorted(out, key=lambda r: (order.get(r["split"], 9), r["id"]))


def write(rep: Report, out_dir: Path = V11_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = list(rep.rows[0].keys())
    with open(out_dir / "promptopt_dataset_v1_1.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rep.rows)
    for split in SPLITS:
        with open(out_dir / f"{split}.jsonl", "w", encoding="utf-8") as f:
            for r in rep.rows:
                if r["split"] == split:
                    f.write(json.dumps({"id": r["id"], "category": r["category"], "instruction": REWRITE_INSTRUCTION,
                                        "input": r["degraded_prompt"], "output": r["optimized_prompt"],
                                        "context": r["context"]}, ensure_ascii=False) + "\n")
    with open(out_dir / "repair_log.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "split", "category", "action", "field", "before", "after"])
        w.writeheader()
        w.writerows(rep.log)


def format_counts(rep: Report) -> str:
    cats = sorted({c for c, _ in rep.counts})
    cols = ["total", "rows_repaired", "repaired_optimized", "repaired_degraded", "subject_dropped", "regenerated",
            "regen_rejected", "removed"]
    lines = ["| category | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for c in cats + ["ALL"]:
        vals = [sum(v for (cc, k), v in rep.counts.items() if k == col and (c == "ALL" or cc == c)) for col in cols]
        lines.append(f"| {c} | " + " | ".join(str(v) for v in vals) + " |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, default=V1_CSV)
    ap.add_argument("--out", type=Path, default=V11_DIR)
    ap.add_argument("--write", action="store_true", help="write the v1.1 files")
    ap.add_argument("--max-calls", type=int, default=0, help="Groq calls for subject drops (0 = use the cache only)")
    args = ap.parse_args()

    import spacy
    nlp = spacy.load("en_core_web_sm")
    rows = _load(args.input)
    cache_path = args.out / "regenerated.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    if args.max_calls:
        from app.evaluation.llm import GroqChat
        cands = subject_candidates(rows, nlp)
        calls = 0
        try:
            calls = regenerate(cands, GroqChat(), cache, args.max_calls)
        finally:
            args.out.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Groq calls: {calls} ({len(cands)} subject-drop rows, {ROWS_PER_CALL} per call)")
    rep = run(rows, nlp, cache)
    print(format_counts(rep))
    if args.write:
        write(rep, args.out)
        print(f"wrote {len(rep.rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
