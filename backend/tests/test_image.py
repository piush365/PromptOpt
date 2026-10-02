"""Image-generation mode: detectors, rules I01-I11, renderers; no user detail may be lost."""
import json
import re

import pytest

from app.image import attributes as att
from app.image.evaluate import PROMPTS
from app.image.optimizer import (DEFAULT_ASPECT, IMAGE_TARGETS, RULE_CODES, ImageIR, i01_clean_request,
                                 i02_move_avoid, i03_aspect_ratio, optimize_image)
from app.image.render import DEFAULTS, as_text, render, render_all, sd_size
from app.stage_a import rules as text_rules

ALL_PROMPTS = [p["prompt"] for p in json.loads(PROMPTS.read_text())]
EXTRA = ["a beach with no people and a blue sky", "a cozy cabin, no snow, no text",
         "pls generate an image of a futuristic city without cars and people for my phone wallpaper",
         "could you please make me a picture of a photo-style portrait of my grandma, without glasses, 4:5"]
_WORDS = re.compile(r"[\w'-]+")
SCAFFOLD = {"can", "could", "would", "will", "you", "please", "pls", "plz", "make", "me", "create", "generate",
            "give", "show", "a", "an", "of", "picture", "image", "pic", "img", "hey", "hi", "hello", "just", "i",
            "want", "need", "some", "produce", "get"}
NEGATIONS = {"no", "without", "avoid", "exclude", "excluding", "don't", "not", "include", "never", "and", "or", "with"}


def words(text: str) -> set[str]:
    return {w.lower() for w in _WORDS.findall(text)}


# ---------------------------------------------------------------- no user detail is lost
@pytest.mark.parametrize("prompt", ALL_PROMPTS + EXTRA)
def test_no_user_detail_is_lost(prompt):
    o = optimize_image(prompt)
    r = render_all(o.ir)
    removed = words(prompt) - words(o.ir.subject)
    assert removed <= SCAFFOLD, f"I01 removed more than filler: {removed}"
    for t in ("dalle", "nano_banana"):
        assert words(o.ir.subject) <= words(r[t]["prompt"])           # the user's sentence, word for word
    sd = r["stable_diffusion"]
    assert words(o.ir.subject_positive or o.ir.subject) <= words(sd["prompt"])
    assert words(o.ir.subject) - NEGATIONS <= words(sd["prompt"]) | words(sd["negative_prompt"])
    for phrase in o.ir.avoid_user:
        assert phrase in sd["negative_prompt"] and phrase in r["dalle"]["prompt"] and phrase in r["nano_banana"]["prompt"]


@pytest.mark.parametrize("prompt", ALL_PROMPTS)
def test_every_renderer_states_every_attribute(prompt):
    o = optimize_image(prompt)
    for t, rendered in render_all(o.ir).items():
        assert all(att.coverage(as_text(rendered)).values()), (t, att.coverage(as_text(rendered)))


# ---------------------------------------------------------------- detectors
@pytest.mark.parametrize("attribute, yes, no", [
    ("style", "a watercolor of a fox", "a fox"),
    ("style", "pls draw a dragon", "a dragon"),
    ("composition", "a close-up of a bee", "a bee"),
    ("composition", "a portrait of a fisherman", "a fisherman in portrait orientation"),
    ("lighting", "a lake at sunrise", "a lake"),
    ("lighting", "soft light on a vase", "a light blue vase"),
    ("palette", "a black and white photo", "a photo"),
    ("mood", "a cozy cabin", "a cabin"),
    ("aspect_ratio", "a lake, 16:9", "a lake"),
    ("aspect_ratio", "a city for my phone wallpaper", "a city"),
    ("background", "a fox in a forest", "a fox"),
    ("avoid", "a beach, no people", "a beach"),
])
def test_detectors(attribute, yes, no):
    assert att.find(attribute, yes) and not att.find(attribute, no)


def test_subject_detail_needs_descriptive_words():
    assert not att.detect("a dog")["subject_detail"]
    assert att.detect("a scruffy three-legged terrier wearing a tiny red raincoat")["subject_detail"]


