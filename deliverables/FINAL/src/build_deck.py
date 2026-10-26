"""Final deck: LA-1 and LA-2 merged into one 10-minute story built on the LA-1 Canva slides (same backgrounds, logo,
fonts). One example, the review prompt, goes through every stage. Plain words; numbers from evaluation/FINAL_RESULTS.md,
evaluation/tokens/token_test.md, evaluation/correctness_suite/RESULTS.md and the review example run through the app.
Usage: python build_deck.py LA1.pptx OUT.pptx   (needs the pptx skill's add_slide.py / clean.py on SKILL_SCRIPTS)"""
import os, re, shutil, subprocess, sys, tempfile, zipfile
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.oxml.ns import qn
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "..", "figures")
SRC, OUT = sys.argv[1], sys.argv[2]
SCRIPTS = os.environ["SKILL_SCRIPTS"]

# ------------------------------------------------------------------ 1. structure: duplicate LA-1 slides in final order
# (base slide number in the LA-1 deck, keep its content?)
ORDER = [(1, True), (2, True), (3, False), (6, True), (12, False), (17, False), (9, False), (12, False), (12, False),
         (9, False), (3, False), (16, False), (12, False), (9, False), (3, False), (5, False), (20, True),
         (8, True), (5, True), (11, True), (18, True), (9, False), (19, True)]
BASE_OF = [f"s{b}" for b, _ in ORDER]

work = tempfile.mkdtemp()
with zipfile.ZipFile(SRC) as z:
    z.extractall(work)
pres_xml = os.path.join(work, "ppt", "presentation.xml")
orig_ids = re.findall(r'<p:sldId [^>]*/>', open(pres_xml).read())
for b, _ in ORDER:
    subprocess.run([sys.executable, os.path.join(SCRIPTS, "add_slide.py"), work, f"slide{b}.xml"], check=True,
                   stdout=subprocess.DEVNULL, cwd=SCRIPTS)
x = open(pres_xml).read()
for sid in orig_ids:
    x = x.replace(sid, "", 1)
open(pres_xml, "w").write(x)
subprocess.run([sys.executable, os.path.join(SCRIPTS, "clean.py"), work], check=True, stdout=subprocess.DEVNULL, cwd=SCRIPTS)
base = OUT + ".base.pptx"
if os.path.exists(base):
    os.remove(base)
with zipfile.ZipFile(base, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(work):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, work))
shutil.rmtree(work)

# ------------------------------------------------------------------ 2. fill
MINT, GREEN, DARK, LIGHT, PALE, MAROON, WHITE = "F5FFF9", "457C5B", "1E4926", "9FC4AE", "8AB79C", "8E1711", "FFFFFF"
SOFT = "E4F2EA"
BOLD, ULTRA, BODY, MONO = "Manifold Bold", "Manifold Ultra-Bold", "Lato", "Courier New"
rgb = RGBColor.from_string

prs = Presentation(base)
S = list(prs.slides)
assert len(S) == len(ORDER), (len(S), len(ORDER))

KEEP = {
    "s9": {"Group 5", "Group 8", "Freeform 11", "TextBox 50"},
    "s12": {"Group 2", "Group 5", "Freeform 8", "TextBox 9"},
    "s3": {"Group 2", "Group 5", "Freeform 8", "Freeform 9", "Freeform 44", "TextBox 10"},
    "s16": {"Group 72", "Group 75", "Freeform 78", "Freeform 79", "Freeform 80", "TextBox 81"},
    "s17": {"Group 2", "Group 5", "TextBox 8", "Freeform 9", "Freeform 10", "Freeform 11"},
    "s5": {"Group 2", "Group 5", "TextBox 8", "Freeform 21", "Freeform 22", "Freeform 23"},
}
TITLE = {"s9": "TextBox 50", "s12": "TextBox 9", "s3": "TextBox 10", "s16": "TextBox 81", "s17": "TextBox 8", "s5": "TextBox 8"}


def set_text_keep(shape, text):
    tf = shape.text_frame; p0 = tf.paragraphs[0]; r0 = p0.runs[0]
    for r in p0.runs[1:]:
        r._r.getparent().remove(r._r)
    r0.text = text
    for p in tf.paragraphs[1:]:
        p._p.getparent().remove(p._p)


def prep(i, title):
    s = S[i]; b = BASE_OF[i]
    for sh in list(s.shapes):
        if sh.name not in KEEP[b]:
            sh._element.getparent().remove(sh._element)
    t = next(sh for sh in s.shapes if sh.name == TITLE[b])
    set_text_keep(t, title)
    t.text_frame.word_wrap = True
    t.left, t.width, t.top = Inches(2.3), Inches(15.4), Inches(0.62)
    return s


