"""Read PromptOpt Dataset v1 (the combined CSV downloaded from Google Drive)."""
import csv
from pathlib import Path

from app.config import DATASET_DIR

DEFAULT_CSV = DATASET_DIR / "promptopt_dataset_v1.csv"


def load_rows(path: Path = DEFAULT_CSV, split: str | None = None) -> list[dict[str, str]]:
    if not Path(path).exists():
        raise SystemExit(f"Dataset not found at {path}. Download promptopt_dataset_v1 from Google Drive into "
                         f"{DATASET_DIR} or set DATASET_DIR.")
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if split is None or r["split"] == split]
