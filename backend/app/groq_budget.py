"""Daily Groq usage ledger, shared by everything that calls Groq (evaluation, dataset expansion, repair).

Groq's free tier limits each model per day (requests and tokens). The API only reports the per-minute token budget
in its headers, so the daily totals are tracked here: every successful call adds its tokens to
data/groq_usage.json under the UTC date, the model and a tag ("evaluation", "generation", ...). Budgets are checked
against this file, and Groq's own daily-limit error remains the final stop. Only rate-limited tokens are recorded:
input tokens served from Groq's prompt cache (gpt-oss models) do not count toward the limits.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import BACKEND_DIR

LEDGER_PATH = BACKEND_DIR.parent / "data" / "groq_usage.json"

# Free-tier limits per model (console.groq.com/docs/rate-limits, checked 2026-09-26).
DAILY_LIMITS = {
    "openai/gpt-oss-120b": {"requests": 1000, "tokens": 200_000},
    "openai/gpt-oss-20b": {"requests": 1000, "tokens": 200_000},
    "qwen/qwen3.8-27b": {"requests": 1000, "tokens": 200_000},
}
TOKENS_PER_MINUTE = 8000


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class UsageLedger:
    def __init__(self, path: Path = LEDGER_PATH, clock=today):
        self.path, self.clock = Path(path), clock

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8") or "{}")

    def record(self, model: str, tag: str, tokens: int) -> None:
        data = self._load()
        entry = data.setdefault(self.clock(), {}).setdefault(model, {}).setdefault(tag, {"requests": 0, "tokens": 0})
        entry["requests"] += 1
        entry["tokens"] += int(tokens)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def used(self, model: str, tag: str | None = None) -> dict[str, int]:
        """Today's requests and tokens for `model`: for one tag, or all tags together."""
        by_tag = self._load().get(self.clock(), {}).get(model, {})
        rows = [by_tag.get(tag, {})] if tag else list(by_tag.values())
        return {"requests": sum(r.get("requests", 0) for r in rows), "tokens": sum(r.get("tokens", 0) for r in rows)}
