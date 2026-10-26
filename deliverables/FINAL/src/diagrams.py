"""Block diagrams for the final report and deck. Every arrow carries a label saying what flows along it.
Usage: python diagrams.py OUT_DIR  -> report versions (navy) as diag_*.png and deck versions (green) as deck_*.png.
Example numbers: the review example run through the real pipeline (Stage A scores, Stage C answer, Compare on
gpt-oss-120b on Groq); everything else from evaluation/FINAL_RESULTS.md and docs/documentation/."""
import sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, FancyArrowPatch

OUT = sys.argv[1]

PALETTES = {
    "diag": dict(ink="#1D2433", edge="#1F3A5F", a="#E8EEF7", b="#E6F2EA", c="#FFF4DD", d="#F3E8F7", e="#FDECEC",
                 dark="#1F3864", darktext="#FFFFFF", label="#3C4A5C", arrow="#374151", note="#5B6573", grey="#F2F4F7"),
    "deck": dict(ink="#1E4926", edge="#457C5B", a="#E4F2EA", b="#D3E8DB", c="#FFF4DD", d="#EAF4EE", e="#FBE9E7",
                 dark="#1E4926", darktext="#F5FFF9", label="#2F5D3F", arrow="#2F5D3F", note="#4B6B57", grey="#F5FFF9"),
}
P = None
FONT = "DejaVu Sans"
plt.rcParams.update({"font.family": FONT})


class D:
    """A canvas in abstract units (1 unit = 1 inch at the figure size)."""

    def __init__(self, w, h):
        self.fig = plt.figure(figsize=(w, h))
        self.ax = self.fig.add_axes([0, 0, 1, 1]); self.ax.set_xlim(0, w); self.ax.set_ylim(0, h); self.ax.axis("off")
        self.n = {}

    def box(self, key, x, y, w, h, title, body="", fill="a", dark=False, tsize=11.5, bsize=10, radius=0.08, lw=1.6,
            align="center", edge=None):
        fc = P["dark"] if dark else P.get(fill, fill)
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}", fc=fc,
                                         ec=edge or P["edge"], lw=lw))
        tc = P["darktext"] if dark else P["ink"]
        ha = "center" if align == "center" else "left"
        tx = x + w / 2 if align == "center" else x + 0.15
        if body:
            self.ax.text(tx, y + h - 0.16, title, ha=ha, va="top", fontsize=tsize, fontweight="bold", color=tc, wrap=True)
            nt = title.count("\n") + 1
            self.ax.text(tx, y + h - 0.16 - nt * tsize / 72 * 1.3 - 0.07, body, ha=ha, va="top", fontsize=bsize, color=tc,
                         linespacing=1.35)
        else:
            self.ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=tsize, fontweight="bold",
                         color=tc, linespacing=1.3)
        self.n[key] = (x, y, w, h)

    def diamond(self, key, cx, cy, w, h, text, size=10.5):
        pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
        self.ax.add_patch(Polygon(pts, closed=True, fc=P["c"], ec=P["edge"], lw=1.6))
        self.ax.text(cx, cy, text, ha="center", va="center", fontsize=size, fontweight="bold", color=P["ink"],
                     linespacing=1.25)
        self.n[key] = (cx - w / 2, cy - h / 2, w, h)

    def pt(self, key, side, frac=0.5):
        x, y, w, h = self.n[key]
        return {"l": (x, y + h * frac), "r": (x + w, y + h * frac), "t": (x + w * frac, y + h),
                "b": (x + w * frac, y)}[side]

    def arrow(self, a, b, label=None, via=None, lpos=0.5, loff=(0, 0.13), lsize=9.5, color=None, ha="center",
              dashed=False):
        """a, b: (key, side[, frac]) or points. via: list of intermediate points (orthogonal routing)."""
        pa = self.pt(*a) if isinstance(a[0], str) else a
        pb = self.pt(*b) if isinstance(b[0], str) else b
        pts = [pa] + (via or []) + [pb]
        col = color or P["arrow"]
        ls = (0, (4, 3)) if dashed else "-"
        for p, q in zip(pts[:-2], pts[1:-1]):
            self.ax.plot([p[0], q[0]], [p[1], q[1]], color=col, lw=1.5, ls=ls, solid_capstyle="butt")
        self.ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=15, color=col, lw=1.5,
                                          linestyle=ls, shrinkA=0, shrinkB=1))
        if label:
            # label on the longest segment, at lpos
            segs = list(zip(pts[:-1], pts[1:]))
            p, q = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
            lx, ly = p[0] + (q[0] - p[0]) * lpos + loff[0], p[1] + (q[1] - p[1]) * lpos + loff[1]
            self.ax.text(lx, ly, label, ha=ha, va="bottom", fontsize=lsize, color=P["label"], style="italic",
                         linespacing=1.2, bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9))

    def text(self, x, y, s, size=10, color=None, bold=False, ha="left", va="top", italic=False):
        self.ax.text(x, y, s, fontsize=size, color=color or P["ink"], fontweight="bold" if bold else "normal", ha=ha,
                     va=va, style="italic" if italic else "normal", linespacing=1.35)

    def frame(self, x, y, w, h, title):
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12", fc="none",
                                         ec=P["note"], lw=1.2, ls=(0, (5, 3))))
        self.ax.text(x + 0.15, y + h - 0.1, title, fontsize=10.5, fontweight="bold", color=P["note"], va="top")

    def save(self, name, prefix):
        self.fig.savefig(f"{OUT}/{prefix}_{name}.png", dpi=200, facecolor="white")
        plt.close(self.fig)


