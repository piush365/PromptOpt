"""Read PromptOpt Dataset v1.1 (the combined CSV; see app.dataset_repair)."""
import csv
from pathlib import Path

from app.config import DATASET_DIR

DEFAULT_CSV = DATASET_DIR / "promptopt_dataset_v1_1.csv"


def load_rows(path: Path = DEFAULT_CSV, split: str | None = None) -> list[dict[str, str]]:
    if not Path(path).exists():
        raise SystemExit(f"Dataset not found at {path}. Build it with `python -m app.dataset_repair --write` "
                         f"(from v1 downloaded from Google Drive), or set DATASET_DIR.")
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if split is None or r["split"] == split]
