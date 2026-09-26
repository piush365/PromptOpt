"""Groq chat completions with the dataset notebook's rate-limit handling.

* 429 with a per-minute limit: wait `retry-after` (or 5, 10, 20, ... s, capped at 60) and retry.
* 429 with a per-day limit (RPD/TPD): raise DailyLimitReached; the harness stops, progress is already saved.
* Model not found / not allowed / decommissioned: raise ModelUnavailable.
* Other API or connection errors: back off (3, 6, 12, ... s, capped at 30) and retry, at most `max_retries` times.
* Calls are spaced at least `min_interval` seconds apart (about 27 requests/min, under the free-tier limit).
* With a `ledger` (app.groq_budget.UsageLedger), every successful call's rate-limited tokens (input minus cached
  input, plus output) are added to today's shared usage.
* JSON mode, Groq's `json_validate_failed` (400): raise JSONGenerationFailed at once, no retries.
* A model that rejects `reasoning_effort` is retried without it (remembered for the rest of the run).
"""
import time
from dataclasses import dataclass
from typing import Any, Callable

import groq

from app.config import GROQ_API_KEY

SECONDS_BETWEEN_CALLS = 2.2


class DailyLimitReached(Exception):
    pass


class ModelUnavailable(Exception):
    pass


class JSONGenerationFailed(ValueError):
    """JSON mode: Groq could not produce valid JSON (e.g. max tokens reached first). Not retried unchanged: the same
    request fails the same way at temperature 0. Callers may retry with more tokens."""


@dataclass
class Completion:
    content: str
    model: str
    input_tokens: int
    output_tokens: int              # billed completion tokens, including hidden reasoning tokens
    reasoning_tokens: int | None    # part of output_tokens spent on reasoning, when the API reports it
    latency_ms: int                 # Groq's usage.total_time; wall clock only if the API does not report it
    finish_reason: str | None
    cached_tokens: int = 0          # part of input_tokens served from Groq's prompt cache (not rate-limited)

    @property
    def rate_limited_tokens(self) -> int:
        """Tokens that count toward Groq's rate limits: cached input tokens do not."""
        return self.input_tokens - self.cached_tokens + self.output_tokens


def _is_daily(e: Exception) -> bool:
    msg = str(e).lower()
    return "per day" in msg or "(rpd)" in msg or "(tpd)" in msg


def _unavailable(e: Exception) -> bool:
    msg = str(e).lower()
    return "decommission" in msg or "does not exist" in msg or "model_not_found" in msg


class GroqChat:
    def __init__(self, client: Any = None, min_interval: float = SECONDS_BETWEEN_CALLS, max_retries: int = 5,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 ledger: Any = None, tag: str = "other"):
        if client is None:
            if not GROQ_API_KEY:
                raise SystemExit("GROQ_API_KEY is not set. Add it to backend/.env (see .env.example).")
            client = groq.Groq(api_key=GROQ_API_KEY)
        self.client, self.min_interval, self.max_retries = client, min_interval, max_retries
        self.sleep, self.clock = sleep, clock
        self._last_call = None
        self.no_reasoning_param: set[str] = set()
        self.calls = 0
        self.ledger, self.tag = ledger, tag     # app.groq_budget.UsageLedger: daily usage shared across tools

    def _pace(self) -> None:
        if self._last_call is not None:
            wait = self.min_interval - (self.clock() - self._last_call)
            if wait > 0:
                self.sleep(wait)
        self._last_call = self.clock()

    def _create(self, kwargs: dict) -> Any:
        self._pace()
        self.calls += 1
        try:
            return self.client.chat.completions.create(**kwargs)
        except groq.BadRequestError as e:
            if "reasoning" in str(e).lower() and "reasoning_effort" in kwargs:
                self.no_reasoning_param.add(kwargs["model"])
                kwargs = {k: v for k, v in kwargs.items() if k != "reasoning_effort"}
                self._pace()
                self.calls += 1
                return self.client.chat.completions.create(**kwargs)
            raise

    def complete(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float = 0.0,
                 reasoning_effort: str | None = None, json_mode: bool = False) -> Completion:
        kwargs: dict[str, Any] = dict(model=model, messages=messages, temperature=temperature,
                                      max_completion_tokens=max_tokens)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if reasoning_effort and model not in self.no_reasoning_param:
            kwargs["reasoning_effort"] = reasoning_effort
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            start = time.perf_counter()
            try:
                resp = self._create(dict(kwargs))
            except (groq.NotFoundError, groq.PermissionDeniedError) as e:
                raise ModelUnavailable(str(e)) from e
            except groq.RateLimitError as e:
                if _is_daily(e):
                    raise DailyLimitReached(str(e)) from e
                headers = getattr(getattr(e, "response", None), "headers", {}) or {}
                try:
                    wait = float(headers.get("retry-after", 0)) or min(60, 5 * 2 ** attempt)
                except ValueError:
                    wait = min(60, 5 * 2 ** attempt)
                self.sleep(wait)
                last_error = e
                continue
            except (groq.APIStatusError, groq.APIConnectionError) as e:
                if "json_validate_failed" in str(e):
                    raise JSONGenerationFailed(str(e)) from e
                if _unavailable(e):
                    raise ModelUnavailable(str(e)) from e
                self.sleep(min(30, 3 * 2 ** attempt))
                last_error = e
                continue
            wall_ms = int(1000 * (time.perf_counter() - start))
            c = _completion(resp, model, wall_ms)
            if self.ledger is not None:
                self.ledger.record(model, self.tag, c.rate_limited_tokens)
            return c
        raise RuntimeError(f"{model}: failed after {self.max_retries} attempts: {last_error}")


def _completion(resp: Any, model: str, wall_ms: int) -> Completion:
    usage = resp.usage
    details = getattr(usage, "completion_tokens_details", None)
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    total_time = getattr(usage, "total_time", None)
    choice = resp.choices[0]
    return Completion(content=choice.message.content or "", model=getattr(resp, "model", model),
                      input_tokens=usage.prompt_tokens, output_tokens=usage.completion_tokens,
                      reasoning_tokens=getattr(details, "reasoning_tokens", None),
                      latency_ms=int(round(1000 * total_time)) if total_time is not None else wall_ms,
                      finish_reason=choice.finish_reason,
                      cached_tokens=getattr(prompt_details, "cached_tokens", None) or 0)
