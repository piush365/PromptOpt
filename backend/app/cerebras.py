"""Cerebras chat completions (OpenAI-compatible API), with the same interface as app.evaluation.llm.GroqChat.

Free-tier limits for gpt-oss-120b, read from the response headers on 2026-09-26: 5 requests/min, 150/hour,
2,400/day; 30K tokens/min, 1M tokens/day; 8K context. The requests-per-hour limit binds first, so calls are spaced
MIN_INTERVAL apart (about 147/hour). Every response carries the remaining daily requests and tokens
(`x-ratelimit-remaining-*-day`); `remaining` keeps the latest values so callers can stop before the limit.

* 429: wait `retry-after` (or 15, 30, ... s, capped at 120) and retry; when the daily remaining is used up, raise
  DailyLimitReached.
* JSON mode could not produce valid JSON (400 mentioning JSON): raise JSONGenerationFailed, no retries.
* Other API or connection errors: back off (3, 6, 12, ... s, capped at 30), at most `max_retries` times.
"""
import os
import time
from typing import Any, Callable

import httpx

from app.evaluation.llm import Completion, DailyLimitReached, JSONGenerationFailed, ModelUnavailable

BASE_URL = "https://api.cerebras.ai/v1"
MIN_INTERVAL = 24.5           # 150 requests/hour -> one every 24 s
LIMITS = {"gpt-oss-120b": {"requests": 2400, "tokens": 1_000_000}}


class CerebrasChat:
    def __init__(self, api_key: str | None = None, http: httpx.Client | None = None,
                 min_interval: float = MIN_INTERVAL, max_retries: int = 5,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 ledger: Any = None, tag: str = "other", ledger_prefix: str = "cerebras/"):
        if http is None:
            api_key = api_key or os.getenv("CEREBRAS_API_KEY")
            if not api_key:
                raise SystemExit("CEREBRAS_API_KEY is not set. Add it to backend/.env.")
            http = httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=120)
        self.http, self.min_interval, self.max_retries = http, min_interval, max_retries
        self.sleep, self.clock = sleep, clock
        self.ledger, self.tag, self.ledger_prefix = ledger, tag, ledger_prefix
        self._last_call: float | None = None
        self.calls = 0
        self.remaining: dict[str, int] = {}      # latest x-ratelimit-remaining-* values

    def _pace(self) -> None:
        if self._last_call is not None:
            wait = self.min_interval - (self.clock() - self._last_call)
            if wait > 0:
                self.sleep(wait)
        self._last_call = self.clock()

    def _read_limits(self, headers: httpx.Headers) -> None:
        for k, v in headers.items():
            if k.lower().startswith("x-ratelimit-remaining-"):
                try:
                    self.remaining[k.lower()[len("x-ratelimit-remaining-"):]] = int(float(v))
                except ValueError:
                    pass

    def complete(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float = 0.0,
                 reasoning_effort: str | None = None, json_mode: bool = False) -> Completion:
        body: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature,
                                "max_completion_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if reasoning_effort in ("low", "medium", "high"):
            body["reasoning_effort"] = reasoning_effort
        last = ""
        for attempt in range(self.max_retries):
            self._pace()
            self.calls += 1
            start = time.perf_counter()
            try:
                r = self.http.post("/chat/completions", json=body)
            except httpx.HTTPError as e:
                last = str(e)
                self.sleep(min(30, 3 * 2 ** attempt))
                continue
            self._read_limits(r.headers)
            if r.status_code == 200:
                return self._completion(r.json(), model, int(1000 * (time.perf_counter() - start)))
            text = r.text[:500]
            if r.status_code == 429:
                if self.remaining.get("tokens-day", 1) <= 0 or self.remaining.get("requests-day", 1) <= 0 \
                        or "day" in text.lower():
                    raise DailyLimitReached(f"cerebras {model}: {text}")
                try:
                    wait = float(r.headers.get("retry-after", 0)) or min(120, 15 * 2 ** attempt)
                except ValueError:
                    wait = min(120, 15 * 2 ** attempt)
                self.sleep(wait)
                last = text
                continue
            if r.status_code in (401, 403, 404):
                raise ModelUnavailable(f"cerebras {model}: {r.status_code} {text}")
            if r.status_code == 400 and "json" in text.lower():
                if self.ledger is not None:
                    chars = sum(len(m.get("content", "")) for m in messages)
                    self.ledger.record(self.ledger_prefix + model, self.tag, chars // 4 + max_tokens)
                raise JSONGenerationFailed(f"cerebras {model}: {text}")
            last = f"{r.status_code} {text}"
            self.sleep(min(30, 3 * 2 ** attempt))
        raise RuntimeError(f"cerebras {model}: failed after {self.max_retries} attempts: {last}")

    def _completion(self, d: dict, model: str, wall_ms: int) -> Completion:
        usage = d.get("usage") or {}
        choice = d["choices"][0]
        c = Completion(content=choice["message"].get("content") or "", model=self.ledger_prefix + model,
                       input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0),
                       reasoning_tokens=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                       latency_ms=wall_ms, finish_reason=choice.get("finish_reason"),
                       cached_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
        if self.ledger is not None:
            self.ledger.record(c.model, self.tag, c.total_tokens, c.cached_tokens)
        return c
