"""Dataset v1 -> v1.1 repair: payload extraction, drop detection, deterministic repair, subject regeneration."""
import json
from types import SimpleNamespace

import pytest

from app import dataset_repair as r


def row(instruction, optimized, degraded="deg", category="classification", context="", **kw):
    return {"id": kw.get("id", "PO-X-1"), "split": kw.get("split", "train"), "category": category,
            "original_instruction": instruction, "degraded_prompt": degraded, "optimized_prompt": optimized,
            "context": context, "reference_response": "", "degraded_word_count": "1", "optimized_word_count": "1"}


# ---- extract_payload

@pytest.mark.parametrize("instruction, kind, text", [
    ("Identify which instrument is string or percussion: Sheker, Taishogoto", "items", "Sheker, Taishogoto"),
    # labels after the colon, then the items in their own sentence
    ("Categorize each as either: 'Mandatory', 'Good to have'. Passport, Cash, Book", "items", "Passport, Cash, Book"),
    # a colon inside an item does not cut the list; the question mark comes first
    ('Which were nominated? "Avatar: The Way of Water", "Navalny"', "items", '"Avatar: The Way of Water", "Navalny"'),
    # the list continues on the next line
    ("Which grapes make white wine: Chardonnay, Riesling,\nMerlot, Syrah.", "items", "Chardonnay, Riesling, Merlot, Syrah"),
    ("classify as mammals vs reptiles:\ngoat\nsnake", "items", "goat\nsnake"),
    ("Classify the cities by country.\nSanaa, Windhoek", "lines", "Sanaa, Windhoek"),
    ("Which characters belong to DC or Marvel Universe? Ghost Rider, Atomic Skull", "items",
     "Ghost Rider, Atomic Skull"),
    ("Is this a fruit or a vegetable? tomato", "after_question", "tomato"),   # one word: the fallback
])
def test_extract_payload_classification(instruction, kind, text):
    p = r.extract_payload(instruction, "classification")
    assert (p.kind, p.text) == (kind, text)


def test_extract_payload_other_categories_only_lines_and_expressions():
    assert r.extract_payload("Classify the type of the expression 5 + 4 * 3 - 7", "coding") == \
        r.Payload("expression", "5 + 4 * 3 - 7")
    code = r.extract_payload("What is the output of this Java code?\nint x = 7;\nint z = x % 3;", "coding")
    assert code == r.Payload("lines", "int x = 7;\nint z = x % 3;")
    # questions and format clauses are not data outside classification
    assert r.extract_payload("Where was Jerry Garcia born, how many fingers did he have, and where did he study?",
                             "closed_qa") is None
    assert r.extract_payload("How much did it cost? Express as an absolute difference.", "closed_qa") is None
    # a date is not an arithmetic expression
    assert r.extract_payload("Get sales between 01-04-2021 and 15-04-2021", "coding") is None


def test_format_lines_are_not_data():
    assert r.extract_payload("Extract the people in this format:\n\n[Name]: [Significance]",
                             "information_extraction") is None
    assert r.extract_payload("List the poems.\n\nAnd sort the list chronologically", "summarization") is None
    # a bracketed list of numbers is data, not a placeholder
    assert r.extract_payload("How would you add this list to JSON?\n[1,2,3]", "coding").text == "[1,2,3]"


# ---- dropped / repair_row

def test_dropped_classification_needs_every_item():
    p = r.Payload("items", "Ratchet, Hasapi")
    # "Ratchet" survives only as the format example: Hasapi is still missing
    assert r.dropped(p, 'Classify each instrument. Example: "Ratchet: percussion".', "classification")
    assert not r.dropped(p, "Classify Ratchet and Hasapi.", "classification")
    # plural/singular and accents do not count as missing
    assert not r.dropped(r.Payload("items", "bacteriophages, Pokémon"), "bacteriophage or pokemon", "classification")


def test_dropped_degraded_allows_user_abbreviations():
    p = r.Payload("items", "Multi-factor Authentication, VPN, Shared Passwords, Anti-Malware Solution")
    assert not r.dropped(p, "label these: mfa, vpn, shared passwords, anti-malware", "classification", degraded=True)
    assert r.dropped(p, "label these as secure or not", "classification", degraded=True)


