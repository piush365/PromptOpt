"""Stage B unit tests. Features come from the real Stage A detectors with a fixed category (no model download)."""
import pytest

from app.db import repository as repo
from app.db.seed import RULES as SEEDED
from app.stage_a.classifier import KeywordClassifier
from app.stage_a.detector import FeatureDetector
from app.stage_b import rules as b
from app.stage_b.ir import PromptIR, render_plain
from app.stage_b.optimizer import RULE_CODES, optimize

CATS = ["closed_qa", "information_extraction", "classification", "summarization", "coding", "other"]
_DET = FeatureDetector(classifier=KeywordClassifier(), use_spacy=False)


def feats(text: str, category: str, confidence: float = 0.9, context: str | None = None):
    rest = (1 - confidence) / (len(CATS) - 1)
    return _DET._build(text, context, {c: confidence if c == category else rest for c in CATS}, "test")


def ir_of(text: str, category: str, **kw) -> PromptIR:
    return PromptIR(category=category, task=text, **kw)


# ---------------------------------------------------------------- tidy
@pytest.mark.parametrize("raw, clean", [
    ("  summarize   the text ", "Summarize the text."),
    ("who wrote hamlet", "Who wrote hamlet?"),
    ("how do i sort a list", "How do I sort a list?"),
    ("i need the names , please", "I need the names, please."),
    ("why does for i in range(3) fail", "Why does for i in range(3) fail?"),
    ("which is odd? 3 4 5", "Which is odd? 3 4 5."),
])
def test_tidy(raw, clean):
    assert b.tidy(raw) == clean


# ---------------------------------------------------------------- B07 structure
def test_b07_moves_code_block_into_context():
    text = "fix this ```def f(x): return x +``` please"
    out = b.b07_standardize_structure(ir_of(text, "coding"), feats(text, "coding"))
    assert out.context == "```def f(x): return x +```" and out.task == "Fix this please."


def test_b07_moves_listed_items_into_context():
    text = "which instrument is string or percussion: tombak, cizhonghlu"
    out = b.b07_standardize_structure(ir_of(text, "classification"), feats(text, "classification"))
    assert out.task == "Which instrument is string or percussion?" and out.context == "tombak, cizhonghlu"


@pytest.mark.parametrize("text, category", [
    ("answer this: what is the capital of france and why?", "classification"),   # tail is a question
    ("see https://example.com, then list the authors", "information_extraction"),  # no ': '
    ("question: who wrote it, and when, and where?", "closed_qa"),                 # not a data category
])
def test_b07_leaves_other_colons_alone(text, category):
    out = b.b07_standardize_structure(ir_of(text, category), feats(text, category))
    assert out.context is None


def test_b07_unchanged_ir_is_returned_as_is():
    ir = ir_of("Summarize the text.", "summarization")
    assert b.b07_standardize_structure(ir, feats(ir.task, "summarization")) is ir


# ---------------------------------------------------------------- B01 filler
@pytest.mark.parametrize("raw, clean", [
    ("hey can you please summarize the text for me?", "Summarize the text."),
    ("I was wondering if you could list the dates", "List the dates."),
    ("could you tell me who won?", "Tell me who won."),
    ("can you explain what kind of animal a quokka is?", "Explain what kind of animal a quokka is."),
    ("just basically write a haiku, thanks so much", "Write a haiku."),
])
def test_b01_removes_filler(raw, clean):
    assert b.b01_remove_filler(ir_of(raw, "other"), feats(raw, "other")).task == clean


@pytest.mark.parametrize("raw, clean", [
    ("js code to print please enter your name", "Js code to print please enter your name."),
    ('make a button that says "thank you so much"', 'Make a button that says "thank you so much".'),
    ("hey write an alert with the message just a moment", "Write an alert with the message just a moment."),
])
def test_b01_keeps_filler_words_that_are_content(raw, clean):
    assert b.b01_remove_filler(ir_of(raw, "coding"), feats(raw, "coding")).task == clean


