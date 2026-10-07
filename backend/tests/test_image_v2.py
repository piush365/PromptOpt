"""Image optimizer v2: only non-conflicting additions, everything else a suggestion. Uses the dev prompts only (the
held-out set is for the one evaluation run)."""
import json
import re

import pytest

from app.image.evaluate import PROMPTS
from app.image.render import DEFAULTS as V1_DEFAULTS
from app.image.v2 import (SUGGESTIONS, avoid_options, i13_style_first, i14_safe_negatives, optimize_image_v2,
                          parse_accepted, render_all_v2, render_v2)

DEV = [p["prompt"] for p in json.loads(PROMPTS.read_text())]
EXTRA = ["a fox in a forest, watercolor", "a beach with no people and a blue sky",
         "a futuristic city without cars and people for my phone wallpaper", "a logo for a bakery called Sunrise"]
_WORDS = re.compile(r"[\w'-]+")
SCAFFOLD = {"can", "could", "would", "will", "you", "please", "pls", "plz", "make", "me", "create", "generate",
            "give", "show", "a", "an", "of", "picture", "image", "pic", "img", "hey", "hi", "hello", "just", "i",
            "want", "need", "some", "produce", "get"}
NEGATIONS = {"no", "without", "avoid", "exclude", "excluding", "don't", "not", "include", "never", "and", "or", "with"}
# the v1 default keywords/sentences that hurt stylised requests: v2 must never insert them on its own
V1_ONLY = [kw for a in ("subject_detail", "lighting", "palette", "mood", "style", "composition", "background")
           for kw in (V1_DEFAULTS[a][1],)]


def words(text: str) -> set[str]:
    return {w.lower() for w in _WORDS.findall(text)}


@pytest.mark.parametrize("prompt", DEV + EXTRA)
def test_no_user_word_lost_and_no_default_attributes_inserted(prompt):
    o = optimize_image_v2(prompt)
    r = render_all_v2(o.ir)
    assert words(prompt) - words(o.ir.subject) <= SCAFFOLD
    for t in ("dalle", "nano_banana"):
        assert words(o.ir.subject) <= words(r[t]["prompt"])
    sd = r["stable_diffusion"]
    assert words(o.ir.subject_positive or o.ir.subject) <= words(sd["prompt"])
    assert words(o.ir.subject) - NEGATIONS <= words(sd["prompt"]) | words(sd["negative_prompt"])
    for t, rendered in r.items():
        for kw in V1_ONLY:
            assert kw not in rendered["prompt"], (t, kw)
    assert words(sd["prompt"]) <= words(o.ir.subject)              # SD: nothing is added to the user's words
    assert sd["negative_prompt"] == ", ".join(o.ir.avoid_user)      # only the user's own avoid list
    assert o.ir.quality is None and o.ir.avoid_default == ()


@pytest.mark.parametrize("prompt", DEV + EXTRA)
def test_suggestions_only_for_missing_attributes(prompt):
    o = optimize_image_v2(prompt)
    offered = {s.attribute for s in o.suggestions}
    # stated attributes are not offered again; "avoid" is the exception: the usual negatives are offered on top of
    # the user's own "no ..." list
    assert not offered & set(o.ir.present) - {"subject_detail", "avoid"}
    for s in o.suggestions:
        assert (s.options == SUGGESTIONS.get(s.attribute, []) or s.attribute == "avoid") and (s.options or s.hint)
        if s.attribute == "avoid":
            assert set(s.options) <= set(SUGGESTIONS["avoid"])


def test_style_first_reorders_only_the_users_chunks():
    o = optimize_image_v2("a fox in a forest, watercolor")
    assert o.ir.style_first == ("watercolor",)
    assert render_v2(o.ir, "stable_diffusion")["prompt"] == "Watercolor, a fox in a forest"
    assert render_v2(o.ir, "dalle")["prompt"].startswith("A fox in a forest, watercolor.")
    already_first = optimize_image_v2("watercolor painting of a fox")
    assert already_first.ir.style_first == () and "I13_STYLE_FIRST" not in already_first.rules_applied
    assert i13_style_first(already_first.ir) == already_first.ir


@pytest.mark.parametrize("prompt, dropped", [
    ("a logo for a bakery called Sunrise", {"text", "logos"}),
    ("a poster for a music festival", {"text"}),
    ("a dog running, motion blur", {"blurry details"}),
    ("a friendly octopus", {"extra limbs"}),
    ("a red apple", set()),
])
def test_conflict_filter_for_negatives(prompt, dropped):
    """I14's filter (used for the draft and for the avoid suggestions) drops what the request needs."""
    ir = i14_safe_negatives(optimize_image_v2(prompt).ir)
    assert not set(ir.avoid_default) & dropped and {"watermarks"} <= set(ir.avoid_default)


