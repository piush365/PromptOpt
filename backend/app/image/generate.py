"""Optional: generate images locally and score them with CLIP against the user's ORIGINAL prompt (so a longer prompt
does not win just by being longer). Run in backend/.venv-gpu:

    python -m app.image.generate --set dev        # tuning set (40): original, v1, v2, v2 + suggestions
    python -m app.image.generate --set heldout    # held-out set (30), run once
    python -m app.image.generate --set dev --score-only

Variants (same seed for every variant of a prompt):
  original      the prompt as typed, 512x512, no negative prompt
  v1            image optimizer v1, Stable Diffusion rendering (default keywords for every missing attribute)
  v2            image optimizer v2, final: the user's words (style first), the user's avoid list and an implied
                ratio; nothing else is added (everything else is a suggestion)
  v2_suggested  v2 plus the FIRST suggestion of every offered attribute except aspect ratio, as if the user had
                clicked each one (simulated; shows what accepting suggestions does)
Tuning variants (dev set only): v2_draft = v2 plus the automatic negatives (I14) and quality term (I15) of the first
v2 draft; v2_no_default_negatives = the draft without the negatives.
Model: Stable Diffusion 1.5 (`stable-diffusion-v1-5/stable-diffusion-v1-5`, fp16; licence CreativeML OpenRAIL-M:
use-based restrictions, research use allowed), DPM-Solver++ 25 steps, guidance 7.5, safety checker on, attention
slicing (peak 3.2 GB on the RTX 3050 4 GB). SD 1.5 rather than SD-Turbo: SD-Turbo ignores negative prompts.
Scoring with CLIP ViT-B/32 (the CLIPScore model): 100 x cosine(image, original prompt); for prompts that state a
non-photographic style (annotated in the prompt files), style adherence = CLIP zero-shot P(stated style) against
P("a photograph"). Every image is saved and recorded as it is made, so an interrupted run resumes.
"""
import argparse
import json
import time

import torch

from app.config import BACKEND_DIR
from app.image.optimizer import optimize_image
from app.image.render import render
from app.image.v2 import i14_safe_negatives, i15_quality_term, optimize_image_v2, render_v2

ROOT = BACKEND_DIR.parent / "data" / "image_eval"
SETS = {"dev": BACKEND_DIR.parent / "evaluation" / "image" / "image_prompts.json",
        "heldout": BACKEND_DIR.parent / "evaluation" / "image" / "heldout_prompts.json"}
SD_MODEL = "stable-diffusion-v1-5/stable-diffusion-v1-5"
CLIP_MODEL = "openai/clip-vit-base-patch32"
STEPS, GUIDANCE, SEED = 25, 7.5, 1000
VARIANTS = ("original", "v1", "v2", "v2_suggested")
TUNING_VARIANTS = ("v2_draft", "v2_no_default_negatives")


def spec(prompt: str, variant: str) -> dict:
    """What Stable Diffusion gets for one variant."""
    if variant == "original":
        return {"prompt": prompt, "negative_prompt": None, "width": 512, "height": 512}
    if variant == "v1":
        r = render(optimize_image(prompt).ir, "stable_diffusion")
    elif variant in TUNING_VARIANTS:
        ir = i15_quality_term(i14_safe_negatives(optimize_image_v2(prompt).ir))
        if variant == "v2_no_default_negatives":
            ir = ir.model_copy(update={"avoid_default": ()})
        r = render_v2(ir, "stable_diffusion")
    else:
        accepted = []
        if variant == "v2_suggested":
            accepted = [f"{s.attribute}:{s.options[0]}" for s in optimize_image_v2(prompt).suggestions
                        if s.options and s.attribute != "aspect_ratio"]
        r = render_v2(optimize_image_v2(prompt, accepted).ir, "stable_diffusion")
    return {"prompt": r["prompt"], "negative_prompt": r["negative_prompt"] or None,
            "width": r["params"]["width"], "height": r["params"]["height"]}


def _same(a: dict, b: dict) -> bool:
    return all(a.get(k) == b.get(k) for k in ("prompt", "negative_prompt", "width", "height"))


