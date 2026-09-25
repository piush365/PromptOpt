"""Initial rule catalogue. Codes are stable identifiers the Stage B code refers to."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Rule

RULES = [
    # Stage A: detectors (record what is wrong, change nothing)
    ("A01_DETECT_TASK_TYPE", "Detect task category", "A",
     "Classify the prompt into closed_qa, information_extraction, classification, summarization, coding or other."),
    ("A02_DETECT_FORMAT", "Detect missing output format", "A",
     "Check whether the prompt explicitly asks for an output format (list, JSON, table, N sentences, ...)."),
    ("A03_DETECT_CONSTRAINTS", "Detect missing constraints", "A",
     "Check for length, audience, tone and language constraints."),
    ("A04_DETECT_REDUNDANCY", "Detect redundant phrases", "A",
     "Find filler/politeness phrases and repeated sentences."),
    ("A05_DETECT_AMBIGUITY", "Detect ambiguous references", "A",
     "Find references such as 'this' or 'that text' with nothing they could refer to."),
    # Stage B: deterministic fixes
    ("B01_REMOVE_FILLER", "Remove filler phrases", "B",
     "Delete politeness and filler ('could you please kindly', 'I was wondering if')."),
    ("B02_REMOVE_DUPLICATES", "Remove repeated sentences", "B",
     "Drop sentences that repeat an earlier sentence."),
    ("B03_ADD_OUTPUT_FORMAT", "Add output format", "B",
     "Append a category-appropriate output format when none is given."),
    ("B04_ADD_LENGTH", "Add length constraint", "B",
     "Append a default length constraint for the detected category."),
    ("B05_ADD_LANGUAGE", "Add programming language", "B",
     "For coding prompts without a language, state the implied one (default Python)."),
    ("B06_ADD_LABELS", "Make label set explicit", "B",
     "For classification prompts, list the allowed labels and ask for the label only."),
    ("B07_STANDARDIZE_STRUCTURE", "Standardize structure", "B",
     "Reorder into task, context, constraints, output format."),
]


def seed_rules(session: Session) -> int:
    """Insert missing rules; existing codes are left untouched. Returns the number inserted."""
    existing = set(session.scalars(select(Rule.code)))
    new = [Rule(code=c, name=n, stage=s, description=d) for c, n, s, d in RULES if c not in existing]
    session.add_all(new)
    session.commit()
    return len(new)