def box(s, x, y, w, h, fill, line=None, radius=0.07, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = radius
    sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
    if line:
        sh.line.color.rgb = rgb(line); sh.line.width = Pt(1.5)
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def text(s, x, y, w, h, paras, size=20, color=DARK, font=BODY, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, space_after=6, line=1.1):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, 0)
    if isinstance(paras, str):
        paras = [paras]
    for k, para in enumerate(paras):
        p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(space_after); p.line_spacing = line
        for t, o in (para if isinstance(para, list) else [(para, {})]):
            r = p.add_run(); r.text = t
            f = r.font; f.size = Pt(o.get("size", size)); f.name = o.get("font", font)
            f.bold = o.get("bold", bold); f.color.rgb = rgb(o.get("color", color))
    return tb


def circle_num(s, x, y, d, n, fill=LIGHT, color=DARK, size=22):
    box(s, x, y, d, d, fill, shape=MSO_SHAPE.OVAL)
    text(s, x, y, d, d, str(n), size=size, color=color, font=BOLD, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def pair_stat(s, x, y, w, h, label, before, after, fill=GREEN, color=MINT, note=None, big=40):
    """A labelled before/after stat: two numbers with their own labels instead of an arrow."""
    box(s, x, y, w, h, fill)
    text(s, x + 0.3, y + 0.18, w - 0.6, 0.5, label, size=18, color=color, font=BOLD, bold=True)
    half = (w - 0.6) / 2
    for k, (num, lab) in enumerate(((before, "vague prompt"), (after, "optimized"))):
        xx = x + 0.3 + k * half
        text(s, xx, y + 0.72, half - 0.1, 0.9, num, size=big, color=color, font=ULTRA, anchor=MSO_ANCHOR.MIDDLE)
        text(s, xx, y + 1.62, half - 0.1, 0.4, lab, size=15, color=LIGHT if fill in (GREEN, DARK) else GREEN)
    if note:
        text(s, x + 0.3, y + h - 0.55, w - 0.6, 0.45, note, size=15, color=color)


def stat(s, x, y, w, h, big, label, fill=GREEN, color=MINT, size=46, lsize=17):
    box(s, x, y, w, h, fill)
    text(s, x + 0.2, y + 0.15, w - 0.4, h * 0.5, big, size=size, color=color, font=ULTRA, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.25, y + h * 0.58, w - 0.5, h * 0.4, label, size=lsize, color=color, align=PP_ALIGN.CENTER)


def picture(s, fname, x, y, w=None, h=None, border=GREEN, crop=None):
    path = os.path.join(FIG, fname); iw, ih = Image.open(path).size
    if crop:  # (left, top, right, bottom) in pixels
        l, t, r, b = crop; iw2, ih2 = r - l, b - t
    else:
        iw2, ih2 = iw, ih
    if w is None:
        w = h * iw2 / ih2
    h = w * ih2 / iw2
    pic = s.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))
    if crop:
        pic.crop_left, pic.crop_top = l / iw, t / ih
        pic.crop_right, pic.crop_bottom = 1 - r / iw, 1 - b / ih
        pic.left, pic.top, pic.width, pic.height = Inches(x), Inches(y), Inches(w), Inches(h)
    if border:
        pic.line.color.rgb = rgb(border); pic.line.width = Pt(1.5)
    return pic


def style_chart(ch, colors, size=16, legend=True):
    ch.font.name = BODY; ch.font.size = Pt(size); ch.font.color.rgb = rgb(DARK)
    for ser, c in zip(ch.plots[0].series, colors):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = rgb(c)
    pl = ch.plots[0]; pl.has_data_labels = True
    dl = pl.data_labels; dl.font.size = Pt(size - 1); dl.font.name = BODY; dl.font.color.rgb = rgb(DARK)
    dl.position = XL_LABEL_POSITION.OUTSIDE_END; dl.number_format = '0'; dl.number_format_is_linked = False
    va = ch.value_axis; va.visible = False; va.has_major_gridlines = False
    ca = ch.category_axis; ca.tick_labels.font.size = Pt(size); ca.format.line.color.rgb = rgb(PALE)
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False; ch.legend.font.size = Pt(size)