def generate(name: str, items: list[dict], variants=VARIANTS) -> dict:
    out_dir = ROOT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    gen_file = out_dir / "generation.json"
    gen = json.loads(gen_file.read_text()) if gen_file.exists() else {}
    todo = [(k, it, v) for k, it in enumerate(items) for v in variants
            if not (gen.get(it["id"], {}).get(v) and _same(gen[it["id"]][v], spec(it["prompt"], v)))]
    if not todo:
        return gen
    from diffusers import DPMSolverMultistepScheduler, StableDiffusionPipeline
    pipe = StableDiffusionPipeline.from_pretrained(SD_MODEL, variant="fp16", dtype=torch.float16)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
    pipe = pipe.to("cuda")
    pipe.enable_attention_slicing()
    pipe.set_progress_bar_config(disable=True)
    for n, (k, it, v) in enumerate(todo, 1):
        s = spec(it["prompt"], v)
        tokens = len(pipe.tokenizer(s["prompt"])["input_ids"])
        torch.cuda.synchronize()
        start = time.perf_counter()
        out = pipe(s["prompt"], negative_prompt=s["negative_prompt"], width=s["width"], height=s["height"],
                   num_inference_steps=STEPS, guidance_scale=GUIDANCE,
                   generator=torch.Generator("cuda").manual_seed(SEED + k))
        torch.cuda.synchronize()
        path = out_dir / f"{it['id']}_{v}.png"
        out.images[0].save(path)
        gen.setdefault(it["id"], {})[v] = {**s, "seconds": round(time.perf_counter() - start, 2),
                                           "clip_tokens": tokens, "truncated": tokens > 77,
                                           "nsfw_flag": bool((out.nsfw_content_detected or [False])[0]),
                                           "path": str(path),
                                           "peak_gib": round(torch.cuda.max_memory_allocated() / 2 ** 30, 2)}
        gen_file.write_text(json.dumps(gen, indent=1), encoding="utf-8")          # saved after every image
        print(f"[{n}/{len(todo)}] {it['id']} {v} {gen[it['id']][v]['seconds']}s", flush=True)
    del pipe
    torch.cuda.empty_cache()
    return gen


@torch.no_grad()
def score(items: list[dict], gen: dict, variants=VARIANTS) -> dict:
    """CLIP vs the original prompt for every image; style adherence for prompts with a stated style."""
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor
    model = CLIPModel.from_pretrained(CLIP_MODEL).to("cuda").eval()
    proc = CLIPProcessor.from_pretrained(CLIP_MODEL)

    scores = {}
    for it in items:
        have = [v for v in variants if v in gen.get(it["id"], {})]
        images = [Image.open(gen[it["id"]][v]["path"]).convert("RGB") for v in have]
        texts = [it["prompt"]] + ([f"a {it['style']}", "a photograph"] if it.get("style") else [])
        batch = proc(text=texts, images=images, return_tensors="pt", padding=True, truncation=True).to("cuda")
        out = model(**batch)                                                  # projected embeddings (CLIPScore)
        img = out.image_embeds / out.image_embeds.norm(dim=-1, keepdim=True)
        txt = out.text_embeds / out.text_embeds.norm(dim=-1, keepdim=True)
        sims = img @ txt.T                                                    # images x texts
        rec = {}
        for i, v in enumerate(have):
            rec[v] = {"clip": round(100 * sims[i, 0].item(), 2)}
            if it.get("style"):
                logits = model.logit_scale.exp() * sims[i, 1:3]
                rec[v]["p_style"] = round(torch.softmax(logits, dim=0)[0].item(), 3)
        scores[it["id"]] = rec
    return scores


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=list(SETS), required=True)
    ap.add_argument("--score-only", action="store_true")
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=[*VARIANTS, *TUNING_VARIANTS])
    args = ap.parse_args()
    if args.set == "heldout" and set(args.variants) & set(TUNING_VARIANTS):
        raise SystemExit("tuning variants run on the dev set only")
    items = json.loads(SETS[args.set].read_text(encoding="utf-8"))
    gen_file = ROOT / args.set / "generation.json"
    gen = json.loads(gen_file.read_text()) if args.score_only else generate(args.set, items, tuple(args.variants))
    meta = {"set": args.set, "sd_model": SD_MODEL, "clip_model": CLIP_MODEL, "steps": STEPS, "guidance": GUIDANCE,
            "gpu": torch.cuda.get_device_name(0), "items": items, "generation": gen,
            "scores": score(items, gen, tuple(v for v in (*VARIANTS, *TUNING_VARIANTS)
                                              if any(v in g for g in gen.values())))}
    (ROOT / args.set / "results.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"wrote {ROOT / args.set / 'results.json'}")


if __name__ == "__main__":
    main()
