"""Spelling suggestions: suggestions only, ranked for typing slips, and nothing technical or quoted is flagged."""
import pytest

from app import spelling

pytestmark = pytest.mark.skipif(not spelling.available(), reason="pyspellchecker not installed")


def words(text, context=None):
    return {t["word"]: t["suggestions"] for t in spelling.suggest(text, context)}


def test_the_reported_prompt():
    text = "frm the list tell me prog lang or animal panda pythom java sanke bunny"
    s = words(text)
    assert s["frm"][0] == "from" and s["pythom"][0] == "python" and s["sanke"][0] == "snake"
    assert set(s) == {"frm", "pythom", "sanke"}                          # "prog", "lang", "bunny" are words
    typos = spelling.suggest(text)
    assert all(text[t["start"]:t["end"]] == t["word"] for t in typos)    # offsets point at the typed word


def test_swapped_letters_rank_first():
    assert words("teh cat")["teh"][0] == "the"
    assert words("a sanke")["sanke"][0] == "snake"                       # not "sake", although "sake" is frequent


def test_never_flagged():
    assert words("parse json with numpy, then call the api over a url and write sql") == {}
    assert words("fix my_func in `utlis.py` and see \"teh\" at https://exmaple.com or ravi@exmaple.com") == {}
    assert words("summarise the colour of the centre") == {}             # British spelling
    assert words("ask Deshmukh about the NASDQ figures") == {}           # a name mid-sentence, an acronym
    assert words("which company bought hackpad", "Hackpad was acquired by Dropbox.") == {}   # word from the text


def test_capitalized_first_word_keeps_its_case():
    assert words("Recieve the file")["Recieve"][0] == "Receive"


def test_apply_and_no_dictionary(monkeypatch):
    assert spelling.apply("frm teh list", [(0, 3, "from"), (4, 7, "the")]) == "from the list"
    monkeypatch.setattr(spelling, "_checker", lambda: None)
    assert spelling.suggest("frm teh list") == [] and not spelling.available()
