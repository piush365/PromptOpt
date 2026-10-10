"""Settings, read from environment variables so nothing is hard-coded.

DATABASE_URL examples
    SQLite (default, development):  backend/promptopt.db, wherever the command is started from
    PostgreSQL (deployment):        postgresql+psycopg://promptopt:password@localhost:5432/promptopt

Values are read from backend/.env if it exists (see .env.example). Variables already set in the
shell take precedence over .env.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

# backend/.env, located relative to this file so it works from any working directory.
load_dotenv(BACKEND_DIR / ".env", override=False)

# Default: SQLite at backend/promptopt.db (an absolute path, so a command run from another directory does not create a
# second, empty database next to it).
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'promptopt.db'}")

# Retention policy: stored prompts (and everything derived from them) are deleted after this many days.
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))

# Echo SQL statements to the console (useful while debugging)
SQL_ECHO = os.getenv("SQL_ECHO", "0") == "1"

# The 5 prompt categories PromptOpt handles, plus "other" for anything Stage A cannot place.
TASK_CATEGORIES = (
    "closed_qa",
    "information_extraction",
    "classification",
    "summarization",
    "coding",
    "other",
)

# ---- Stage A
# Sentence-Transformers model for task-category detection (same model the dataset quality checks used)
SENTENCE_MODEL = os.getenv("SENTENCE_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
# k-NN index built from the dataset's train split by `python -m app.stage_a.build_index` (git-ignored)
CATEGORY_INDEX_PATH = Path(os.getenv("CATEGORY_INDEX_PATH", BACKEND_DIR / "artifacts" / "category_index.npz"))
# PromptOpt Dataset v1.2 final (v1.2 after human validation and the LLM-assisted filter; docs/DATASET_CARD.md;
# git-ignored). Every dataset folder holds `<folder name>.csv`, so DATASET_DIR=.../promptopt_dataset_v1_1 still works.
DATASET_DIR = Path(os.getenv("DATASET_DIR", BACKEND_DIR.parent / "data" / "promptopt_dataset_v1_2_final"))
DATASET_CSV = Path(os.getenv("DATASET_CSV", DATASET_DIR / f"{DATASET_DIR.name}.csv"))

# ---- Evaluation harness
# Groq API key for the target LLM and the judge. Put it in backend/.env; never hard-code it.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Resumable cache of LLM calls per evaluation run (git-ignored, under data/)
EVAL_DIR = Path(os.getenv("EVAL_DIR", BACKEND_DIR.parent / "data" / "evaluation"))

# ---- Stage C (LoRA fallback; docs/STAGE_C_PLAN.md)
STAGE_C_BASE_MODEL = os.getenv("STAGE_C_BASE_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
# Trained adapter folder (git-ignored, like the category index). Missing -> the app runs without Stage C.
STAGE_C_ADAPTER = Path(os.getenv("STAGE_C_ADAPTER", BACKEND_DIR / "artifacts" / "stage_c_adapter"))
# "auto" = cuda if available, else cpu
STAGE_C_DEVICE = os.getenv("STAGE_C_DEVICE", "auto")