def test_repair_row_appends_items_to_both_prompts():
    res = r.repair_row(row("Divide these sneakers into Air Jordan and Air Max: Tokyo 96, Chicago",
                           'Classify each sneaker as "Air Jordan" or "Air Max". Output JSON.',
                           degraded="split these sneakers into air jordan or air max"))
    assert res.action == "repaired" and res.fixed_fields == ("degraded_prompt", "optimized_prompt")
    assert res.row["optimized_prompt"].endswith("Output JSON.\n\nItems: Tokyo 96, Chicago")
    assert res.row["degraded_prompt"] == "split these sneakers into air jordan or air max: Tokyo 96, Chicago"
    assert res.row["optimized_word_count"] == str(len(res.row["optimized_prompt"].split()))


def test_repair_row_code_and_expression_labels():
    res = r.repair_row(row("What is the output of this Java code?\nint x = 7;\nint z = x % 3;",
                           "Analyze the provided Java code snippet.", degraded="what does this java print\nint x = 7;"
                           "\nint z = x % 3;", category="coding"))
    assert res.fixed_fields == ("optimized_prompt",)
    assert res.row["optimized_prompt"].endswith("snippet.\n\nInput:\nint x = 7;\nint z = x % 3;")
    res = r.repair_row(row("Classify the type of the expression 5 + 4 * 3 - 7", "Classify the provided expression.",
                           degraded="what type is 5 + 4 * 3 - 7", category="coding"))
    assert res.row["optimized_prompt"].endswith("\n\nExpression: 5 + 4 * 3 - 7")


def test_repair_row_leaves_complete_rows_alone():
    src = row("Identify which is string or percussion: Tombak, Cizhonghlu",
              "Classify Tombak and Cizhonghlu as string or percussion.", degraded="tombak cizhonghlu string or drum?")
    res = r.repair_row(src)
    assert res.action == "ok" and res.row == src


@pytest.mark.parametrize("instruction, context, removed", [
    ("Tell me whether these numbers are odd or even", "", True),
    ("Classify these animals as either a reptile or an amphibian", "", True),
    ("Categorize each of these as either liquids or solids.", "", True),
    ("Write a C++ program using the following function.", "", True),
    ("Write a C++ program using the following function.", "int f() {}", False),   # the data is in the context
    ('Reverse this sentence: "I can do coding."', "", False),
    ("Write a function that checks if a given number is prime.", "", False),
])
def test_rows_without_source_data_are_removed(instruction, context, removed):
    cat = "classification" if "these" in instruction or "each of" in instruction else "coding"
    res = r.repair_row(row(instruction, "opt", category=cat, context=context))
    assert (res.action == "removed") is removed


# ---- subject drops

class FakeNLP:
    """spaCy stand-in: entities given as (text, label, token_start)."""
    def __init__(self, ents):
        self.ents = ents

    def __call__(self, text):
        return SimpleNamespace(ents=[SimpleNamespace(text=t, label_=lab, start=s) for t, lab, s in self.ents])


def test_lost_subjects_filters():
    nlp = FakeNLP([("Convert", "ORG", 0), ("Kenneth McAlpine", "PERSON", 5), ("Wikipedia", "ORG", 8),
                   ("USA", "GPE", 10), ("Albania", "GPE", 12)])
    ctx = "Kenneth McAlpine was born in Albania. USA."
    assert r.lost_subjects("...", "State his birthplace in Albanian history.", ctx, nlp) == ["Kenneth McAlpine"]
    # no context (classification): the context filter is off
    assert r.lost_subjects("...", "Classify.", "", FakeNLP([("Wikipedia", "ORG", 3)])) == ["Wikipedia"]
    assert r.lost_subjects("...", "the EPA-rated range", "", FakeNLP([("EPAX", "ORG", 3)])) == ["EPAX"]


def test_accept_edit():
    old = "Answer using only the provided text. State his birthplace."
    assert r.accept_edit(old, "Answer using only the provided text. State Kenneth McAlpine's birthplace.",
                         ["Kenneth McAlpine"])
    assert not r.accept_edit(old, "Answer using only the provided text. State the birthplace.", ["Kenneth McAlpine"])
    assert not r.accept_edit(old, "", ["Kenneth McAlpine"])
    assert not r.accept_edit(old, old + " Kenneth McAlpine" + " padding" * 20, ["Kenneth McAlpine"])


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def complete(self, model, messages, **kw):
        self.calls.append(json.loads(messages[1]["content"]))
        return SimpleNamespace(content=self.replies.pop(0))


