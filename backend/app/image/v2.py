"""Image optimizer v2 (the app's default). Lesson from v1 (evaluation/image_mode.md): default lighting / palette /
detail keywords are not neutral for Stable Diffusion; they pull stylised requests toward photographs. So v2 adds
only what cannot conflict with the request and turns every other missing attribute into a suggestion the user may
accept.

    out = optimize_image_v2("a fox in a forest, watercolor", accepted=["lighting:soft daylight"])
    out.ir, out.suggestions, out.steps;  render_v2(out.ir, "stable_diffusion")

Rules (each change logged, like Stage B):
  I01 clean request, I02 "no X" -> avoid list            (shared with v1, unchanged)
  I12 aspect ratio only when the request implies one      (no default ratio: the model's own default is used)
  I13 style first: the user's comma-chunks that state a style go to the front of the Stable Diffusion prompt
  I16 accepted suggestions: what the user clicked, added after the user's own words and marked as accepted
Missing style / composition / lighting / palette / mood / background / aspect ratio / usual negatives ->
`suggestions` (chips in the UI, never inserted automatically); missing subject detail -> a hint only.

Decided on the dev set (evaluation/image_mode.md, 3b): a draft also added the usual negatives (I14, filtered for
conflicts) and the quality term "high quality" (I15) automatically. Both still pulled Stable Diffusion images away
from the request (dev CLIP vs original 29.21 vs 29.95; the watercolor fox lost its style), so they are no longer
automatic: the negatives are an "avoid" suggestion (I14's conflict filter decides which are offered), and the quality
term is dropped. I14/I15 are kept for the record and for the dev-set "v2 draft" comparison only.
"""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.image.attributes import ATTRIBUTES, detect
from app.image.optimizer import (DEFAULT_AVOID, ImageIR, ImageTarget, i01_clean_request, i02_move_avoid,
                                 i03_aspect_ratio)

_I = re.IGNORECASE
QUALITY = "high quality"
SUGGESTIONS: dict[str, list[str]] = {
    "style": ["photograph", "digital illustration", "watercolor painting", "3d render"],
    "composition": ["close-up", "wide shot", "centered composition"],
    "lighting": ["soft daylight", "golden hour light", "dramatic studio lighting"],
    "palette": ["warm tones", "pastel colors", "vibrant colors"],
    "mood": ["calm mood", "cheerful mood", "mysterious mood"],
    "background": ["plain white background", "blurred background", "natural outdoor setting"],
    "aspect_ratio": ["1:1", "16:9", "9:16", "3:4"],
    "avoid": ["text and watermarks", "distorted anatomy", "blurry details"],
}
# which default negative (I14's conflict list) an avoid suggestion stands for
_AVOID_SUGGESTION_KEY = {"text and watermarks": "text", "distorted anatomy": "distorted anatomy",
                         "blurry details": "blurry details"}
SUBJECT_HINT = "Describe the subject a little more (color, size, pose, clothing, material, what it is doing)."
# negatives the request itself can contradict
_CONFLICTS = {
    "text": r"\b(?:logo|icon|poster|sign|signs|label|invitation|card|banner|title|text|typography|lettering|called|"
            r"named|says|saying|quote|menu|book cover|cover)\b|[\"“”]",
    "logos": r"\b(?:logo|logos|brand|branding|icon)\b",
    "blurry details": r"\b(?:blur|blurry|blurred|bokeh|motion|soft focus|out of focus|dreamy|foggy|fog|mist)\b",
    "distorted anatomy": r"\b(?:abstract|surreal|cubis[tm]|monster|creature|alien|caricature|cartoon|distorted)\b",
    "extra limbs": r"\b(?:octopus|spider|centipede|monster|creature|alien|multi-armed|many arms|insect)\b",
}


class ImageIRv2(ImageIR):
    model_config = ConfigDict(frozen=True)

    version: Literal["v2"] = "v2"
    aspect_ratio: str | None = None               # only when the request implies one (or the user accepts one)
    style_first: tuple[str, ...] = ()             # the user's chunks that state a style (front of the SD prompt)
    quality: str | None = None
    accepted: tuple[tuple[str, str], ...] = ()    # (attribute, value) the user accepted from the suggestions


class Suggestion(BaseModel):
    attribute: str
    options: list[str]
    hint: str | None = None


class ImageOptimizationV2(BaseModel):
    original: str
    ir: ImageIRv2
    steps: list[dict[str, str]]
    detected: dict[str, list[str]]
    suggestions: list[Suggestion]

    @property
    def rules_applied(self) -> list[str]:
        return [s["rule_code"] for s in self.steps]


