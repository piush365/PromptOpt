"""Dataset validation tooling: assignment, sheets, Fleiss' Kappa, merge."""
import math

import pytest

from app import validation as v

CATS = ["closed_qa", "information_extraction", "classification", "summarization", "coding"]
STUDENTS = ["asha", "piush", "rahul"]


def make_rows(n_per_cat: int, start: int = 0, split=None) -> list[dict[str, str]]:
    rows = []
    for c in CATS:
        for i in range(start, start + n_per_cat):
            sp = split or ("benchmark" if i < 10 else ("test" if i < 50 else "train"))
            rows.append({"id": f"{c}-{i}", "source_id": f"src-{c}-{i}", "category": c, "split": sp,
                         "original_instruction": f"orig {c} {i}", "context": "", "degraded_prompt": f"deg {c} {i}",
                         "optimized_prompt": f"opt {c} {i}", "sim_degraded_vs_original": "0.9",
                         "sim_optimized_vs_original": "0.9"})
    return rows


def answer(row: dict, value: str = "Y") -> dict:
    return {**row, **{q: value for q in v.QCOLS}}


def test_fleiss_kappa_wikipedia_example():
    # 10 items, 14 raters, 5 categories: kappa = 0.210 (Fleiss 1971 worked example, as on Wikipedia)
    table = [[0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
             [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7]]
    assert round(v.fleiss_kappa(table), 3) == 0.210


def test_fleiss_kappa_edge_cases():
    assert v.fleiss_kappa([[3, 0], [0, 3]]) == 1.0
    assert math.isnan(v.fleiss_kappa([[3, 0], [3, 0]]))          # everyone always says Y: undefined
    with pytest.raises(ValueError):
        v.fleiss_kappa([[3, 0], [2, 0]])


def test_assignment_sizes_and_no_record_in_two_roles():
    rows = make_rows(100)
    a = v.assign(rows, STUDENTS)
    cat = {r["source_id"]: r for r in rows}
    assert len(a.lab) == 20
    assert all(sum(cat[s]["category"] == c for s in a.lab) == 4 for c in CATS)
    assert all(cat[s]["split"] == "benchmark" for s in a.lab)
    assert len(a.overlap) == 90
    assert all(sum(cat[s]["category"] == c for s in a.overlap) == 18 for c in CATS)
    assert all(len(ids) == 60 for ids in a.single.values())
    flat = a.lab + a.overlap + [s for ids in a.single.values() for s in ids]
    assert len(flat) == len(set(flat)) == 20 + 90 + 180
    assert a.raters_of(a.overlap[0]) == STUDENTS and a.role_of(a.overlap[0]) == "overlap"
    unrated = next(s for s in cat if s not in set(flat))
    assert a.raters_of(unrated) == [] and a.role_of(unrated) == "none"


def test_extras_follow_priority_order():
    rows = make_rows(100)
    a = v.assign(rows, STUDENTS, extra=10)
    cat = {r["source_id"]: r for r in rows}
    assert all(cat[s]["split"] in ("benchmark", "test") for ids in a.single.values() for s in ids)

    rows = make_rows(40, split="train")                       # same split: borderline first, then noisy categories
    for r in rows[::7]:
        r["sim_optimized_vs_original"] = "0.40"               # passed the 0.35 check by less than the margin
    borderline = {r["source_id"] for r in rows[::7]}
    a = v.assign(rows, STUDENTS, extra=4)
    extras = [s for ids in a.single.values() for s in ids]
    assert set(extras) <= borderline
    left = borderline - set(a.lab + a.overlap)
    a = v.assign(rows, STUDENTS, extra=len(left) // 3 + 3)    # borderline ones used up, noisy categories next
    cat = {r["source_id"]: r for r in rows}
    extras = {s for ids in a.single.values() for s in ids}
    rest = extras - borderline
    assert left <= extras and rest and all(cat[s]["category"] in v.NOISY_CATEGORIES for s in rest)


def test_extras_are_dealt_evenly_by_usefulness():
    rows = make_rows(100)
    a = v.assign(rows, STUDENTS)
    ranked = sorted((r for r in rows if r["source_id"] not in set(a.lab + a.overlap)), key=v.extra_priority)
    first = [r["source_id"] for r in ranked[:3]]
    assert [a.single[s][0] for s in STUDENTS] == first        # every student gets one of the top 3


def test_small_dataset_gives_what_it_can():
    a = v.assign(make_rows(10), STUDENTS)                     # 50 rows: 20 lab, 30 overlap, nothing left
    assert len(a.lab) == 20 and len(a.overlap) == 30 and all(ids == [] for ids in a.single.values())


def test_frozen_assignment_survives_growth():
    small, big = make_rows(30), make_rows(30) + make_rows(70, start=30)
    a = v.assign(small, STUDENTS, extra=20)
    b = v.assign(big, STUDENTS, extra=30, frozen=a)
    assert b.lab == a.lab
    assert b.overlap[:len(a.overlap)] == a.overlap and len(b.overlap) == 90
    for s in STUDENTS:
        assert a.single[s] and b.single[s][:len(a.single[s])] == a.single[s] and len(b.single[s]) == 30
    unfrozen = v.assign(big, STUDENTS, extra=30)
    assert set(unfrozen.overlap) != set(b.overlap)            # without freezing, the pick would move


def test_frozen_rows_that_left_the_dataset_are_dropped():
    rows = make_rows(100)
    a = v.assign(rows, STUDENTS)
    gone = a.overlap[0]
    b = v.assign([r for r in rows if r["source_id"] != gone], STUDENTS, frozen=a)
    assert gone not in b.overlap and len(b.overlap) == 90 and b.overlap[:89] == a.overlap[1:]


def test_assignment_file_round_trip(tmp_path):
    rows = make_rows(100)
    a = v.assign(rows, STUDENTS)
    path = tmp_path / v.ASSIGNMENT_FILE
    v.write_assignment(path, rows, a)
    b = v.read_assignment(path, STUDENTS)
    assert set(b.lab) == set(a.lab) and set(b.overlap) == set(a.overlap)
    assert all(set(b.single[s]) == set(a.single[s]) for s in STUDENTS)
    assert v.read_assignment(path, ["asha", "piush", "new"]).single["new"] == []


def test_old_assignment_file_is_refused(tmp_path):
    path = tmp_path / v.ASSIGNMENT_FILE
    path.write_text("source_id,id,category,split,role,raters\nsrc-1,PO-1,coding,train,single,student_A\n")
    with pytest.raises(SystemExit, match="--reset"):
        v.read_assignment(path, STUDENTS)


def test_assignment_rejects_bad_input():
    with pytest.raises(ValueError):
        v.assign(make_rows(20), ["a", "a", "b"])
    rows = make_rows(20)
    rows[1]["source_id"] = rows[0]["source_id"]
    with pytest.raises(ValueError):
        v.assign(rows, STUDENTS)


def test_sheets_are_keyed_by_source_id_not_id():
    assert "id" not in v.SHEET_COLS and "source_id" in v.SHEET_COLS


def test_sheets_keep_answers_and_reset_regenerated_pairs(tmp_path):
    rows = make_rows(30)
    a = v.assign(rows, STUDENTS, extra=10)
    v.build_sheets(rows, a, tmp_path)
    sheet = tmp_path / "asha.xlsx"
    rated = v.read_sheet(sheet)
    rated[0] = answer(rated[0], "Y")
    rated[1] = answer(rated[1], "N") | {"notes": "drifted"}
    v.write_sheet(sheet, "asha", rated)
    kept_id, regen_id = rated[0]["source_id"], rated[1]["source_id"]

    grown = make_rows(30) + make_rows(20, start=30)
    for r in grown:
        r["id"] = "RENUMBERED-" + r["id"]                     # the notebook renumbers `id` on every rebuild
        if r["source_id"] == regen_id:
            r["optimized_prompt"] = "a regenerated optimized prompt"
    stats = v.build_sheets(grown, v.assign(grown, STUDENTS, extra=20, frozen=a), tmp_path)

    after = {r["source_id"]: r for r in v.read_sheet(sheet)}
    assert all(after[kept_id][q] == "Y" for q in v.QCOLS)
    assert all(after[regen_id][q] == "" for q in v.QCOLS)
    assert after[regen_id]["notes"].startswith("REGENERATED") and "drifted" in after[regen_id]["notes"]
    assert stats["asha"]["kept"] >= 1 and stats["asha"]["reset"] == 1 and stats["asha"]["new"] > 0


def test_sheets_drop_unanswered_rows_and_keep_answered_ones_no_longer_assigned(tmp_path):
    rows = make_rows(30)
    v.build_sheets(rows, v.assign(rows, STUDENTS, extra=10), tmp_path)
    sheet = tmp_path / "asha.xlsx"
    rated = v.read_sheet(sheet)
    rated[0] = answer(rated[0], "Y")
    v.write_sheet(sheet, "asha", rated)

    empty = v.Assignment(single={s: [] for s in STUDENTS})     # e.g. after --reset with a different pick
    stats = v.build_sheets(rows, empty, tmp_path)
    after = v.read_sheet(sheet)
    assert [r["source_id"] for r in after] == [rated[0]["source_id"]]
    assert after[0]["notes"].startswith("NO LONGER ASSIGNED") and after[0]["Q1_degraded_same_task"] == "Y"
    assert stats["asha"]["orphaned"] == 1 and stats["piush"]["rows"] == 0


def test_text_starting_with_equals_stays_text(tmp_path):
    row = make_rows(1)[0] | {"degraded_prompt": "=SUM(A1:A3) what does this do\x07"}
    path = tmp_path / "x.xlsx"
    v.write_sheet(path, "x", [row])
    assert v.read_sheet(path)[0]["degraded_prompt"] == "=SUM(A1:A3) what does this do"
    from openpyxl import load_workbook
    ws = load_workbook(path)["ratings"]
    col = v.SHEET_COLS.index("degraded_prompt") + 1
    assert ws.cell(row=2, column=col).data_type == "s"              # stored as text, not a formula


def _sheets_with_overlap(answers_by_student):
    """One overlap record rated by every student with the given answer for all questions."""
    base = make_rows(1)[0]
    return {s: [answer(base, a)] for s, a in answers_by_student.items()}


def test_resolve_majority_vote_and_lab_priority():
    sheets = _sheets_with_overlap({"asha": "Y", "piush": "Y", "rahul": "N"})
    final = v.resolve(sheets)
    (res,) = final.values()
    assert res["validation_accept"] == "True" and res["validated_by"] == "asha+piush+rahul"

    lab_row = answer(make_rows(1)[0] | {"source_id": "lab-1"}, "N")
    final = v.resolve({**sheets, v.LAB_SHEET: [lab_row]})
    assert final["lab-1"]["validated_by"] == v.LAB_SHEET and final["lab-1"]["validation_accept"] == "False"


def test_two_way_tie_stays_unresolved():
    sheets = _sheets_with_overlap({"asha": "Y", "piush": "N"})
    sheets["rahul"] = []
    assert v.resolve(sheets) == {}


def test_agreement_and_report(tmp_path):
    rows = [answer(r) for r in make_rows(4)]
    sheets = {s: [dict(r) for r in rows] for s in STUDENTS}
    sheets["rahul"][0] = answer(rows[0], "N")
    n, stats = v.agreement(sheets)
    assert n == len(rows)
    kappa, raw = stats["Q1_degraded_same_task"]
    assert raw == pytest.approx((len(rows) - 1) / len(rows))
    text = v.report_text(sheets)
    assert "Fleiss" in text and f"Validated records: **{len(rows)}**" in text


def test_invalid_answer_is_reported(tmp_path):
    row = answer(make_rows(1)[0]) | {"Q1_degraded_same_task": "maybe"}
    v.write_sheet(tmp_path / "asha.xlsx", "asha", [row])
    with pytest.raises(SystemExit, match="not Y or N"):
        v.load_all(tmp_path)
