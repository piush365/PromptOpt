"""Image mode on the hand-written prompt set: attribute coverage before/after, per attribute and per target.

    python -m app.image.evaluate --out ../evaluation/image_mode.md
    python -m app.image.evaluate --blind ../evaluation/image/blind_test.csv --out ../evaluation/image_blind_test.md

Coverage = the attribute detectors (app.image.attributes) find the attribute in the text: before = the user's
request (scaffolding and filler removed), after = each rendering (with the Stable Diffusion negative prompt). The
same detectors fill the gaps, so "after" mainly checks that every renderer carries every attribute; the split into
"stated by the user" vs "default" is the informative part.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from app.config import BACKEND_DIR
from app.image.attributes import ATTRIBUTES, coverage
from app.image.optimizer import IMAGE_TARGETS, RULE_CODES, i01_clean_request, ImageIR, optimize_image
from app.image.render import as_text, render_all

PROMPTS = BACKEND_DIR.parent / "evaluation" / "image" / "image_prompts.json"
GEN_RESULTS = BACKEND_DIR.parent / "data" / "image_eval" / "results.json"
EXAMPLE_DIR = BACKEND_DIR.parent / "evaluation" / "image" / "examples"
TIE = 0.5                          # CLIP-score differences smaller than this count as a tie
EXAMPLE_IDS = ("img-01", "img-06", "img-13")


def _pct(a: int, n: int) -> str:
    return f"{100 * a / n:.0f}%" if n else "-"


def run(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        o = optimize_image(it["prompt"])
        rendered = render_all(o.ir)
        out.append({**it, "opt": o, "rendered": rendered,
                    "before": coverage(i01_clean_request(ImageIR(subject=it["prompt"])).subject),
                    "after": {t: coverage(as_text(r)) for t, r in rendered.items()}})
    return out


def coverage_table(res: list[dict]) -> str:
    n = len(res)
    lines = ["| attribute | before (stated by user) | after: DALL-E | after: Nano Banana | after: Stable Diffusion | "
             "filled by a default |", "|---|---|---|---|---|---|"]
    for a in ATTRIBUTES:
        before = sum(r["before"][a] for r in res)
        after = [sum(r["after"][t][a] for r in res) for t in IMAGE_TARGETS]
        default = sum(a in r["opt"].ir.defaults for r in res)
        lines.append(f"| {a} | {before}/{n} ({_pct(before, n)}) | " + " | ".join(f"{x}/{n} ({_pct(x, n)})" for x in after)
                     + f" | {default} |")
    mean_b = sum(sum(r["before"].values()) for r in res) / n
    mean_a = {t: sum(sum(r["after"][t].values()) for r in res) / n for t in IMAGE_TARGETS}
    lines.append(f"| **mean attributes per prompt (of {len(ATTRIBUTES)})** | **{mean_b:.1f}** | "
                 + " | ".join(f"**{mean_a[t]:.1f}**" for t in IMAGE_TARGETS) + " | |")
    return "\n".join(lines)


def example(r: dict) -> list[str]:
    o, rd = r["opt"], r["rendered"]
    sd = rd["stable_diffusion"]
    return [f"**{r['id']}: `{r['prompt']}`**  ", f"Rules: {', '.join(o.rules_applied)}; defaults (marked in the UI): "
            f"{', '.join(o.ir.defaults) or 'none'}; avoid from the user: {', '.join(o.ir.avoid_user) or 'none'}\n",
            "| target | optimized prompt |", "|---|---|",
            f"| DALL-E (size {rd['dalle']['params']['size']}) | {rd['dalle']['prompt']} |",
            f"| Nano Banana | {rd['nano_banana']['prompt']} |",
            f"| Stable Diffusion ({sd['params']['width']}x{sd['params']['height']}) | {sd['prompt']}<br>**negative:** "
            f"{sd['negative_prompt']} |", ""]


def report(res: list[dict]) -> str:
    fired = Counter(c for r in res for c in r["opt"].rules_applied)
    lines = ["# Image-generation mode\n",
             "A separate mode the user selects explicitly (no auto-detection; the text pipeline Stage A/B/C is "
             "unchanged and frozen at `final-for-test`). Rule-based: `backend/app/image/` (detectors "
             "`attributes.py`, rules I01-I11 `optimizer.py`, renderers `render.py`).\n",
             f"## 1. Attribute coverage on {len(res)} hand-written vague prompts\n",
             "Prompts: `evaluation/image/image_prompts.json` (varied subjects; some already state a style, ratio or "
             "something to avoid). Before = detectors on the user's request; after = on each rendering.\n",
             coverage_table(res), "",
             "Rules fired: " + ", ".join(f"{c} {fired[c]}" for c in RULE_CODES) + ".\n",
             "The defaults are worded to defer to the subject (\"lighting that suits the scene\", \"let the mood "
             "follow from the subject\"), but section 3 shows that in Stable Diffusion keyword form they are not "
             "neutral in effect for stylised requests. The user's description is never rewritten (tests check every user word "
             "survives in every rendering). Detector limits: a name can look like an attribute (\"a bakery called "
             "Sunrise\" counts as lighting), and a subject that implies a setting or mood (\"an underwater coral "
             "reef\") is not recognised as stating it.\n",
             "## 2. Before / after examples\n"]
    for r in res:
        if r["id"] in EXAMPLE_IDS:
            lines += example(r)
    lines += generation_section()
    lines += ["## 4. All prompts\n", "| id | prompt | stated by user | defaults added | avoid (user) |",
              "|---|---|---|---|---|"]
    for r in res:
        stated = [a for a in ATTRIBUTES if r["before"][a]]
        lines.append(f"| {r['id']} | {r['prompt']} | {', '.join(stated) or '-'} | {len(r['opt'].ir.defaults)} | "
                     f"{', '.join(r['opt'].ir.avoid_user) or '-'} |")
    return "\n".join(lines) + "\n"


def _sign_test(wins: int, losses: int) -> float:
    """Two-sided exact sign test p-value (ties dropped)."""
    from math import comb
    n, k = wins + losses, min(wins, losses)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def thumbnails(results: list[dict], ids: tuple[str, ...] = EXAMPLE_IDS) -> dict[str, list[str]]:
    """Small JPEG copies of the example pairs for the committed report (made with Pillow; without it, existing
    copies are reused)."""
    out = {}
    for r in results:
        if r["id"] not in ids:
            continue
        names = [f"{r['id']}_{v}.jpg" for v in ("original", "optimized")]
        try:
            from PIL import Image
            EXAMPLE_DIR.mkdir(parents=True, exist_ok=True)
            for v, name in zip(("original", "optimized"), names):
                img = Image.open(r[v]["path"]).convert("RGB")
                img.thumbnail((256, 256))
                img.save(EXAMPLE_DIR / name, quality=85)
        except (ImportError, FileNotFoundError):
            if not all((EXAMPLE_DIR / n).exists() for n in names):
                continue
        out[r["id"]] = names
    return out


def generation_section() -> list[str]:
    if not GEN_RESULTS.exists():
        return ["## 3. Local image generation\n", "Not run (`python -m app.image.generate` in `backend/.venv-gpu`).\n"]
    meta = json.loads(GEN_RESULTS.read_text(encoding="utf-8"))
    res = meta["results"]
    n = len(res)
    clip = {v: [r[v]["clip"] for r in res] for v in ("original", "optimized")}
    diffs = [b - a for a, b in zip(clip["original"], clip["optimized"])]
    wins = sum(d >= TIE for d in diffs)
    losses = sum(d <= -TIE for d in diffs)
    secs = {v: sorted(r[v]["seconds"] for r in res) for v in ("original", "optimized")}
    med = lambda xs: xs[len(xs) // 2]  # noqa: E731
    trunc = sum(r["optimized"]["truncated"] for r in res)
    nsfw = sum(r[v]["nsfw_flag"] for r in res for v in ("original", "optimized"))
    thumbs = thumbnails(res)
    lines = ["## 3. Local image generation (optional step)\n",
             f"Model `{meta['sd_model']}` (Stable Diffusion 1.5, fp16; licence **CreativeML OpenRAIL-M**: use-based "
             f"restrictions, research use allowed) on the {meta['gpu']} (4 GB): DPM-Solver++ {meta['steps']} steps, "
             f"guidance {meta['guidance']}, attention slicing, peak {res[0]['peak_gib']} GiB, safety checker on. SD 1.5 "
             "rather than SD-Turbo because SD-Turbo runs without guidance and ignores negative prompts. Same seed for "
             "both images of a prompt. Original = the prompt as typed (512x512, no negative prompt); optimized = the "
             "Stable Diffusion rendering (keywords, negative prompt, width/height).\n",
             f"Scored with CLIP `{meta['clip_model']}` against the user's **original** prompt: 100 x cosine(image, "
             "original prompt). The optimized prompt's extra words are not in the scoring text, so a longer prompt "
             "does not win automatically.\n",
             "| | original prompt | optimized prompt |", "|---|---|---|",
             f"| CLIP score vs original prompt (mean) | {sum(clip['original']) / n:.2f} | "
             f"**{sum(clip['optimized']) / n:.2f}** |",
             f"| time per image, median (mean) | {med(secs['original']):.2f} s ({sum(secs['original']) / n:.2f} s) | "
             f"{med(secs['optimized']):.2f} s ({sum(secs['optimized']) / n:.2f} s) |", "",
             f"Paired over {n} prompts: optimized higher in {wins}, lower in {losses}, tie (|difference| < {TIE}) in "
             f"{n - wins - losses}; mean difference {sum(diffs) / n:+.2f}; two-sided sign test p = "
             f"{_sign_test(wins, losses):.3f}. Optimized prompts over CLIP's 77-token limit (Stable Diffusion cuts them "
             f"off; the user's words come first, so only defaults are lost): {trunc}. Images blacked out by the "
             f"safety checker: {nsfw}.\n",
             "CLIP measures agreement with the request text, not aesthetic quality, and ViT-B/32 is a weak judge of "
             "fine detail; treat this as a check that the defaults do not pull images away from what the user asked "
             "for, not as a quality score.\n"]
    if thumbs:
        lines += ["| prompt | original (CLIP) | optimized (CLIP) |", "|---|---|---|"]
        for r in res:
            if r["id"] in thumbs:
                a, b = thumbs[r["id"]]
                lines.append(f"| {r['id']}: `{r['prompt']}` | ![](image/examples/{a}) {r['original']['clip']:.1f} | "
                             f"![](image/examples/{b}) {r['optimized']['clip']:.1f} |")
        lines.append("")
    drops = sorted(res, key=lambda r: r["optimized"]["clip"] - r["original"]["clip"])[:3]
    drop_thumbs = thumbnails(res, tuple(r["id"] for r in drops))
    lines += ["### Finding: the Stable Diffusion defaults are not neutral for stylised requests\n",
              "The three largest drops (below) are all prompts that state a style. Their words survive (tested), but "
              "the default keywords \"natural lighting\", \"natural balanced color palette\" and \"detailed "
              "subject\" act as photographic cues for SD 1.5 and pull the image away from the requested style or "
              "subject. The defaults were **not** tuned on this set afterwards (that would fit the evaluation "
              "prompts); a fix needs a fresh held-out prompt set.\n",
              "| prompt | Stable Diffusion prompt | original (CLIP) | optimized (CLIP) |", "|---|---|---|---|"]
    for r in drops:
        if r["id"] in drop_thumbs:
            a, b = drop_thumbs[r["id"]]
            lines.append(f"| {r['id']}: `{r['prompt']}` | {r['optimized']['prompt']} | ![](image/examples/{a}) "
                         f"{r['original']['clip']:.1f} | ![](image/examples/{b}) {r['optimized']['clip']:.1f} |")
    lines.append("")
    lines.append("Per prompt (CLIP vs original prompt): " + "; ".join(
        f"{r['id']} {r['original']['clip']:.1f} -> {r['optimized']['clip']:.1f}" for r in res) + ".\n")
    return lines


def blind_report(res: list[dict]) -> str:
    lines = ["# Blind image-prompt test (written by the team without seeing the rules)\n",
             "Reported separately from the 40 hand-written prompts. `meets expectation` is for the team to fill in.\n"]
    if not res:
        return "\n".join(lines + ["No rows filled in yet (`evaluation/image/blind_test.csv`)."]) + "\n"
    lines += ["| id | prompt | target | stated by user | optimized prompt | expected behaviour (team) | meets expectation |",
              "|---|---|---|---|---|---|---|"]
    for r in res:
        t = r["target"] if r["target"] in IMAGE_TARGETS else "dalle"
        rd = r["rendered"][t]
        text = rd["prompt"] + (f" / negative: {rd['negative_prompt']}" if rd.get("negative_prompt") else "")
        stated = [a for a in ATTRIBUTES if r["before"][a]]
        lines.append(f"| {r['id']} | {r['prompt']} | {t} | {', '.join(stated) or '-'} | {text.replace('|', '/')} | "
                     f"{r['expected']} |  |")
    return "\n".join(lines) + "\n"


def load_blind(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{"id": r["id"], "prompt": r["prompt"].strip(), "target": r["target_model"].strip().lower(),
                 "expected": r["expected_behaviour"].strip()} for r in csv.DictReader(f) if r["prompt"].strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    items = load_blind(args.blind) if args.blind else json.loads(PROMPTS.read_text(encoding="utf-8"))
    res = run(items)
    text = blind_report(res) if args.blind else report(res)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
