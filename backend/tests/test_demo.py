"""Offline demo: `python -m app.demo`."""
import pytest

from app import demo
from app.stage_a.classifier import KeywordClassifier
from app.stage_a.detector import FeatureDetector

DET = FeatureDetector(classifier=KeywordClassifier(), use_spacy=False)


def test_report_shows_features_rules_and_stage_c():
    text, out = demo.explain("hey can you just summarize this article for me", DET)
    assert "STAGE A" in text and "category:" in text and "confidence" in text
    assert "'hey'" in text and "ambiguous refs:" in text and "missing format" in text
    for step in out.steps:                                   # every rule that fired, with before and after
        assert step["rule_code"] in text
        assert step["before"].splitlines()[0] in text and step["after"].splitlines()[0] in text
    assert "B01_REMOVE_FILLER" in out.rules_applied
    assert out.optimized_text in text.replace("\n    ", "\n")
    assert out.needs_stage_c and "would go to Stage C: yes (ambiguous reference" in text


def test_user_category_overrides_stage_a_and_target_renders():
    text, out = demo.explain("classify these as fruit or veg: tomato, apple", DET, category="classification",
                             target="claude")
    assert out.ir.category == "classification" and out.ir.category_source == "user"
    assert "chosen by the user" in text
    assert "RENDERED FOR CLAUDE" in text and "<task>" in text
    assert "would go to Stage C: no" in text


@pytest.mark.parametrize("target", demo.TARGETS)
def test_every_target_renders(target):
    text, _ = demo.explain("write a python function that reverses a list", DET, target=target)
    assert f"RENDERED FOR {target.upper()}" in text


def test_examples_cover_every_category():
    assert sorted(c for c, _ in demo.EXAMPLES) == sorted(
        ["closed_qa", "information_extraction", "classification", "summarization", "coding"])


def test_cli_examples_and_errors(monkeypatch, capsys):
    monkeypatch.setattr("app.stage_a.detector.FeatureDetector", lambda: DET)
    demo.main(["--examples", "--target", "gpt"])
    out = capsys.readouterr().out
    assert out.count("EXAMPLE:") == 5 and out.count("OPTIMIZED PROMPT") == 5 and "RENDERED FOR GPT" in out
    with pytest.raises(SystemExit):
        demo.main([])
    with pytest.raises(SystemExit):
        demo.main(["x", "--target", "llama"])
