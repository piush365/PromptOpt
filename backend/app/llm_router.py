"""One `complete` for every provider: "cerebras/<model>" goes to Cerebras, anything else to Groq."""
from typing import Any


def provider_of(model: str) -> str:
    return "cerebras" if model.startswith("cerebras/") else "groq"


class Router:
    """One `complete` for every provider: "cerebras/<model>" goes to Cerebras, anything else to Groq."""

    def __init__(self, groq: Any = None, cerebras: Any = None):
        self.groq, self.cerebras = groq, cerebras

    def complete(self, model: str, messages: list[dict[str, str]], **kw: Any) -> Any:
        if provider_of(model) == "cerebras":
            if self.cerebras is None:
                from app.evaluation.llm import ModelUnavailable
                raise ModelUnavailable("no Cerebras client (CEREBRAS_API_KEY not set)")
            return self.cerebras.complete(model.split("/", 1)[1], messages, **kw)
        if self.groq is None:
            from app.evaluation.llm import ModelUnavailable
            raise ModelUnavailable("no Groq client")
        return self.groq.complete(model, messages, **kw)

    def cerebras_allows(self, est_tokens: float, reserve: float = 0.02) -> bool | None:
        """From Cerebras' own headers (latest response): True/False whether a call of `est_tokens` fits in what is
        left of its daily limit (keeping `reserve` of 1M tokens back); None when no response has been seen yet."""
        rem = getattr(self.cerebras, "remaining", None) or {}
        if "tokens-day" not in rem:
            return None
        return rem["tokens-day"] - est_tokens >= reserve * 1_000_000 and rem.get("requests-day", 1) >= 1

    def set_groq_pace(self, seconds: float) -> None:
        if self.groq is not None:
            self.groq.min_interval = seconds
