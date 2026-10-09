"""Static checks of coding reference answers (CodeAlpaca), without running any model or any code.

Two wrong references were found on val by reading judge rationales (codealpaca-16240: the "equal-sum" split it
prints sums to 10 and 18; codealpaca-12152: claims the maximum depth of a binary tree with n nodes is log2(n)).
Those are logic errors, which a static check cannot see. What it can see:

* does_not_parse   the reference is Python and `ast.parse` fails, or its brackets are badly unbalanced
* wrong_language   the instruction names a language and the reference is clearly another one
* not_code         a code-writing instruction whose reference contains no code
* missing_name     the instruction names a function/class/variable ("called X", "named X") that the code lacks

    python -m app.reference_check --splits test benchmark      # writes evaluation/dataset/reference_suspects.csv
"""
import argparse
import ast
import csv
import re
from pathlib import Path

from app.config import BACKEND_DIR

EVAL_DOCS = BACKEND_DIR.parent / "evaluation"
SUSPECTS_CSV = EVAL_DOCS / "dataset" / "reference_suspects.csv"
WRONG_REFERENCES_CSV = EVAL_DOCS / "dataset" / "wrong_references.csv"

LANG_IN_INSTRUCTION = [      # (language, pattern in the instruction); order matters (JavaScript before Java)
    ("javascript", r"\b(?:javascript|js|node\.?js|jquery|react|typescript)\b"),
    ("java", r"\bjava\b"),
    ("cpp", r"\bc\+\+|\bcpp\b"),
    ("csharp", r"\bc#"),
    ("python", r"\bpython\b"),
    ("sql", r"\b(?:sql|mysql|postgresql|sqlite)\b"),
    ("html", r"\bhtml\b"),
    ("css", r"\bcss\b"),
    ("php", r"\bphp\b"),
    ("ruby", r"\bruby\b"),
    ("bash", r"\b(?:bash|shell script)\b"),
    ("r", r"\bR\s+(?:script|program|code|function)\b|\bin R\b"),
]
LANG_SIGNS = {               # strong signs that code is in a language
    "python": r"^\s*def \w+\(.*\)\s*:|^\s*import \w+|^\s*from \w+ import|\bprint\(|^\s*class \w+(\(.*\))?\s*:",
    "java": r"\bpublic\s+(?:static\s+)?(?:class|void|int|String)\b|System\.out\.print",
    "cpp": r"#include\s*<|\bstd::|\bcout\s*<<|\bint\s+main\s*\(",
    "csharp": r"\busing System\b|Console\.Write|\bforeach\s*\(\s*\w+ \w+ in\b|\bfrom \w+ in \w+|\(\s*string \w+[,)]",
    "javascript": r"\bfunction\s+\w*\s*\(|console\.log|\b(?:let|const|var)\s+\w+\s*=|=>",
    "sql": r"^\s*(?:SELECT|INSERT|UPDATE|DELETE|CREATE\s+TABLE)\b",
    "html": r"<\s*(?:html|div|body|p|table|form|input|h1|span|ul|li)\b",
    "php": r"<\?php|\$\w+\s*=",
    "ruby": r"^\s*def \w+(?!.*:\s*$)|\bputs\b|\bend\s*$",
    "bash": r"^#!/bin/(?:ba)?sh|^\s*echo\s|\bmkdir\b",
    "r": r"<-\s*\w|\bc\(\d",
}
# Languages that are often mixed (HTML with CSS/JS, JS with HTML): never flagged against each other.
COMPATIBLE = {("html", "css"), ("html", "javascript"), ("css", "html"), ("javascript", "html"), ("cpp", "c")}
CODE_WRITING = re.compile(r"\b(?:write|create|implement|generate|construct|develop|design|build|code|compose|"
                          r"edit|modify|rewrite|fix|complete)\b.*\b(?:function|program|code|script|class|method|"
                          r"query|statement|snippet|loop|regex|expression|page|component)\b", re.I)
NAMED = re.compile(r"\b(?:called|named)\s+[\"'`“]?([A-Za-z_][A-Za-z0-9_]*)", re.I)
CODE_TOKENS = re.compile(r"[(){};=\[\]<>*]|\b(?:def|return|SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE)\b", re.I)
REGEX_TASK = re.compile(r"\b(?:regex|regular expression)\b", re.I)
EXPLAIN_TASK = re.compile(r"^\s*(?:how|explain|describe|suggest|what|why|which|identify|compare|name|list|"
                          r"classify|determine|count|find out)\b", re.I)
PROSE_START = re.compile(r"^[A-Z][a-z']+(?: [A-Za-z',]+){3,}")
# "Output:" notes after the code: a comment line, or an "Output:" line followed by the printed results
OUTPUT_NOTE = re.compile(r"^\s*(?://|#)\s*output\s*[:=].*$|^\s*output\s*:\s*$(?:\n.*)*", re.I | re.M)


