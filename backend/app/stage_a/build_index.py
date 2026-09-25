"""Build the k-NN category index from the dataset's TRAIN split only (val/test stay unseen).

    python -m app.stage_a.build_index [--dataset path/to/promptopt_dataset_v1.csv] [--dolly path/to/dolly.jsonl]

With --dolly, instructions from Dolly-15k brainstorming/creative_writing (tasks PromptOpt does not handle) are added with the label "other".
Records are assigned to the index or to a held-out "other" evaluation set by a hash of their Dolly row number,
so `evaluate` never scores an "other" example the index has seen.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from app.config import CATEGORY_INDEX_PATH, DATASET_DIR, SENTENCE_MODEL
from app.dataset_io import DEFAULT_CSV, load_rows
from app.stage_a.classifier import KNOWN, keyword_features, sentence_encoder


def training_texts(rows: list[dict[str, str]]) -> tuple[list[str], list[str]]:
    """Degraded prompts (what real users type) plus the original instructions, labelled with their category."""
    texts, labels = [], []
    for r in rows:
        if r["category"] not in KNOWN:
            continue
        for field in ("degraded_prompt", "original_instruction"):
            t = (r.get(field) or "").strip()
            if t:
                texts.append(t)
                labels.append(r["category"])
    return texts, labels


DEFAULT_DOLLY = DATASET_DIR.parent / "dolly" / "databricks-dolly-15k.jsonl"
# open_qa/general_qa are deliberately NOT used: without their passage, degraded closed_qa prompts look exactly like
# open_qa questions, and adding them cut closed_qa recall on val from 0.80 to 0.70.
OTHER_DOLLY_CATEGORIES = ("brainstorming", "creative_writing")
OTHER_PER_CATEGORY = 250      # index examples per Dolly category
OTHER_EVAL_FRACTION = 0.2     # share of Dolly out-of-scope rows held out for evaluation
HEAD_C = 4.0                  # inverse regularisation of the linear head, chosen by 5-fold CV on train


def _bucket(row_no: int) -> float:
    return int(hashlib.sha256(f"dolly-{row_no}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def dolly_other(path: Path, held_out: bool) -> list[str]:
    """Out-of-scope Dolly instructions: the index part (held_out=False) or the evaluation part (held_out=True)."""
    per_cat: dict[str, list[tuple[float, str]]] = {c: [] for c in OTHER_DOLLY_CATEGORIES}
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            if r["category"] in per_cat and r["instruction"].strip():
                b = _bucket(i)
                if (b < OTHER_EVAL_FRACTION) == held_out:
                    per_cat[r["category"]].append((b, r["instruction"].strip()))
    out = []
    for items in per_cat.values():
        out.extend(t for _, t in sorted(items)[:OTHER_PER_CATEGORY if not held_out else None])
    return out


def train_head(emb: np.ndarray, texts: list[str], labels: list[str]):
    """Logistic regression over [embedding, keyword features], classes weighted so each category counts equally."""
    from sklearn.linear_model import LogisticRegression

    x = np.hstack([emb, np.vstack([keyword_features(t) for t in texts])])
    return LogisticRegression(C=HEAD_C, class_weight="balanced", max_iter=3000).fit(x, labels)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--dolly", type=Path, default=DEFAULT_DOLLY,
                    help="Dolly-15k jsonl for 'other' examples (skipped if the file does not exist)")
    ap.add_argument("--out", type=Path, default=CATEGORY_INDEX_PATH)
    args = ap.parse_args()

    texts, labels = training_texts(load_rows(args.dataset, split="train"))
    if args.dolly.exists():
        other = dolly_other(args.dolly, held_out=False)
        texts += other
        labels += ["other"] * len(other)
    else:
        print(f"No Dolly file at {args.dolly}: index has no 'other' examples")
    start = time.perf_counter()
    emb = sentence_encoder(SENTENCE_MODEL)(texts)
    head = train_head(emb, texts, labels)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, embeddings=emb, labels=np.array(labels), model_name=np.array(SENTENCE_MODEL),
                        head_coef=head.coef_, head_intercept=head.intercept_, head_classes=head.classes_)
    print(f"Indexed {len(texts)} train texts ({emb.shape[1]}-d) and trained the linear head in "
          f"{time.perf_counter() - start:.1f}s -> {args.out}")


if __name__ == "__main__":
    main()
