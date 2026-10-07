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
from app.image.v2 import optimize_image_v2, render_all_v2

PROMPTS = BACKEND_DIR.parent / "evaluation" / "image" / "image_prompts.json"
GEN_RESULTS = BACKEND_DIR.parent / "data" / "image_eval" / "dev" / "results_v1_report.json"   # v1 run, as reported
SET_RESULTS = {s: BACKEND_DIR.parent / "data" / "image_eval" / s / "results.json" for s in ("dev", "heldout")}
HELDOUT = BACKEND_DIR.parent / "evaluation" / "image" / "heldout_prompts.json"
VARIANT_LABELS = {"original": "original prompt", "v1": "v1 (default keywords)", "v2": "v2 (final)",
                  "v2_suggested": "v2 + all first suggestions (simulated user)",
                  "v2_draft": "tuning: v2 draft (+ automatic negatives and quality term)",
                  "v2_no_default_negatives": "tuning: v2 draft without the automatic negatives"}
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
             "`attributes.py`; v1: rules I01-I11 `optimizer.py`, renderers `render.py`; v2, the app's default: "
             "`v2.py`). Contents: v1 on the dev set (as first reported), the problem it showed, v2, and v1 vs v2 on a "
             "held-out set run once.\n",
             f"## 1. Attribute coverage on {len(res)} hand-written vague prompts (dev set)\n",
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
             "## 2. Before / after examples (v1, then v2)\n"]
    for r in res:
        if r["id"] in EXAMPLE_IDS:
            lines += example(r)
    lines += ["### v2 (the app's default since this phase)\n",
              "v2 adds only what cannot conflict with the request; every other missing attribute is offered as a "
              "suggestion (a clickable chip in the UI) and inserted only if the user picks it. On the dev prompts:\n",
              v2_coverage_table([{"id": r["id"], "prompt": r["prompt"]} for r in res]), ""]
    for r in res:
        if r["id"] in EXAMPLE_IDS:
            lines += v2_example(r)
    lines += generation_section()
    lines += ["### 3b. v2 on the dev set (tuning check)\n",
              "The dev set was used to check the fix and choose the final v2 (the v2 draft and its variant are "
              "tuning rows); these numbers are not the evidence.\n"] + variant_section("dev")
    lines += ["### 3c. Held-out set, run once: original vs v1 vs v2\n",
              "30 new prompts (`evaluation/image/heldout_prompts.json`), written and committed before any v2 code "
              "(commit d656add); the team's 10 blind prompts were not filled in yet, so n = 30. One run, no changes "
              "afterwards.\n"] + variant_section("heldout") + heldout_examples()
    lines += LESSON
    lines += ["## 5. All dev prompts (v1)\n", "| id | prompt | stated by user | defaults added | avoid (user) |",
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
    lines = ["## 3. Local image generation (optional step)\n", "### 3a. v1 on the dev set (as first reported)\n",
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
    lines += ["#### Finding: the Stable Diffusion defaults are not neutral for stylised requests\n",
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


def _conflict_dropped(o) -> bool:
    """An avoid suggestion not offered because the request needs that thing (a logo needs text, ...)."""
    from app.image.v2 import SUGGESTIONS, avoid_options
    return len(avoid_options(o.ir)) < len(SUGGESTIONS["avoid"])


def v2_coverage_table(items: list[dict]) -> str:
    """v2 on the dev prompts: per attribute, stated by the user, added automatically, or offered as a suggestion."""
    outs = [optimize_image_v2(it["prompt"]) for it in items]
    n = len(outs)
    lines = ["| attribute | stated by user | added automatically | offered as a suggestion |", "|---|---|---|---|"]
    for a in ATTRIBUTES:
        stated = sum(bool(o.detected[a]) for o in outs)
        offered = sum(any(s.attribute == a for s in o.suggestions) for o in outs)
        if a == "avoid":
            auto = sum(bool(o.ir.avoid_user) for o in outs)            # the user's own "no ..." list only
        elif a == "aspect_ratio":
            auto = sum(o.ir.aspect_ratio is not None for o in outs)
        else:
            auto = 0
        lines.append(f"| {a} | {stated}/{n} | {auto}/{n} | {offered}/{n} |")
    lines.append(f"\nNothing else is added automatically (no quality term, no default negatives). Style chunks moved to "
                 f"the front of the Stable Diffusion prompt: {sum(bool(o.ir.style_first) for o in outs)} prompts. "
                 "The usual negatives are offered as an \"avoid\" suggestion; ones the request needs are not offered "
                 f"(text/logos for a logo or poster, ...): {sum(_conflict_dropped(o) for o in outs)} prompts.")
    return "\n".join(lines)


def v2_example(it: dict) -> list[str]:
    o = optimize_image_v2(it["prompt"])
    rd = render_all_v2(o.ir)
    sd = rd["stable_diffusion"]
    sugg = "; ".join(f"{s.attribute}: {' / '.join(s.options)}" if s.options else f"{s.attribute}: hint"
                     for s in o.suggestions)
    return [f"**{it['id']} with v2: `{it['prompt']}`**  ", f"Rules: {', '.join(o.rules_applied)}. Suggestions offered "
            f"(nothing inserted): {sugg}.\n", "| target | optimized prompt (v2) |", "|---|---|",
            f"| DALL-E ({rd['dalle']['params']['size']}) | {rd['dalle']['prompt']} |",
            f"| Nano Banana | {rd['nano_banana']['prompt']} |",
            f"| Stable Diffusion ({sd['params']['width']}x{sd['params']['height']}) | {sd['prompt']}<br>**negative:** "
            f"{sd['negative_prompt']} |", ""]


def variant_section(name: str) -> list[str]:
    """Original vs v1 vs v2 vs v2 + suggestions on one prompt set (new-format results)."""
    path = SET_RESULTS[name]
    if not path.exists():
        return [f"Not run yet (`python -m app.image.generate --set {name}` in `backend/.venv-gpu`).\n"]
    meta = json.loads(path.read_text(encoding="utf-8"))
    items, gen, sc = meta["items"], meta["generation"], meta["scores"]
    variants = [v for v in VARIANT_LABELS if all(v in sc[it["id"]] for it in items)]
    styled = [it for it in items if it.get("style")]
    lines = ["| variant | CLIP vs original prompt (mean) | vs original: higher / lower / tie | sign test p | "
             f"style kept (of {len(styled)} styled prompts) | P(stated style vs photo), mean | time per image, median |",
             "|---|---|---|---|---|---|---|"]
    med = lambda xs: sorted(xs)[len(xs) // 2]  # noqa: E731
    for v in variants:
        clip = [sc[it["id"]][v]["clip"] for it in items]
        mean = sum(clip) / len(clip)
        if v == "original":
            cmp_cell, p_cell = "-", "-"
        else:
            d = [sc[it["id"]][v]["clip"] - sc[it["id"]]["original"]["clip"] for it in items]
            w, lo = sum(x >= TIE for x in d), sum(x <= -TIE for x in d)
            cmp_cell, p_cell = f"{w} / {lo} / {len(d) - w - lo}", f"{_sign_test(w, lo):.3f}"
        ps = [sc[it["id"]][v]["p_style"] for it in styled]
        kept = sum(p > 0.5 for p in ps)
        secs = [gen[it["id"]][v]["seconds"] for it in items]
        lines.append(f"| {VARIANT_LABELS[v]} | **{mean:.2f}** | {cmp_cell} | {p_cell} | {kept}/{len(ps)} | "
                     f"{sum(ps) / len(ps):.2f} | {med(secs):.2f} s |" if ps else
                     f"| {VARIANT_LABELS[v]} | **{mean:.2f}** | {cmp_cell} | {p_cell} | - | - | {med(secs):.2f} s |")
    if "v2" in variants:
        moved = [(it, sc[it["id"]]["v2"]["clip"] - sc[it["id"]]["original"]["clip"]) for it in items]
        moved = [(it, d) for it, d in moved if abs(d) >= TIE]
        if moved:
            lines.append("")
            lines.append("Where v2 differs from the original by at least 0.5: " + "; ".join(
                f"{it['id']} `{it['prompt']}` {d:+.1f} (v2 SD prompt `{gen[it['id']]['v2']['prompt']}`"
                + (f", negative `{gen[it['id']]['v2']['negative_prompt']}`" if gen[it['id']]['v2']['negative_prompt'] else "")
                + f", {gen[it['id']]['v2']['width']}x{gen[it['id']]['v2']['height']})" for it, d in moved) + ".")
    trunc = sum(g[v]["truncated"] for g in gen.values() for v in g)
    nsfw = sum(g[v]["nsfw_flag"] for g in gen.values() for v in g)
    lines += ["", f"{len(items)} prompts; same seed for every variant of a prompt; prompts over the 77-token CLIP limit: "
                  f"{trunc}; images blacked out by the safety checker: {nsfw}. Style kept = CLIP zero-shot prefers "
                  "\"a <stated style>\" over \"a photograph\" for the image (styles annotated in the prompt file before "
                  "any run).\n",
              "Per prompt, CLIP vs original prompt (" + " / ".join(variants) + "): " + "; ".join(
                  f"{it['id']} " + " / ".join(f"{sc[it['id']][v]['clip']:.1f}" for v in variants) for it in items)
              + ".\n"]
    return lines


def heldout_examples() -> list[str]:
    path = SET_RESULTS["heldout"]
    if not path.exists():
        return []
    meta = json.loads(path.read_text(encoding="utf-8"))
    sc, gen = meta["scores"], meta["generation"]
    styled = [it for it in meta["items"] if it.get("style")][:3]
    try:
        from PIL import Image
    except ImportError:
        Image = None
    lines = ["| held-out prompt | original | v1 | v2 |", "|---|---|---|---|"]
    for it in styled:
        cells = []
        for v in ("original", "v1", "v2"):
            name = f"{it['id']}_{v}.jpg"
            if Image is not None and Path(gen[it["id"]][v]["path"]).exists():
                EXAMPLE_DIR.mkdir(parents=True, exist_ok=True)
                img = Image.open(gen[it["id"]][v]["path"]).convert("RGB")
                img.thumbnail((256, 256))
                img.save(EXAMPLE_DIR / name, quality=85)
            cells.append(f"![](image/examples/{name}) CLIP {sc[it['id']][v]['clip']:.1f}, P(style) "
                         f"{sc[it['id']][v]['p_style']:.2f}" if (EXAMPLE_DIR / name).exists() else "-")
        lines.append(f"| {it['id']}: `{it['prompt']}` ({it['style']}) | " + " | ".join(cells) + " |")
    return lines + [""]


LESSON = [
    "## 4. Lesson learned\n",
    "* A default that is \"neutral\" in words is not neutral in effect. For Stable Diffusion, keyword defaults such as "
    "\"natural lighting\", \"natural balanced color palette\" and \"detailed subject\" are photographic cues and "
    "override a stated style or even the subject (v1, section 3a).",
    "* Coverage of attributes is the wrong target on its own: v1 reached 9.0 of 9 attributes per prompt and made the "
    "images match the request worse. The image model's output against the user's own request is the check that "
    "matters.",
    "* Even \"safe\" automatic additions were not safe: a v2 draft that added only conflict-filtered negatives and "
    "the quality term \"high quality\" still lowered agreement with the request on the dev set (29.21 vs 29.95) and "
    "lost the watercolor style; without them it matched the original (29.82, style kept 5/6) (section 3b). Final v2 "
    "adds nothing automatically except what the user's own words imply (their avoid list, a ratio they ask for, their "
    "style moved to the front for Stable Diffusion); everything else, the usual negatives included, is a suggestion "
    "the user chooses.",
    "* CLIP against the original prompt detects harm, not improvement: it rewards agreement with the user's own "
    "wording. On the held-out set v2 ties the original on 26 of 30 prompts; the 4 differences are things v2 does on "
    "purpose (a 16:9 or poster ratio the user implied changes the image shape; \"without clouds\" moves clouds to the "
    "negative prompt, while CLIP, which ignores negation, scores the text \"... without clouds\" higher for images "
    "with clouds; removing \"pls create an image of\"). v2's value is in what it does not break (style kept 12/12 "
    "vs v1 10/12) and in the user-chosen suggestions, which a CLIP-vs-original score cannot measure.",
    "* Accepting every suggestion at once is not a good default either (\"v2 + all first suggestions\" lowers CLIP "
    "vs the original on held-out, p < 0.001): suggestions are options to pick, which is why nothing is preselected.",
    "* Protocol: v1's numbers stay as first reported (dev set); v2 was checked and its final configuration chosen on "
    "the dev set only; the 30 held-out prompts were written and committed before any v2 code, and run once (3c).\n",
]


def run_blind(items: list[dict]) -> list[dict]:
    """The app's optimizer (v2) on the team's prompts, as a user sees it before accepting any suggestion."""
    out = []
    for it in items:
        o = optimize_image_v2(it["prompt"], target=it["target"])
        out.append({**it, "v2": o, "rendered": render_all_v2(o.ir)})
    return out


def blind_report(res: list[dict]) -> str:
    lines = ["# Blind image-prompt test (written by the team without seeing the rules)\n",
             "Reported separately from the 40 hand-written prompts. Optimized prompt = the app's optimizer (v2), before "
             "the user accepts any suggestion; suggestions = the attributes offered as clickable chips. "
             "`meets expectation` is for the team to fill in.\n"]
    if not res:
        return "\n".join(lines + ["**Not completed.** The team has not filled in `evaluation/image/blind_test.csv` "
                                   "(0 of 10 rows), so there is no blind result; the held-out set "
                                   "(`image_mode.md`) is the independent check."]) + "\n"
    lines += ["| id | prompt | target | stated by user | optimized prompt (v2) | suggestions offered | expected behaviour "
              "(team) | meets expectation |", "|---|---|---|---|---|---|---|---|"]
    for r in res:
        rd = r["rendered"][r["target"]]
        text = rd["prompt"] + (f" / negative: {rd['negative_prompt']}" if rd.get("negative_prompt") else "")
        stated = [a for a in ATTRIBUTES if r["v2"].detected[a]]
        offered = [s.attribute for s in r["v2"].suggestions]
        lines.append(f"| {r['id']} | {r['prompt']} | {r['target']} | {', '.join(stated) or '-'} | "
                     f"{text.replace('|', '/')} | {', '.join(offered) or '-'} | {r['expected']} |  |")
    return "\n".join(lines) + "\n"


TARGET_ALIASES = {"dall-e": "dalle", "dall_e": "dalle", "nano banana": "nano_banana", "nano-banana": "nano_banana",
                  "stable diffusion": "stable_diffusion", "stable-diffusion": "stable_diffusion", "sd": "stable_diffusion"}


def load_blind(path: Path) -> list[dict]:
    """Filled rows of the team's blind CSV (rows without a prompt are skipped); a bad target stops with a message."""
    items = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if not (r.get("prompt") or "").strip():
                continue
            raw = r["target_model"].strip().lower()
            target = TARGET_ALIASES.get(raw, raw)
            if target not in IMAGE_TARGETS:
                raise SystemExit(f"{r['id']}: target_model must be one of {IMAGE_TARGETS}; got {raw!r}")
            items.append({"id": r["id"], "prompt": r["prompt"].strip(), "target": target,
                          "expected": r["expected_behaviour"].strip()})
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blind", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    items = load_blind(args.blind) if args.blind else json.loads(PROMPTS.read_text(encoding="utf-8"))
    res = run_blind(items) if args.blind else run(items)
    text = blind_report(res) if args.blind else report(res)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
