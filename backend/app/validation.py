"""Human validation of PromptOpt Dataset v1: rater sheets, agreement (Fleiss' Kappa) and the merged result.

Design: lab assistants validate LAB_COUNT records (from the benchmark split). The three students all rate the same
OVERLAP set (OVERLAP_PER_CATEGORY per category, 90 in total), which is used for Fleiss' Kappa. On top of that each
student rates EXTRA records alone, chosen by usefulness for filtering (see `extra_priority`). The rest of the dataset
is not human-rated and relies on the automatic checks from the Colab notebook.

    python -m app.validation assign --students Asha Piush Rahul       # create / update the sheets
    python -m app.validation report                                    # progress + Fleiss' Kappa
    python -m app.validation merge                                     # write the validated dataset

Everything is keyed on `source_id` (the row number in the original Dolly-15k / CodeAlpaca-20k download), which
stays the same when the notebook rebuilds the dataset; the dataset's `id` column is renumbered on every rebuild and
is not used. The assignment is frozen in `assignment.csv`: re-running `assign` keeps every lab, overlap and extra
record already chosen and only tops up what is missing, so answers are never moved. If a pair was regenerated (its
degraded or optimized text changed), its old answers are cleared and the note says to re-rate it.
"""
import argparse
import csv
import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from app.config import DATASET_DIR
from app.dataset_io import DEFAULT_CSV, load_rows

DEFAULT_SHEETS = DATASET_DIR.parent / "validation"
ASSIGNMENT_FILE = "assignment.csv"
LAB_SHEET = "lab_assistants"
CATEGORIES = ["closed_qa", "information_extraction", "classification", "summarization", "coding"]
LAB_COUNT = 20                # records validated by the lab assistants (spread evenly over the 5 categories)
OVERLAP_PER_CATEGORY = 18     # records rated by ALL students, per category (90 in total), for Fleiss' Kappa
EXTRA_PER_STUDENT = 60        # records each student rates alone, for filtering
SEED = "promptopt-validation-v1"

# Automatic-check thresholds used when the dataset was built (DATASET_CARD.md). Pairs that passed by less than
# BORDERLINE_MARGIN are the ones the automatic checks are least sure about.
SIM_DEGRADED_MIN = 0.45
SIM_OPTIMIZED_MIN = 0.35
BORDERLINE_MARGIN = 0.10
NOISY_CATEGORIES = {"summarization", "information_extraction"}      # Dolly labels often wrong (plain questions)
SPLIT_RANK = {"benchmark": 0, "test": 1, "val": 2, "train": 3}

QUESTIONS = [
    ("Q1_degraded_same_task", "Does the DEGRADED prompt ask for the same task as the original instruction?"),
    ("Q2_degraded_realistic", "Is the DEGRADED prompt a realistic vaguer version a real user might type "
                              "(not broken, not nonsense, not a different question)?"),
    ("Q3_optimized_same_intent", "Does the OPTIMIZED prompt keep the same task and intent, without adding facts, "
                                 "answers or requirements the user did not ask for?"),
    ("Q4_optimized_better", "Is the OPTIMIZED prompt clearer and better specified than the degraded prompt "
                            "(output format, constraints, no filler)?"),
    ("Q5_category_correct", "Is the CATEGORY label correct?"),
]
QCOLS = [q for q, _ in QUESTIONS]
TEXT_COLS = ["source_id", "category", "split", "original_instruction", "context",
             "degraded_prompt", "optimized_prompt"]
SHEET_COLS = TEXT_COLS + QCOLS + ["notes"]
ANSWERS = {"Y", "N"}


# ---------------------------------------------------------------- assignment
def _unit(*parts: str) -> float:
    """Deterministic uniform number in [0, 1) from the given strings."""
    h = hashlib.sha256(":".join((SEED,) + parts).encode()).hexdigest()
    return int(h[:15], 16) / 16 ** 15


def _sim(row: dict[str, str], col: str) -> float | None:
    try:
        return float(row.get(col, ""))
    except ValueError:
        return None