def describe_v2(ir: ImageIRv2) -> str:
    parts = [ir.subject]
    if ir.style_first:
        parts.append("Style first (Stable Diffusion): " + ", ".join(ir.style_first))
    if ir.accepted:
        parts.append("Accepted: " + ", ".join(f"{a} {v}" for a, v in ir.accepted))
    if ir.avoid_user or ir.avoid_default:
        parts.append("Avoid: " + ", ".join((*ir.avoid_user, *ir.avoid_default)))
    if ir.aspect_ratio:
        parts.append(f"Aspect ratio: {ir.aspect_ratio} ({ir.aspect_source})")
    if ir.quality:
        parts.append(f"Quality: {ir.quality}")
    return "\n".join(parts)


def i12_aspect_if_implied(ir: ImageIRv2) -> ImageIRv2:
    """Aspect ratio only when the request implies one ("16:9", "phone wallpaper", "poster"); no default."""
    v1 = i03_aspect_ratio(ImageIR(subject=ir.subject))
    if v1.aspect_source != "user" or ir.aspect_ratio == v1.aspect_ratio:
        return ir
    return ir.model_copy(update={"aspect_ratio": v1.aspect_ratio, "aspect_source": "user"})


_CHUNK = re.compile(r"\s*,\s*")


def i13_style_first(ir: ImageIRv2) -> ImageIRv2:
    """The user's comma-separated chunks that state a style, moved to the front of the Stable Diffusion prompt
    (earlier tokens weigh more). Only reorders the user's own words; DALL-E / Nano Banana keep the sentence as is."""
    chunks = [c for c in _CHUNK.split(ir.subject_positive or ir.subject) if c]
    styled = tuple(c for c in chunks[1:] if detect(c)["style"])           # the first chunk is already in front
    return ir if not styled or styled == ir.style_first else ir.model_copy(update={"style_first": styled})


def i14_safe_negatives(ir: ImageIRv2) -> ImageIRv2:
    """The usual negatives, minus any the request conflicts with or the user already listed."""
    have = " ".join(ir.avoid_user).lower()
    keep = tuple(n for n in DEFAULT_AVOID if not re.search(_CONFLICTS.get(n, r"$^"), ir.subject, _I)
                 and n.split()[0].rstrip("s") not in have)
    return ir if keep == ir.avoid_default else ir.model_copy(update={"avoid_default": keep})


def i15_quality_term(ir: ImageIRv2) -> ImageIRv2:
    """A quality term that never implies a medium."""
    return ir if ir.quality == QUALITY else ir.model_copy(update={"quality": QUALITY})


def parse_accepted(accepted: list[str] | tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    """'lighting:soft daylight' -> ('lighting', 'soft daylight'); only values from the suggestion lists."""
    out = []
    for item in accepted or ():
        attr, _, value = item.partition(":")
        if attr in SUGGESTIONS and value in SUGGESTIONS[attr]:
            out.append((attr, value))
        else:
            raise ValueError(f"unknown suggestion {item!r}")
    return tuple(dict.fromkeys(out))


def i16_accepted(ir: ImageIRv2, accepted: tuple[tuple[str, str], ...]) -> ImageIRv2:
    """Suggestions the user accepted, added after the user's words (an accepted aspect ratio sets the ratio; an
    accepted "avoid" goes to the avoid list / negative prompt)."""
    if not accepted or accepted == ir.accepted:
        return ir
    update: dict = {"accepted": tuple(a for a in accepted if a[0] != "aspect_ratio")}
    if ratio := next((v for a, v in accepted if a == "aspect_ratio"), None):
        update.update(aspect_ratio=ratio, aspect_source="user")
    return ir.model_copy(update=update)


RULES_V2 = ["I01_CLEAN_REQUEST", "I02_MOVE_AVOID", "I12_ASPECT_IF_IMPLIED", "I13_STYLE_FIRST",
            "I16_ACCEPTED_SUGGESTIONS"]
RULE_DOCS_V2 = {"I12_ASPECT_IF_IMPLIED": i12_aspect_if_implied.__doc__, "I13_STYLE_FIRST": i13_style_first.__doc__,
                "I14_SAFE_NEGATIVES": i14_safe_negatives.__doc__, "I15_QUALITY_TERM": i15_quality_term.__doc__,
                "I16_ACCEPTED_SUGGESTIONS": i16_accepted.__doc__}


def avoid_options(ir: ImageIRv2) -> list[str]:
    """Negatives worth suggesting: not conflicting with the request (I14's filter), not already avoided/accepted."""
    keep = set(i14_safe_negatives(ir.model_copy(update={"avoid_default": ()})).avoid_default)
    done = {v for a, v in ir.accepted if a == "avoid"}
    return [o for o in SUGGESTIONS["avoid"] if _AVOID_SUGGESTION_KEY[o] in keep and o not in done]


def suggestions_for(stated: set[str], ir: ImageIRv2) -> list[Suggestion]:
    have = stated | {a for a, _ in ir.accepted if a != "avoid"} | ({"aspect_ratio"} if ir.aspect_ratio else set())
    out = [Suggestion(attribute=a, options=opts) for a, opts in SUGGESTIONS.items() if a not in have and a != "avoid"]
    if opts := avoid_options(ir):
        out.append(Suggestion(attribute="avoid", options=opts))
    if "subject_detail" not in stated:
        out.insert(0, Suggestion(attribute="subject_detail", options=[], hint=SUBJECT_HINT))
    return out


def optimize_image_v2(prompt: str, accepted: list[str] | tuple[str, ...] = (),
                      target: ImageTarget | None = None) -> ImageOptimizationV2:
    acc = parse_accepted(accepted)
    detected = detect(i01_clean_request(ImageIR(subject=prompt.strip())).subject)
    stated = {a for a in ATTRIBUTES if detected[a]}
    ir = ImageIRv2(subject=prompt.strip(), target=target, present=tuple(sorted(stated)))
    steps = []
    funcs = [("I01_CLEAN_REQUEST", i01_clean_request), ("I02_MOVE_AVOID", i02_move_avoid),
             ("I12_ASPECT_IF_IMPLIED", i12_aspect_if_implied), ("I13_STYLE_FIRST", i13_style_first),
             ("I16_ACCEPTED_SUGGESTIONS", lambda x: i16_accepted(x, acc))]
    for code, rule in funcs:
        new = rule(ir)
        if new != ir:
            steps.append({"rule_code": code, "before": describe_v2(ir), "after": describe_v2(new)})
        ir = new
    return ImageOptimizationV2(original=prompt, ir=ir, steps=steps, detected=detected,
                               suggestions=suggestions_for(stated, ir))


# ---------------------------------------------------------------- renderers
DALLE_SIZES = {"square": "1024x1024", "landscape": "1792x1024", "portrait": "1024x1792"}


def _sentence(text: str) -> str:
    text = text.strip()
    text = text[:1].upper() + text[1:]
    return text if text.endswith((".", "!", "?")) else text + "."


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]


