"""Static reference checks (no model, no code execution)."""
import pytest

from app import reference_check as rc


@pytest.mark.parametrize("instruction, reference, issue", [
    ("Write a Python script that checks if a string is a palindrome.", "The given string is a palindrome.", "not_code"),
    ("Write a function in Python that concatenates two strings.",
     "def my_concat(a, b)\n    return a + ' ' + b", "does_not_parse"),
    ("Write a code in JavaScript to make all letters upper case.",
     "def makeUpperCase(s):\n    return s.upper()", "wrong_language"),
    ("Design a function in PHP that checks two strings.", "function check(a, b) {\n  return a == b;\n}\nconsole.log(check(1, 2));",
     "wrong_language"),
    ("Create a function called addNumbers in Python.", "def add(a, b):\n    return a + b", "missing_name"),
])
def test_suspects_are_found(instruction, reference, issue):
    assert any(i.startswith(issue) for i in rc.check(instruction, reference))


@pytest.mark.parametrize("instruction, reference", [
    ("Write a SQL query to select all customers.", "SELECT * FROM customers;"),
    ("Write a script for swapping two variables in Ruby.", "x, y = y, x"),
    ("Create a bash script to create a folder.", "#!/bin/bash\nfolder=x\nmkdir $folder"),
    ("Using a loop, output the even numbers.", "for i in range(2, n+1, 2):\n    print(i)\n// Output: 2,4,6"),
    ("How many lines of code are in the given snippet?", "4 lines of code."),
    ("Convert the following SQL query to Pandas.", "df.groupby('Country').size()"),
    ("Create a regex pattern to match an 'a'.", "/a/"),
    ("Write a JavaScript function to add two numbers.", "function add(a, b) {\n  return a + b;\n}"),
    ("Write an HTML page with a heading.", "<html><body><h1>Hi</h1><script>let x = 1;</script></body></html>"),
    ("Create a Python function.", " def f():\n    return 1"),                     # non-breaking spaces
])
def test_valid_references_are_not_flagged(instruction, reference):
    assert rc.check(instruction, reference) == []


def test_scan_only_coding_rows_and_wrong_reference_file(tmp_path):
    rows = [{"source_id": "c1", "split": "test", "category": "coding", "original_instruction": "Write a Python script.",
             "reference_response": "It works."},
            {"source_id": "d1", "split": "test", "category": "closed_qa", "original_instruction": "Write code?",
             "reference_response": "No."}]
    assert [s["source_id"] for s in rc.scan(rows)] == ["c1"]
    path = tmp_path / "wrong.csv"
    path.write_text("source_id,reason,found_by\ncodealpaca-1,prints unequal sums,judge rationale\n")
    assert rc.load_wrong_references(path) == {"codealpaca-1": "prints unequal sums"}
    assert rc.load_wrong_references(tmp_path / "missing.csv") == {}


@pytest.mark.parametrize("instruction, reference", [
    # false positives of the first version on the test split (the checker was fixed; no model was run)
    ("Write a C# method that returns the character count.",
     "public static int CharCount(string str)\n{\n    int count = 0;\n    foreach (char c in str)\n    {\n"
     "        count++;\n    }\n    return count;\n}"),
    ("Write a LINQ query in C# to select customers from the USA.",
     'var r = from customer in customers\n        where customer.Country == "USA"\n        select customer;'),
    ("Design a function in Python to delete duplicates from a list.",
     "def f(xs):\n    return list(set(xs))\n\nprint(f([1, 1]))\n\nOutput: \n[1]"),
])
def test_csharp_idioms_and_output_blocks_are_not_flagged(instruction, reference):
    assert rc.check(instruction, reference) == []