def test_b01_keeps_prompt_that_is_only_filler():
    ir = ir_of("please, thank you", "other")
    assert b.b01_remove_filler(ir, feats(ir.task, "other")) is ir


# ---------------------------------------------------------------- B02 repetition
def test_b02_removes_repeated_sentences_and_doubled_words():
    text = "Summarize the the article. Keep it short. Summarize the article."
    out = b.b02_remove_duplicates(ir_of(text, "summarization"), feats(text, "summarization"))
    assert out.task == "Summarize the article. Keep it short."


def test_b02_keeps_allowed_doubles():
    ir = ir_of("He had had enough.", "other")
    assert b.b02_remove_duplicates(ir, feats(ir.task, "other")) is ir


# ---------------------------------------------------------------- B06 labels
@pytest.mark.parametrize("task, labels", [
    ("Which one is string or percussion", ["string", "percussion"]),
    ("Classify these as fruit, vegetable or grain", ["fruit", "vegetable", "grain"]),
    ("Sort them into mammals and birds", ["mammals", "birds"]),
    ("Which are mammals and which are birds", ["mammals", "birds"]),
    ("Is it a fruit or a vegetable?", ["fruit", "vegetable"]),
    ("Classify each word as a 'day of the week' or a 'month'", ["day of the week", "month"]),
    ("which instrument is string or percussion agiarut agung", ["string", "percussion"]),   # item glued on
    ("Which fruit would be a bad choice for a song lyric", []),
])
def test_extract_labels(task, labels):
    assert b.extract_labels(task) == labels


def test_b06_states_labels():
    text = "Classify these as positive or negative."
    out = b.b06_add_labels(ir_of(text, "classification"), feats(text, "classification"))
    assert out.requirements == ('Use only these labels: "positive", "negative".',)


def test_b06_which_of_these_becomes_yes_no():
    text = "Which of these ski resorts are in Utah?"
    out = b.b06_add_labels(ir_of(text, "classification"), feats(text, "classification"))
    assert out.requirements == ('Use only these labels: "yes", "no".',)


def test_b06_unknown_labels_go_to_stage_c():
    text = "What are the main elements in earth?"
    out = b.b06_add_labels(ir_of(text, "classification"), feats(text, "classification"))
    assert out.requirements == () and out.unresolved == ("label set",)


def test_b06_skips_prompts_that_already_list_labels():
    ir = ir_of("Classify these. Labels: spam, ham.", "classification")
    assert b.b06_add_labels(ir, feats(ir.task, "classification")) is ir


# ---------------------------------------------------------------- B05 language
def test_b05_defaults_to_python():
    text = "Write a function that reverses a list."
    assert b.b05_add_language(ir_of(text, "coding"), feats(text, "coding")).constraints == ("Use Python.",)


def test_b05_keeps_language_of_supplied_code():
    text = "Edit that function to return squares."
    out = b.b05_add_language(ir_of(text, "coding"), feats(text, "coding", context="function f(a) { return a; }"))
    assert out.constraints == (b.KEEP_LANGUAGE,)


@pytest.mark.parametrize("text", ["Write a js function to compare strings.", "Write a Rust function to add two numbers."])
def test_b05_named_language_is_left_alone(text):
    ir = ir_of(text, "coding")
    assert b.b05_add_language(ir, feats(text, "coding")) is ir


# ---------------------------------------------------------------- B04 length
def test_b04_adds_length_where_it_matters():
    text = "Who wrote Hamlet?"
    assert b.b04_add_length(ir_of(text, "closed_qa"), feats(text, "closed_qa")).constraints == (
        b.LENGTH_DEFAULTS["closed_qa"],)
    text = "Classify these as red or blue."
    ir = ir_of(text, "classification")
    assert b.b04_add_length(ir, feats(text, "classification")) is ir


def test_b04_respects_stated_length():
    ir = ir_of("Summarize the article in 3 sentences.", "summarization")
    assert b.b04_add_length(ir, feats(ir.task, "summarization")) is ir