def chart_title(ch, t, size=17):
    ch.has_title = True; ch.chart_title.text_frame.text = t
    r = ch.chart_title.text_frame.paragraphs[0].runs[0]; r.font.size = Pt(size); r.font.color.rgb = rgb(GREEN)
    r.font.name = BOLD


def code_card(s, x, y, w, h, head, body, size=14):
    box(s, x, y, w, h, WHITE, line=GREEN)
    text(s, x + 0.25, y + 0.15, w - 0.5, 0.55, head, size=22, color=GREEN, font=BOLD, bold=True)
    text(s, x + 0.25, y + 0.8, w - 0.5, h - 0.95, body, size=size, color=DARK, font=MONO, space_after=0, line=1.0)


def notes(s, t):
    s.notes_slide.notes_text_frame.text = t


GPTM = "OpenAI's GPT model (gpt-oss-120b)"

# 1 Title ---------------------------------------------------------------------------------------------------------
s = S[0]
for sh in s.shapes:
    if sh.has_text_frame:
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                r.text = r.text.replace("LA-1 EVALUATION", "FINAL EVALUATION").replace("LA-1", "FINAL").replace("Sciecne", "Science")
    widths = {"TextBox 18": 13.5, "TextBox 19": 11.5, "TextBox 20": 11.0, "TextBox 21": 3.0, "TextBox 11": 9.0, "TextBox 12": 6.0}
    if sh.name in widths:
        c = sh.left + sh.width // 2; sh.width = Inches(widths[sh.name]); sh.left = c - sh.width // 2
notes(s, "Piush. Good morning. We are Piush, Nirzara and Siddhi; our guide is Prof. A. S. Pawar. PromptOpt takes a "
      "vague prompt, makes it clear and short for the AI you use, shows every change, and we measured that it saves "
      "tokens. We will follow one example prompt through the whole system.")

# 2 Agenda --------------------------------------------------------------------------------------------------------
s = S[1]
agenda = {"TextBox 31": "The Problem", "TextBox 36": "What Exists & the Gap", "TextBox 33": "Our Goal",
          "TextBox 37": "Our Data", "TextBox 34": "One Example, Start to Finish", "TextBox 38": "Results",
          "TextBox 35": "Testing & the Working App", "TextBox 39": "Challenges & Next Steps"}
for sh in s.shapes:
    if sh.name in agenda:
        set_text_keep(sh, agenda[sh.name])
notes(s, "Piush. Problem, what exists, our goal and our data; then one example through every step; then results, "
      "testing, the app and what comes next.")

# 3 Problem -------------------------------------------------------------------------------------------------------
s = prep(2, "THE PROBLEM")
box(s, 1.0, 2.2, 18.0, 1.15, DARK)
text(s, 1.35, 2.25, 17.3, 1.05, "People type short, vague prompts. The AI has to guess, so it writes long answers "
     "nobody asked for, and every extra word costs tokens, time and money.", size=21, color=MINT,
     anchor=MSO_ANCHOR.MIDDLE)
box(s, 1.0, 3.7, 9.6, 6.55, WHITE, line=PALE)
text(s, 1.35, 3.9, 9.0, 0.5, "A REAL EXAMPLE", size=19, color=GREEN, font=BOLD, bold=True)
box(s, 1.35, 4.5, 8.9, 1.55, SOFT)
text(s, 1.6, 4.62, 8.4, 1.35, [[("The user types: ", {"font": BOLD, "bold": True, "color": GREEN}),
     ("“hey can you just tell me if this review is good or bad”", {"font": MONO, "size": 18})],
     [("+ a short phone review", {"size": 16, "color": GREEN})]], size=18, space_after=2)
box(s, 1.35, 6.25, 8.9, 2.55, SOFT)
text(s, 1.6, 6.37, 8.4, 2.35, [[("The AI answers with a whole page: ", {"font": BOLD, "bold": True, "color": GREEN}),
     ("a heading, positive points, negative points and a closing paragraph.", {})],
     [("166 tokens", {"font": ULTRA, "size": 34, "color": MAROON}), ("  in the answer alone", {"size": 17})]], size=18)
