"""Stage A entry point: `detect_features(prompt, context=None) -> PromptFeatures`.

    from app.stage_a import detect_features
    features = detect_features("summarize this for me please")
    repository.save_features(db, prompt.id, features.model_dump())
"""
import logging
from functools import lru_cache

from app.config import CATEGORY_INDEX_PATH
from app.stage_a import rules
from app.stage_a.classifier import EmbeddingClassifier, KeywordClassifier
from app.stage_a.schema import PromptFeatures

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _spacy_nlp():
    """spaCy English pipeline, or None if it is not installed (the regex detectors still work)."""
    try:
        import spacy
        return spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
    except (ImportError, OSError):
        log.warning("spaCy model en_core_web_sm not available; pronoun-based ambiguity check disabled")
        return None


def default_classifier():
    """Embedding classifier when the index exists, otherwise the keyword classifier."""
    if CATEGORY_INDEX_PATH.exists():
        return EmbeddingClassifier.load(CATEGORY_INDEX_PATH)
    log.warning("No category index at %s; using keyword classifier. Build it with "
                "`python -m app.stage_a.build_index`.", CATEGORY_INDEX_PATH)
    return KeywordClassifier()


class FeatureDetector:
    def __init__(self, classifier=None, use_spacy: bool = True):
        self.classifier = classifier if classifier is not None else default_classifier()
        self.nlp = _spacy_nlp() if use_spacy else None

    def detect(self, prompt: str, context: str | None = None) -> PromptFeatures:
        return self._build(prompt, context, *self.classifier.predict(prompt))

    def detect_many(self, prompts: list[str], contexts: list[str | None] | None = None) -> list[PromptFeatures]:
        """Batch version: encodes all prompts in one pass when the classifier supports it."""
        contexts = contexts if contexts is not None else [None] * len(prompts)
        if hasattr(self.classifier, "predict_many"):
            preds = self.classifier.predict_many(prompts)
        else:
            preds = [self.classifier.predict(p) for p in prompts]
        return [self._build(p, c, s, m) for p, c, (s, m) in zip(prompts, contexts, preds)]

    def _build(self, prompt: str, context: str | None, scores: dict[str, float], method: str) -> PromptFeatures:
        text = prompt.strip()
        task_type = max(scores, key=scores.get)
        has_context = bool(context and context.strip()) or rules.detect_embedded_context(text)
        doc = self.nlp(text) if self.nlp is not None else None
        sentences = [s.text for s in doc.sents] if doc is not None else None
        format_evidence = rules.detect_format_spec(text)
        present = rules.detect_constraints(text)
        return PromptFeatures(
            task_type=task_type,
            confidence=round(scores[task_type], 4),
            category_scores={c: round(v, 4) for c, v in scores.items()},
            classifier=method,
            has_format_spec=bool(format_evidence),
            format_evidence=format_evidence,
            has_context=has_context,
            constraints_present=list(present),
            missing_constraints=[c for c in rules.RELEVANT_CONSTRAINTS[task_type] if c not in present],
            redundant_phrases=rules.detect_filler(text) + rules.detect_repetition(text, sentences),
            ambiguous_refs=rules.detect_ambiguous_refs(text, has_context, doc),
            word_count=len(text.split()),
        )


@lru_cache(maxsize=1)
def default_detector() -> FeatureDetector:
    return FeatureDetector()


def detect_features(prompt: str, context: str | None = None) -> PromptFeatures:
    return default_detector().detect(prompt, context)
