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

    def set_groq_pace(self, seconds: float) -> None:
        if self.groq is not None:
            self.groq.min_interval = seconds