text(s, 1.35, 9.0, 8.9, 1.1, "The user only wanted one word: good or bad.", size=18, color=GREEN, font=BOLD, bold=True)
text(s, 11.1, 3.7, 7.9, 0.5, "OUR SURVEY OF STUDENTS AND DEVELOPERS", size=19, color=GREEN, font=BOLD, bold=True)
for k, (num, lab) in enumerate([("72%", "run out of tokens very quickly"), ("58%", "need several prompts to get one answer"),
                                ("50%", "often or very often ask the AI again")]):
    y = 4.35 + k * 1.98
    box(s, 11.1, y, 7.9, 1.78, GREEN)
    text(s, 11.4, y + 0.1, 2.6, 1.58, num, size=46, color=MINT, font=ULTRA, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 14.1, y + 0.1, 4.7, 1.58, lab, size=19, color=MINT, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Piush. The problem in one line: vague prompts make the AI guess and write long answers, which costs tokens. "
      "Example: a student pastes a phone review and asks 'is this good or bad'. The AI writes a whole page, 166 tokens, "
      "when one word was enough. Our survey: 72% run out of tokens quickly, 58% need several prompts for one answer, "
      "half often ask again.")

# 4 Gap analysis: LA-1 slide unchanged --------------------------------------------------------------------------------
notes(S[3], "Piush. Existing tools rewrite prompts, but none checks the new prompt on a real AI, none reports input "
      "and output tokens together, and none mixes fixed rules with a small trained model. Those four gaps are what we "
      "built PromptOpt for.")

# 5 Our goal ------------------------------------------------------------------------------------------------------
s = prep(4, "OUR GOAL")
goals = [("To find what a prompt is missing", "answer format, length, language, or which text “this” means"),
         ("To fix it with simple rules", "and show every change, before and after"),
         ("To use a small AI model only when the rules are stuck", "trained by us, checked before it is used"),
         ("To write the prompt the way each AI likes it", "GPT, Gemini or Claude: same content, their layout"),
         ("To prove it with numbers", "fewer tokens, same or better answers, on prompts never seen before")]
for k, (h, b) in enumerate(goals):
    y = 2.3 + k * 1.6
    box(s, 1.0, y, 18.0, 1.38, SOFT if k % 2 else WHITE, line=PALE)
    circle_num(s, 1.3, y + 0.24, 0.9, k + 1, fill=GREEN, color=MINT, size=24)
    text(s, 2.55, y + 0.12, 15.9, 0.6, h, size=23, color=DARK, font=BOLD, bold=True)
    text(s, 2.55, y + 0.75, 15.9, 0.5, b, size=18, color=GREEN)
notes(s, "Piush. Five goals: find what is missing, fix it with simple rules and show every change, call a small AI "
      "model only when the rules are stuck, write the prompt in the layout each AI prefers, and prove all of it with "
      "numbers on prompts the system never saw.")

# 6 Our data ------------------------------------------------------------------------------------------------------
s = prep(5, "OUR DATA")
box(s, 1.0, 2.2, 8.2, 8.0, WHITE, line=PALE)
cd = CategoryChartData(); cd.categories = ["Question\nabout text", "Pull out\nfacts", "Sort into\ngroups", "Summary", "Code"]
cd.add_series("pairs", (1089, 1000, 1042, 1050, 1003))
ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1.2), Inches(2.35), Inches(7.8), Inches(7.7), cd).chart
style_chart(ch, [GREEN], size=15, legend=False); ch.value_axis.maximum_scale = 1300
chart_title(ch, "5,184 example pairs, about 1,000 per task type")
steps = [("Real requests", "from two public datasets: Dolly (text tasks) and CodeAlpaca (code)"),
         ("Vague + clear version", "an AI wrote how a rushed user would type it, and a clear version"),
         ("Checked by computer", "drift, missing data, too long; dropped data put back"),
         ("Checked by us", "330 pairs read by the three of us and our guide: 295 kept"),
         ("Split once", "4,509 to learn from · 149 to tune · 482 to test, used only once")]
for k, (h, b) in enumerate(steps):
    y = 2.2 + k * 1.62
    box(s, 9.7, y, 9.3, 1.42, GREEN)
    circle_num(s, 9.95, y + 0.26, 0.9, k + 1, fill=LIGHT, color=DARK, size=22)
    text(s, 11.1, y + 0.13, 7.7, 0.5, h, size=20, color=MINT, font=BOLD, bold=True)
    text(s, 11.1, y + 0.66, 7.7, 0.7, b, size=16, color=MINT)
notes(s, "Piush. No dataset pairs a vague prompt with a clear one, so we built it. We took real requests from Dolly "
      "and CodeAlpaca; an AI wrote a vague and a clear version of each; the computer checked them and put back data "
      "that was dropped; and we three plus our guide read 330 pairs and kept 295. Result: 5,184 pairs, about 1,000 per "
      "task type. 482 are kept aside and used only once, for the final test.")

