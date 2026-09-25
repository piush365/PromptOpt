"""Stage A unit tests. No model downloads: the embedding classifier is tested with a fake encoder."""
import numpy as np
import pytest

from app.stage_a import rules
from app.stage_a.classifier import EmbeddingClassifier, KeywordClassifier, LinearHead, keyword_features
from app.stage_a.detector import FeatureDetector
from app.stage_a.schema import PromptFeatures


# ---------------------------------------------------------------- A02 format
@pytest.mark.parametrize("text", [
    "Return a JSON object with keys name and year.",
    "List them as bullet points.",
    "Answer in one sentence.",
    "Output only the label.",
    "Respond with the appropriate label only.",
    "Give a concise answer (max 5 words).",
    "Answer yes or no.",
    "Put the results in a table.",
    "Respond with the date in \"Month Day, Year\" format only.",
])
def test_format_detected(text):
    assert rules.detect_format_spec(text)


@pytest.mark.parametrize("text", [
    "why was the east side of the bridge rebuilt?",
    "summarize the history of the roman empire",
    "write a function to reverse a list",
    "which one is string or percussion: tombak, cizhonghlu",
])
def test_format_not_detected(text):
    assert rules.detect_format_spec(text) == []


# ---------------------------------------------------------------- A03 constraints
def test_constraints_detected():
    found = rules.detect_constraints(
        "Explain recursion to a complete beginner in a friendly tone, in under 100 words, using Python.")
    assert set(found) == {"length", "tone", "audience", "language"}


def test_audience_needs_a_reader_not_content():
    assert "audience" not in rules.detect_constraints("make a class for customer data")
    assert "audience" not in rules.detect_constraints("is candy a healthy choice for kids?")
    assert "audience" in rules.detect_constraints("explain photosynthesis to a 10 year old")


@pytest.mark.parametrize("text, lang", [
    ("write it in go", True), ("an R script to plot data", True), ("use C++ templates", True),
    ("go to the store and get milk", False), ("write a function to add two numbers", False),
])
def test_programming_language(text, lang):
    assert ("language" in rules.detect_constraints(text)) is lang


def test_missing_constraints_depend_on_category():
    assert rules.missing_constraints("summarize this article", "summarization") == ["length", "audience", "tone"]
    assert rules.missing_constraints("summarize this article briefly", "summarization") == ["audience", "tone"]
    assert rules.missing_constraints("write a function to sort a list", "coding") == ["language"]
    assert rules.missing_constraints("write a python function to sort a list", "coding") == []
    assert rules.missing_constraints("classify these animals", "classification") == []


# ---------------------------------------------------------------- A04 redundancy
def test_filler_detected():
    hits = [h.lower() for h in rules.detect_filler(
        "Hey, could you please kindly just summarize this for me? Thanks in advance!")]
    for phrase in ("hey", "please", "kindly", "just", "for me", "thanks in advance"):
        assert phrase in hits, phrase


def test_kind_of_in_a_question_is_not_filler():
    assert rules.detect_filler("What kind of animal is a whale?") == []


def test_repetition_detected():
    hits = rules.detect_repetition("Summarize the text. Keep it short. Summarize the text! Use the the list.")
    assert "Summarize the text!" in hits
    assert "the the" in hits


def test_clean_prompt_has_no_redundancy():
    text = "Summarize the passage in three bullet points."
    assert rules.detect_filler(text) == [] and rules.detect_repetition(text) == []


# ---------------------------------------------------------------- A05 ambiguity
def test_dangling_reference_without_context():
    assert rules.detect_ambiguous_refs("summarize this", has_context=False)
    assert rules.detect_ambiguous_refs("Based on the reference text, when was it built?", has_context=False)


def test_no_ambiguity_when_context_supplied():
    assert rules.detect_ambiguous_refs("summarize this", has_context=True) == []


def test_the_noun_inside_a_longer_phrase_is_not_ambiguous():
    assert rules.detect_ambiguous_refs("make a function that returns the page content", has_context=False) == []


def test_embedded_context():
    assert rules.detect_embedded_context("which one is string or percussion: tombak, cizhonghlu")
    assert rules.detect_embedded_context("Fix this code:\n```\ndef f(x): return x+\n```")
    assert not rules.detect_embedded_context("why was the bridge rebuilt?")


# ---------------------------------------------------------------- A01 classifiers
@pytest.mark.parametrize("text, category", [
    ("summarize the article in a few lines", "summarization"),
    ("write a python function that reverses a string", "coding"),
    ("classify each as a fruit or vegetable: apple, carrot", "classification"),
    ("extract all the dates mentioned in the text", "information_extraction"),
    ("when was the eiffel tower built?", "closed_qa"),
    ("hello there friend", "other"),
])
def test_keyword_classifier(text, category):
    scores, method = KeywordClassifier().predict(text)
    assert method == "keyword"
    assert max(scores, key=scores.get) == category


def _fake_classifier(**kwargs):
    """Each 'text' is encoded by a lookup table of 2-d unit vectors."""
    vec = {"code": [1, 0], "sum": [0, 1], "diag": [0.7071, 0.7071], "far": [-1, 0]}
    enc = lambda texts: np.array([vec[t] for t in texts], dtype=np.float32)  # noqa: E731
    emb = np.array([[1, 0], [0.99, 0.141], [0, 1], [0.141, 0.99]], dtype=np.float32)
    labels = ["coding", "coding", "summarization", "summarization"]
    return EmbeddingClassifier(emb, labels, enc, k=2, keyword_weight=0.0, **kwargs)


