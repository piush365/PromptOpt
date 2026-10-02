"""Build Stage C training/validation data from the final dataset.

    python -m app.stage_c.data                  # writes data/stage_c/{train,val}.jsonl + stats.json, then packages
    python -m app.stage_c.data --package        # only package: config.json, manifest.json, stage_c_data_v1.zip
    python -m app.stage_c.data --test           # final evaluation only: data/stage_c/test.jsonl (run once)

The zip (data/stage_c_data_v1.zip) is what the Colab notebook reads from Drive: train/val JSONL, config.json, the
training script and manifest.json (sha256 + row counts). The data stays out of git; docs/stage_c_data_manifest.json
(a copy of the manifest) is committed so the zip on Drive can be checked against the commit.

One example per dataset row:
    input   the degraded prompt, the category Stage A (or the user) gave it, and Stage B's IR with the fields Stage C
            must fill set to null and listed in `unresolved`
    target  JSON with exactly those fields, taken from the dataset's optimized prompt by app.stage_c.parse

Which fields are unresolved:
* routed      the prompt goes to Stage C (optimizer.STAGE_C_REASONS): "task category" -> output_format + constraints
              (Stage B added nothing category-specific) + category; "ambiguous reference" -> task
* recorded    "output format" left by B03 -> output_format (not routed in the pipeline, but the same contract)
* forced      everything else: a seeded random non-empty subset of task / output_format / constraints, so the model
              also learns to fill any field it is asked for (Phase 3 evaluates forced routing of all prompts)
On val, every row also gets a `forced_all` example (all three fields) for the forced-routing evaluation.

Stage A on train is cross-fitted: the category index was built from the train split, so each train prompt is
classified by an index and head built without its fold (5 folds, grouped by original instruction). The embeddings
are the ones already stored in the index; nothing is re-encoded. Val/test are not in the index, so they use it as is.
"""
import argparse
import hashlib
import json
import random
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from app.config import BACKEND_DIR, CATEGORY_INDEX_PATH
from app.dataset_io import DEFAULT_CSV, load_rows
from app.stage_a.build_index import DEFAULT_DOLLY, dolly_other, train_head
from app.stage_a.classifier import EmbeddingClassifier, LinearHead, sentence_encoder
from app.stage_a.detector import FeatureDetector
from app.stage_b.optimizer import optimize
from app.stage_c.contract import FIELDS, SYSTEM_PROMPT, model_input, natural_unresolved, to_messages
from app.stage_c.parse import is_format, parse_optimized, states_format