# ------------------------------------------------------------------ 1. the story: one example through every stage
def story(prefix):
    d = D(15, 6.4)
    W, H = 4.0, 2.65
    xs = [0.3, 5.5, 10.7]
    top, bot = 3.45, 0.3
    d.box("in", xs[0], top, W, H, "1. The user types",
          "\u201chey can you just tell me if this\nreview is good or bad\u201d\n+ pasted review: \u201cThe battery lasts\ntwo days and the camera is great, but\nthe phone heats up while gaming.\u201d",
          fill="grey", align="left")
    d.box("a", xs[1], top, W, H, "2. Stage A: understand",
          "Task type? summarization 0.52,\n   classification 0.35: below 0.6, not sure\nFiller: \u201chey\u201d, \u201ccan you\u201d, \u201cjust\u201d\nNo answer format stated\nText is attached",
          fill="a", align="left")
    d.box("b", xs[2], top, W, H, "3. Stage B: fix with rules",
          "B07 tidy + B01 remove filler:\n\u201cTell me if this review is good or bad.\u201d\nCategory not sure: no rule guesses\na format. Task category unresolved,\nso the prompt goes to Stage C",
          fill="b", align="left")
    d.box("c", xs[2], bot, W, H, "4. Stage C: small trained model",
          "Asked for: format, constraints, category\nAnswer passed every check:\n  format: \u201cProvide only the label.\u201d\n  category: \u201cclassification\u201d\nThe user is asked to confirm it",
          fill="c", align="left")
    d.box("r", xs[1], bot, W, H, "5. Written for the target LLM",
          "### Task\nTell me if this review is good or bad.\n### Context   (the review)\n### Output format\nProvide only the label.",
          fill="d", align="left")
    d.box("cmp", xs[0], bot, W, H, "6. Compare on a real model",
          "OpenAI GPT model (gpt-oss-120b)\nVague prompt: 166-token explanation\nOptimized prompt: \u201cgood\u201d (41 tokens)\nTotal tokens: 270 vs 162 (\u221240%)\nTime: 353 ms vs 97 ms",
          fill="e", align="left")
    d.arrow(("in", "r"), ("a", "l"), "prompt +\nreview", lsize=9)
    d.arrow(("a", "r"), ("b", "l"), "what is\nmissing", lsize=9)
    d.arrow(("b", "b"), ("c", "t"), "unresolved: task category", loff=(0.15, -0.15), ha="left", lsize=9)
    d.arrow(("c", "l"), ("r", "r"), "final\nprompt", lsize=9)
    d.arrow(("r", "l"), ("cmp", "r"), "GPT\nrendering", lsize=9)
    d.save("story", prefix)


