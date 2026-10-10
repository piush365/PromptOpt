"""Stage B extensions (B16): app-only rules after the frozen ones. Off by default, so the frozen pipeline is unchanged."""
import pytest

from app.stage_a.classifier import KeywordClassifier
from app.stage_a.detector import FeatureDetector
from app.stage_b.optimizer import RULE_CODES, optimize

DET = FeatureDetector(classifier=KeywordClassifier(), use_spacy=False)


def run(prompt, category="classification", **kw):
    return optimize(prompt, DET.detect(prompt), category=category, extensions=True, **kw)


def test_the_reported_prompt_gets_labels_and_its_items_in_the_input():
    out = run("frm the list tell me prog lang or animal panda pythom java sanke bunny")
    assert 'Use only these labels: "prog lang", "animal".' in out.ir.requirements
    assert out.ir.context == "panda pythom java sanke bunny"              # no commas: kept as typed, not split
    assert out.ir.task == "Frm the list tell me prog lang or animal."
    assert "label set" not in out.ir.unresolved and out.rules_applied[-1] == "B16_LABELS_WIDER"


@pytest.mark.parametrize("prompt, labels, items", [
    ("say whether it is a city or a country paris, berlin", ("city", "country"), "paris, berlin"),
    ("tell me if each is a programming language or an animal: panda, python, java",
     ("programming language", "animal"), "panda, python, java"),
])
def test_labels_after_a_request_verb(prompt, labels, items):
    out = run(prompt)
    assert f'Use only these labels: "{labels[0]}", "{labels[1]}".' in out.ir.requirements
    assert out.ir.context == items


def test_glued_items_after_b06_labels_move_and_one_glued_word_is_undone():
    out = run("check which is a city or a country paris, france, berlin")
    assert 'Use only these labels: "city", "country".' in out.ir.requirements      # B06 alone: "country paris"
    assert out.ir.context == "paris, france, berlin" and out.ir.task == "Check which is a city or a country."
    out = run("which of these are flowers and which are european countries? roses, norway, and tulips")
    assert out.ir.context == "roses, norway, tulips"                                # "and" dropped from the last item


def test_moving_the_items_resolves_a_reference_to_them():
    det = FeatureDetector(classifier=KeywordClassifier())             # spaCy flags the bare "these"
    if det.nlp is None:
        pytest.skip("spaCy model not installed")
    prompt = "say whether these are fruits or vegetables tomato carrot apple"
    f = det.detect(prompt)
    frozen = optimize(prompt, f, category="classification")
    out = optimize(prompt, f, category="classification", extensions=True)
    assert any(u.startswith("ambiguous reference") for u in frozen.ir.unresolved)
    assert out.ir.context == "tomato carrot apple" and not out.needs_stage_c


@pytest.mark.parametrize("prompt", [
    "classify these teams epl or la liga: barcelona, tottenham",       # object noun before the labels: B06 / Stage C
    "tell me if these were originally board or computer games",       # first label would be 3 words
    "are these hockey or baseball teams red wings, padres, blues",     # several words glued on: unclear, left alone
    "classify the following animals",                                  # no labels anywhere
])
def test_does_not_guess(prompt):
    out = run(prompt)
    frozen = optimize(prompt, DET.detect(prompt), category="classification")
    assert out.optimized_text == frozen.optimized_text and "B16_LABELS_WIDER" not in out.rules_applied


def test_other_categories_and_default_are_untouched():
    prompt = "frm the list tell me prog lang or animal panda pythom java sanke bunny"
    assert "B16_LABELS_WIDER" not in run(prompt, category="coding").rules_applied
    f = DET.detect(prompt)
    assert "B16_LABELS_WIDER" not in optimize(prompt, f, category="classification").rules_applied   # off by default
    assert "B16_LABELS_WIDER" not in RULE_CODES                         # not part of the frozen rule list
    assert "B16_LABELS_WIDER" not in run(prompt, disabled={"B16_LABELS_WIDER"}).rules_applied