# 7 One example, start to finish ------------------------------------------------------------------------------------
s = prep(6, "ONE EXAMPLE, START TO FINISH")
box(s, 1.0, 2.15, 18.0, 8.2, WHITE, line=PALE)
picture(s, "deck_story.png", 1.25, 2.3, w=17.5, border=None)
notes(s, "Nirzara. Here is the whole journey of our example. 1, the user types the vague prompt with the review. 2, "
      "Step A understands it. 3, Step B fixes it with rules. 4, Step C, a small model, fills what the rules could not. "
      "5, the prompt is written for GPT. 6, Compare runs both prompts on the same AI. Let us go step by step.")

# 8 Step A --------------------------------------------------------------------------------------------------------
s = prep(7, "STEP A: UNDERSTAND THE PROMPT")
picture(s, "story_stage-a.png", 1.0, 2.25, w=9.4)
cards = [("What kind of task is it?", "Summary 52%, sorting into a label 35%. Below 60% means “not sure”, so "
          "nothing will be guessed."),
         ("What is missing?", "No answer format. Filler words: “hey”, “can you”, “just”."),
         ("How does it decide?", "It compares the prompt with 9,000+ example prompts from our data and checks it "
          "with word rules.")]
for k, (h, b) in enumerate(cards):
    y = 2.25 + k * 2.68
    box(s, 10.9, y, 8.1, 2.45, GREEN)
    text(s, 11.2, y + 0.2, 7.5, 0.55, h, size=21, color=MINT, font=BOLD, bold=True)
    text(s, 11.2, y + 0.85, 7.5, 1.5, b, size=18, color=MINT)
notes(s, "Nirzara. Step A only reads. It asks: what kind of task is this? It thinks 'summary' at 52% and 'sorting "
      "into a label' at 35%. Below 60% we call it not sure, and we do not guess. It also finds what is missing: no "
      "answer format, and filler words like 'hey can you just'. It decides by comparing with over 9,000 example "
      "prompts from our data, plus word rules.")

# 9 Step B --------------------------------------------------------------------------------------------------------
s = prep(8, "STEP B: FIX WITH SIMPLE RULES")
picture(s, "story_stage-b.png", 1.0, 2.25, w=9.4)
box(s, 10.9, 2.25, 8.1, 2.9, WHITE, line=GREEN)
text(s, 11.2, 2.4, 7.5, 0.5, "BEFORE", size=17, color=MAROON, font=BOLD, bold=True)
text(s, 11.2, 2.85, 7.5, 0.8, "hey can you just tell me if this review is good or bad", size=17, font=MONO, line=1.0)
text(s, 11.2, 3.7, 7.5, 0.5, "AFTER", size=17, color=GREEN, font=BOLD, bold=True)
text(s, 11.2, 4.15, 7.5, 0.8, "Tell me if this review is good or bad.", size=17, font=MONO, line=1.0)
text(s, 10.9, 5.4, 8.1, 0.5, "15 SMALL RULES, EACH ONE TESTED", size=19, color=GREEN, font=BOLD, bold=True)
chips = ["remove filler", "remove repeats", "move pasted data", "add answer format", "add length", "add language",
         "list the labels", "answer from the text", "attachments"]