# ---------------------------------------------------------------- rules
@pytest.mark.parametrize("raw, clean", [
    ("can you make me a picture of a cat on a windowsill", "A cat on a windowsill"),
    ("hey could you please create an image of a lion", "A lion"),
    ("pls draw a dragon", "Draw a dragon"),                       # 'draw' is the user's style: kept
    ("a photo of a dog", None),                                    # nothing to remove (only capitalisation)
    ("give me a pic of a sunset", "A sunset"),
])
def test_i01_removes_only_scaffolding_and_filler(raw, clean):
    out = i01_clean_request(ImageIR(subject=raw))
    assert out.subject == (clean or raw)


@pytest.mark.parametrize("text, avoid, positive", [
    ("a beach with no people and a blue sky", ("people",), "A beach and a blue sky"),
    ("a futuristic city without cars and people for my phone wallpaper", ("cars", "people"),
     "A futuristic city for my phone wallpaper"),
    ("a cozy cabin, no snow, no text", ("snow", "text"), "A cozy cabin"),
    ("a red car", (), None),
])
def test_i02_negation_scope(text, avoid, positive):
    out = i02_move_avoid(ImageIR(subject=text))
    assert out.avoid_user == avoid and out.subject_positive == positive
    assert out.subject == text                                      # the user's sentence itself is untouched


@pytest.mark.parametrize("text, ratio, source", [
    ("a lake, 16:9", "16:9", "user"), ("a city for my phone wallpaper", "9:16", "user"),
    ("a minimalist poster of a whale", "2:3", "user"), ("a dog", DEFAULT_ASPECT, "default"),
])
def test_i03_aspect_ratio(text, ratio, source):
    out = i03_aspect_ratio(ImageIR(subject=text))
    assert (out.aspect_ratio, out.aspect_source) == (ratio, source)
    assert ("aspect_ratio" in out.defaults) == (source == "default")


def test_defaults_only_for_missing_attributes_and_logged():
    o = optimize_image("watercolor painting of a fox in a forest at sunset, pastel colors, 16:9, no text")
    assert not {"style", "lighting", "palette", "background", "aspect_ratio", "avoid"} & set(o.ir.defaults)
    assert {"composition", "mood"} <= set(o.ir.defaults)
    for s in o.steps:
        assert s["rule_code"] in RULE_CODES and s["before"] != s["after"]
    bare = optimize_image("a dog")
    assert set(bare.ir.defaults) == set(att.ATTRIBUTES)               # everything missing: everything defaulted
    assert "Defaults:" in bare.steps[-1]["after"]


def test_rules_can_be_switched_off_and_unknown_rejected():
    o = optimize_image("a dog", disabled={"I05_DEFAULT_STYLE"})
    assert "style" not in o.ir.defaults and "I05_DEFAULT_STYLE" not in o.rules_applied
    with pytest.raises(ValueError):
        optimize_image("a dog", disabled={"B01_REMOVE_FILLER"})


def test_text_pipeline_filler_list_is_only_read():
    assert text_rules.FILLER_PATTERNS                                 # imported, never modified


# ---------------------------------------------------------------- renderers
def test_formats_per_target():
    o = optimize_image("a lighthouse, without boats, 16:9")
    d, nb, sd = (render(o.ir, t) for t in IMAGE_TARGETS)
    assert d["params"] == {"size": "1792x1024"} and d["prompt"].startswith("A lighthouse")
    assert nb["prompt"].startswith("Generate an image: A lighthouse") and nb["params"]["aspect_ratio"] == "16:9"
    assert "," in sd["prompt"] and "." not in sd["prompt"] and sd["negative_prompt"].startswith("boats")
    assert (sd["params"]["width"], sd["params"]["height"]) == sd_size(o.ir) and sd["params"]["width"] % 8 == 0
    assert DEFAULTS["lighting"][0] in d["prompt"] and DEFAULTS["lighting"][1] in sd["prompt"]
    with pytest.raises(ValueError):
        render(o.ir, "midjourney")


def test_neutral_defaults_do_not_impose_a_style_on_a_user_style():
    o = optimize_image("a watercolor of a fox")
    text = render(o.ir, "dalle")["prompt"]
    assert "realistic" not in text.lower()
