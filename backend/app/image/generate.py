"""Optional: generate images locally for the original vs the optimized prompt, and score both with CLIP against the
user's ORIGINAL prompt (so a longer prompt does not win just by being longer). Run in backend/.venv-gpu:

    python -m app.image.generate                    # 40 prompts x 2 images -> data/image_eval/, results.json
    python -m app.image.generate --score-only       # re-score the saved images (generation.json) with CLIP

Model: Stable Diffusion 1.5 (`stable-diffusion-v1-5/stable-diffusion-v1-5`, fp16; licence CreativeML OpenRAIL-M:
use-based restrictions, research use allowed), DPM-Solver++ 25 steps, guidance 7.5, safety checker on, fp16 with
attention slicing (peak 3.2 GB on the RTX 3050 4 GB). SD 1.5 rather than SD-Turbo: SD-Turbo runs without
classifier-free guidance, so it ignores negative prompts, and the Stable Diffusion renderer's negative prompt would not
be tested. Same seed for both images of a prompt. Original = the prompt as typed, 512x512, no negative prompt;
optimized = the Stable Diffusion rendering (keywords, negative prompt, width/height).
Scoring: CLIP ViT-B/32 (`openai/clip-vit-base-patch32`, the CLIPScore model), 100 x cosine(image, original prompt),
after the diffusion model is unloaded.
"""
import argparse
import json
import time

import torch

from app.config import BACKEND_DIR
from app.image.evaluate import PROMPTS
from app.image.optimizer import optimize_image
from app.image.render import render

OUT = BACKEND_DIR.parent / "data" / "image_eval"
SD_MODEL = "stable-diffusion-v1-5/stable-diffusion-v1-5"
CLIP_MODEL = "openai/clip-vit-base-patch32"
STEPS, GUIDANCE, SEED = 25, 7.5, 1000


def generate(items: list[dict]) -> list[dict]:
    from diffusers import DPMSolverMultistepScheduler, StableDiffusionPipeline
    pipe = StableDiffusionPipeline.from_pretrained(SD_MODEL, variant="fp16", dtype=torch.float16)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
    pipe = pipe.to("cuda")
    pipe.enable_attention_slicing()
    pipe.set_progress_bar_config(disable=True)
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for k, it in enumerate(items):
        sd = render(optimize_image(it["prompt"]).ir, "stable_diffusion")
        runs = {"original": {"prompt": it["prompt"], "negative_prompt": None, "width": 512, "height": 512},
                "optimized": {"prompt": sd["prompt"], "negative_prompt": sd["negative_prompt"],
                              "width": sd["params"]["width"], "height": sd["params"]["height"]}}
        rec = {"id": it["id"], "prompt": it["prompt"]}
        for name, r in runs.items():
            tokens = len(pipe.tokenizer(r["prompt"])["input_ids"])
            torch.cuda.synchronize()
            start = time.perf_counter()
            out = pipe(r["prompt"], negative_prompt=r["negative_prompt"], width=r["width"], height=r["height"],
                       num_inference_steps=STEPS, guidance_scale=GUIDANCE,
                       generator=torch.Generator("cuda").manual_seed(SEED + k))
            torch.cuda.synchronize()
            path = OUT / f"{it['id']}_{name}.png"
            out.images[0].save(path)
            rec[name] = {**r, "seconds": round(time.perf_counter() - start, 2), "clip_tokens": tokens,
                         "truncated": tokens > 77, "nsfw_flag": bool((out.nsfw_content_detected or [False])[0]),
                         "path": str(path)}
        results.append(rec)
        print(f"[{k + 1}/{len(items)}] {it['id']} original {rec['original']['seconds']}s, optimized "
              f"{rec['optimized']['seconds']}s", flush=True)
    rec_mem = round(torch.cuda.max_memory_allocated() / 2 ** 30, 2)
    del pipe
    torch.cuda.empty_cache()
    for r in results:
        r["peak_gib"] = rec_mem
    return results


@torch.no_grad()
def clip_scores(results: list[dict]) -> None:
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor
    model = CLIPModel.from_pretrained(CLIP_MODEL).to("cuda").eval()
    proc = CLIPProcessor.from_pretrained(CLIP_MODEL)
    for r in results:
        images = [Image.open(r[v]["path"]).convert("RGB") for v in ("original", "optimized")]
        batch = proc(text=[r["prompt"]], images=images, return_tensors="pt", padding=True, truncation=True).to("cuda")
        out = model(**batch)                          # projected embeddings, as CLIPScore uses them
        img, txt = out.image_embeds, out.text_embeds
        img = img / img.norm(dim=-1, keepdim=True)
        txt = txt / txt.norm(dim=-1, keepdim=True)
        sims = (img @ txt.T).squeeze(-1).tolist()
        r["original"]["clip"], r["optimized"]["clip"] = round(100 * sims[0], 2), round(100 * sims[1], 2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--score-only", action="store_true", help="score the images in generation.json again")
    args = ap.parse_args()
    gen_file = OUT / "generation.json"
    if args.score_only:
        results = json.loads(gen_file.read_text(encoding="utf-8"))
    else:
        results = generate(json.loads(PROMPTS.read_text(encoding="utf-8")))
        gen_file.write_text(json.dumps(results, indent=1), encoding="utf-8")       # saved before scoring
    clip_scores(results)
    meta = {"sd_model": SD_MODEL, "clip_model": CLIP_MODEL, "steps": STEPS, "guidance": GUIDANCE,
            "gpu": torch.cuda.get_device_name(0), "results": results}
    (OUT / "results.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"wrote {OUT / 'results.json'}")


if __name__ == "__main__":
    main()
