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
    ("B08_GROUP_FALLBACK", "Text-based group fallback", "B",
     "When no single category is certain but closed_qa/information_extraction/summarization together are and text "
     "is attached, ask for an answer grounded in the text and concise; no category-specific format."),
    # Stage B: attachment modifier (one rule per attachment type, so the ablation can switch each off)
    ("B09_ATTACHMENT_IMAGE", "Image attachment", "B",
     "Use what is visible in the attached image; say so when something is not visible."),
    ("B10_ATTACHMENT_PDF", "PDF attachment", "B",
     "Use the attached PDF as the source and cite page or section numbers."),
    ("B11_ATTACHMENT_PPTX", "Slide deck attachment", "B",
     "Use the attached slides as the source and refer to slides by number."),
    ("B12_ATTACHMENT_DOCX", "Word document attachment", "B",
     "Use the attached document as the source and cite section headings."),
    ("B13_ATTACHMENT_OTHER", "Other attachment", "B",
     "Use the attached file as the source; say so if it cannot be read."),
    ("B14_ATTACHMENT_SPREADSHEET", "Spreadsheet attachment", "B",
     "Use the attached spreadsheet as the source and refer to sheets, columns and rows by name."),
    ("B15_ATTACHMENT_CODE", "Code file attachment", "B",
     "Use the attached code file as the code to work on and point to functions and line numbers."),
    # Stage B extension (after the final test run; app only, app.stage_b.extensions)
    ("B16_LABELS_WIDER", "Wider label detection", "B",
     "Classification with no label set found by B06: labels named after a request verb ('tell me X or Y'); items "
     "glued on after them move to the input block."),
]


def seed_rules(session: Session) -> int:
    """Insert missing rules; existing codes are left untouched. Returns the number inserted."""
    existing = set(session.scalars(select(Rule.code)))
    new = [Rule(code=c, name=n, stage=s, description=d) for c, n, s, d in RULES if c not in existing]
    session.add_all(new)
    session.commit()
    return len(new)