# ---------------------------------------------------------------- B03 format
def test_b03_adds_category_format():
    text = "Summarize the article."
    assert b.b03_add_output_format(ir_of(text, "summarization"), feats(text, "summarization")).output_format == (
        b.FORMAT_DEFAULTS["summarization"])


def test_b03_respects_stated_format():
    for text in ("Summarize the article as a JSON object.", "List the ingredients separated by commas."):
        ir = ir_of(text, "summarization")
        assert b.b03_add_output_format(ir, feats(text, "summarization")) is ir


@pytest.mark.parametrize("text, single", [
    ("Is a tomato a fruit or a vegetable?", True),
    ("Does a whale count as a fish or a mammal?", True),
    ("Classify these as fruit or vegetable.", False),
    # items glued onto the question (val: dolly-728 got "Output only the label." and answered one item)
    ("Which instrument is string or percussion lummi stick timple?", False),
    ("Which characters are dc or marvel? sif, wonder woman.", False),
    ("Is french fries a healthy choice for kids or not? Same for banana, candy, vegetables.", False),
    ("Is Sif and Wonder Woman dc or marvel?", False),
])
def test_b03_classification_single_vs_many_items(text, single):
    out = b.b03_add_output_format(ir_of(text, "classification"), feats(text, "classification"))
    assert out.output_format == (b.SINGLE_LABEL_FORMAT if single else b.FORMAT_DEFAULTS["classification"])


def test_b03_items_in_context_are_never_single():
    text = "Is it a fruit or a vegetable?"
    ir = ir_of(text, "classification", context="tomato")
    assert b.b03_add_output_format(ir, feats(text, "classification")).output_format == b.FORMAT_DEFAULTS["classification"]


def test_every_default_format_is_recognised_by_stage_a():
    """Otherwise running Stage B twice would add a second format line."""
    for fmt in [*b.FORMAT_DEFAULTS.values(), b.SINGLE_LABEL_FORMAT]:
        assert feats(fmt, "other").has_format_spec, fmt
    for text in [*b.LENGTH_DEFAULTS.values(), b.GROUP_LENGTH, b.GROUP_BOTH]:
        assert "length" in feats(text, "other").constraints_present, text


# ---------------------------------------------------------------- category gate
@pytest.mark.parametrize("category, confidence", [("summarization", 0.45), ("other", 0.9)])
def test_uncertain_or_other_category_gets_clean_up_only(category, confidence):
    text = "hey summarize the article"
    out = optimize(text, feats(text, category, confidence))
    assert out.optimized_text == "Summarize the article."
    assert out.rules_applied == ["B07_STANDARDIZE_STRUCTURE", "B01_REMOVE_FILLER"]
    assert "task category" in out.unresolved and "output format" in out.unresolved
    assert out.needs_stage_c


# ---------------------------------------------------------------- optimizer
def test_optimize_full_example():
    text = "hey which instrument is string or percussion: tombak, cizhonghlu"
    out = optimize(text, feats(text, "classification", 0.9))
    assert out.optimized_text == (
        "Which instrument is string or percussion?\n\nInput:\ntombak, cizhonghlu\n\n"
        'Use only these labels: "string", "percussion". For each item, output "item: label" on its own line.')
    assert out.rules_applied == ["B07_STANDARDIZE_STRUCTURE", "B01_REMOVE_FILLER", "B06_ADD_LABELS",
                                 "B03_ADD_OUTPUT_FORMAT"]
    assert out.confidence == 0.9 and not out.needs_stage_c and out.unresolved == ()


def test_steps_form_a_chain_from_original_to_result():
    text = "can you please write a function that sorts a list"
    out = optimize(text, feats(text, "coding"))
    assert out.steps[0]["before"] == text
    for prev, nxt in zip(out.steps, out.steps[1:]):
        assert prev["after"] == nxt["before"]
    assert out.steps[-1]["after"] == out.optimized_text == render_plain(out.ir)
    assert out.optimized_text == ("Write a function that sorts a list.\n\n"
                                  "Use Python. Return only the code, in a single code block.")