# ------------------------------------------------------------------ 2. architecture, each block with the example
def architecture(prefix):
    d = D(15, 7.0)
    y, h, w = 3.2, 2.3, 2.05
    xs = [0.3, 2.85, 5.4, 7.95]
    boxes = [("ui", "Web UI (React)", "e.g. \u201chey can you just\ntell me if this review\nis good or bad\u201d\n+ the review", "grey"),
             ("api", "FastAPI", "e.g. POST\n/api/optimize,\ntarget GPT,\ncategory auto", "grey"),
             ("a", "Stage A", "e.g. summarization\n0.52 (not sure);\nfiller \u201chey can\nyou just\u201d", "a"),
             ("b", "Stage B: 15 rules", "e.g. filler removed;\nno format guessed;\ntask category\nunresolved", "b")]
    for (k, t, b, f), x in zip(boxes, xs):
        d.box(k, x, y, w, h, t, b, fill=f, tsize=11, bsize=9.2)
    d.diamond("q", 11.5, y + h / 2, 2.3, 1.9, "Category or\nreference\nunresolved?", size=9.5)
    d.box("c", 10.45, 5.85, 2.1, 1.0, "Stage C\nLoRA model", fill="c", tsize=10.5)
    d.text(7.95, 6.75, "e.g. adds \u201cProvide only the label.\u201d;\nsuggests classification", size=8.6,
           color=P["note"], italic=True)
    d.box("ir", 13.05, y, 1.65, h, "Renderers", "IR written per\nLLM, e.g.\n### Task\n### Context\n### Output format",
          fill="d", tsize=10.5, bsize=8.6)
    d.box("db", 2.85, 0.3, 4.6, 1.3, "Database (10 tables)", "written only through repository.py,\none commit per request",
          fill="grey", tsize=10.5, bsize=9.2)
    d.box("cmp", 9.0, 0.3, 5.7, 1.3, "Compare: original vs optimized on a real model",
          "e.g. total tokens 270 vs 162 (\u221240%), OpenAI GPT model gpt-oss-120b", fill="e", tsize=10.5, bsize=9.2)
    d.arrow(("ui", "r"), ("api", "l"), "request", lsize=8.8)
    d.arrow(("api", "r"), ("a", "l"), "prompt", lsize=8.8)
    d.arrow(("a", "r"), ("b", "l"), "features", lsize=8.8)
    d.arrow(("b", "r"), ("q", "l"), "IR", lsize=8.8)
    d.arrow(("q", "t"), ("c", "b", 0.5), "yes (6.4%)", loff=(0.1, -0.1), ha="left", lsize=8.8)
    d.arrow(("c", "r"), ("ir", "t", 0.5), "filled fields", via=[(13.875, 6.35)], lpos=0.45, lsize=8.8, loff=(0.1, -0.1), ha="left")
    d.arrow(("q", "r"), ("ir", "l"), "no", lsize=8.8)
    d.arrow(("ir", "b"), ("cmp", "t", (13.875 - 9.0) / 5.7), "rendered prompt", loff=(0.1, -0.1), ha="left", lsize=8.8)
    d.arrow(("api", "b"), ("db", "t", (3.875 - 2.85) / 4.6), "stores results", loff=(0.1, -0.1), ha="left", lsize=8.8)
    d.save("architecture", prefix)


# ------------------------------------------------------------------ 3. Stage A, every arrow labelled
def stage_a(prefix):
    d = D(14.5, 6.6)
    d.box("p", 0.3, 3.0, 1.75, 1.0, "Prompt\n(+ pasted text)", fill="grey", tsize=10.5)
    d.box("emb", 2.85, 4.6, 2.3, 1.1, "Sentence embedding\nall-MiniLM-L6-v2", fill="a", tsize=10)
    d.box("kw", 2.85, 2.55, 2.3, 1.1, "Keyword cues\n(weighted regex)", fill="a", tsize=10)
    d.box("knn", 6.0, 5.2, 2.4, 1.05, "k-NN vote\n25 nearest train prompts", fill="a", tsize=10)
    d.box("head", 6.0, 3.75, 2.4, 1.05, "Logistic-regression\nhead", fill="a", tsize=10)
    d.box("bl", 9.2, 3.8, 2.75, 1.75, "Blend\n0.5 \u00d7 (0.7 \u00d7 k-NN\n+ 0.3 \u00d7 cues)\n+ 0.5 \u00d7 head",
          fill="b", tsize=10)
    d.diamond("bs", 13.2, 4.675, 1.9, 1.5, "nearest\nsimilarity\n< 0.3?", size=9.5)
    d.box("oth", 12.25, 5.85, 1.9, 0.6, "\u201cother\u201d gets \u2265 half", fill="c", tsize=9)
    d.box("cat", 12.15, 2.35, 2.1, 1.1, "Category +\nconfidence\n(top score)", fill="b", tsize=10)
    d.frame(2.85, 0.25, 5.6, 1.95, "Rule detectors (spaCy + regex)")
    for i, (t, x, y) in enumerate([("A02 output format", 3.05, 1.1), ("A03 constraints", 5.8, 1.1),
                                   ("A04 filler / repeats", 3.05, 0.4), ("A05 ambiguous refs", 5.8, 0.4)]):
        d.box(f"r{i}", x, y, 2.45, 0.55, t, fill="a", tsize=9.5)
    d.box("pf", 11.6, 0.4, 2.65, 1.15, "PromptFeatures\n(Pydantic object\nto Stage B)", dark=True, tsize=10)
    d.arrow(("p", "r", 0.8), ("emb", "l"), "text", via=[(2.45, 3.8), (2.45, 5.15)], lpos=0.5, loff=(0.05, 0.05))
    d.arrow(("p", "r", 0.3), ("kw", "l"), "words", via=[(2.45, 3.3), (2.45, 3.1)], lpos=0.7, loff=(0, 0.05))
    d.arrow(("p", "b"), ("r0", "l"), "text", via=[(1.17, 1.37)], lpos=0.6)
    d.arrow(("emb", "r", 0.75), ("knn", "l"), "384-number\nvector", via=[(5.55, 5.42), (5.55, 5.72)],
            loff=(0, 0.02), lsize=8.3)
    d.arrow(("emb", "r", 0.25), ("head", "l", 0.7), None, via=[(5.55, 4.88), (5.55, 4.49)])
    d.arrow(("kw", "r"), ("head", "l", 0.3), "cue features", via=[(5.75, 3.1), (5.75, 4.07)], lpos=0.3,
            loff=(-0.45, 0.04), lsize=8.3)
    d.arrow(("knn", "r"), ("bl", "t", 0.5), "6 vote shares", via=[(10.575, 5.72)], lpos=0.4, lsize=8.3)
    d.arrow(("head", "r"), ("bl", "l", (4.275 - 3.8) / 1.75), "6 probabilities", lsize=8.3, loff=(0, 0.05))
    d.arrow(("kw", "b"), ("bl", "b", 0.5), "cue weights", via=[(4.0, 2.35), (10.575, 2.35)], lpos=0.6, lsize=8.3)
    d.arrow(("bl", "r"), ("bs", "l"), None)
    d.arrow(("bs", "t"), ("oth", "b", (13.2 - 12.25) / 1.9), "yes", lsize=8.3, loff=(0.08, -0.1), ha="left")
    d.arrow(("bs", "b"), ("cat", "t", (13.2 - 12.15) / 2.1), "no", lsize=8.3, loff=(0.1, -0.1), ha="left")
    d.arrow(("cat", "b"), ("pf", "t", (13.2 - 11.6) / 2.65), "task type,\nconfidence, scores", lsize=8.3,
            loff=(0.1, -0.25), ha="left")
    d.arrow(("r3", "r"), ("pf", "l", 0.4), "missing format, constraints,\nfiller, references", lsize=8.3,
            via=[(10.2, 0.67), (10.2, 0.86)], lpos=0.5, loff=(-0.25, 0.03))
    d.save("stage_a", prefix)


