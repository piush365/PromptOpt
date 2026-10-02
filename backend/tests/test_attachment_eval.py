"""Blind attachment CSV loading (the team's file)."""
import csv

import pytest

from app.attachment_eval import load_blind

HEADER = ["id", "prompt", "attachment_type", "attachment_name", "category", "expected_behaviour", "author"]


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    return path


def test_blank_rows_are_skipped_and_defaults_applied(tmp_path):
    p = write(tmp_path / "b.csv", [["blind-01", "", "", "", "", "", ""],
                                   ["blind-02", " sum column B ", "Spreadsheet", "", "", "use the sheet", "AB"]])
    assert load_blind(p) == [{"id": "blind-02", "prompt": "sum column B", "type": "spreadsheet", "name": None,
                              "category": "auto", "expected": "use the sheet", "author": "AB"}]


@pytest.mark.parametrize("kind, cat", [("xlsx", "auto"), ("pdf", "math")])
def test_bad_values_stop_with_a_message(tmp_path, kind, cat):
    p = write(tmp_path / "b.csv", [["blind-01", "a prompt", kind, "", cat, "", ""]])
    with pytest.raises(SystemExit, match="blind-01"):
        load_blind(p)
