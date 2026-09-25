"""A01: task-category detection.

Two classifiers with the same interface, `predict(text) -> (scores: dict[category, float], method: str)`:

* EmbeddingClassifier: Sentence-Transformers (all-MiniLM-L6-v2) k-nearest-neighbour vote over labelled prompts
  from the dataset's *train* split, averaged with a logistic-regression head trained on the same embeddings plus
  the keyword cues. Build the index (and the head) once with `python -m app.stage_a.build_index`.
  In 5-fold cross-validation on train the average beats either part alone: accuracy 72.9% vs 69.3% (k-NN) and
  70.4% (head), and at 90% precision it keeps 63% of prompts above the confidence gate vs 53% (k-NN).
* KeywordClassifier: regex cues. Used when no index has been built, and blended into the embedding scores
  because explicit cues ("summarize", "write a function") are more reliable than similarity alone.

"other" is learned from labelled out-of-scope examples in the index (Dolly brainstorming and
creative_writing, see build_index.py). As a backstop, a prompt whose nearest labelled neighbour is not similar
enough is also classified as "other".
"""
import re
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

from app.config import TASK_CATEGORIES

KNOWN = [c for c in TASK_CATEGORIES if c != "other"]   # categories with keyword cues
LABELS = list(TASK_CATEGORIES)                          # labels allowed in the k-NN index
_I = re.IGNORECASE

KEYWORD_CUES: dict[str, list[tuple[re.Pattern, float]]] = {
    "coding": [(re.compile(p, _I), w) for p, w in (
        (r"\b(?:function|program|script|code|algorithm|implement\w*|class|method|compile|regex|regular expression|"
         r"api|endpoint|array|linked list|loop|recursion|variable|debug|bug|syntax|sql query|query|database schema|"
         r"html|css|unit tests?|refactor|runtime|big-?o|data structure|string|integer|boolean)\b", 1.0),
        (r"\b(?:python|java|javascript|typescript|c\+\+|c#|golang|rust|ruby|php|swift|kotlin|sql|bash|node\.?js|react)\b", 1.5),
        (r"\b(?:write|create|generate|construct|develop|design|build) (?:a |an )?(?:\w+ ){0,3}(?:function|program|"
         r"script|class|method|query|algorithm|code|web ?page|app)\b", 2.0),
    )],
    "summarization": [(re.compile(p, _I), w) for p, w in (
        (r"\b(?:summar(?:y|ies|i[sz]e[sd]?|i[sz]ing)|tl;?dr|sum (?:it )?up|recap|gist|condense|in a nutshell|"
         r"synopsis|overview)\b", 3.0),
        (r"\b(?:main|key) (?:points|ideas|takeaways)\b", 1.5),
    )],
    "classification": [(re.compile(p, _I), w) for p, w in (
        (r"\b(?:classify|categori[sz]e|label|sort (?:these|them|the following) into|group (?:these|them)|"
         r"sentiment)\b", 3.0),
        (r"\bwhich (?:of (?:these|the following|them) )?(?:one|ones)?\s*(?:is|are)\b", 1.5),
        (r"\b(?:identify|tell me|say) which\b", 2.0),
        (r"\b\w+ or \w+\s*[:?]", 1.0),
        (r"\bis (?:a|an) \w+ (?:a|an) \w+\b", 0.5),
    )],
    "information_extraction": [(re.compile(p, _I), w) for p, w in (
        (r"\bextract\w*\b", 3.0),
        (r"\b(?:list|pull out|find|identify|give me)(?: all| out| the)? (?:\w+ ){0,2}(?:names?|dates?|places?|"
         r"people|numbers?|years?|cities|countries|companies|products|locations?|entities|items)\b", 2.0),
        (r"\b(?:mentioned|listed|named) in\b", 1.5),
        (r"\blist (?:all|the|out|of)\b", 1.5),
        (r"\bfrom (?:the|this) (?:text|passage|paragraph|article)\b", 1.0),
    )],
    "closed_qa": [(re.compile(p, _I), w) for p, w in (
        (r"^\s*(?:what|who|whom|when|where|why|how|which|is|are|was|were|does|do|did|can|could|has|have)\b", 1.5),
        (r"\?\s*$", 1.0),
        (r"\b(?:according to|based on) (?:the|this) (?:text|passage|paragraph|article|reference)\b", 1.5),
    )],
}


def keyword_scores(text: str) -> dict[str, float]:
    """Raw keyword cue weights per known category (not normalised; all zero when nothing matches)."""
    return {cat: sum(w for p, w in cues if p.search(text)) for cat, cues in KEYWORD_CUES.items()}


def keyword_features(text: str) -> np.ndarray:
    """Keyword cues as features for the linear head: normalised cue weight per known category, and a question mark."""
    raw = keyword_scores(text)
    total = sum(raw.values())
    return np.array([raw[c] / total if total else 0.0 for c in KNOWN] + [float(text.strip().endswith("?"))],
                    dtype=np.float32)


def _normalise(scores: dict[str, float]) -> dict[str, float]:
    total = sum(scores.values())
    if total <= 0:
        return {c: 0.0 for c in scores}
    return {c: v / total for c, v in scores.items()}