# ------------------------------------------------------------------ 4. confidence for the example (bar chart)
def confidence(prefix):
    cats = ["closed_qa", "info_extraction", "classification", "summarization", "coding", "other"]
    knn = [0.000, 0.050, 0.690, 0.181, 0.019, 0.060]
    head = [0.001, 0.003, 0.008, 0.858, 0.010, 0.120]
    final = [0.001, 0.026, 0.349, 0.520, 0.014, 0.090]
    fig, ax = plt.subplots(figsize=(10, 4.3))
    import numpy as np
    x = np.arange(len(cats)); w = 0.26
    c1, c2, c3 = ("#9FB6D6", "#5C7FB0", P["dark"]) if prefix == "diag" else ("#B9D8C5", "#7FB394", P["dark"])
    ax.bar(x - w, knn, w, color=c1, label="k-NN vote (similar train prompts)")
    ax.bar(x, head, w, color=c2, label="logistic-regression head")
    ax.bar(x + w, final, w, color=c3, label="final score = 0.5 × k-NN + 0.5 × head (no keyword cue fired)")
    for i, v in enumerate(final):
        if v > 0.05:
            ax.text(x[i] + w, v + 0.02, f"{v:.2f}", ha="center", fontsize=10, fontweight="bold", color=P["ink"])
    ax.axhline(0.6, color="#B42318", lw=1.4, ls=(0, (5, 3)))
    ax.text(5.45, 0.615, "0.6 gate", color="#B42318", fontsize=10, ha="right", va="bottom")
    ax.set_xticks(x, cats, fontsize=10); ax.set_ylim(0, 1.0); ax.set_ylabel("score (sums to 1 per method)")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    ax.set_title("“hey can you just tell me if this review is good or bad”: top score 0.52 (summarization) < 0.6, "
                 "so the category is not reliable", fontsize=10.5, color=P["ink"])
    fig.tight_layout(); fig.savefig(f"{OUT}/{prefix}_confidence.png", dpi=200, facecolor="white"); plt.close(fig)