def strip_fences(code: str) -> str:
    """Fences removed, non-breaking spaces made plain (formatting, not a wrong reference), common indent removed."""
    import textwrap

    code = re.sub(r"^```\w*\s*$", "", code, flags=re.M).replace("\u00a0", " ")
    return textwrap.dedent(code).strip()


def language_asked(instruction: str) -> str | None:
    """The one language the instruction names, or None if it names none or several ("convert this SQL to Pandas")."""
    text = re.sub(LANG_IN_INSTRUCTION[0][1], " ", instruction, flags=re.I)          # "JavaScript" is not "Java"
    found = [lang for lang, pattern in LANG_IN_INSTRUCTION[1:] if re.search(pattern, text, re.I)]
    if re.search(LANG_IN_INSTRUCTION[0][1], instruction, re.I):
        found.append("javascript")
    if re.search(r"\bpandas|numpy|django|flask\b", instruction, re.I):
        found.append("python")
    found = list(dict.fromkeys(found))
    return found[0] if len(found) == 1 else None


def languages_seen(code: str) -> set[str]:
    return {lang for lang, pattern in LANG_SIGNS.items() if re.search(pattern, code, re.M | re.I if lang == "sql"
                                                                      else re.M)}


def _balanced(code: str) -> bool:
    """Brackets balanced, ignoring string literals and comments (a rough check: only gross imbalance counts)."""
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`[^`]*`', "", code)
    text = re.sub(r"#[^\n]*|//[^\n]*|/\*.*?\*/", "", text, flags=re.S)
    return all(abs(text.count(a) - text.count(b)) <= 1 for a, b in ("()", "[]", "{}"))


def check(instruction: str, reference: str) -> list[str]:
    """Issues found in one coding reference; [] if none."""
    code = strip_fences(reference or "")
    issues = []
    seen = languages_seen(code)
    tokens = len(CODE_TOKENS.findall(code))
    if (CODE_WRITING.search(instruction) and not EXPLAIN_TASK.search(instruction) and not REGEX_TASK.search(instruction)
            and not seen and tokens == 0):
        return ["not_code"]
    if not seen and tokens < 3:
        return []
    # explanations, and code introduced by prose, are not checked for parsing (they are not meant to run as a whole)
    parse_it = not EXPLAIN_TASK.search(instruction) and not PROSE_START.match(code)
    code = OUTPUT_NOTE.sub("", code)                      # "// Output: 2,4,6" notes after the code
    asked = language_asked(instruction)
    if not parse_it:
        pass
    elif asked == "python" or (asked is None and seen == {"python"}):
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"does_not_parse (python: {e.msg}, line {e.lineno})")
    elif seen and asked not in ("bash", "r") and not _balanced(code):
        issues.append("does_not_parse (unbalanced brackets)")
    if asked and seen and asked not in seen and not any((asked, s) in COMPATIBLE for s in seen):
        issues.append(f"wrong_language (instruction: {asked}, reference looks like: {', '.join(sorted(seen))})")
    for name in NAMED.findall(instruction):
        if name.lower() not in {"a", "an", "the", "function", "class", "method"} and name not in code:
            issues.append(f"missing_name ({name})")
    return issues


def scan(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for r in rows:
        if r["category"] != "coding":
            continue
        issues = check(r["original_instruction"], r["reference_response"])
        if issues:
            out.append({"source_id": r["source_id"], "split": r["split"], "issues": "; ".join(issues),
                        "instruction": r["original_instruction"][:200], "reference": r["reference_response"][:300]})
    return out


def load_wrong_references(path: Path = WRONG_REFERENCES_CSV) -> dict[str, str]:
    """{source_id: reason} of rows whose reference answer is wrong; the evaluation report excludes them."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        return {r["source_id"]: r["reason"] for r in csv.DictReader(f)}


def main() -> None:
    from app.dataset_io import DEFAULT_CSV, load_rows

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dataset", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--splits", nargs="+", default=["test", "benchmark"])
    ap.add_argument("--out", type=Path, default=SUSPECTS_CSV)
    args = ap.parse_args()
    rows = [r for r in load_rows(args.dataset) if r["split"] in args.splits]
    suspects = scan(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source_id", "split", "issues", "instruction", "reference"])
        w.writeheader()
        w.writerows(suspects)
    n = sum(r["category"] == "coding" for r in rows)
    print(f"{len(suspects)} suspect references among {n} coding rows in {', '.join(args.splits)}; wrote {args.out}")
    for s in suspects:
        print(f"  {s['source_id']} [{s['split']}] {s['issues']}\n      {s['instruction'][:110]}")


if __name__ == "__main__":
    main()
