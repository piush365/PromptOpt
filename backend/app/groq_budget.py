"""Groq usage ledger over a rolling 24 hours, shared by everything that calls Groq (evaluation, dataset expansion,
repair).

Groq's free tier limits each model per rolling 24 hours (its 429 says "try again in 3m"), in requests and tokens,
and the API only reports the per-minute token budget in its headers. So every call is recorded here with a
timestamp, the model, a tag ("evaluation", "generation", ...) and its tokens, and budgets are checked against the
last 24 hours. Groq's own limit error remains the final stop.

Each event keeps the call's total tokens and the part served from Groq's prompt cache. Groq's docs say cached
tokens do not count toward the limits; that is not verified yet (2026-09-26: the test was confounded by usage from
the day before), so COUNT_CACHED is True, the conservative choice, until a measurement settles it. Calls that fail
inside Groq (JSON validation) also use tokens; they are recorded as an estimate.
"""
import contextlib
import fcntl
import json
import os
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
COUNT_CACHED = True


class UsageLedger:
    """{"events": [[unix_time, model, tag, tokens, cached_tokens], ...]}; events older than the window are dropped."""

    def __init__(self, path: Path = LEDGER_PATH, clock: Callable[[], float] = time.time):
        self.path, self.clock = Path(path), clock

    # Several processes (evaluation, generation) share the file, and data/ is on an NTFS (fuseblk) mount where a
    # rename over an existing file is not reliable: updates take an exclusive lock, write a per-process temporary
    # file, and fall back to writing in place if the rename fails; reads retry a file caught mid-write.
    def _load(self) -> list[list]:
        for attempt in range(5):
            if not self.path.exists():
                return []
            try:
                return json.loads(self.path.read_text(encoding="utf-8") or "{}").get("events", [])
            except (json.JSONDecodeError, OSError):
                time.sleep(0.05 * (attempt + 1))
        return []

    @contextlib.contextmanager
    def _lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path.with_suffix(".lock"), "a+") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX)
            except OSError:                    # the filesystem may not support locks: still write, unlocked
                pass
            yield

    def record(self, model: str, tag: str, tokens: int, cached: int = 0) -> None:
        with self._lock():
            now = self.clock()
            events = [e for e in self._load() if e[0] > now - WINDOW_SECONDS]
            events.append([now, model, tag, int(tokens), int(cached)])
            data = json.dumps({"events": events})
            tmp = self.path.with_name(f"{self.path.stem}.{os.getpid()}.tmp")
            try:
                tmp.write_text(data, encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                self.path.write_text(data, encoding="utf-8")
                with contextlib.suppress(OSError):
                    tmp.unlink()

    def used(self, model: str, tag: str | None = None) -> dict[str, int]:
        """Requests and tokens for `model` in the last 24 hours: for one tag, or all tags together."""
        since = self.clock() - WINDOW_SECONDS
        rows = [e for e in self._load() if e[0] > since and e[1] == model and (tag is None or e[2] == tag)]
        return {"requests": len(rows),
                "tokens": sum(e[3] - (0 if COUNT_CACHED else (e[4] if len(e) > 4 else 0)) for e in rows)}