# ------------------------------------------------------------------ 5. Stage B decision flow
def stage_b(prefix):
    d = D(14, 6.2)
    d.box("in", 0.3, 4.4, 1.9, 1.2, "Stage A\nfeatures +\nprompt", fill="grey", tsize=10)
    d.box("b07", 2.8, 4.4, 2.1, 1.2, "B07 structure\nmove pasted data\nout of the task", fill="b", tsize=9.5)
    d.box("b01", 5.5, 4.4, 2.1, 1.2, "B01 filler\nB02 duplicates", fill="b", tsize=10)
    d.box("att", 8.2, 4.4, 2.3, 1.2, "B09\u2013B15\nattachment rules\n(only with a file)", fill="b", tsize=9.5)
    d.diamond("g", 12.1, 5.0, 2.5, 1.6, "Stage A\nconfidence\n\u2265 0.6?", size=10)
    d.box("cat", 11.85, 1.85, 2.0, 1.8, "Category rules\nB06 labels\nB05 language\nB04 length\nB03 format",
          fill="b", tsize=9.5)
    d.diamond("grp", 7.3, 2.75, 3.0, 1.75, "QA + extraction +\nsummary \u2265 0.6\nand text attached?", size=9.5)
    d.box("b08", 6.05, 0.2, 2.5, 1.1, "B08 group rule\n\u201cAnswer from the provided\ntext in \u2264 3 sentences\u201d",
          fill="b", tsize=9)
    d.box("un", 2.9, 2.2, 2.5, 1.1, "Mark \u201ctask category\u201d\nunresolved \u2192 Stage C", fill="c", tsize=9.5)
    d.box("out", 10.8, 0.25, 2.9, 1.0, "IR + change log\n(before / after per rule)", dark=True, tsize=10)
    d.box("u", 0.3, 2.0, 1.9, 1.5, "Ambiguous\n\u201cthis\u201d with\nno text?\n\u2192 Stage C", fill="c", tsize=9)
    d.arrow(("in", "r"), ("b07", "l"), "task text", lsize=8.5)
    d.arrow(("b07", "r"), ("b01", "l"), "clean task", lsize=8.5)
    d.arrow(("b01", "r"), ("att", "l"), "IR", lsize=8.5)
    d.arrow(("att", "r"), ("g", "l"), "IR", lsize=8.5)
    d.arrow(("g", "b"), ("cat", "t", (12.1 - 11.85) / 2.0), "yes", loff=(0.12, -0.1), ha="left", lsize=8.8)
    d.arrow((12.1 - 0.625, 5.0 - 0.4), ("grp", "r"), "no", via=[(12.1 - 0.625, 2.75)], lpos=0.5, lsize=8.8)
    d.arrow(("grp", "b"), ("b08", "t", (7.3 - 6.05) / 2.5), "yes", loff=(0.12, -0.12), ha="left", lsize=8.8)
    d.arrow(("grp", "l"), ("un", "r"), "no", lsize=8.8)
    d.arrow(("cat", "b"), ("out", "t", (12.85 - 10.8) / 2.9), "rules that\napplied", loff=(0.12, -0.2), ha="left", lsize=8.5)
    d.arrow(("b08", "r"), ("out", "l", (0.75 - 0.25) / 1.0), "group answer", lsize=8.5)
    d.arrow(("in", "b"), ("u", "t"), "A05 evidence", loff=(0.1, -0.1), ha="left", lsize=8.5)
    d.save("stage_b", prefix)


# ------------------------------------------------------------------ 6. Stage C in block form
def stage_c(prefix):
    d = D(14.6, 6.9)
    d.box("b", 0.3, 4.4, 2.2, 1.2, "Stage B result\n(IR + unresolved)", fill="b", tsize=10)
    d.diamond("q", 4.15, 5.0, 2.6, 1.6, "\u201ctask category\u201d or\n\u201cambiguous reference\u201d\nunresolved?", size=9)
    d.box("req", 6.3, 4.4, 2.3, 1.2, "Build request\nprompt + IR + fields\nto fill (rest locked)", fill="c", tsize=9.5)
    d.box("m", 9.2, 4.4, 2.2, 1.2, "Qwen2.5-0.5B\n+ LoRA adapter\n(trained by us)", fill="c", tsize=9.5)
    d.box("chk", 12.1, 4.1, 2.2, 1.8, "Checker\nvalid JSON \u00b7 exact keys\nno vague \u201cthis\u201d\nformat stated\nvalid category",
          fill="c", tsize=9)
    d.diamond("ok", 13.2, 2.45, 2.0, 1.4, "passes\nevery check?", size=9.5)
    d.box("patch", 9.2, 1.9, 2.3, 1.1, "Fill only the\nrequested fields", fill="b", tsize=10)
    d.box("fb", 9.2, 0.1, 2.3, 1.06, "Fallback: keep\nStage B\u2019s result", fill="e", tsize=10)
    d.diamond("cq", 6.9, 2.45, 2.1, 1.4, "category\nrequested?", size=9.5)
    d.box("ask", 3.35, 1.95, 2.3, 1.0, "Ask the user,\npre-select the guess", fill="d", tsize=9.5)
    d.box("fin", 0.3, 0.1, 2.6, 1.3, "Final IR \u2192\nrenderers", dark=True, tsize=10.5)
    d.arrow(("b", "r"), ("q", "l"), "IR", lsize=8.8)
    d.arrow(("q", "r"), ("req", "l"), "yes", lsize=8.8)
    d.arrow(("req", "r"), ("m", "l"), "JSON input", lsize=8.5)
    d.arrow(("m", "r"), ("chk", "l", 0.5), "JSON answer", lsize=8.5)
    d.arrow(("chk", "b"), ("ok", "t"), "checked answer", loff=(0.12, -0.1), ha="left", lsize=8.5)
    d.arrow(("ok", "b"), ("fb", "r"), "no", via=[(13.2, 0.63)], lpos=0.5, lsize=8.8)
    d.arrow(("ok", "l"), ("patch", "r"), "yes", lsize=8.8)
    d.arrow(("patch", "l"), ("cq", "r"), "patched IR", lsize=8.3)
    d.arrow(("cq", "l"), ("ask", "r"), "yes", lsize=8.8)
    d.arrow(("ask", "l"), ("fin", "t", 0.4), "user\u2019s choice", via=[(1.34, 2.45)], lpos=0.6, lsize=8.5)
    d.arrow(("cq", "b"), ("fin", "r", 0.8), "no", via=[(6.9, 1.14)], lpos=0.5, lsize=8.8)
    d.arrow(("fb", "l"), ("fin", "r", (0.63 - 0.1) / 1.3), "Stage B IR", lsize=8.5)
    d.arrow(("q", "t"), ("fin", "l", 0.5), None, via=[(4.15, 6.1), (0.12, 6.1), (0.12, 0.75)])
    d.text(0.25, 6.4, "no (93.6% of prompts): Stage B\u2019s IR goes straight on", size=8.5, color=P["label"], italic=True)
    d.text(6.3, 6.75, "Review example: fields = format, constraints, category; answer {\u201coutput_format\u201d: \u201cProvide only "
                      "the label.\u201d,\n\u201cconstraints\u201d: [], \u201ccategory\u201d: \u201cclassification\u201d}: passes, "
                      "format applied, category asked", size=8.5, color=P["note"], italic=True)
    d.save("stage_c", prefix)


