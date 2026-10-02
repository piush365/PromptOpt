"""Stage C routing contract: locked fields, validation with the Stage A detectors, fallback to Stage B."""
import json

import pytest

from app.stage_b.ir import Attachment
from app.stage_b.optimizer import RULE_CODES, optimize
from app.stage_c.contract import (CATEGORIES, apply_stage_c, category_decision, c_only_input, model_input, natural_unresolved,
                                  to_messages, validate)
from tests.test_stage_b import feats


def routed(text="which season goes with flowers, snowflakes", category="classification", confidence=0.3):
    f = feats(text, category, confidence)
    return f, optimize(text, f)


def fake(answer):
    calls = []

    def generate(messages):
        calls.append(messages)
        return answer if isinstance(answer, str) else json.dumps(answer)
    generate.calls = calls
    return generate


def test_unresolved_category_asks_for_format_constraints_and_category():
    f, out = routed()
    assert out.needs_stage_c and natural_unresolved(out) == ["output_format", "constraints", "category"]
    inp = model_input("p", f, out.ir, natural_unresolved(out))
    assert inp["ir"]["output_format"] is None and inp["ir"]["category"] is None
    assert inp["ir"]["task"] == out.ir.task                       # locked field shown with Stage B's value


def test_accepted_answer_fills_only_the_requested_fields():
    f, out = routed()
    gen = fake({"output_format": "Output each item followed by its season on a separate line.",
                "constraints": [], "category": "classification"})
    res = apply_stage_c("p", f, out, gen)
    assert res.used and res.accepted and not res.fallback
    assert res.ir.output_format.startswith("Output each item") and res.ir.category == "classification"
    assert res.ir.category_source == "stage_c" and "task category" not in res.ir.unresolved
    assert res.ir.task == out.ir.task                             # locked
    assert json.loads(gen.calls[0][1]["content"])["unresolved"] == ["output_format", "constraints", "category"]


@pytest.mark.parametrize("answer, error", [
    ("not json", "not a JSON object"),
    ({"output_format": None, "constraints": []}, "keys"),
    ({"output_format": "Be nice.", "constraints": [], "category": "coding"}, "states no format"),
    ({"output_format": None, "constraints": "short", "category": "coding"}, "not a list"),
    ({"output_format": None, "constraints": [], "category": "other"}, "unknown"),
    ({"output_format": None, "constraints": [], "category": "coding", "task": "x y"}, "keys"),
])
def test_invalid_answers_fall_back_to_stage_b(answer, error):
    f, out = routed()
    res = apply_stage_c("p", f, out, fake(answer))
    assert res.fallback and res.ir == out.ir
    assert any(error in e for e in res.errors)


def test_task_with_a_dangling_reference_is_rejected():
    assert validate('{"task": "Summarize this."}', ["task"], has_context=False)[1]
    assert validate('{"task": "Summarize this."}', ["task"], has_context=True) == ({"task": "Summarize this."}, [])
    assert validate('```json\n{"task": "Explain recursion simply."}\n```', ["task"], False)[0]


def test_ambiguous_reference_is_resolved_by_a_task():
    text = "summarize this"
    f = feats(text, "summarization")
    out = optimize(text, f)
    assert natural_unresolved(out) == ["task"]
    res = apply_stage_c(text, f, out, fake({"task": "Summarize the text the user will paste below."}))
    assert res.accepted and not any(u.startswith("ambiguous") for u in res.ir.unresolved)


def test_not_routed_means_not_called():
    text = "write a python function that reverses a string"
    f = feats(text, "coding")
    gen = fake("{}")
    res = apply_stage_c(text, f, optimize(text, f), gen)
    assert not res.used and not gen.calls


def test_forced_fields_and_c_only_input():
    text = "write a python function that reverses a string"
    f = feats(text, "coding")
    out = optimize(text, f)
    res = apply_stage_c(text, f, out, fake({"task": "Write a Python function that reverses a string.",
                                            "output_format": "Return only the code in a code block.",
                                            "constraints": ["Use Python."]}), fields=["task", "output_format",
                                                                                     "constraints"])
    assert res.accepted and res.ir.constraints == ("Use Python.",)
    bare = optimize(text, f, disabled=frozenset(RULE_CODES))
    inp = c_only_input(text, f, bare.ir.model_copy(update={"requirements": ("x",)}))
    assert inp["ir"]["requirements"] == [] and inp["unresolved"] == ["task", "output_format", "constraints"]


def test_messages_match_training_format():
    msgs = to_messages({"a": 1}, {"task": "t"})
    assert [m["role"] for m in msgs] == ["system", "user", "assistant"] and set(CATEGORIES) == {
        "closed_qa", "information_extraction", "classification", "summarization", "coding"}


def test_attachment_is_passed_to_stage_c():
    text = "describe what is happening in the picture"
    f = feats(text, "coding", 0.35)
    out = optimize(text, f, attachment=Attachment(type="image"))
    assert out.needs_stage_c
    assert model_input(text, f, out.ir, natural_unresolved(out))["attachment"] == "image"


# ---------------------------------------------------------------- category policy
def scored(text, scores):
    f = feats(text, max(scores, key=scores.get), max(scores.values()))
    return f.model_copy(update={"category_scores": scores, "confidence": max(scores.values())})


@pytest.mark.parametrize("scores, guess, status", [
    ({"coding": 0.45, "summarization": 0.35, "closed_qa": 0.2}, "summarization", "accepted"),   # Stage A's 2nd
    ({"coding": 0.45, "summarization": 0.35, "closed_qa": 0.2}, "coding", "accepted"),          # Stage A's 1st
    ({"coding": 0.45, "summarization": 0.35, "closed_qa": 0.2}, "closed_qa", "uncertain"),      # 3rd, conf >= 0.3
    ({"coding": 0.28, "summarization": 0.27, "closed_qa": 0.25, "classification": 0.2}, "classification",
     "accepted"),                                                                                 # conf < 0.3
])
def test_category_decision(scores, guess, status):
    assert category_decision(guess, scored("x", scores)) == status


def test_uncertain_category_stays_unresolved_but_other_fields_apply():
    text = "which season goes with flowers, snowflakes"
    f = scored(text, {"coding": 0.45, "summarization": 0.35, "closed_qa": 0.2})
    out = optimize(text, f)
    assert out.needs_stage_c
    res = apply_stage_c(text, f, out, fake({"output_format": "Output one label per line.", "constraints": [],
                                            "category": "classification"}))
    assert res.accepted and res.category_status == "uncertain" and res.category_guess == "classification"
    assert "task category" in res.ir.unresolved and res.ir.category == out.ir.category
    assert res.ir.category_source == "stage_a" and res.ir.output_format == "Output one label per line."


def test_accepted_category_resolves_it():
    text = "which season goes with flowers, snowflakes"
    f = scored(text, {"coding": 0.45, "classification": 0.35, "closed_qa": 0.2})
    res = apply_stage_c(text, f, optimize(text, f), fake({"output_format": None, "constraints": [],
                                                          "category": "classification"}))
    assert res.category_status == "accepted" and res.ir.category == "classification"
    assert "task category" not in res.ir.unresolved
