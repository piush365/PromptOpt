"""Settings, read from environment variables so nothing is hard-coded.

DATABASE_URL examples
    SQLite (default, development):  sqlite:///./promptopt.db
    PostgreSQL (deployment):        postgresql+psycopg://promptopt:password@localhost:5432/promptopt

Values are read from backend/.env if it exists (see .env.example). Variables already set in the
shell take precedence over .env.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env, located relative to this file so it works from any working directory.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./promptopt.db")

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
BACKEND_DIR = Path(__file__).resolve().parent.parent
# Sentence-Transformers model for task-category detection (same model the dataset quality checks used)
SENTENCE_MODEL = os.getenv("SENTENCE_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
# k-NN index built from the dataset's train split by `python -m app.stage_a.build_index` (git-ignored)
CATEGORY_INDEX_PATH = Path(os.getenv("CATEGORY_INDEX_PATH", BACKEND_DIR / "artifacts" / "category_index.npz"))
# PromptOpt Dataset v1, downloaded from Google Drive (git-ignored)
DATASET_DIR = Path(os.getenv("DATASET_DIR", BACKEND_DIR.parent / "data" / "promptopt_dataset_v1"))

# ---- Evaluation harness
# Groq API key for the target LLM and the judge. Put it in backend/.env; never hard-code it.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Resumable cache of LLM calls per evaluation run (git-ignored, under data/)
EVAL_DIR = Path(os.getenv("EVAL_DIR", BACKEND_DIR.parent / "data" / "evaluation"))