# ------------------------------------------------------------------ 7. pipeline flow of one request (was "transaction flow")
def pipeline(prefix):
    d = D(14.4, 7.4)
    W, H, gap = 2.2, 1.4, 0.65
    row1 = 5.65
    xs = [0.3 + i * (W + gap) for i in range(5)]
    t1 = [("1. User submits", "prompt, target LLM,\ncategory, attachment"),
          ("2. Clean old data", "delete prompts\nolder than 30 days"),
          ("3. Save the prompt", "e-mails, phones\nremoved \u2192 prompts"),
          ("4. Stage A", "detect features\n\u2192 prompt_features"),
          ("5. Stage B (+ C)", "optimize, log changes\n\u2192 optimization_results,\ntransformations")]
    for i, ((t, b), x) in enumerate(zip(t1, xs)):
        d.box(f"s{i+1}", x, row1, W, H, t, b, fill=["grey", "a", "a", "a", "b"][i], tsize=10.5, bsize=8.8)
    d.box("s6", xs[4], 3.3, W, H, "6. Render + count", "GPT / Claude / Gemini\n\u2192 renderings,\ntoken_usage",
          fill="d", tsize=10.5, bsize=8.8)
    d.diamond("s7", 8.2, 4.0, 2.7, 1.75, "7. Every step\nsucceeded?", size=10)
    d.box("ok", 4.0, 3.3, 2.3, H, "Commit", "one database commit\nfor the whole request", dark=True, tsize=10.5,
          bsize=8.8)
    d.box("no", 7.0, 0.35, 2.4, 1.1, "Roll back", "nothing is stored", fill="e", tsize=10.5, bsize=8.8)
    d.box("s8", 0.3, 3.3, 2.4, H, "8. Response", "features, rules fired,\nrenderings, tokens", fill="grey",
          tsize=10.5, bsize=8.8)
    d.box("s9", 0.3, 0.35, 2.4, 1.3, "9. Compare (optional)", "original vs optimized\non the same model", fill="e",
          tsize=10.5, bsize=8.8)
    d.box("s10", 3.4, 0.35, 2.4, 1.3, "10. History", "search, view, delete\n(deletes cascade)", fill="grey",
          tsize=10.5, bsize=8.8)
    labels = ["POST\n/api/optimize", "clean\ndatabase", "prompt\nid", "features"]
    for i, lab in enumerate(labels):
        d.arrow((f"s{i+1}", "r"), (f"s{i+2}", "l"), lab, lsize=8.3, loff=(0, 0.08))
    d.arrow(("s5", "b"), ("s6", "t"), "final IR", loff=(0.12, -0.1), ha="left", lsize=8.5)
    d.arrow(("s6", "l"), ("s7", "r"), "rows flushed,\nnot committed", lsize=8.3, loff=(0, 0.08))
    d.arrow(("s7", "l"), ("ok", "r"), "yes", lsize=8.8, loff=(0, 0.08))
    d.arrow(("s7", "b"), ("no", "t", (8.2 - 7.0) / 2.4), "no (any error)", loff=(0.12, -0.15), ha="left", lsize=8.5)
    d.arrow(("ok", "l"), ("s8", "r"), "saved", lsize=8.5, loff=(0, 0.08))
    d.arrow(("s8", "b", 0.3), ("s9", "t", 0.3), "user clicks\nCompare", lsize=8.3, loff=(0.1, -0.2), ha="left")
    d.arrow(("s8", "b", 0.85), ("s10", "t", 0.5), "later visit", via=[(2.34, 2.3), (4.6, 2.3)], lsize=8.3, lpos=0.5,
            loff=(0, 0.03))
    d.text(10.0, 1.6, "Only app/db/repository.py reads and\nwrites the database; its functions\nflush (ids exist) but never commit.",
           size=8.8, color=P["note"], italic=True)
    d.save("pipeline", prefix)


