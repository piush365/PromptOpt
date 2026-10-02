"""Render an ImageIR for an image model. The user's description always comes first and unchanged.

* DALL-E (OpenAI): natural descriptive sentences; the size is a request parameter (1024x1024, 1792x1024, 1024x1792).
* Nano Banana (Gemini image): natural descriptive sentences opening with "Generate an image:", aspect ratio stated
  in the text and as a parameter.
* Stable Diffusion: comma-separated keywords (the description first) plus a negative prompt; width/height
  parameters for SD 1.5 (multiples of 8, about 512x512 pixels in area).

Each default fills an attribute the user did not state, with neutral wording (it defers to the subject).
"""
from app.image.optimizer import ImageIR, ImageTarget

# attribute -> (sentence for DALL-E / Nano Banana, keywords for Stable Diffusion)
DEFAULTS = {
    "subject_detail": ("Show the subject clearly and in detail.", "detailed subject"),
    "style": ("Use a realistic, detailed style.", "realistic, detailed"),
    "composition": ("Keep the subject centered and fully in frame.", "centered composition, subject fully in frame"),
    "lighting": ("Use clear, natural lighting that suits the scene.", "natural lighting"),
    "palette": ("Use a natural, balanced color palette that suits the subject.", "natural balanced color palette"),
    "mood": ("Let the mood follow from the subject; do not add a different one.", "mood matching the subject"),
    "background": ("Keep the background uncluttered and consistent with the scene.", "uncluttered background"),
}
SD_QUALITY = "high quality"
DALLE_SIZES = {"1:1": "1024x1024", "landscape": "1792x1024", "portrait": "1024x1792"}


def _ratio(ir: ImageIR) -> tuple[int, int]:
    w, h = (int(x) for x in ir.aspect_ratio.split(":"))
    return (w, h) if w and h else (1, 1)


def _sentence(text: str) -> str:
    text = text.strip()
    text = text[:1].upper() + text[1:]
    return text if text.endswith((".", "!", "?")) else text + "."


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]


def _sentences(ir: ImageIR) -> list[str]:
    parts = [DEFAULTS[a][0] for a in DEFAULTS if a in ir.defaults]
    if ir.avoid_user or ir.avoid_default:
        parts.append(f"Do not include {_join([*ir.avoid_user, *ir.avoid_default])}.")
    return parts


def render_dalle(ir: ImageIR) -> dict:
    w, h = _ratio(ir)
    size = DALLE_SIZES["1:1" if w == h else ("landscape" if w > h else "portrait")]
    text = " ".join([_sentence(ir.subject), *_sentences(ir), f"Aspect ratio {ir.aspect_ratio}."])
    return {"prompt": text, "params": {"size": size}}


def render_nano_banana(ir: ImageIR) -> dict:
    text = " ".join([f"Generate an image: {_sentence(ir.subject)}", *_sentences(ir),
                     f"Aspect ratio {ir.aspect_ratio}."])
    return {"prompt": text, "params": {"aspect_ratio": ir.aspect_ratio}}


def sd_size(ir: ImageIR, area: int = 512 * 512) -> tuple[int, int]:
    w, h = _ratio(ir)
    scale = (area / (w * h)) ** 0.5
    return int(round(w * scale / 8) * 8), int(round(h * scale / 8) * 8)


def render_stable_diffusion(ir: ImageIR) -> dict:
    subject = (ir.subject_positive or ir.subject).rstrip(".")
    keywords = [subject[:1].upper() + subject[1:]] + [DEFAULTS[a][1] for a in DEFAULTS if a in ir.defaults] + [SD_QUALITY]
    width, height = sd_size(ir)
    return {"prompt": ", ".join(keywords), "negative_prompt": ", ".join([*ir.avoid_user, *ir.avoid_default]),
            "params": {"width": width, "height": height, "aspect_ratio": ir.aspect_ratio}}


RENDERERS = {"dalle": render_dalle, "nano_banana": render_nano_banana, "stable_diffusion": render_stable_diffusion}


def render(ir: ImageIR, target: ImageTarget) -> dict:
    if target not in RENDERERS:
        raise ValueError(f"unknown image target {target!r}; expected one of {tuple(RENDERERS)}")
    return RENDERERS[target](ir)


def render_all(ir: ImageIR) -> dict[str, dict]:
    return {t: r(ir) for t, r in RENDERERS.items()}


def as_text(rendered: dict) -> str:
    """One text per rendering for coverage checks: the prompt, the negative prompt as an avoid line, and for Stable
    Diffusion the aspect ratio, which it gets as width/height parameters rather than words."""
    neg = rendered.get("negative_prompt")
    text = rendered["prompt"] + (f"\nAvoid {neg}" if neg else "")
    if neg is not None and "aspect_ratio" in rendered.get("params", {}):
        text += f"\n(parameter) {rendered['params']['aspect_ratio']}"
    return text