def is_borderline(row: dict[str, str]) -> bool:
    """True if either similarity check passed by less than BORDERLINE_MARGIN."""
    for col, low in (("sim_degraded_vs_original", SIM_DEGRADED_MIN), ("sim_optimized_vs_original", SIM_OPTIMIZED_MIN)):
        x = _sim(row, col)
        if x is not None and x < low + BORDERLINE_MARGIN:
            return True
    return False


def extra_priority(row: dict[str, str]) -> tuple:
    """Sort key for extra records, most useful first: evaluation splits (benchmark, test), then borderline
    automatic-check scores, then the categories with noisy Dolly labels, then a fixed pseudo-random order."""
    return (0 if row["split"] in ("benchmark", "test") else 1, 0 if is_borderline(row) else 1,
            0 if row["category"] in NOISY_CATEGORIES else 1, _unit("extra", row["source_id"]))


@dataclass
class Assignment:
    lab: list[str] = field(default_factory=list)                        # source_ids
    overlap: list[str] = field(default_factory=list)
    single: dict[str, list[str]] = field(default_factory=dict)          # student -> extra source_ids

    def raters_of(self, source_id: str) -> list[str]:
        if source_id in self.lab:
            return [LAB_SHEET]
        if source_id in self.overlap:
            return list(self.single)
        return [s for s, ids in self.single.items() if source_id in ids]

    def role_of(self, source_id: str) -> str:
        if source_id in self.lab:
            return "lab"
        if source_id in self.overlap:
            return "overlap"
        return "extra" if any(source_id in ids for ids in self.single.values()) else "none"


def assign(rows: list[dict[str, str]], students: list[str], lab_count: int = LAB_COUNT,
           overlap_per_category: int = OVERLAP_PER_CATEGORY, extra: int = EXTRA_PER_STUDENT,
           frozen: Assignment | None = None) -> Assignment:
    """Choose the lab, overlap and extra records, keeping every record already in `frozen`.

    Lab: lab_count / 5 per category, benchmark split first (those rows are used in the live A/B evaluation, so they
    deserve the most careful check), then test. Overlap: overlap_per_category per category, fixed pseudo-random pick
    from the remaining rows. Extra: up to `extra` per student, most useful first (`extra_priority`), dealt out so the
    students' shares stay equally useful.
    """
    if len(set(students)) != len(students) or LAB_SHEET in students or not students:
        raise ValueError("students must be distinct names, and not 'lab_assistants'")
    ids = [r["source_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("source_id is not unique in the dataset")
    present = set(ids)
    frozen = frozen or Assignment()

    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    cat_of = {r["source_id"]: r["category"] for r in rows}

    def top_up(chosen: list[str], per_cat: int, key, taken: set[str]) -> list[str]:
        for cat in sorted(by_cat):
            have = sum(cat_of[s] == cat for s in chosen)
            ranked = sorted((r for r in by_cat[cat] if r["source_id"] not in taken), key=key)
            new = [r["source_id"] for r in ranked[:max(per_cat - have, 0)]]
            chosen += new
            taken.update(new)
        return chosen

    lab = [s for s in frozen.lab if s in present]
    taken = set(lab)
    lab = top_up(lab, lab_count // len(CATEGORIES),
                 lambda r: (SPLIT_RANK.get(r["split"], 9), _unit("lab", r["source_id"])), taken)
    extra_lab = lab_count - len(lab)                     # lab_count not divisible by 5: fill from benchmark
    if extra_lab > 0:
        rest = sorted((r for r in rows if r["source_id"] not in taken),
                      key=lambda r: (SPLIT_RANK.get(r["split"], 9), _unit("lab", r["source_id"])))
        lab += [r["source_id"] for r in rest[:extra_lab]]
        taken.update(lab)

    overlap = [s for s in frozen.overlap if s in present and s not in taken]
    taken.update(overlap)
    overlap = top_up(overlap, overlap_per_category, lambda r: _unit("overlap", r["source_id"]), taken)

    single = {s: [x for x in frozen.single.get(s, []) if x in present and x not in taken] for s in students}
    for ids_ in single.values():
        taken.update(ids_)
    candidates = iter(sorted((r for r in rows if r["source_id"] not in taken), key=extra_priority))
    while True:
        short = [s for s in students if len(single[s]) < extra]
        if not short:
            break
        s = min(short, key=lambda s: (len(single[s]), students.index(s)))
        nxt = next(candidates, None)
        if nxt is None:
            break
        single[s].append(nxt["source_id"])
    return Assignment(lab=lab, overlap=overlap, single=single)


def read_assignment(path: Path, students: list[str]) -> Assignment:
    """The frozen assignment from a previous `assign` run. Extra records of students not in `students` are dropped."""
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and ("id" in rows[0] or any(r["role"] == "single" for r in rows)):
        raise SystemExit(f"{path} is from the old assignment design (6% overlap, everything assigned). Nobody had "
                         f"rated it yet, so re-run with --reset to start from the new design.")
    a = Assignment(single={s: [] for s in students})
    dropped = set()
    for r in rows:
        if r["role"] == "lab":
            a.lab.append(r["source_id"])
        elif r["role"] == "overlap":
            a.overlap.append(r["source_id"])
        elif r["role"] == "extra":
            if r["raters"] in a.single:
                a.single[r["raters"]].append(r["source_id"])
            else:
                dropped.add(r["raters"])
    if dropped:
        print(f"Warning: {', '.join(sorted(dropped))} not in --students; their extra records are reassigned "
              f"(answers already given stay in their sheets).")
    return a


def write_assignment(path: Path, rows: list[dict[str, str]], a: Assignment) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "category", "split", "role", "raters"])
        for r in rows:
            sid = r["source_id"]
            w.writerow([sid, r["category"], r["split"], a.role_of(sid), ";".join(a.raters_of(sid))])