for k, c in enumerate(chips):
    x, y = 10.9 + (k % 3) * 2.75, 6.05 + (k // 3) * 0.82
    box(s, x, y, 2.6, 0.66, SOFT, line=PALE)
    text(s, x + 0.1, y, 2.4, 0.66, c, size=15, color=DARK, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
box(s, 10.9, 8.6, 8.1, 1.65, DARK)
text(s, 11.2, 8.72, 7.5, 1.45, "Not sure of the task? Then no rule adds a format. The question goes to Step C.",
     size=18, color=MINT, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Nirzara. Step B fixes with fixed rules, and shows every change. Here two rules fired: tidy the sentence, "
      "and remove 'hey can you just'. We have 15 rules, each a small tested function: add an answer format, a length, a "
      "programming language, the list of labels, and so on. But because Step A was not sure of the task, no rule "
      "guesses a format. That open question goes to Step C.")

# 10 Step C -------------------------------------------------------------------------------------------------------
s = prep(9, "STEP C: A SMALL MODEL, ONLY WHEN STUCK")
box(s, 1.0, 2.15, 12.3, 6.0, WHITE, line=PALE)
picture(s, "deck_stage_c_simple.png", 1.15, 2.25, h=5.8, border=None)
box(s, 1.0, 8.4, 12.3, 1.85, GREEN)
text(s, 1.3, 8.5, 11.7, 1.65, [[("For our example it added ", {}), ("“Provide only the label.”", {"font": BOLD, "bold": True}),
     (" and suggested ", {}), ("“sort into a label”", {"font": BOLD, "bold": True}),
     (". The app asks the user to confirm.", {})]], size=19, color=MINT, anchor=MSO_ANCHOR.MIDDLE)
stat(s, 13.7, 2.15, 5.3, 2.5, "6 in 100", "prompts need Step C; the rules handle the rest", size=40)
box(s, 13.7, 4.85, 5.3, 2.75, GREEN)
text(s, 14.0, 4.95, 4.7, 0.45, "ANSWERS THAT PASS THE CHECK", size=15, color=MINT, font=BOLD, bold=True)
for k, (num, lab) in enumerate((("5 / 100", "before training"), ("98 / 100", "after our training"))):
    yy = 5.45 + k * 1.05
    text(s, 14.0, yy, 2.6, 0.9, num, size=30, color=MINT, font=ULTRA, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 16.7, yy, 2.2, 0.9, lab, size=16, color=LIGHT, anchor=MSO_ANCHOR.MIDDLE)
stat(s, 13.7, 7.8, 5.3, 2.45, "51 min", "to train on a 4 GB laptop GPU", size=40)
notes(s, "Nirzara. Step C is a small AI model, Qwen 0.5B, that we trained ourselves with LoRA on a laptop GPU in 51 "
      "minutes. It is called only when the rules are stuck: 6 in 100 prompts. It may fill only the missing parts; "
      "everything else is locked. Its answer is checked; if the check fails, we keep Step B's result. Without our "
      "training only 5 in 100 answers passed the check; after training 98 in 100. For our example it added 'Provide "
      "only the label' and suggested the task type, which the user confirms.")

# 11 Step D -------------------------------------------------------------------------------------------------------
s = prep(10, "STEP D: WRITTEN FOR YOUR AI")
cards = [("Claude", "<context>\n<document>\nThe battery lasts two\ndays and the camera is\ngreat, but the phone\nheats up while gaming.\n</document>\n</context>\n<task>\nTell me if this review\nis good or bad.\n</task>\n<output_format>\nProvide only the label.\n</output_format>"),
         ("GPT", "### Task\nTell me if this review\nis good or bad.\n\n### Context\nDocument:\n```\nThe battery lasts two\ndays and the camera ...\n```\n\n### Output format\nProvide only the label."),
         ("Gemini", "Task: Tell me if this\nreview is good or bad.\n\nOutput format: Provide\nonly the label.\n\nContext:\nDocument:\n```\nThe battery lasts two\ndays and the camera ...\n```")]
for k, (h, c) in enumerate(cards):
    code_card(s, 1.0 + k * 6.1, 2.2, 5.8, 6.6, h, c, size=14)
box(s, 1.0, 9.05, 18.0, 1.2, GREEN)
text(s, 1.3, 9.1, 17.4, 1.1, "Same content for every AI, in the layout its makers recommend. Our prompt for GPT: 50 "
     "tokens, counted exactly.", size=19, color=MINT, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Nirzara. Step D writes the same content in the layout each AI prefers: XML tags with the document first for "
      "Claude, headed sections for GPT, plain labels with the instruction first for Gemini. Our tests read every "
      "version back to make sure nothing is lost.")

# 12 Result for our example (dark) ----------------------------------------------------------------------------------
s = prep(11, "THE RESULT FOR OUR EXAMPLE")
box(s, 1.0, 2.15, 9.6, 8.15, MINT)
picture(s, "story_compare.png", 1.15, 2.3, h=7.85, border=None, crop=(470, 650, 1200, 1370))
pair_stat(s, 11.0, 2.15, 8.0, 2.5, "Total tokens", "270", "162", fill=MINT, color=DARK, big=42)
pair_stat(s, 11.0, 4.85, 8.0, 2.5, "Tokens in the answer", "166", "41", fill=MINT, color=DARK, big=42)
pair_stat(s, 11.0, 7.55, 8.0, 2.75, "Answer", "a page", "“good”", fill=MINT, color=DARK, big=34,
          note="Same AI for both: " + GPTM)
notes(s, "Nirzara. We sent both prompts to the same AI, OpenAI's GPT model gpt-oss-120b. The vague prompt cost 270 "
      "tokens in total, the optimized one 162: 40% fewer. The answer itself went from 166 tokens to 41: the word "
      "'good'. And it came back in 97 ms instead of 353. The vague answer said 'mixed', a fair reading, but the user "
      "asked good or bad, and the optimized prompt answers exactly that question.")

# 13 Results on 482 prompts -----------------------------------------------------------------------------------------
s = prep(12, "DOES IT WORK ON 482 NEW PROMPTS?")
box(s, 1.0, 2.15, 10.6, 8.15, WHITE, line=PALE)
cd = CategoryChartData(); cd.categories = ["Prompt (input)", "Answer (output)", "Total"]
cd.add_series("Vague prompt", (226, 682, 909)); cd.add_series("Optimized prompt", (241, 165, 406))
ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1.2), Inches(2.3), Inches(10.2), Inches(7.9), cd).chart
style_chart(ch, [MAROON, GREEN], size=16); ch.value_axis.maximum_scale = 1050
chart_title(ch, "Average tokens per prompt, " + GPTM)
stat(s, 12.0, 2.15, 7.0, 2.4, "39% fewer", "total tokens per prompt (482 test prompts)", size=42)
pair_stat(s, 12.0, 4.75, 7.0, 2.45, "Answer format stated", "3 in 100", "95 in 100", big=30)
pair_stat(s, 12.0, 7.4, 7.0, 2.9, "Quality, blind judge (0-10)", "8.2", "9.0", big=36,
          note="Task done right: 67% vs 85%")
