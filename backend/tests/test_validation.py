"""Dataset validation tooling: assignment, sheets, Fleiss' Kappa, merge."""
import math

import pytest

from app import validation as v

CATS = ["closed_qa", "information_extraction", "classification", "summarization", "coding"]
STUDENTS = ["asha", "piush", "rahul"]


def make_rows(n_per_cat: int, start: int = 0) -> list[dict[str, str]]:
    rows = []
    for c in CATS:
        for i in range(start, start + n_per_cat):
            split = "benchmark" if i < 10 else ("test" if i < 50 else "train")
            rows.append({"id": f"{c}-{i}", "source_id": f"src-{c}-{i}", "category": c, "split": split,
                         "original_instruction": f"orig {c} {i}", "context": "", "degraded_prompt": f"deg {c} {i}",
                         "optimized_prompt": f"opt {c} {i}"})
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


def test_assignment_covers_every_record_exactly_once():
    rows = make_rows(100)
    a = v.assign(rows, STUDENTS)
    groups = [a.lab, a.overlap, *a.single.values()]
    flat = [sid for g in groups for sid in g]
    assert sorted(flat) == sorted(r["source_id"] for r in rows)
    assert len(a.lab) == 20
    cat = {r["source_id"]: r for r in rows}
    assert all(sum(cat[s]["category"] == c for s in a.lab) == 4 for c in CATS)
    assert all(cat[s]["split"] == "benchmark" for s in a.lab)
    assert 10 <= len(a.overlap) <= 50                               # ~6% of 480
    sizes = [len(ids) for ids in a.single.values()]
    assert max(sizes) - min(sizes) < 60


def test_assignment_is_stable_when_dataset_grows():
    small, big = make_rows(60), make_rows(60) + make_rows(40, start=60)
    a, b = v.assign(small, STUDENTS), v.assign(big, STUDENTS)
    assert a.lab == b.lab
    assert set(a.overlap) <= set(b.overlap)
    for s in STUDENTS:
        assert set(a.single[s]) <= set(b.single[s])


def test_assignment_rejects_bad_input():
    with pytest.raises(ValueError):
        v.assign(make_rows(20), ["a", "a", "b"])
    rows = make_rows(20)
    rows[1]["source_id"] = rows[0]["source_id"]
    with pytest.raises(ValueError):
        v.assign(rows, STUDENTS)


def test_sheets_keep_answers_and_reset_regenerated_pairs(tmp_path):
    rows = make_rows(30)
    v.build_sheets(rows, v.assign(rows, STUDENTS), tmp_path)
    sheet = tmp_path / "asha.xlsx"
    rated = v.read_sheet(sheet)
    rated[0] = answer(rated[0], "Y")
    rated[1] = answer(rated[1], "N") | {"notes": "drifted"}
    v.write_sheet(sheet, "asha", rated)
    kept_id, regen_id = rated[0]["source_id"], rated[1]["source_id"]

    grown = make_rows(30) + make_rows(20, start=30)
    for r in grown:
        if r["source_id"] == regen_id:
            r["optimized_prompt"] = "a regenerated optimized prompt"
    stats = v.build_sheets(grown, v.assign(grown, STUDENTS), tmp_path)

    after = {r["source_id"]: r for r in v.read_sheet(sheet)}
    assert all(after[kept_id][q] == "Y" for q in v.QCOLS)
    assert all(after[regen_id][q] == "" for q in v.QCOLS)
    assert after[regen_id]["notes"].startswith("REGENERATED") and "drifted" in after[regen_id]["notes"]
    assert stats["asha"]["kept"] >= 1 and stats["asha"]["reset"] == 1 and stats["asha"]["new"] > 0


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