# ---------------------------------------------------------------- sheets (xlsx)
def _clean(value: str) -> str:
    """Text as it will round-trip through Excel: no control characters, no surrounding whitespace."""
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

    return ILLEGAL_CHARACTERS_RE.sub("", value or "").strip()


def _sheet_path(folder: Path, name: str) -> Path:
    return folder / f"{name}.xlsx"


def read_sheet(path: Path) -> list[dict[str, str]]:
    from openpyxl import load_workbook

    ws = load_workbook(path, read_only=True)["ratings"]
    it = ws.iter_rows(values_only=True)
    header = [str(h) for h in next(it)]
    return [{h: ("" if v is None else str(v)).strip() for h, v in zip(header, row)} for row in it if any(row)]


def write_sheet(path: Path, rater: str, rows: list[dict[str, str]]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "ratings"
    ws.append(SHEET_COLS)
    for r in rows:
        ws.append([_clean(r.get(c, "")) for c in SHEET_COLS])
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if cell.data_type == "f":           # text starting with "=" must stay text, never become a formula
                cell.data_type = "s"
    widths = {"source_id": 16, "category": 20, "split": 10, "original_instruction": 45, "context": 45,
              "degraded_prompt": 45, "optimized_prompt": 60, "notes": 40}
    for i, col in enumerate(SHEET_COLS, start=1):
        letter = ws.cell(row=1, column=i).column_letter
        ws.column_dimensions[letter].width = widths.get(col, 12)
        ws.cell(row=1, column=i).font = Font(bold=True)
        if col in QCOLS:
            ws.cell(row=1, column=i).fill = PatternFill("solid", fgColor="FFF2CC")
    wrap = Alignment(wrap_text=True, vertical="top")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = wrap
    first_q = SHEET_COLS.index(QCOLS[0]) + 1
    last_q = SHEET_COLS.index(QCOLS[-1]) + 1
    dv = DataValidation(type="list", formula1='"Y,N"', allow_blank=True, showErrorMessage=True,
                        errorTitle="Y or N", error="Answer Y (yes) or N (no).")
    ws.add_data_validation(dv)
    dv.add(f"{ws.cell(row=2, column=first_q).coordinate}:{ws.cell(row=max(len(rows) + 1, 2), column=last_q).coordinate}")
    ws.freeze_panes = ws.cell(row=2, column=SHEET_COLS.index("degraded_prompt") + 1)
    ws.auto_filter.ref = ws.dimensions

    guide = wb.create_sheet("instructions")
    guide.column_dimensions["A"].width = 28
    guide.column_dimensions["B"].width = 110
    guide.append(["Rater", rater])
    guide.append(["How", "Answer every yellow column with Y or N (use the drop-down). Read the original "
                          "instruction and context first; they are the ground truth for the task."])
    guide.append(["Accept rule", "A pair is accepted only if all five answers are Y. Use 'notes' for anything "
                                 "unclear or to suggest a fix; do not edit the prompt columns."])
    guide.append([])
    for q, text in QUESTIONS:
        guide.append([q, text])
    for row in guide.iter_rows():
        for cell in row:
            cell.alignment = wrap
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def build_sheets(rows: list[dict[str, str]], a: Assignment, folder: Path) -> dict[str, dict[str, int]]:
    """Create or update one sheet per rater, keeping existing answers. Returns per-sheet statistics."""
    by_id = {r["source_id"]: r for r in rows}
    wanted = {LAB_SHEET: a.lab, **{s: a.overlap + ids for s, ids in a.single.items()}}
    stats = {}
    for rater, ids in wanted.items():
        path = _sheet_path(folder, rater)
        old = {r["source_id"]: r for r in read_sheet(path)} if path.exists() else {}
        out, kept, reset, added = [], 0, 0, 0
        for sid in sorted(ids, key=lambda s: _unit("order", s)):          # mixed categories, stable order
            fresh = {c: _clean(by_id[sid].get(c, "")) for c in TEXT_COLS}
            prev = old.pop(sid, None)
            if prev is None:
                added += 1
            elif any(prev.get(c, "") != fresh[c] for c in ("degraded_prompt", "optimized_prompt")):
                reset += 1
                fresh["notes"] = "REGENERATED: pair changed since you rated it, please re-rate. " + prev.get("notes", "")
            else:
                kept += 1
                fresh.update({c: prev.get(c, "") for c in QCOLS + ["notes"]})
            out.append(fresh)
        orphaned = 0
        for sid, prev in old.items():               # never throw answers away; unanswered leftovers are dropped
            if not (any(prev.get(q) for q in QCOLS) or prev.get("notes")):
                continue
            orphaned += 1
            if not prev.get("notes", "").startswith("NO LONGER ASSIGNED"):
                prev["notes"] = ("NO LONGER ASSIGNED (removed from the dataset or reassigned; kept so no answers are "
                                 "lost). " + prev.get("notes", ""))
            out.append({c: prev.get(c, "") for c in SHEET_COLS})
        write_sheet(path, rater, out)
        stats[rater] = {"rows": len(out), "new": added, "kept": kept, "reset": reset, "orphaned": orphaned}
    return stats


# ---------------------------------------------------------------- agreement
def fleiss_kappa(counts: list[list[int]]) -> float:
    """Fleiss' Kappa. counts[i][j] = number of raters who put item i in category j (same total per item).

    Returns NaN when agreement by chance is 1 (every rating identical), where kappa is undefined.
    """
    if not counts:
        return math.nan
    n = sum(counts[0])
    if n < 2 or any(sum(r) != n for r in counts):
        raise ValueError("every item needs the same number (>= 2) of ratings")
    items = len(counts)
    p_j = [sum(r[j] for r in counts) / (items * n) for j in range(len(counts[0]))]
    p_i = [(sum(c * c for c in r) - n) / (n * (n - 1)) for r in counts]
    p_bar, p_e = sum(p_i) / items, sum(p * p for p in p_j)
    return math.nan if p_e == 1 else (p_bar - p_e) / (1 - p_e)


def interpret_kappa(k: float) -> str:
    """Landis & Koch (1977) bands."""
    if math.isnan(k):
        return "undefined (all answers identical)"
    for limit, label in ((0, "poor"), (0.2, "slight"), (0.4, "fair"), (0.6, "moderate"), (0.8, "substantial")):
        if k <= limit:
            return label
    return "almost perfect"


def _complete(r: dict[str, str]) -> bool:
    return all(r.get(q, "").upper() in ANSWERS for q in QCOLS)


def load_all(folder: Path) -> dict[str, list[dict[str, str]]]:
    sheets = {p.stem: read_sheet(p) for p in sorted(folder.glob("*.xlsx")) if not p.name.startswith("~$")}
    if not sheets:
        raise SystemExit(f"No rater sheets in {folder}. Run `python -m app.validation assign` first.")
    for name, rows in sheets.items():
        for r in rows:
            for q in QCOLS:
                v = r.get(q, "").upper()
                if v and v not in ANSWERS:
                    raise SystemExit(f"{name}.xlsx, {r['source_id']}, {q}: '{r[q]}' is not Y or N")
                r[q] = v
    return sheets


def agreement(sheets: dict[str, list[dict[str, str]]]) -> tuple[int, dict[str, tuple[float, float]]]:
    """Fleiss' Kappa and raw percent agreement per question, over records rated completely by 3+ students."""
    ratings = defaultdict(dict)
    for rater, rows in sheets.items():
        if rater == LAB_SHEET:
            continue
        for r in rows:
            if _complete(r):
                ratings[r["source_id"]][rater] = r
    students = [s for s in sheets if s != LAB_SHEET]
    shared = [by for by in ratings.values() if len(by) == len(students) >= 2]
    out = {}
    for q in QCOLS + ["accept"]:
        table = []
        for by in shared:
            vals = [("Y" if all(r[x] == "Y" for x in QCOLS) else "N") if q == "accept" else r[q] for r in by.values()]
            table.append([vals.count("Y"), vals.count("N")])
        agree = sum(1 for y, n in table if y == 0 or n == 0) / len(table) if table else math.nan
        out[q] = (fleiss_kappa(table) if table else math.nan, agree)
    return len(shared), out


# ---------------------------------------------------------------- merge
def resolve(sheets: dict[str, list[dict[str, str]]]) -> dict[str, dict[str, str]]:
    """Final answers per source_id. Lab assistants decide their records; overlap records go by majority vote
    (at least 2 matching answers per question); others take their single rater's answers."""
    by_id = defaultdict(list)
    for rater, rows in sheets.items():
        for r in rows:
            if _complete(r):
                by_id[r["source_id"]].append((rater, r))
    final = {}
    for sid, rated in by_id.items():
        lab = [r for rater, r in rated if rater == LAB_SHEET]
        if lab:
            chosen, who = {q: lab[0][q] for q in QCOLS}, LAB_SHEET
        elif len(rated) == 1:
            chosen, who = {q: rated[0][1][q] for q in QCOLS}, rated[0][0]
        else:
            chosen, who = {}, "+".join(sorted(rater for rater, _ in rated))
            for q in QCOLS:
                (top, n), *rest = Counter(r[q] for _, r in rated).most_common() + [("", 0)]
                chosen[q] = top if n >= 2 and n > rest[0][1] else ""
            if not all(chosen.values()):
                continue                                                     # tie: needs another rating
        chosen["validation_accept"] = str(all(chosen[q] == "Y" for q in QCOLS))
        chosen["validated_by"] = who
        chosen["validator_notes"] = " | ".join(r["notes"] for _, r in rated if r.get("notes"))
        final[sid] = chosen
    return final


# ---------------------------------------------------------------- commands
def cmd_assign(args) -> None:
    rows = load_rows(args.dataset)
    frozen_path = args.sheets / ASSIGNMENT_FILE
    frozen = read_assignment(frozen_path, args.students) if frozen_path.exists() and not args.reset else None
    a = assign(rows, args.students, args.lab_count, args.overlap_per_category, args.extra, frozen)
    stats = build_sheets(rows, a, args.sheets)
    write_assignment(frozen_path, rows, a)
    extras = sum(map(len, a.single.values()))
    print(f"{len(rows)} records: {len(a.lab)} lab assistants, {len(a.overlap)} overlap (all students), "
          f"{extras} extra (one student each), {len(rows) - len(a.lab) - len(a.overlap) - extras} not human-rated")
    short = [c for c in CATEGORIES if sum(r["category"] == c and r["source_id"] in a.overlap for r in rows)
             < args.overlap_per_category]
    if short:
        print(f"Warning: fewer than {args.overlap_per_category} overlap records for {', '.join(short)}")
    for rater, s in stats.items():
        print(f"  {rater + '.xlsx':<22} {s['rows']:>5} rows  (new {s['new']}, unchanged {s['kept']}, "
              f"reset {s['reset']}, no longer assigned {s['orphaned']})")


def report_text(sheets: dict[str, list[dict[str, str]]]) -> str:
    lines = ["# Dataset validation report", "", "| sheet | rows | completed | accepted |", "|---|---|---|---|"]
    for name, rows in sheets.items():
        done = [r for r in rows if _complete(r)]
        acc = sum(all(r[q] == "Y" for q in QCOLS) for r in done)
        lines.append(f"| {name} | {len(rows)} | {len(done)} ({100 * len(done) / max(len(rows), 1):.0f}%) | {acc} |")
    n, stats = agreement(sheets)
    student_sets = [{r["source_id"] for r in rows} for name, rows in sheets.items() if name != LAB_SHEET]
    n_overlap = len(set.intersection(*student_sets)) if len(student_sets) >= 2 else 0
    lines += ["", f"## Inter-rater agreement (Fleiss' Kappa, {n} of {n_overlap} overlap records rated by every "
                  f"student)", ""]
    if n:
        lines += ["| question | kappa | interpretation | raw agreement |", "|---|---|---|---|"]
        for q, (k, pa) in stats.items():
            lines.append(f"| {q} | {'n/a' if math.isnan(k) else f'{k:.3f}'} | {interpret_kappa(k)} | {100 * pa:.1f}% |")
        lines += ["", "When almost every answer is Y, kappa can be low even with high raw agreement "
                      "(the kappa paradox); report both."]
    else:
        lines.append("No overlap record has been completed by every student yet.")
    final = resolve(sheets)
    accepted = sum(v["validation_accept"] == "True" for v in final.values())
    lines += ["", "## Result", "", f"Validated records: **{len(final)}**, accepted: **{accepted}**. Records nobody rated rely on the "
                                     f"automatic checks."]
    by_cat = Counter()
    cat_of = {r["source_id"]: r["category"] for rows in sheets.values() for r in rows}
    for sid, v in final.items():
        if v["validation_accept"] == "True":
            by_cat[cat_of.get(sid, "?")] += 1
    if by_cat:
        lines.append("Accepted per category: " + ", ".join(f"{c} {n}" for c, n in sorted(by_cat.items())))
    return "\n".join(lines) + "\n"


def cmd_report(args) -> None:
    text = report_text(load_all(args.sheets))
    print(text)
    (args.sheets / "validation_report.md").write_text(text, encoding="utf-8")


def cmd_merge(args) -> None:
    final = resolve(load_all(args.sheets))
    rows = load_rows(args.dataset)
    cols = list(rows[0]) + QCOLS + ["validation_accept", "validated_by", "validator_notes"]
    out_rows = []
    for r in rows:
        v = final.get(r["source_id"])
        r = dict(r, human_validated=str(v is not None), **(v or {}))
        if not args.accepted_only or (v and v["validation_accept"] == "True"):
            out_rows.append(r)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    print(f"Wrote {len(out_rows)} rows to {args.out} ({len(final)} validated, "
          f"{sum(v['validation_accept'] == 'True' for v in final.values())} accepted)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sheets", type=Path, default=DEFAULT_SHEETS, help="folder with the rater .xlsx files")
    ap.add_argument("--dataset", type=Path, default=DEFAULT_CSV)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("assign", help="create or update the rater sheets")
    p.add_argument("--students", nargs="+", default=["student_A", "student_B", "student_C"])
    p.add_argument("--lab-count", type=int, default=LAB_COUNT)
    p.add_argument("--overlap-per-category", type=int, default=OVERLAP_PER_CATEGORY,
                   help="records per category rated by all students (for Fleiss' Kappa)")
    p.add_argument("--extra", type=int, default=EXTRA_PER_STUDENT, help="records each student rates alone")
    p.add_argument("--reset", action="store_true",
                   help=f"ignore the frozen {ASSIGNMENT_FILE} and choose again (answers in the sheets are kept)")
    p.set_defaults(func=cmd_assign)
    sub.add_parser("report", help="progress and Fleiss' Kappa").set_defaults(func=cmd_report)
    p = sub.add_parser("merge", help="write the dataset with validation columns")
    p.add_argument("--out", type=Path, default=DATASET_DIR / "promptopt_dataset_v1_validated.csv")
    p.add_argument("--accepted-only", action="store_true")
    p.set_defaults(func=cmd_merge)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