def _ratio(ratio: str | None) -> tuple[int, int]:
    if not ratio:
        return 1, 1
    w, h = (int(x) for x in ratio.split(":"))
    return (w, h) if w and h else (1, 1)


def negatives(ir: ImageIRv2) -> list[str]:
    return [*ir.avoid_user, *ir.avoid_default, *(v for a, v in ir.accepted if a == "avoid")]


def _positives(ir: ImageIRv2) -> list[tuple[str, str]]:
    return [(a, v) for a, v in ir.accepted if a != "avoid"]


def _tail_sentences(ir: ImageIRv2) -> list[str]:
    parts = [_sentence(f"{a.replace('_', ' ').capitalize()}: {v}") for a, v in _positives(ir)]
    if ir.quality:
        parts.append(_sentence(f"{ir.quality.capitalize()} image"))
    if neg := negatives(ir):
        parts.append(f"Do not include {_join(neg)}.")
    if ir.aspect_ratio:
        parts.append(f"Aspect ratio {ir.aspect_ratio}.")
    return parts


def render_v2(ir: ImageIRv2, target: ImageTarget) -> dict:
    w, h = _ratio(ir.aspect_ratio)
    if target == "dalle":
        size = DALLE_SIZES["square" if w == h else ("landscape" if w > h else "portrait")]
        return {"prompt": " ".join([_sentence(ir.subject), *_tail_sentences(ir)]), "params": {"size": size}}
    if target == "nano_banana":
        params = {"aspect_ratio": ir.aspect_ratio} if ir.aspect_ratio else {}
        return {"prompt": " ".join([f"Generate an image: {_sentence(ir.subject)}", *_tail_sentences(ir)]),
                "params": params}
    if target == "stable_diffusion":
        chunks = [c for c in _CHUNK.split((ir.subject_positive or ir.subject).rstrip(".")) if c]
        ordered = [*ir.style_first, *[c for c in chunks if c not in ir.style_first]]
        ordered[0] = ordered[0][:1].upper() + ordered[0][1:]
        keywords = ordered + [v for _, v in _positives(ir)] + ([ir.quality] if ir.quality else [])
        scale = (512 * 512 / (w * h)) ** 0.5
        width, height = int(round(w * scale / 8) * 8), int(round(h * scale / 8) * 8)
        return {"prompt": ", ".join(keywords), "negative_prompt": ", ".join(negatives(ir)),
                "params": {"width": width, "height": height, **({"aspect_ratio": ir.aspect_ratio}
                                                                 if ir.aspect_ratio else {})}}
    raise ValueError(f"unknown image target {target!r}")


def render_all_v2(ir: ImageIRv2) -> dict[str, dict]:
    return {t: render_v2(ir, t) for t in ("dalle", "nano_banana", "stable_diffusion")}