class KeywordClassifier:
    name = "keyword"

    def predict(self, text: str) -> tuple[dict[str, float], str]:
        raw = keyword_scores(text)
        if not any(raw.values()):
            return {**{c: 0.0 for c in KNOWN}, "other": 1.0}, self.name
        return {**_normalise(raw), "other": 0.0}, self.name


Encoder = Callable[[Sequence[str]], np.ndarray]


def sentence_encoder(model_name: str) -> Encoder:
    """Lazily loaded Sentence-Transformers encoder returning L2-normalised float32 vectors."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, device="cpu")

    def encode(texts: Sequence[str]) -> np.ndarray:
        return model.encode(list(texts), batch_size=64, normalize_embeddings=True,
                            convert_to_numpy=True, show_progress_bar=False).astype(np.float32)
    return encode


class LinearHead:
    """Multinomial logistic regression over [embedding, keyword_features]. Trained with scikit-learn in build_index;
    prediction is plain numpy, so scikit-learn is not needed at runtime."""

    def __init__(self, coef: np.ndarray, intercept: np.ndarray, classes: Sequence[str]):
        if coef.shape != (len(classes), coef.shape[1]) or intercept.shape != (len(classes),):
            raise ValueError("coef/intercept do not match the classes")
        unknown = set(classes) - set(LABELS)
        if unknown:
            raise ValueError(f"unknown classes in head: {sorted(unknown)}")
        self.coef, self.intercept, self.classes = coef.astype(np.float32), intercept.astype(np.float32), list(classes)

    def predict_proba(self, embeddings: np.ndarray, texts: Sequence[str]) -> list[dict[str, float]]:
        z = np.hstack([embeddings, np.vstack([keyword_features(t) for t in texts])]) @ self.coef.T + self.intercept
        z = np.exp(z - z.max(axis=1, keepdims=True))
        p = z / z.sum(axis=1, keepdims=True)
        return [{c: float(row[self.classes.index(c)]) if c in self.classes else 0.0 for c in LABELS} for row in p]


class EmbeddingClassifier:
    """k-NN over labelled example prompts, blended with keyword cues, averaged with the linear head if there is one."""

    name = "embedding"

    def __init__(self, embeddings: np.ndarray, labels: Sequence[str], encoder: Encoder, *,
                 k: int = 25, keyword_weight: float = 0.3, other_threshold: float = 0.3,
                 temperature: float = 0.05, head: LinearHead | None = None, head_weight: float = 0.5):
        # Defaults tuned on the val split (see evaluate.py); never tune on test.
        if len(embeddings) != len(labels):
            raise ValueError("embeddings and labels differ in length")
        unknown = set(labels) - set(LABELS)
        if unknown:
            raise ValueError(f"unknown labels in index: {sorted(unknown)}")
        self.embeddings = embeddings.astype(np.float32)
        self.labels = np.asarray(labels)
        self.encoder = encoder
        self.k, self.keyword_weight = k, keyword_weight
        self.other_threshold, self.temperature = other_threshold, temperature
        self.head, self.head_weight = head, head_weight

    @classmethod
    def load(cls, path: Path, encoder: Encoder | None = None, **kwargs) -> "EmbeddingClassifier":
        data = np.load(path, allow_pickle=False)
        model_name = str(data["model_name"])
        head = None
        if "head_coef" in data:
            head = LinearHead(data["head_coef"], data["head_intercept"], [str(x) for x in data["head_classes"]])
        return cls(data["embeddings"], [str(x) for x in data["labels"]],
                   encoder or sentence_encoder(model_name), head=head, **kwargs)

    def knn_scores(self, query: np.ndarray) -> tuple[dict[str, float], float]:
        """Similarity-weighted vote of the k nearest examples. Returns (scores, top-1 similarity)."""
        sims = self.embeddings @ query
        k = min(self.k, len(sims))
        top = np.argpartition(-sims, k - 1)[:k]
        weights = np.exp((sims[top] - sims[top].max()) / self.temperature)
        scores = {c: 0.0 for c in LABELS}
        for label, w in zip(self.labels[top], weights):
            scores[str(label)] += float(w)
        return _normalise(scores), float(sims[top].max())

    def predict(self, text: str) -> tuple[dict[str, float], str]:
        return self.predict_many([text])[0]

    def predict_many(self, texts: Sequence[str]) -> list[tuple[dict[str, float], str]]:
        out = []
        queries = self.encoder(texts)
        head = self.head.predict_proba(queries, texts) if self.head is not None else [None] * len(texts)
        for text, q, h in zip(texts, queries, head):
            knn, best_sim = self.knn_scores(q)
            kw = {**_normalise(keyword_scores(text)), "other": 0.0}
            w = self.keyword_weight if any(kw.values()) else 0.0
            scores = {c: (1 - w) * knn[c] + w * kw[c] for c in LABELS}
            if h is not None:
                scores = {c: (1 - self.head_weight) * scores[c] + self.head_weight * h[c] for c in LABELS}
            if best_sim < self.other_threshold:
                # Nothing in the labelled data looks like this prompt. "other" gets at least half the mass (so it
                # always wins), more the less similar the nearest example is.
                keep = max(best_sim, 0.0) / self.other_threshold / 2
                scores = {c: v * keep for c, v in scores.items()}
                scores["other"] += 1.0 - keep
            out.append((scores, self.name))
        return out