def test_avoid_suggestions_respect_the_request():
    assert "text and watermarks" not in avoid_options(optimize_image_v2("a logo for a bakery called Sunrise").ir)
    assert "blurry details" not in avoid_options(optimize_image_v2("a dog running, motion blur").ir)
    assert avoid_options(optimize_image_v2("a red apple").ir) == SUGGESTIONS["avoid"]
    o = optimize_image_v2("a red apple", ["avoid:text and watermarks"])
    assert render_v2(o.ir, "stable_diffusion")["negative_prompt"] == "text and watermarks"
    assert "Do not include text and watermarks." in render_v2(o.ir, "dalle")["prompt"]
    assert "text and watermarks" not in render_v2(o.ir, "stable_diffusion")["prompt"]
    assert avoid_options(o.ir) == ["distorted anatomy", "blurry details"]


def test_aspect_ratio_only_when_implied():
    assert optimize_image_v2("a dog").ir.aspect_ratio is None
    assert render_v2(optimize_image_v2("a dog").ir, "dalle")["params"] == {"size": "1024x1024"}
    assert "Aspect ratio" not in render_v2(optimize_image_v2("a dog").ir, "nano_banana")["prompt"]
    o = optimize_image_v2("a mountain lake at sunrise, 16:9")
    assert o.ir.aspect_ratio == "16:9" and render_v2(o.ir, "stable_diffusion")["params"]["width"] == 680


def test_accepted_suggestions_are_added_after_the_users_words_and_marked():
    o = optimize_image_v2("a dog", ["lighting:soft daylight", "aspect_ratio:16:9", "style:watercolor painting"])
    assert o.ir.accepted == (("lighting", "soft daylight"), ("style", "watercolor painting"))
    assert o.ir.aspect_ratio == "16:9" and "I16_ACCEPTED_SUGGESTIONS" in o.rules_applied
    sd = render_v2(o.ir, "stable_diffusion")["prompt"]
    assert sd.startswith("A dog, ") and "soft daylight" in sd and "watercolor painting" in sd
    assert "Lighting: soft daylight." in render_v2(o.ir, "dalle")["prompt"]
    assert {s.attribute for s in o.suggestions}.isdisjoint({"lighting", "style", "aspect_ratio"})
    with pytest.raises(ValueError):
        parse_accepted(["lighting:anything I like"])          # only offered values
    with pytest.raises(ValueError):
        parse_accepted(["colour:red"])


# ---------------------------------------------------------------- blind test report (the team's CSV)
def _blind_csv(path, rows):
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "prompt", "target_model", "expected_behaviour", "author"])
        w.writerows(rows)
    return path


def test_blind_loader_normalizes_targets_and_skips_blank_rows(tmp_path):
    from app.image.evaluate import load_blind
    p = _blind_csv(tmp_path / "b.csv", [["blind-img-01", "", "", "", ""],
                                        ["blind-img-02", " a pixel art spaceship ", "Stable Diffusion", "keep it", "AB"],
                                        ["blind-img-03", "a cat", "DALL-E", "", ""]])
    assert [(i["id"], i["prompt"], i["target"]) for i in load_blind(p)] == [
        ("blind-img-02", "a pixel art spaceship", "stable_diffusion"), ("blind-img-03", "a cat", "dalle")]


def test_blind_loader_rejects_unknown_target(tmp_path):
    from app.image.evaluate import load_blind
    with pytest.raises(SystemExit, match="blind-img-01"):
        load_blind(_blind_csv(tmp_path / "b.csv", [["blind-img-01", "a cat", "midjourney", "", ""]]))


def test_blind_report_shows_the_apps_v2_prompt_not_v1_defaults():
    from app.image.evaluate import blind_report, run_blind
    items = [{"id": "blind-img-01", "prompt": "a watercolor fox", "target": "stable_diffusion", "expected": "keep style"}]
    text = blind_report(run_blind(items))
    row = next(line for line in text.splitlines() if line.startswith("| blind-img-01"))
    prompt_cell = row.split(" | ")[4].lower()
    assert "watercolor" in prompt_cell
    assert not any(keyword in prompt_cell for _, keyword in V1_DEFAULTS.values())
