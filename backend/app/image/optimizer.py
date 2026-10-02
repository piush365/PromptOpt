"""Image-generation mode: rule-based optimizer (rules I01-I11). Separate from the text pipeline (Stage A/B/C stay
frozen at `final-for-test`); used only when the user explicitly picks "Image generation".

    out = optimize_image("can you make me a picture of a cat on a windowsill, no text")
    out.ir.subject, out.ir.avoid_user, out.ir.defaults, out.steps

The user's words are kept: I01 removes only politeness filler and generic request scaffolding ("make me a picture
of"), never a style word ("photo", "drawing" stay). I02 copies "no X" / "without X and Y" into the avoid list: the
description keeps the user's sentence word for word (DALL-E and Nano Banana read negation correctly), and only
`subject_positive`, used for the Stable Diffusion keywords, has the negated phrase removed (it goes to the negative
prompt instead, since SD has no negation in the positive prompt). Every attribute the prompt does not state gets a neutral
default (I03-I11), recorded in `ir.defaults` so the UI can mark it; defaults defer to the subject ("lighting that
suits the scene", "a mood that follows from the subject") instead of imposing one. Every change is logged as a step.
"""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.image.attributes import ATTRIBUTES, detect
from app.stage_a import rules as text_rules

_I = re.IGNORECASE
ImageTarget = Literal["dalle", "nano_banana", "stable_diffusion"]
IMAGE_TARGETS: tuple[ImageTarget, ...] = ("dalle", "nano_banana", "stable_diffusion")
DEFAULT_ASPECT = "1:1"
DEFAULT_AVOID = ("text", "watermarks", "logos", "distorted anatomy", "extra limbs", "blurry details")