def test_disabled_rules_are_skipped_for_ablation():
    text = "write a function that sorts a list"
    out = optimize(text, feats(text, "coding"), disabled={"B05_ADD_LANGUAGE"})
    assert "B05_ADD_LANGUAGE" not in out.rules_applied and "Python" not in out.optimized_text
    with pytest.raises(ValueError):
        optimize(text, feats(text, "coding"), disabled={"B99_NOPE"})


def test_ambiguous_reference_goes_to_stage_c_even_with_a_sure_category():
    text = "summarize this"                                       # nothing to summarize
    out = optimize(text, feats(text, "summarization", 0.9))
    assert out.unresolved == ("ambiguous reference: 'summarize this'",)
    assert out.needs_stage_c and out.stage_c_reasons == ["ambiguous reference: 'summarize this'"]
    assert out.confidence == pytest.approx(0.7)                   # 0.9 - 0.2 per unresolved item


def test_sure_category_with_nothing_unresolved_finishes_after_stage_b():
    text = "who wrote hamlet"
    out = optimize(text, feats(text, "closed_qa", 0.62))          # just above the gate, confidence below 0.7
    assert "B03_ADD_OUTPUT_FORMAT" in out.rules_applied and out.unresolved == () and not out.needs_stage_c


def test_missing_label_set_is_recorded_but_not_routed():
    text = "which fruit would be a bad choice for a song lyric"
    out = optimize(text, feats(text, "classification", 0.9))
    assert out.unresolved == ("label set",) and not out.needs_stage_c


# ---------------------------------------------------------------- B08 group fallback
PASSAGE = "The Eiffel Tower was completed in 1889 for the World's Fair in Paris."


def test_b08_applies_group_rules_when_only_the_group_is_sure():
    text = "when was it finished"
    f = feats(text, "closed_qa", 0.45, context=PASSAGE)          # rest 0.11 each: group = 0.45 + 0.22 = 0.67
    assert b.group_applies(f)
    out = optimize(text, f)
    assert out.optimized_text == "When was it finished?\n\nAnswer from the provided text in at most three sentences."
    assert out.rules_applied == ["B07_STANDARDIZE_STRUCTURE", "B08_GROUP_FALLBACK"]
    assert out.ir.category_group == b.TEXT_GROUP_NAME and out.ir.output_format is None
    assert out.unresolved == () and not out.needs_stage_c


@pytest.mark.parametrize("text, added", [
    ("based on the text, describe the tower in two sentences", ()),
    ("describe the tower in two sentences", (b.GROUP_GROUNDED,)),
    ("from the provided text, describe the tower", (b.GROUP_LENGTH,)),
])
def test_b08_only_adds_what_is_missing(text, added):
    out = b.b08_group_fallback(ir_of(text, "summarization"), feats(text, "summarization", 0.45, context=PASSAGE))
    assert out.constraints == added and out.category_group == b.TEXT_GROUP_NAME


def test_b08_output_is_stable_when_run_again():
    text = "when was it finished"
    once = optimize(text, feats(text, "closed_qa", 0.45, context=PASSAGE))
    twice = b.b08_group_fallback(ir_of(once.optimized_text, "closed_qa"),
                                 feats(once.optimized_text, "closed_qa", 0.45, context=PASSAGE))
    assert twice.constraints == ()


@pytest.mark.parametrize("category, confidence, context", [
    ("closed_qa", 0.45, None),              # no attached text
    ("coding", 0.45, PASSAGE),              # group only 0.33
    ("closed_qa", 0.65, PASSAGE),           # single category is sure: category rules instead
    ("other", 0.62, PASSAGE),               # sure it is out of scope
])
def test_b08_does_not_apply(category, confidence, context):
    text = "when was it finished"
    assert not b.group_applies(feats(text, category, confidence, context=context))


