"""Basic PII stripping (project scope: email addresses and phone numbers).

Runs BEFORE a prompt is written to the database, so raw PII is never stored.
Same patterns as the dataset-preparation notebook, so training data and live data are treated alike.
"""
import re

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?<![\w-])(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?![\w-])"   # 555-123-4567, (555) 123-4567
    r"|(?<![\w-])(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?![\w-])"                             # Indian mobile: 98765 43210
)


def scrub_pii(text: str) -> tuple[str, int]:
    """Returns (scrubbed_text, number_of_redactions)."""
    text, n_email = EMAIL_RE.subn("[EMAIL]", text)
    text, n_phone = PHONE_RE.subn("[PHONE]", text)
    return text, n_email + n_phone