class ImageIR(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject: str                                  # the user's description, in their words (negations included)
    subject_positive: str | None = None           # the description without negated phrases (Stable Diffusion)
    avoid_user: tuple[str, ...] = ()              # things the user said to leave out
    avoid_default: tuple[str, ...] = ()
    aspect_ratio: str = DEFAULT_ASPECT
    aspect_source: Literal["user", "default"] = "default"
    present: tuple[str, ...] = ()                 # attributes the user's prompt states
    defaults: tuple[str, ...] = ()                # attributes filled with a neutral default (marked in the UI)
    target: ImageTarget | None = None


class ImageOptimization(BaseModel):
    original: str
    ir: ImageIR
    steps: list[dict[str, str]]
    detected: dict[str, list[str]]

    @property
    def rules_applied(self) -> list[str]:
        return [s["rule_code"] for s in self.steps]


def describe(ir: ImageIR) -> str:
    """Plain summary used for the before/after log (not a rendering)."""
    parts = [ir.subject]
    if ir.avoid_user or ir.avoid_default:
        parts.append("Avoid: " + ", ".join((*ir.avoid_user, *ir.avoid_default)))
    parts.append(f"Aspect ratio: {ir.aspect_ratio} ({ir.aspect_source})")
    if ir.defaults:
        parts.append("Defaults: " + ", ".join(ir.defaults))
    return "\n".join(parts)


# ---------------------------------------------------------------- I01 clean request
_SCAFFOLD = re.compile(
    r"^\s*(?:(?:hey|hi|hello)[,!]?\s+)?(?:(?:please|pls|plz)\s+)?(?:(?:can|could|would|will) you\s+)?"
    r"(?:(?:please|pls|plz)\s+)?(?:generate|create|make|produce|give me|show me|i want|i need|i'?d like|get me)\s+"
    r"(?:me\s+)?(?:an?\s+|some\s+)?(?:image|picture|pic|img|visual|artwork|art)s?\s+(?:of|showing|with|that shows)\s+",
    _I)


def _tidy(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", t)
    t = re.sub(r"^[\s,.;:!?-]+|[\s,;:!?-]+$", "", t).rstrip(".")
    return t[:1].upper() + t[1:] if t else t


_CHAT_FILLER = re.compile(r"\b(?:pls|plz|thx|thanks)\b", _I)


def i01_clean_request(ir: ImageIR) -> ImageIR:
    """Remove request scaffolding ("can you make me a picture of") and politeness filler ("please", "just", "pls"),
    using the same filler list as Stage A (A04) plus chat abbreviations. Style words and verbs ("draw") are kept."""
    text = _CHAT_FILLER.sub(" ", _SCAFFOLD.sub("", ir.subject))
    for p in text_rules.FILLER_PATTERNS:
        text = p.sub(" ", text)
    text = _tidy(text)
    if not text or text.lower() == ir.subject.strip().rstrip(".").lower():      # capitalisation only: no change
        return ir
    return ir.model_copy(update={"subject": text})


# ---------------------------------------------------------------- I02 avoid list
_NEGATION = re.compile(r"(?:,\s*|\s+|^)(?:with\s+)?(?:no|without|avoid(?:ing)?|exclude|excluding|"
                       r"(?:but\s+)?(?:don'?t|do not) (?:include|show|add)|never show|not include)\s+", _I)
# the negated phrase ends at punctuation or a preposition/clause word; "and"/"or" continue the list ("without cars and
# people") unless a new noun phrase starts with an article or number ("no people and a blue sky")
_STOP = re.compile(r"\s+(?:but|with|in|on|at|while|so|for|under|near|by|from)\s+|\s+(?:and|or)\s+(?=(?:a|an|the|some|"
                   r"one|two|three|\d+|my|his|her|their)\b)|[,.;:!?]", _I)
_LIST = re.compile(r"\s*(?:,|\band\b|\bor\b)\s*", _I)


def i02_move_avoid(ir: ImageIR) -> ImageIR:
    """'no text', 'without cars and people' -> avoid list ['text'], ['cars', 'people'] (word for word). The
    description keeps the sentence; `subject_positive` (for Stable Diffusion) drops the negated phrase."""
    text, avoid = ir.subject, list(ir.avoid_user)
    while m := _NEGATION.search(text):
        rest = text[m.end():]
        stop = _STOP.search(rest)
        phrase = (rest[:stop.start()] if stop else rest).strip()
        if not phrase:
            break
        avoid += [p for p in _LIST.split(phrase) if p.strip()]
        text = text[:m.start()] + (" " + rest[stop.start():].lstrip(" ") if stop else "")
    if not avoid or tuple(avoid) == ir.avoid_user:
        return ir
    return ir.model_copy(update={"subject_positive": _tidy(text), "avoid_user": tuple(avoid)})


# ---------------------------------------------------------------- I03 aspect ratio
_RATIO = re.compile(r"\b(\d{1,2})\s?:\s?(\d{1,2})\b")
_NAMED_RATIOS = [
    (r"\b(?:phone|mobile) wallpaper\b|\binstagram story\b|\bstory format\b", "9:16"),
    (r"\binstagram post\b|\bsquare\b", "1:1"),
    (r"\bposter\b", "2:3"),
    (r"\bportrait (?:orientation|format|mode)\b|\bvertical\b", "3:4"),
    (r"\b(?:desktop )?wallpaper\b|\blandscape (?:orientation|format|mode)\b|\bhorizontal\b|\bwidescreen\b|"
     r"\bwide ?format\b|\bbanner\b|\bheader\b|\bcover photo\b|\bthumbnail\b", "16:9"),
]


def i03_aspect_ratio(ir: ImageIR) -> ImageIR:
    """Use the ratio the user states ("16:9", "phone wallpaper") as a parameter; otherwise the default 1:1. The user's
    words stay in the description."""
    if m := _RATIO.search(ir.subject):
        ratio = f"{m.group(1)}:{m.group(2)}"
    else:
        ratio = next((r for p, r in _NAMED_RATIOS if re.search(p, ir.subject, _I)), None)
    if ratio is None:
        return ir.model_copy(update={"aspect_ratio": DEFAULT_ASPECT, "aspect_source": "default",
                                     "defaults": (*ir.defaults, "aspect_ratio")})
    return ir.model_copy(update={"aspect_ratio": ratio, "aspect_source": "user"})


# ---------------------------------------------------------------- I04-I10 neutral defaults, I11 avoid defaults
def _default_rule(attribute: str):
    def rule(ir: ImageIR) -> ImageIR:
        if attribute in ir.present or attribute in ir.defaults:
            return ir
        return ir.model_copy(update={"defaults": (*ir.defaults, attribute)})
    rule.__name__ = f"i_default_{attribute}"
    rule.__doc__ = f"No {attribute.replace('_', ' ')} stated: add the neutral default (marked as a default)."
    return rule


def i11_avoid_defaults(ir: ImageIR) -> ImageIR:
    """Add the usual quality negatives (text, watermarks, distorted anatomy, ...) unless the user already lists them."""
    have = " ".join(ir.avoid_user).lower()
    add = tuple(a for a in DEFAULT_AVOID if a.split()[0].rstrip("s") not in have)
    if not add or ir.avoid_default:
        return ir
    update = {"avoid_default": add}
    if "avoid" not in ir.present:
        update["defaults"] = (*ir.defaults, "avoid")
    return ir.model_copy(update=update)


RULES = [
    ("I01_CLEAN_REQUEST", i01_clean_request),
    ("I02_MOVE_AVOID", i02_move_avoid),
    ("I03_ASPECT_RATIO", i03_aspect_ratio),
    ("I04_DEFAULT_SUBJECT_DETAIL", _default_rule("subject_detail")),
    ("I05_DEFAULT_STYLE", _default_rule("style")),
    ("I06_DEFAULT_COMPOSITION", _default_rule("composition")),
    ("I07_DEFAULT_LIGHTING", _default_rule("lighting")),
    ("I08_DEFAULT_PALETTE", _default_rule("palette")),
    ("I09_DEFAULT_MOOD", _default_rule("mood")),
    ("I10_DEFAULT_BACKGROUND", _default_rule("background")),
    ("I11_AVOID_DEFAULTS", i11_avoid_defaults),
]
RULE_CODES = [c for c, _ in RULES]


def optimize_image(prompt: str, target: ImageTarget | None = None,
                   disabled: frozenset[str] | set[str] = frozenset()) -> ImageOptimization:
    unknown = set(disabled) - set(RULE_CODES)
    if unknown:
        raise ValueError(f"unknown image rule codes: {sorted(unknown)}")
    # attributes are detected on the request without its scaffolding and filler ("could you please create an image
    # of" is not subject detail)
    detected = detect(i01_clean_request(ImageIR(subject=prompt.strip())).subject)
    ir = ImageIR(subject=prompt.strip(), target=target,
                 present=tuple(a for a in ATTRIBUTES if detected[a] and a != "aspect_ratio"))
    steps = []
    for code, rule in RULES:
        if code in disabled:
            continue
        new = rule(ir)
        if new != ir:
            steps.append({"rule_code": code, "before": describe(ir), "after": describe(new)})
        ir = new
    return ImageOptimization(original=prompt, ir=ir, steps=steps, detected=detected)
