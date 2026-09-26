"""Groq usage ledger over a rolling 24 hours, shared by everything that calls Groq (evaluation, dataset expansion,
repair).

Groq's free tier limits each model per rolling 24 hours (its 429 says "try again in 3m"), in requests and tokens,
and the API only reports the per-minute token budget in its headers. So every call is recorded here with a
timestamp, the model, a tag ("evaluation", "generation", ...) and its tokens, and budgets are checked against the
last 24 hours. Groq's own limit error remains the final stop.

What counts, as measured on 2026-09-26 (Groq's count vs this ledger): all input tokens, cached ones included (the
docs say cached tokens do not count, but gpt-oss-20b reached Groq's 200K with 164K raw tokens recorded), plus the
output. Calls that fail inside Groq (JSON validation) also use tokens; they are recorded as an estimate.
"""
import json
import time
from pathlib import Path
from typing import Callable

from app.config import BACKEND_DIR

LEDGER_PATH = BACKEND_DIR.parent / "data" / "groq_usage.json"
WINDOW_SECONDS = 24 * 3600

# Free-tier limits per model (console.groq.com/docs/rate-limits, checked 2026-09-26).
DAILY_LIMITS = {
    "openai/gpt-oss-120b": {"requests": 1000, "tokens": 200_000},
    "openai/gpt-oss-20b": {"requests": 1000, "tokens": 200_000},
    "qwen/qwen3.8-27b": {"requests": 1000, "tokens": 200_000},
}
TOKENS_PER_MINUTE = 8000


class UsageLedger:
    """events.json: {"events": [[unix_time, model, tag, tokens], ...]}; events older than the window are dropped."""

    def __init__(self, path: Path = LEDGER_PATH, clock: Callable[[], float] = time.time):
        self.path, self.clock = Path(path), clock

    def _load(self) -> list[list]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8") or "{}").get("events", [])

    def record(self, model: str, tag: str, tokens: int) -> None:
        now = self.clock()
        events = [e for e in self._load() if e[0] > now - WINDOW_SECONDS]
        events.append([now, model, tag, int(tokens)])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"events": events}), encoding="utf-8")
        tmp.replace(self.path)

    def used(self, model: str, tag: str | None = None) -> dict[str, int]:
        """Requests and tokens for `model` in the last 24 hours: for one tag, or all tags together."""
        since = self.clock() - WINDOW_SECONDS
        rows = [e for e in self._load() if e[0] > since and e[1] == model and (tag is None or e[2] == tag)]
        return {"requests": len(rows), "tokens": sum(e[3] for e in rows)}