# ------------------------------------------------------------------ 8. SDLC followed
def sdlc(prefix):
    d = D(14, 4.4)
    ph = [("Requirement\nanalysis", "survey, literature,\nresearch gap, SRS"),
          ("Dataset\npreparation", "Dolly + CodeAlpaca,\nLLM pairs, repair,\nhuman validation"),
          ("Design", "architecture, IR,\ndatabase (10 tables),\nB\u2192C contract"),
          ("Implementa-\ntion", "Stage A, Stage B,\nStage C training,\nweb app"),
          ("Validation", "tune only on the\nvalidation split;\nfreeze the code"),
          ("Testing", "unit, integration,\nsystem; test split\nrun once"),
          ("Deployment", "LAN service,\nrelease v1.0")]
    w, gap = 1.7, 0.25
    y0, h = 1.55, 1.75
    for i, (t, b) in enumerate(ph):
        x = 0.3 + i * (w + gap)
        d.box(f"p{i}", x, y0, w, h, t, b, fill=["a", "b", "a", "b", "c", "a", "d"][i], tsize=10.2, bsize=8.4)
    for i in range(6):
        d.arrow((f"p{i}", "r"), (f"p{i+1}", "l"), None)
    cx = lambda i: 0.3 + i * (w + gap) + w / 2
    d.arrow(("p4", "b"), ("p3", "b"), "validation results feed back (rules, thresholds, Stage C policy)",
            via=[(cx(4), 0.85), (cx(3), 0.85)], lsize=8.5, loff=(0, -0.42))
    d.arrow(("p3", "t"), ("p1", "t"), "dataset fixes (v1.1 repair, v1.2 expansion)",
            via=[(cx(3), 3.85), (cx(1), 3.85)], lsize=8.5, loff=(0, 0.02))
    d.save("sdlc", prefix)


# ------------------------------------------------------------------ 9. dataset pipeline
def dataset(prefix):
    d = D(14, 6.0)
    d.box("dolly", 0.3, 3.9, 2.3, 1.2, "Dolly-15k", "15,011 rows; 4 categories", fill="grey", tsize=10.5, bsize=8.8)
    d.box("ca", 0.3, 2.2, 2.3, 1.2, "CodeAlpaca-20k", "20,022 rows; coding", fill="grey", tsize=10.5, bsize=8.8)
    d.box("clean", 3.3, 3.0, 2.3, 1.4, "Clean", "de-duplicate, drop\noutliers, remove PII,\nlength buckets", fill="a",
          tsize=10.5, bsize=8.8)
    d.box("samp", 6.3, 3.0, 2.3, 1.4, "Stratified sample", "by length bucket and\nby has-context", fill="a",
          tsize=10.5, bsize=8.8)
    d.box("gen", 9.3, 3.0, 2.3, 1.4, "LLM writes pairs", "degraded + optimized\nprompt (Groq/Cerebras)",
          fill="c", tsize=10.5, bsize=8.8)
    d.box("chk", 11.9, 3.0, 1.85, 1.4, "Automatic\nchecks", "similarity, format,\nlength, code", fill="a",
          tsize=10, bsize=8.3)
    d.box("rep", 11.65, 0.35, 2.1, 1.3, "Repair", "put dropped data\nback (349 rows)", fill="b", tsize=10.5, bsize=8.8)
    d.box("spl", 8.6, 0.35, 2.3, 1.3, "Split by\ninstruction", "train/val/test/bench,\nno overlap", fill="b",
          tsize=10, bsize=8.6)
    d.box("hum", 5.55, 0.35, 2.3, 1.3, "Human review", "3 raters + faculty;\n295 of 330 accepted", fill="d",
          tsize=10.5, bsize=8.6)
    d.box("fin", 0.3, 0.35, 4.4, 1.3, "PromptOpt Dataset v1.2 final", "5,184 pairs: train 4,509 · val 149 ·\n"
          "test 482 · benchmark 44", dark=True, tsize=10.5, bsize=9)
    d.arrow(("dolly", "r"), ("clean", "l", 0.7), None, via=[(2.95, 4.5), (2.95, 3.98)])
    d.arrow(("ca", "r"), ("clean", "l", 0.3), None, via=[(2.95, 2.8), (2.95, 3.42)])
    d.arrow(("clean", "r"), ("samp", "l"), "clean pool", lsize=8.5)
    d.arrow(("samp", "r"), ("gen", "l"), "3,203 new\nsource rows", lsize=8.3)
    d.arrow(("gen", "r"), ("chk", "l"), "pairs", lsize=8.5)
    d.arrow(("chk", "b"), ("rep", "t", 0.55), "2,983 passed", loff=(0.1, -0.1), ha="left", lsize=8.5)
    d.arrow(("rep", "l"), ("spl", "r"), "rows", lsize=8.5)
    d.arrow(("spl", "l"), ("hum", "r"), "5,228 rows", lsize=8.3)
    d.arrow(("hum", "l"), ("fin", "r"), "−35 rejected,\n−9 LLM filter", lsize=8.3, loff=(0, 0.05))
    d.save("dataset", prefix)