def test_regenerate_batches_and_caches():
    cands = [{"id": f"id{i}", "original_instruction": "o", "optimized_prompt": "p", "subjects": ["X"]}
             for i in range(7)]
    reply1 = json.dumps({"items": [{"id": f"id{i}", "optimized_prompt": f"new {i}"} for i in range(4)]})
    llm = FakeLLM([reply1, "not json"])
    cache = {"id6": "done before"}
    calls = r.regenerate(cands, llm, cache, max_calls=10)
    assert calls == 2
    assert [len(c["items"]) for c in llm.calls] == [5, 1]            # id6 was cached: 6 rows -> 5 + 1
    assert cache["id0"] == "new 0" and cache["id4"] == ""             # id4 missing from the reply: tried, rejected
    assert "id5" not in cache                                         # unparseable reply: retried next run
    assert cache["id6"] == "done before"
    assert r.regenerate(cands, FakeLLM([]), cache, max_calls=0) == 0  # budget respected


def test_run_counts_and_applies_accepted_edits(tmp_path):
    rows = [row("Which is string or percussion: Sheker, Taishogoto", "Classify each listed instrument.", id="a"),
            row("Tell me whether these are countries or continents", "Classify each term.", id="b"),
            row("Given a text about Kenneth McAlpine, where was he born?", "State his birthplace.",
                category="closed_qa", context="Kenneth McAlpine was born in Kent.", id="c"),
            row("Given a text about Ada Lovelace, when was she born?", "State her birth year.",
                category="closed_qa", context="Ada Lovelace was born in 1815.", id="d", split="test")]
    nlp = FakeNLP([])
    nlp_for = {"c": [("Kenneth McAlpine", "PERSON", 4)], "d": [("Ada Lovelace", "PERSON", 4)]}

    class RowNLP:
        def __call__(self, text):
            key = "c" if "McAlpine" in text else "d" if "Lovelace" in text else None
            return FakeNLP(nlp_for.get(key, []))(text)

    cands = r.subject_candidates(rows, RowNLP())
    assert [c["id"] for c in cands] == ["d", "c"]                     # evaluation splits first
    cache = {"c": "State Kenneth McAlpine's birthplace.", "d": "State the birth year."}
    rep = r.run(rows, RowNLP(), cache)
    assert [x["id"] for x in rep.rows] == ["a", "c", "d"]
    assert rep.rows[0]["optimized_prompt"].endswith("Items: Sheker, Taishogoto")
    assert rep.rows[1]["optimized_prompt"] == "State Kenneth McAlpine's birthplace."
    assert rep.rows[2]["optimized_prompt"] == "State her birth year."    # rejected edit: unchanged
    assert rep.counts[("classification", "removed")] == 1
    assert rep.counts[("closed_qa", "regenerated")] == 1 and rep.counts[("closed_qa", "regen_rejected")] == 1
    assert {e["action"] for e in rep.log} == {"repaired", "removed", "regenerated"}

    r.write(rep, tmp_path)
    lines = (tmp_path / "train.jsonl").read_text().splitlines()
    assert [json.loads(x)["id"] for x in lines] == ["a", "c"]
    assert json.loads(lines[0])["output"].endswith("Items: Sheker, Taishogoto")
    assert (tmp_path / "test.jsonl").read_text().count("\n") == 1
    assert (tmp_path / "promptopt_dataset_v1_1.csv").exists() and (tmp_path / "repair_log.csv").exists()


@pytest.mark.parametrize("prompt, instruction, category, expected", [
    ("Name the director of Lost in Translation. Answer in 20 words. Items: Lost in Translation",
     "Who directed Lost in Translation?", "closed_qa", "Name the director of Lost in Translation. Answer in 20 words."),
    ("From the provided text, answer: who is he? Items: Who is Mariano Sánchez?",
     "Who is Mariano Sánchez?", "closed_qa", "From the provided text, answer: who is he?"),     # repeats the question
    ("Summarize the text. Items: carbon, nitrogen",
     "Summarize the text about carbon and nitrogen.", "summarization", "Summarize the text."),
    # data found nowhere else stays
    ("Explain the difference. Items: tomato, cucumber", "Explain the difference.", "closed_qa",
     "Explain the difference. Items: tomato, cucumber"),
    # classification keeps its item list
    ("Classify each item. Items: apple, carrot", "Classify: apple, carrot", "classification",
     "Classify each item. Items: apple, carrot"),
    ("Write a function. Return code only.", "Write a function.", "coding", "Write a function. Return code only."),
])
def test_strip_redundant_items(prompt, instruction, category, expected):
    assert r.strip_redundant_items(prompt, instruction, category) == expected