OUT_DIR = BACKEND_DIR.parent / "data" / "stage_c"
FOLDS = 5
SEED = 13
DATA_VERSION = "stage_c_data_v1"
MANIFEST_COPY = BACKEND_DIR.parent / "docs" / "stage_c_data_manifest.json"
# Training settings, read by train.py (local and Colab). Max length: chat-templated train examples are 291 tokens at
# the median, 371 at p99 and 446 at most (Qwen2.5 tokenizer), so 512 truncates nothing.
TRAIN_CONFIG = {
    "base_model": "Qwen/Qwen2.5-0.5B-Instruct",
    "seed": SEED,
    "max_length": 512,
    "fields": [*FIELDS, "category"],
    "categories": ["closed_qa", "information_extraction", "classification", "summarization", "coding"],
    "system_prompt": None,                     # filled from SYSTEM_PROMPT below; also inside every example
    "lora": {"r": 16, "alpha": 32, "dropout": 0.05,
             "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]},
    "train": {"epochs": 3, "batch_size": 4, "grad_accum": 4, "eval_batch_size": 8, "lr": 2e-4, "weight_decay": 0.0,
              "warmup_ratio": 0.03, "max_grad_norm": 1.0, "eval_every": 50, "patience": 3},
}

def _fold(row: dict[str, str]) -> int:
    key = (row["original_instruction"] or row["degraded_prompt"]).strip().lower()
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % FOLDS


class _Lookup:
    """Encoder that returns stored embeddings (falls back to the real encoder for unseen text)."""

    def __init__(self, texts: list[str], emb: np.ndarray, model_name: str):
        self.table = {t: e for t, e in zip(texts, emb)}
        self.model_name, self._real = model_name, None

    def __call__(self, texts):
        missing = [t for t in texts if t not in self.table]
        if missing:
            self._real = self._real or sentence_encoder(self.model_name)
            self.table.update(zip(missing, self._real(missing)))
        return np.vstack([self.table[t] for t in texts])


def crossfit_features(train: list[dict[str, str]], index_path: Path = CATEGORY_INDEX_PATH) -> list:
    """Stage A features for each train row from an index + head that never saw the row's fold."""
    data = np.load(index_path, allow_pickle=False)
    emb, labels, model_name = data["embeddings"], [str(x) for x in data["labels"]], str(data["model_name"])
    owner, texts = [], []                       # index position -> train row (or -1 for Dolly "other"), and its text
    for i, r in enumerate(train):
        for field in ("degraded_prompt", "original_instruction"):
            if (r.get(field) or "").strip():
                owner.append(i)
                texts.append(r[field].strip())
    n_other = len(labels) - len(owner)
    if n_other < 0 or labels[:len(owner)] != [train[i]["category"] for i in owner]:
        raise SystemExit(f"{index_path} was not built from this train split; rebuild it with app.stage_a.build_index")
    other = dolly_other(DEFAULT_DOLLY, held_out=False) if n_other else []
    if len(other) != n_other:
        raise SystemExit(f"{index_path} has {n_other} 'other' examples but {DEFAULT_DOLLY} gives {len(other)}")
    owner += [-1] * n_other
    texts += other
    folds = np.array([_fold(train[o]) if o >= 0 else -1 for o in owner])
    encoder = _Lookup(texts, emb, model_name)
    feats: list = [None] * len(train)
    for k in range(FOLDS):
        keep = folds != k
        head = train_head(emb[keep], list(np.array(texts)[keep]), list(np.array(labels)[keep]))
        clf = EmbeddingClassifier(emb[keep], list(np.array(labels)[keep]), encoder,
                                  head=LinearHead(head.coef_, head.intercept_, head.classes_))
        idx = [i for i, r in enumerate(train) if _fold(r) == k]
        det = FeatureDetector(classifier=clf)
        for i, f in zip(idx, det.detect_many([train[i]["degraded_prompt"] for i in idx],
                                             [train[i]["context"] or None for i in idx])):
            feats[i] = f
    return feats


def target(parsed, category: str, unresolved: list[str]) -> dict:
    values = {"task": parsed.task, "output_format": parsed.output_format, "constraints": parsed.constraints,
              "category": category}
    return {k: values[k] for k in unresolved}


def clean(parsed, unresolved: list[str]) -> bool:
    """False when an asked-for format is still inside the parsed task (the target would miss it)."""
    return not ("output_format" in unresolved and "task" not in unresolved and is_format(parsed.task))


def build(rows: list[dict[str, str]], feats: list, split: str, rng: random.Random) -> list[dict]:
    out_rows = []
    for r, f in zip(rows, feats):
        out = optimize(r["degraded_prompt"], f, separate_text=bool(r["context"].strip()))
        parsed = parse_optimized(r["optimized_prompt"])
        nat = natural_unresolved(out)
        variants = []
        if nat:
            variants.append(("routed" if out.needs_stage_c else "recorded", nat))
        else:
            subset = [k for k in FIELDS if rng.random() < 0.5] or [rng.choice(FIELDS)]
            variants.append(("forced", subset))
        if split != "train":
            variants.append(("forced_all", list(FIELDS)))
        for kind, unresolved in variants:
            inp = model_input(r["degraded_prompt"], f, out.ir, unresolved)
            tgt = target(parsed, r["category"], unresolved)
            out_rows.append({"id": r["id"], "split": split, "category": r["category"], "kind": kind,
                             "stage_a_category": f.task_type, "stage_a_confidence": round(f.confidence, 4),
                             "rules": out.rules_applied, "clean": clean(parsed, unresolved),
                             "human_validated": r["human_validated"] == "True",
                             "input": inp, "target": tgt, "messages": to_messages(inp, tgt)})
    return out_rows


def coverage(rows: list[dict[str, str]]) -> dict:
    """Parser coverage per category: share of prompts whose stated format / constraint lands in its own field."""
    from app.stage_c import parse as P
    stats: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        o, p = r["optimized_prompt"], parse_optimized(r["optimized_prompt"])
        in_task = P.constraint_cues(p.task, ignore_language=True)
        in_cons = set().union(*(P.constraint_cues(c) for c in p.constraints)) if p.constraints else set()
        for c in (r["category"], "all"):
            s = stats[c]
            s["n"] += 1
            s["task"] += len(p.task.split()) >= 3
            s["format_stated"] += states_format(o)
            s["format_separated"] += states_format(o) and p.output_format is not None and not is_format(p.task)
            s["constraint_stated"] += bool(in_task or in_cons)
            s["constraint_separated"] += bool(in_cons) and not in_task
    return {c: dict(s) for c, s in stats.items()}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def package(out: Path) -> Path:
    """config.json + the training script + manifest.json next to the JSONL files, then one zip of exactly these."""
    (out / "config.json").write_text(json.dumps({**TRAIN_CONFIG, "system_prompt": SYSTEM_PROMPT}, indent=2),
                                     encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("train.py"), out / "train_stage_c.py")
    names = ["train.jsonl", "val.jsonl", "config.json", "train_stage_c.py"]
    files = {}
    for name in names:
        rows = sum(1 for line in open(out / name, encoding="utf-8") if line.strip()) if name.endswith(".jsonl") else None
        files[name] = {"sha256": _sha256(out / name), "bytes": (out / name).stat().st_size, "rows": rows}
    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    manifest = {"version": DATA_VERSION, "built_by": "python -m app.stage_c.data", "source": DEFAULT_CSV.name,
                "files": files, "examples": stats["examples"]}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    MANIFEST_COPY.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    zip_path = out.parent / f"{DATA_VERSION}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in [*names, "manifest.json"]:
            z.write(out / name, f"{DATA_VERSION}/{name}")
    print(f"packaged {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB); manifest copy in {MANIFEST_COPY}")
    return zip_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--package", action="store_true", help="only package the existing files")
    ap.add_argument("--test", action="store_true",
                    help="final evaluation only: write test.jsonl (built like val, own seed); train/val untouched")
    args = ap.parse_args()
    if args.package:
        package(args.out)
        return
    if args.test:
        test = load_rows(args.dataset, split="test")
        feats = FeatureDetector().detect_many([r["degraded_prompt"] for r in test], [r["context"] or None for r in test])
        rows = build(test, feats, "test", random.Random(SEED + 1))
        with open(args.out / "test.jsonl", "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(e, ensure_ascii=False) + "\n" for e in rows)
        print(f"test.jsonl: {len(rows)} examples, {Counter(e['kind'] for e in rows)}")
        return

    rng = random.Random(SEED)
    train = load_rows(args.dataset, split="train")
    val = load_rows(args.dataset, split="val")
    examples = build(train, crossfit_features(train), "train", rng)
    examples += build(val, FeatureDetector().detect_many([r["degraded_prompt"] for r in val],
                                                         [r["context"] or None for r in val]), "val", rng)
    args.out.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val"):
        with open(args.out / f"{split}.jsonl", "w", encoding="utf-8") as fh:
            for e in examples:
                if e["split"] == split:
                    fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    stats = {"coverage_train": coverage(train),
             "examples": Counter(f"{e['split']}/{e['kind']}" for e in examples),
             "clean": Counter(f"{e['split']}/{e['clean']}" for e in examples)}
    (args.out / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    package(args.out)


if __name__ == "__main__":
    main()