notes(s, "Siddhi. One example is not proof, so we tested on 482 prompts the system never saw, using one AI, OpenAI's "
      "GPT model. The optimized prompt is slightly longer, 226 to 241 tokens, but the answers are much shorter, 682 to "
      "165. Total: 39% fewer tokens per prompt. The answer format is stated in 95 of 100 prompts instead of 3, and a "
      "blind judge scored quality 9.0 instead of 8.2. Honest limit: 87 of the 482 prompts cost a little more, because "
      "their answer was already short.")

# 14 Testing ------------------------------------------------------------------------------------------------------
s = prep(13, "TESTING")
cols = [("UNIT", "798", "automatic tests, all pass", ["every rule tested on its own", "4 sample cases per module in the report"]),
        ("INTEGRATION", "42 / 50", "real-life questions right (vague: 37)", ["10 per task type", "29.6% fewer tokens"]),
        ("SYSTEM", "13 / 13", "browser tests of the whole app pass", ["482 test prompts run once", "frozen code checked byte by byte"])]
for k, (h, big, lab, bl) in enumerate(cols):
    x = 1.0 + k * 6.1
    box(s, x, 2.15, 5.8, 4.75, GREEN)
    text(s, x + 0.3, 2.3, 3.0, 0.5, h, size=20, color=MINT, font=BOLD, bold=True)
    text(s, x + 0.3, 2.85, 5.2, 1.0, big, size=46, color=MINT, font=ULTRA, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.3, 3.9, 5.2, 0.5, lab, size=17, color=LIGHT)
    text(s, x + 0.3, 4.65, 5.2, 2.1, [[("●  ", {"color": LIGHT, "size": 14}), (t, {})] for t in bl], size=20,
         color=MINT, space_after=10)
box(s, 1.0, 7.1, 18.0, 3.2, WHITE, line=PALE)
cd = CategoryChartData(); cd.categories = ["Question about text", "Pull out facts", "Sort into groups", "Summary", "Code"]
cd.add_series("Vague prompt", (8, 7, 7, 7, 8)); cd.add_series("Optimized prompt", (10, 10, 8, 5, 9))
ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1.2), Inches(7.2), Inches(17.6), Inches(3.0), cd).chart
style_chart(ch, [MAROON, GREEN], size=14); ch.value_axis.maximum_scale = 12; ch.plots[0].gap_width = 120
ch.legend.position = XL_LEGEND_POSITION.RIGHT
chart_title(ch, "Integration test by task type: right answers out of 10", size=15)
notes(s, "Siddhi. Three levels. Unit: 798 automatic tests, every rule on its own, all pass. Integration: 50 new "
      "real-life questions, 10 per task type, each with a known right answer; the optimized prompts got 42 right, "
      "the vague ones 37, with 30% fewer tokens. System: 13 browser tests drive the real app, all pass; the 482 test "
      "prompts were run once at the end, and a check proves the code we measured never changed.")

