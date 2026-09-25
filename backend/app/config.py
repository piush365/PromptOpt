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