# ------------------------------------------------------------------ 10. Stage C training
def training(prefix):
    d = D(14.4, 3.4)
    st = [("Train split", "4,509 rows", "grey"),
          ("Stage A + B", "Stage A cross-fitted;\nwhat stays unresolved", "a"),
          ("Training examples", "routed 377 +\nforced 4,132;\n4,456 clean", "a"),
          ("Targets", "parsed from the\ndataset\u2019s optimized\nprompt", "b"),
          ("LoRA fine-tuning", "Qwen2.5-0.5B, rank 16,\nlr 2e-4, batch 16,\nRTX 3050 (4 GB)", "c"),
          ("Best adapter", "val loss 0.7047\nat step 550", "dark")]
    w, gap = 1.95, 0.45
    for i, (t, b, f) in enumerate(st):
        x = 0.3 + i * (w + gap)
        d.box(f"t{i}", x, 1.1, w, 1.55, t, b, fill=f if f != "dark" else "a", dark=f == "dark", tsize=10, bsize=8.4)
    labs = ["rows", "routing\nper row", "input\nJSON", "input +\ntarget", "best on\nval loss"]
    for i, l in enumerate(labs):
        d.arrow((f"t{i}", "r"), (f"t{i+1}", "l"), l, lsize=7.8, loff=(0, 0.08))
    d.text(0.3, 0.8, "Early stopping: validation loss every 50 steps; stop after 3 checks without improvement "
                     "(stopped at step 700, 51 minutes).", size=8.6, color=P["note"], italic=True)
    d.save("training", prefix)


def stage_c_simple(prefix):
    """Plain-words Stage C for the deck: big text, five blocks."""
    d = D(12.3, 5.9)
    d.box("b", 0.2, 3.55, 3.3, 1.9, "Step B is stuck", "task type not sure\n(6 in 100 prompts)", fill="b", tsize=16, bsize=14)
    d.box("m", 4.5, 3.55, 3.3, 1.9, "Small model", "trained by us; fills\nonly the missing parts", fill="c", tsize=16, bsize=14)
    d.box("k", 8.8, 3.55, 3.3, 1.9, "Check the answer", "right shape? no vague\n\u201cthis\u201d? real task type?", fill="c", tsize=16, bsize=14)
    d.box("ok", 6.6, 0.35, 5.5, 1.9, "Passes: use it", "format added; the user confirms\nthe suggested task type", fill="b", tsize=16, bsize=14)
    d.box("fb", 0.2, 0.35, 5.0, 1.9, "Fails: keep Step B\u2019s result", "nothing is lost", fill="e", tsize=16, bsize=14)
    d.arrow(("b", "r"), ("m", "l"), "missing\nparts", lsize=12, loff=(0, 0.1))
    d.arrow(("m", "r"), ("k", "l"), "its\nanswer", lsize=12, loff=(0, 0.1))
    d.arrow(("k", "b", 0.6), ("ok", "t", (10.78 - 6.6) / 5.5), "passes", lsize=12, loff=(0.12, -0.15), ha="left")
    d.arrow(("k", "b", 0.2), ("fb", "r", 0.5), "fails", via=[(9.46, 2.75), (5.9, 2.75), (5.9, 1.3)], lsize=12, lpos=0.5,
            loff=(0, 0.05))
    d.save("stage_c_simple", prefix)


for prefix in ("diag", "deck"):
    P = PALETTES[prefix]
    for f in (story, architecture, stage_a, confidence, stage_b, stage_c, stage_c_simple, pipeline, sdlc, dataset, training):
        f(prefix)
print("ok")