# 15 Working app --------------------------------------------------------------------------------------------------
s = prep(14, "THE WORKING APP")
picture(s, "story_optimize_full.png", 1.0, 2.2, w=11.0, crop=(240, 90, 1440, 960))
box(s, 12.4, 2.2, 6.6, 8.0, GREEN)
text(s, 12.7, 2.4, 6.0, 0.55, "LIVE DEMO", size=22, color=MINT, font=BOLD, bold=True)
demo = [("Optimize", "our review example: every step on screen"), ("Compare", "both prompts on a real AI"),
        ("History", "past prompts, deleted after 30 days"), ("Test suite", "the 50 real-life questions")]
for k, (h, b) in enumerate(demo):
    y = 3.2 + k * 1.7
    circle_num(s, 12.7, y, 0.85, k + 1, fill=LIGHT, color=DARK, size=22)
    text(s, 13.8, y - 0.05, 5.0, 0.5, h, size=20, color=MINT, font=BOLD, bold=True)
    text(s, 13.8, y + 0.5, 5.0, 0.9, b, size=17, color=MINT)
notes(s, "Siddhi. The app: FastAPI and React, running on our laptop. Live demo: Optimize our review example and watch "
      "each step; Compare both prompts on a real AI; History, where prompts are deleted after 30 days; and the test "
      "suite. If the network fails, Compare shows saved past runs.")

# 16 Challenges & next (dark) ----------------------------------------------------------------------------------------
s = prep(15, "CHALLENGES AND NEXT STEPS")
text(s, 1.0, 2.2, 8.6, 0.55, "WHAT WAS HARD, AND WHAT WE DID", size=20, color=MINT, font=BOLD, bold=True)
ch_ = [("AI-written data dropped facts", "computer checks, repair, and we read 330 pairs"),
       ("The small model made things up", "training (5 to 98 in 100) and a check before use"),
       ("Free AI limits per day", "a usage log, pacing, runs that resume next day"),
       ("4 GB laptop GPU", "memory-saving training: 51 minutes")]
for k, (h, b) in enumerate(ch_):
    y = 2.95 + k * 1.82
    box(s, 1.0, y, 8.6, 1.6, MINT)
    text(s, 1.3, y + 0.15, 8.0, 0.55, h, size=19, color=DARK, font=BOLD, bold=True)
    text(s, 1.3, y + 0.8, 8.0, 0.7, b, size=17, color=GREEN)
text(s, 10.4, 2.2, 8.6, 0.55, "NEXT STEPS", size=20, color=MINT, font=BOLD, bold=True)
nx = [("Lean mode", "add less when the answer is already short"), ("Real GPT, Claude, Gemini", "with paid API keys"),
      ("Bigger tests", "more real-life questions, written by outsiders"), ("Research paper", "on the method and results")]
for k, (h, b) in enumerate(nx):
    y = 2.95 + k * 1.82
    box(s, 10.4, y, 8.6, 1.6, LIGHT)
    circle_num(s, 10.65, y + 0.36, 0.88, k + 1, fill=MINT, color=DARK, size=22)
    text(s, 11.8, y + 0.15, 7.0, 0.55, h, size=19, color=DARK, font=BOLD, bold=True)
    text(s, 11.8, y + 0.8, 7.0, 0.7, b, size=17, color=DARK)
notes(s, "Siddhi. What was hard: AI-written data that dropped facts, a small model that made things up before training, "
      "daily limits on free AI services, and a 4 GB laptop GPU. Next: a lean mode for prompts whose answer is already "
      "short, tests on real GPT, Claude and Gemini, bigger tests written by people outside the team, and a research paper.")

# 17 Thank you: LA-1 slide unchanged ---------------------------------------------------------------------------------
notes(S[16], "Siddhi. Thank you. We are happy to take questions. (Appendix slides follow for questions.)")

# Appendix: 18 tech stack, 19 literature, 20 SDG, 21 Gantt kept; 22 pipeline flow; 23 references kept -------------------
for i, t in ((17, "Appendix. Tech stack, from LA-1."), (18, "Appendix. Literature review, from LA-1."),
             (19, "Appendix. SDG alignment, from LA-1."), (20, "Appendix. Timeline, from LA-1."),
             (22, "Appendix. References, from LA-1.")):
    notes(S[i], t)
s = prep(21, "APPENDIX: PIPELINE FLOW OF ONE REQUEST")
box(s, 1.0, 2.15, 18.0, 8.2, WHITE, line=PALE)
picture(s, "deck_pipeline.png", 1.8, 2.25, h=8.0, border=None)
notes(s, "Appendix. One request is one database transaction: steps 1-6 write, step 7 commits only if every step "
      "succeeded, otherwise nothing is stored.")

prs.save(OUT)
os.remove(base)
print("saved", OUT, len(prs.slides))
