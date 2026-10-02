"""Prove that Stage A + Stage B behave exactly as at `frozen-for-test` on prompts without an attachment.

    python -m app.freeze_check [--split test] [--ref frozen-for-test]

Checks out the reference tag in a temporary git worktree, runs the same dump (Stage A features, IR, optimized text,
steps, Stage C routing, confidence for every prompt of the split) with the reference code and with the current code,
and compares the two. Both use the current category index and the final dataset, so only code can differ. Exit code
0 = byte-identical.
"""
import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import BACKEND_DIR, CATEGORY_INDEX_PATH, DATASET_CSV

DUMP = r'''
import json, sys
from app.dataset_io import load_rows
from app.stage_a.detector import FeatureDetector
from app.stage_b.optimizer import optimize
rows = load_rows(sys.argv[2], split=sys.argv[3])
feats = FeatureDetector().detect_many([r["degraded_prompt"] for r in rows], [r["context"] or None for r in rows])
out = {}
for r, f in zip(rows, feats):
    o = optimize(r["degraded_prompt"], f)
    out[r["id"]] = {"text": o.optimized_text, "steps": o.steps, "ir": o.ir.model_dump(mode="json"),
                    "needs_c": o.needs_stage_c, "conf": o.confidence, "features": f.model_dump()}
json.dump(out, open(sys.argv[1], "w"), sort_keys=True)
'''


def dump(backend: Path, out: Path, split: str) -> str:
    env = {**os.environ, "PYTHONPATH": str(backend), "CATEGORY_INDEX_PATH": str(CATEGORY_INDEX_PATH)}
    subprocess.run([sys.executable, "-c", DUMP, str(out), str(DATASET_CSV), split], cwd=backend, env=env, check=True,
                   stderr=subprocess.DEVNULL)
    return hashlib.sha256(out.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--ref", default="frozen-for-test")
    args = ap.parse_args()
    repo = BACKEND_DIR.parent
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "ref"
        subprocess.run(["git", "worktree", "add", "-q", "--detach", str(tree), args.ref], cwd=repo, check=True)
        try:
            ref = dump(tree / "backend", Path(tmp) / "ref.json", args.split)
            now = dump(BACKEND_DIR, Path(tmp) / "now.json", args.split)
            n = (Path(tmp) / "now.json").read_text().count('"needs_c"')
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(tree)], cwd=repo, check=True)
    print(f"{args.ref}: {ref}\ncurrent:          {now}\n{n} {args.split} prompts: "
          + ("BYTE-IDENTICAL" if ref == now else "DIFFERENT"))
    sys.exit(0 if ref == now else 1)


if __name__ == "__main__":
    main()