def test_b08_can_be_switched_off_for_ablation():
    text = "when was it finished"
    out = optimize(text, feats(text, "closed_qa", 0.45, context=PASSAGE), disabled={"B08_GROUP_FALLBACK"})
    assert out.needs_stage_c and "task category" in out.unresolved and out.ir.category_group is None


def test_running_twice_adds_nothing_new():
    for text, cat in [("write a function that sorts a list", "coding"), ("who wrote hamlet", "closed_qa"),
                      ("classify these as spam or ham", "classification"), ("summarize the article", "summarization"),
                      ("extract the dates from the text", "information_extraction")]:
        once = optimize(text, feats(text, cat))
        twice = optimize(once.optimized_text, feats(once.optimized_text, cat))
        added = {"B03_ADD_OUTPUT_FORMAT", "B04_ADD_LENGTH", "B05_ADD_LANGUAGE", "B06_ADD_LABELS"}
        assert not added & set(twice.rules_applied), (text, twice.rules_applied)


def test_rule_codes_match_the_seeded_catalogue():
    seeded_b = {code for code, _, stage, _ in SEEDED if stage == "B"}
    assert set(RULE_CODES) == seeded_b


def test_result_is_saved_through_the_repository(db):
    text = "hey summarize the article in the text"
    out = optimize(text, feats(text, "summarization", 0.9, context="Some article."))
    prompt = repo.create_prompt(db, text)
    result = repo.save_optimization(db, prompt.id, out.optimized_text, out.ir.model_dump(mode="json"),
                                    out.confidence, out.steps)
    db.commit()
    assert result.ir["category"] == "summarization" and result.ir["output_format"] == "Use bullet points."
    assert [t.rule.code for t in result.transformations] == out.rules_applied


# ---------------------------------------------------------------- B09-B13 attachment modifier
from app.stage_b.ir import Attachment  # noqa: E402

ATTACHMENT_RULES = [("image", b.b09_attachment_image), ("pdf", b.b10_attachment_pdf), ("pptx", b.b11_attachment_pptx),
                    ("docx", b.b12_attachment_docx), ("other", b.b13_attachment_other)]


@pytest.mark.parametrize("kind, rule", ATTACHMENT_RULES)
def test_attachment_rule_adds_its_requirements_first(kind, rule):
    text = "summarize this"
    ir = ir_of(text, "summarization", attachment=Attachment(type=kind, name="f.x"),
               requirements=("Existing requirement.",), unresolved=("ambiguous reference: 'this'", "label set"))
    out = rule(ir, feats(text, "summarization"))
    expected = tuple(r.format(name=" (f.x)") for r in b.ATTACHMENT_REQUIREMENTS[kind])
    assert out.requirements == (*expected, "Existing requirement.")
    assert "f.x" in out.requirements[0]
    assert out.unresolved == ("label set",)            # the attachment is what 'this' refers to


@pytest.mark.parametrize("kind, rule", ATTACHMENT_RULES)
def test_attachment_rule_ignores_other_types(kind, rule):
    text = "summarize this"
    for other in ("none", "image", "pdf", "pptx", "docx", "other"):
        if other == kind:
            continue
        ir = ir_of(text, "summarization", attachment=Attachment(type=other))
        assert rule(ir, feats(text, "summarization")) == ir


def test_attachment_wording():
    ir = ir_of("x", "summarization", attachment=Attachment(type="pdf"))
    out = b.b10_attachment_pdf(ir, feats("x", "summarization"))
    assert out.requirements[:2] == ("Use the attached PDF as the source.",
                                    "Cite the page or section numbers for the information you use.")
    ir = ir_of("x", "closed_qa", attachment=Attachment(type="image", name="shot.png"))
    out = b.b09_attachment_image(ir, feats("x", "closed_qa"))
    assert out.requirements[0] == "Use what is visible in the attached image (shot.png); describe the parts you rely on."