def test_embedding_classifier_votes_by_neighbours():
    clf = _fake_classifier()
    scores, _ = clf.predict("code")
    assert max(scores, key=scores.get) == "coding"
    scores, method = clf.predict("sum")
    assert method == "embedding" and max(scores, key=scores.get) == "summarization"
    assert abs(sum(scores.values()) - 1) < 1e-6


def test_embedding_classifier_falls_back_to_other_when_nothing_is_similar():
    scores, _ = _fake_classifier(other_threshold=0.3).predict("far")
    assert max(scores, key=scores.get) == "other" and scores["other"] >= 0.5


def test_embedding_classifier_rejects_unknown_labels():
    with pytest.raises(ValueError):
        EmbeddingClassifier(np.zeros((1, 2)), ["poetry"], lambda t: np.zeros((len(t), 2)))


def test_index_roundtrip(tmp_path):
    path = tmp_path / "idx.npz"
    np.savez_compressed(path, embeddings=np.eye(2, dtype=np.float32), labels=np.array(["coding", "other"]),
                        model_name=np.array("fake"))
    clf = EmbeddingClassifier.load(path, encoder=lambda t: np.array([[1.0, 0.0]] * len(t), dtype=np.float32))
    assert max(clf.predict("x")[0], key=clf.predict("x")[0].get) == "coding"
    assert clf.head is None                                          # indexes built before the head still load


def _fitted_head():
    """sklearn logistic regression on [2-d embedding, keyword features] for texts the fake encoder knows."""
    from sklearn.linear_model import LogisticRegression

    texts = ["code", "sum", "code", "sum", "diag"]
    x = np.hstack([_fake_classifier().encoder(texts), np.vstack([keyword_features(t) for t in texts])])
    return texts, x, LogisticRegression(C=4.0).fit(x, ["coding", "summarization", "coding", "summarization",
                                                         "other"])


def test_linear_head_matches_sklearn():
    texts, x, lr = _fitted_head()
    head = LinearHead(lr.coef_, lr.intercept_, lr.classes_)
    probs = head.predict_proba(_fake_classifier().encoder(texts), texts)
    expected = lr.predict_proba(x)
    for p, e in zip(probs, expected):
        assert [p[c] for c in lr.classes_] == pytest.approx(list(e), abs=1e-5)
        assert p["closed_qa"] == 0.0 and sum(p.values()) == pytest.approx(1.0)


def test_head_is_averaged_with_knn():
    texts, _, lr = _fitted_head()
    head = LinearHead(lr.coef_, lr.intercept_, lr.classes_)
    knn = _fake_classifier().predict("diag")[0]
    blended = _fake_classifier(head=head, head_weight=0.5).predict("diag")[0]
    h = head.predict_proba(_fake_classifier().encoder(["diag"]), ["diag"])[0]
    assert blended == pytest.approx({c: 0.5 * knn[c] + 0.5 * h[c] for c in knn})


def test_index_roundtrip_with_head(tmp_path):
    _, _, lr = _fitted_head()
    path = tmp_path / "idx.npz"
    clf = _fake_classifier()
    np.savez_compressed(path, embeddings=clf.embeddings, labels=clf.labels, model_name=np.array("fake"),
                        head_coef=lr.coef_, head_intercept=lr.intercept_, head_classes=lr.classes_)
    loaded = EmbeddingClassifier.load(path, encoder=clf.encoder, k=2, keyword_weight=0.0)
    assert loaded.head is not None and loaded.head.classes == list(lr.classes_)
    assert max(loaded.predict("code")[0], key=loaded.predict("code")[0].get) == "coding"


def test_linear_head_rejects_bad_shapes_and_classes():
    with pytest.raises(ValueError):
        LinearHead(np.zeros((2, 3)), np.zeros(3), ["coding", "other"])
    with pytest.raises(ValueError):
        LinearHead(np.zeros((1, 3)), np.zeros(1), ["poetry"])


# ---------------------------------------------------------------- detector end to end
@pytest.fixture(scope="module")
def detector():
    return FeatureDetector(classifier=KeywordClassifier(), use_spacy=False)


def test_detector_output(detector):
    f = detector.detect("Hey, can you summarize this for me?")
    assert isinstance(f, PromptFeatures)
    assert f.task_type == "summarization" and 0 <= f.confidence <= 1
    assert not f.has_format_spec and not f.has_context
    assert f.missing_constraints == ["length", "audience", "tone"]
    assert "this" in " ".join(f.ambiguous_refs)
    assert {"hey", "can you", "for me"} <= {p.lower() for p in f.redundant_phrases}


def test_detector_with_context(detector):
    f = detector.detect("summarize this in two sentences", context="The Eiffel Tower was built in 1889 ...")
    assert f.has_context and f.ambiguous_refs == [] and f.has_format_spec
    assert "length" not in f.missing_constraints


def test_features_fit_the_database(detector, tmp_path):
    """Stage A output can be stored with repository.save_features unchanged."""
    from sqlalchemy.orm import sessionmaker

    from app.db import models, repository  # noqa: F401
    from app.db.base import Base, make_engine
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        prompt = repository.create_prompt(db, "write a function to sort a list please")
        f = detector.detect(prompt.original_text)
        row = repository.save_features(db, prompt.id, f.model_dump())
        db.commit()
        assert row.task_type == "coding" and row.missing_constraints == ["language"]
    engine.dispose()


def test_spacy_pronoun_check():
    pytest.importorskip("spacy")
    det = FeatureDetector(classifier=KeywordClassifier(), use_spacy=True)
    if det.nlp is None:
        pytest.skip("en_core_web_sm not installed")
    assert "it" in det.detect("what does it mean?").ambiguous_refs
    assert det.detect("what does the word serendipity mean?").ambiguous_refs == []
