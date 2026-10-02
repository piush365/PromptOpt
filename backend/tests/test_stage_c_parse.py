"""Parser that turns the dataset's optimized prompts into IR fields (Stage C targets)."""
import pytest

from app.stage_c.parse import constraint_cues, parse_optimized, split_sentences


@pytest.mark.parametrize("text, task, fmt, cons", [
    # later sentences: format vs constraint vs task
    ("Write an SQL query to find employees who joined in the last 5 years. Output only the query in a code block.",
     "Write an SQL query to find employees who joined in the last 5 years.",
     "Output only the query in a code block.", []),
    ("Answer only from the provided text: why is ext3 better than ext2? Respond in one sentence.",
     "Why is ext3 better than ext2?", None, ["Answer only from the provided text.", "Respond in one sentence."]),
    # a format phrase is cut out of the first sentence
    ("Summarize the causes of civil war from the provided text in 4 bullet points, covering definition and origin.",
     "Summarize the causes of civil war from the provided text, covering definition and origin.",
     "Use 4 bullet points.", []),
    # a trailing format clause becomes its own sentence
    ('Extract the date of the battle from the provided text and output it as JSON: {"date": "..."}.',
     "Extract the date of the battle from the provided text.", 'Output it as JSON: {"date": "..."}.', []),
    # a plain source reference stays in the task; only "only/solely" grounding is a constraint
    ("From the provided text, extract the names of people with eponymous laws. Output a JSON array of names.",
     "From the provided text, extract the names of people with eponymous laws.", "Output a JSON array of names.", []),
    # length before grounding, so the task never ends up being a constraint
    ("Answer the question using only the provided text, limiting the response to 15 words or fewer.",
     "Answer the question.", None,
     ["Limit the response to 15 words or fewer.", "Answer using only the provided text."]),
    # a lone grounding sentence first is a constraint, not the task
    ("Answer only from the provided text. How many siblings does she have?",
     "How many siblings does she have?", None, ["Answer only from the provided text."]),
    # a follow-up sentence describing the format's elements is format too
    ("For each team, indicate its league. Output a JSON array. Each element has \"team\" and \"league\" fields.",
     "For each team, indicate its league.", 'Output a JSON array. Each element has "team" and "league" fields.', []),
])
def test_parse_fields(text, task, fmt, cons):
    p = parse_optimized(text)
    assert (p.task, p.output_format, p.constraints) == (task, fmt, cons)


def test_data_block_is_context_and_no_sentence_is_lost():
    text = "Classify each item as fruit or vegetable. Output one label per line. Use lowercase.\n\nItems: apple, leek"
    p = parse_optimized(text)
    assert p.context == "Items: apple, leek"
    kept = " ".join([p.task, p.output_format or "", *p.constraints])
    for s in split_sentences(text.split("\n\n")[0]):
        assert s in kept


def test_split_sentences_keeps_abbreviations_and_numbers():
    assert split_sentences("Use e.g. Python 3.12 here. Then stop.") == ["Use e.g. Python 3.12 here.", "Then stop."]


def test_constraint_cues():
    assert constraint_cues("Answer using only the provided text.") == {"grounding"}
    assert constraint_cues("Extract the year from the provided text.") == set()
    assert constraint_cues("Write a Python function.", ignore_language=True) == set()
    assert "length" in constraint_cues("Keep it under 50 words.")


def test_layouts_a02_misses_are_format():
    p = parse_optimized("Assign the correct season to each item. Output each item followed by its season on a "
                        "separate line.")
    assert p.output_format == "Output each item followed by its season on a separate line."