def test_optimize_with_attachment_logs_the_rule_and_can_switch_it_off():
    text = "summarize this"
    f = feats(text, "summarization")
    out = optimize(text, f, attachment=Attachment(type="pdf", name="r.pdf"))
    assert "B10_ATTACHMENT_PDF" in out.rules_applied and out.ir.context_ref == "attachment"
    assert "Use the attached PDF (r.pdf) as the source." in out.optimized_text
    assert not any(u.startswith("ambiguous reference") for u in out.unresolved)
    off = optimize(text, f, attachment=Attachment(type="pdf"), disabled={"B10_ATTACHMENT_PDF"})
    assert "B10_ATTACHMENT_PDF" not in off.rules_applied and "PDF" not in off.optimized_text
    assert off.ir.attachment.type == "pdf"             # still recorded in the IR for the renderers


def test_attachment_counts_as_material_for_the_group_fallback():
    text = "when was it finished"
    f = feats(text, "closed_qa", 0.45)                  # no text attached: B08 cannot apply
    assert "B08_GROUP_FALLBACK" not in optimize(text, f).rules_applied
    assert "B08_GROUP_FALLBACK" in optimize(text, f, attachment=Attachment(type="docx")).rules_applied


# ---------------------------------------------------------------- user-selected category
def test_user_category_overrides_stage_a():
    text = "tell me about the causes of the war"
    f = feats(text, "closed_qa", 0.4)                   # Stage A unsure, and wrong
    auto = optimize(text, f)
    assert auto.ir.category == "closed_qa" and auto.ir.category_source == "stage_a"
    assert "task category" in auto.unresolved and auto.needs_stage_c
    user = optimize(text, f, category="summarization")
    assert user.ir.category == "summarization" and user.ir.category_source == "user"
    assert "task category" not in user.unresolved
    assert user.ir.output_format == b.FORMAT_DEFAULTS["summarization"]
    assert b.LENGTH_DEFAULTS["summarization"] in user.ir.constraints   # constraints re-derived for summarization
    assert f.task_type == "closed_qa"                   # Stage A's features are not modified


def test_user_category_is_logged(caplog):
    import logging
    text = "sort a list"
    with caplog.at_level(logging.INFO, logger="app.stage_b.optimizer"):
        optimize(text, feats(text, "closed_qa", 0.5), category="coding")
    assert "category coding from user (Stage A said closed_qa)" in caplog.text


def test_unknown_user_category_is_rejected():
    with pytest.raises(ValueError, match="unknown category"):
        optimize("x", feats("x", "closed_qa"), category="poetry")
    with pytest.raises(ValueError):
        optimize("x", feats("x", "closed_qa"), category="other")


@pytest.mark.parametrize("context, separate, att, ref", [
    (None, False, "none", "none"), ("a, b", False, "none", "inline"), (None, True, "none", "separate"),
    ("a, b", True, "none", "separate"), (None, True, "pdf", "attachment")])
def test_context_ref(context, separate, att, ref):
    from app.stage_b.ir import context_ref_for
    assert context_ref_for(context, separate, Attachment(type=att)) == ref


def test_target_llm_is_recorded_in_the_ir():
    assert optimize("sort a list", feats("sort a list", "coding"), target_llm="gemini").ir.target_llm == "gemini"



@pytest.mark.parametrize("text, labels", [
    # val dolly-7818: got "yes"/"no" and the model answered "no" for every country
    ("Which of these are flowers and which are european countries? roses, norway, tulips",
     ["flowers", "european countries"]),
    ("Which are dogs and which are birds: Phoenix, Husky", ["dogs", "birds"]),
])
def test_b06_two_groups_with_words_before_are(text, labels):
    assert b.extract_labels(text.rstrip(".?!")) == labels
    ir = b.b06_add_labels(ir_of(text, "classification"), feats(text, "classification"))
    assert "yes" not in ir.requirements[0] and labels[0] in ir.requirements[0]


def test_b06_yes_no_only_without_named_groups():
    text = "Which of these ski resorts are in utah"
    ir = b.b06_add_labels(ir_of(text, "classification"), feats(text, "classification"))
    assert ir.requirements == ('Use only these labels: "yes", "no".',)
