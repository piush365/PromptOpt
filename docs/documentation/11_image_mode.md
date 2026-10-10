# 11. Image-generation mode

[Back to the index](README.md)

A separate mode the user selects explicitly ("Image generation"); it is never auto-detected, and Stage A/B/C are not
involved (the text pipeline stays frozen). Targets: DALL-E, Nano Banana (Gemini image) and Stable Diffusion. Code:
`backend/app/image/`; report: `evaluation/image/image_mode.md`. Built in finish phase 5 as v1, measured, found to
harm, and replaced by v2 — the story is the main lesson of this chapter.

---

## 11.1 Attribute detectors (`image/attributes.py`)

Nine attributes, each a lexicon/regex detector that returns evidence (like Stage A):

| attribute | counts when the prompt names … (examples) |
|---|---|
| style | photo, realistic, oil painting, watercolor, sketch, illustration, cartoon, anime, 3D render, pixel art, cinematic, logo, poster, … |
| composition | close-up, macro, wide shot, full body, bird's-eye view, from below, centered, rule of thirds, panoramic, portrait (not "portrait orientation"), … |
| lighting | lighting, backlit, golden hour, sunset, night, neon, candlelit, soft/hard/natural/warm light, shadows, volumetric, … |
| palette | pastel, monochrome, black and white, sepia, vibrant, muted, earth tones, color scheme, "shades of blue", "red tones", … |
| mood | cozy, eerie, serene, whimsical, melancholic, mysterious, dreamy, epic, nostalgic, atmosphere, mood, … |
| aspect ratio | "16:9", `--ar`, square, portrait/landscape orientation, vertical, widescreen, banner, wallpaper, Instagram story, poster, thumbnail, … |
| background | background, backdrop, setting, "in front of", or a preposition + a place noun (in a forest, on a beach, at night sky, …) |
| avoid | "no …", "without …", "avoid …", "don't include/show …" |
| subject detail | more than 3 **content words** remain (not stop words, not another attribute's evidence): a head noun plus descriptive words |

Known limits: a name can look like an attribute ("a bakery called Sunrise" counts as lighting); a subject that
implies a setting or mood ("an underwater coral reef") is not recognized as stating it.

## 11.2 v1 (rules I01–I11, `image/optimizer.py`, `render.py`) — kept for the evaluation only

| rule | does |
|---|---|
| I01 clean request | removes request scaffolding ("can you make me a picture of"), politeness filler (Stage A's A04 list) and chat abbreviations (pls, thx); never a style word or verb ("draw" stays) |
| I02 move avoid | "no text", "without cars and people" → avoid list `[text]`, `[cars, people]` word for word; the description keeps the sentence (DALL-E and Nano Banana read negation), while `subject_positive` (for Stable Diffusion, which has no negation in its positive prompt) drops the negated phrase, which goes to the negative prompt |
| I03 aspect ratio | an explicit "W:H", or a named format (phone wallpaper / story → 9:16; Instagram post / square → 1:1; poster → 2:3; portrait / vertical → 3:4; wallpaper / landscape / banner / header / thumbnail → 16:9); otherwise the default 1:1 |
| I04–I10 defaults | each missing attribute (subject detail, style, composition, lighting, palette, mood, background) gets a "neutral" default, marked as a default in the UI ("Use clear, natural lighting that suits the scene." / SD keyword "natural lighting") |
| I11 avoid defaults | the usual negatives: text, watermarks, logos, distorted anatomy, extra limbs, blurry details (unless already listed) |

## 11.3 Renderers

| target | prompt | parameters |
|---|---|---|
| DALL-E | the user's sentence first, then the added sentences, "Do not include …", "Aspect ratio W:H." | `size`: 1024×1024 (square), 1792×1024 (landscape), 1024×1792 (portrait) — DALL-E 3's sizes |
| Nano Banana | "Generate an image: " + the same sentences | `aspect_ratio` |
| Stable Diffusion | comma-separated keywords, the user's words first; a separate **negative prompt** | `width`, `height` |

**Stable Diffusion size, derived.** SD 1.5 was trained at 512×512, and its VAE works on latents 8× smaller than the
image, so width and height must be multiples of 8 and the area should stay near $512^2$. For a ratio $w{:}h$:

$$s = \sqrt{\frac{512^2}{w\,h}}, \qquad \text{width} = 8\Big\lfloor \frac{w s}{8} \Big\rceil, \qquad \text{height} = 8\Big\lfloor \frac{h s}{8} \Big\rceil$$

| ratio | width × height | area ÷ 512² |
|---|---|---|
| 1:1 | 512 × 512 | 1.000 |
| 16:9 | 680 × 384 | 0.996 |
| 9:16 | 384 × 680 | 0.996 |
| 3:4 | 440 × 592 | 0.994 |
| 2:3 | 416 × 624 | 0.990 |

## 11.4 Evaluating v1, and why it failed

**Coverage** (dev set of 40 hand-written vague prompts): attributes stated per prompt rose from **0.8 to 9.0 of 9** in
every rendering. By that measure v1 was perfect — and that measure turned out to be the wrong target.

**Image check** (`image/generate.py`, `.venv-gpu`): each prompt was rendered by Stable Diffusion 1.5
(`stable-diffusion-v1-5/stable-diffusion-v1-5`, fp16, DPM-Solver++ 25 steps, guidance 7.5, attention slicing, safety
checker on; peak 3.18 GiB on the 4 GB RTX 3050; about 7.5 s per image) for the original prompt and for the optimized
Stable Diffusion rendering, with the **same seed** per prompt (1000 + prompt index). SD 1.5 rather than SD-Turbo,
because SD-Turbo runs without guidance and ignores negative prompts.

**CLIP score** against the user's **original** prompt (the extra words of the optimized prompt are not in the scoring
text, so a longer prompt cannot win just by being longer):

$$\text{CLIPScore}(I, T) = 100 \cdot \cos\big(\mathbf{v}_I, \mathbf{t}_T\big)$$

with the projected image and text embeddings of `openai/clip-vit-base-patch32`, L2-normalized. Pairs differing by
less than 0.5 count as ties; significance by the two-sided sign test (chapter 8.4).

**Style adherence** (prompts that state a non-photographic style, annotated before any run): CLIP zero-shot
probability of "a ⟨stated style⟩" against "a photograph" for the image:

$$P(\text{style}) = \frac{\exp(\lambda \cos(\mathbf{v}_I, \mathbf{t}_{style}))}{\exp(\lambda \cos(\mathbf{v}_I, \mathbf{t}_{style})) + \exp(\lambda \cos(\mathbf{v}_I, \mathbf{t}_{photo}))}$$

($\lambda$ = CLIP's learned logit scale); "style kept" = $P(\text{style}) > 0.5$.

**Result (dev, 40 prompts):** CLIP 29.95 (original) vs **28.44** (v1); v1 higher in 9, lower in 25, tie 6; sign test
**p = 0.009**. The three largest drops were all prompts that state a style: keywords such as "natural lighting",
"natural balanced color palette" and "detailed subject" act as **photographic cues** for SD 1.5 and pulled, for
example, a watercolor request into a photo. The defaults were *not* tuned on this set afterwards (that would fit the
evaluation prompts); a fix needed a fresh held-out set.

## 11.5 v2 (`image/v2.py`) — the app's default

Principle: add only what **cannot conflict** with the request; turn every other missing attribute into a
**suggestion** the user may click.

| rule | does |
|---|---|
| I01, I02 | as v1 (clean request; "no X" → avoid list / negative prompt) |
| I12 aspect if implied | a ratio only when the request implies one (v1's I03 logic); **no default** — the model's own default is used |
| I13 style first | the user's comma-separated chunks that state a style move to the front of the Stable Diffusion prompt (earlier tokens weigh more); only reorders the user's own words |
| I16 accepted suggestions | what the user clicked, added after the user's words (an accepted ratio sets the ratio; an accepted "avoid" goes to the negative prompt) |

**Suggestions** (chips in the UI; nothing preselected): style (photograph, digital illustration, watercolor painting,
3D render), composition (close-up, wide shot, centered composition), lighting (soft daylight, golden hour light,
dramatic studio lighting), palette (warm tones, pastel colors, vibrant colors), mood (calm, cheerful, mysterious),
background (plain white, blurred, natural outdoor setting), aspect ratio (1:1, 16:9, 9:16, 3:4), avoid (text and
watermarks, distorted anatomy, blurry details), plus a hint to describe the subject more. Only values from these
lists are accepted (`parse_accepted`; anything else → 422).

**Avoid suggestions are conflict-filtered** (I14's filter): "text" is not offered when the request mentions a logo,
poster, sign, label, title, quote, menu, cover or quoted text; "blurry details" not for bokeh/motion/fog/dreamy;
"distorted anatomy" not for abstract/surreal/cubist/monster/cartoon; "extra limbs" not for octopus/spider/monster/…

**Tuning on dev only:** a first v2 draft also added the conflict-filtered negatives (I14) and the quality term "high
quality" (I15) automatically. Even these lowered agreement with the request (dev CLIP 29.21 vs 29.95; the watercolor
fox lost its style); without them v2 matched the original (29.82, style kept 5/6). So both became optional (I14/I15
are kept in the code only to reproduce that comparison).

## 11.6 Held-out evaluation, run once

30 new prompts (`evaluation/image/heldout_prompts.json`), written and **committed before any v2 code** (commit
`d656add`), run once:

| variant | CLIP vs original (mean) | higher / lower / tie | sign test p | style kept (12 styled) | P(style), mean |
|---|---|---|---|---|---|
| original prompt | 33.08 | – | – | 12/12 | 0.99 |
| v1 | 30.78 | 7 / 18 / 5 | 0.043 | 10/12 | 0.82 |
| **v2** | **32.77** | 0 / 4 / 26 | 0.125 | **12/12** | 0.99 |
| v2 + every first suggestion (simulated user) | 31.07 | 3 / 20 / 7 | < 0.001 | 10/12 | 0.87 |

The 4 prompts where v2 is lower are things v2 does on purpose: an implied 16:9 or poster ratio changes the image
shape; "without clouds" moves clouds to the negative prompt, while CLIP — which ignores negation — scores the text
"… without clouds" higher for images **with** clouds; removing "pls create an image of".

**Lessons.** (1) A default that is "neutral" in words is not neutral in effect. (2) Attribute coverage is the wrong
target: v1 reached 9.0/9 and made images worse; the image model's output against the user's own request is the check
that matters. (3) CLIP against the original prompt detects harm, not improvement; v2's value lies in what it does not
break and in user-chosen suggestions, which this score cannot measure. (4) Accepting every suggestion at once is not a
good default either, which is why nothing is preselected.

## 11.7 In the app

`POST /api/optimize` with `category = "image_generation"` and an image target (`dalle`, `nano_banana`,
`stable_diffusion`; a text target → 422): the prompt is stored like a text prompt (PII scrubbed, retention), the
image IR and its rule log go into the result's IR JSON, and the response lists what the user stated, the avoid list,
what was added automatically (only what the user's words imply), the accepted suggestions, the offered suggestions,
the rules fired with before/after, and the three renderings (with a Stable Diffusion negative prompt).

**Limitations:** measured with SD 1.5 and CLIP only (DALL-E and Nano Banana untested without API keys); all prompts
developer-written (a blind set of 10 by outsiders is future work).
