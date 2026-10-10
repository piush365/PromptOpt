"""Models Compare can run on, which of them are available, and one `complete` call for all of them.

* Groq and Cerebras (gpt-oss-120b): the evaluation harness's clients (app.evaluation.llm.GroqChat,
  app.cerebras.CerebrasChat), with their pacing, retries and the rolling 24-hour usage ledgers. Compare stays within
  BUDGET_FRACTION of each daily limit, like dataset generation.
* Gemini (Google AI Studio free tier): GeminiChat below, when GEMINI_API_KEY is in backend/.env. The key goes in the
  `x-goog-api-key` header, never in the URL, so it cannot end up in a log line.
* GPT (OpenAI) and Claude (Anthropic): listed but disabled ("add OPENAI_API_KEY / ANTHROPIC_API_KEY"); no client
  exists yet, so Compare never calls them.
Keys are read from the environment only and never logged or returned by the API.
"""
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import BACKEND_DIR
from app.evaluation.llm import Completion, DailyLimitReached, ModelUnavailable

BUDGET_FRACTION = 0.7
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"


@dataclass(frozen=True)
class ModelInfo:
    id: str                    # what the API accepts, e.g. "cerebras/gpt-oss-120b"
    label: str
    provider: str              # groq | cerebras | gemini | openai | anthropic
    family: str                # the target-LLM family it actually is: gpt-oss | gemini | gpt | claude
    key_env: str
    daily_tokens: int | None   # free-tier daily token limit we stay under (None: the provider's own 429 decides)

    @property
    def available(self) -> bool:
        return bool(os.getenv(self.key_env)) and self.provider in CLIENTS

    @property
    def reason(self) -> str | None:
        if self.provider not in CLIENTS:
            return f"Not wired up yet: add {self.key_env} to backend/.env and a client for {self.provider}."
        if not os.getenv(self.key_env):
            return f"Add {self.key_env} to backend/.env to enable it."
        return None


MODELS = [
    ModelInfo("cerebras/gpt-oss-120b", "gpt-oss-120b on Cerebras", "cerebras", "gpt-oss", "CEREBRAS_API_KEY", 1_000_000),
    ModelInfo("groq/openai/gpt-oss-120b", "gpt-oss-120b on Groq", "groq", "gpt-oss", "GROQ_API_KEY", 200_000),
    ModelInfo(f"gemini/{GEMINI_MODEL}", f"{GEMINI_MODEL} (Google AI Studio)", "gemini", "gemini", "GEMINI_API_KEY", None),
    ModelInfo("openai/gpt", "GPT (OpenAI API)", "openai", "gpt", "OPENAI_API_KEY", None),
    ModelInfo("anthropic/claude", "Claude (Anthropic API)", "anthropic", "claude", "ANTHROPIC_API_KEY", None),
]
BY_ID = {m.id: m for m in MODELS}
CLIENTS = {"groq", "cerebras", "gemini"}          # providers with a client; openai/anthropic come with API keys


def _daily_quota(body: str) -> bool:
    """A Gemini 429 for the daily quota. Every quota 429 says "Quota exceeded"; the quota id tells the window
    ("...PerDayPerProjectPerModel-FreeTier" vs "...PerMinute..."). A per-minute limit is waited out and retried;
    a 429 that names neither window counts as daily, so the caller stops instead of retrying in vain."""
    text = body.lower().replace(" ", "")
    if "perday" in text:
        return True
    return "perminute" not in text and "quota" in text


class GeminiChat:
    """Gemini generateContent with the same `complete` interface as GroqChat / CerebrasChat."""

    def __init__(self, api_key: str | None = None, http: httpx.Client | None = None, max_retries: int = 3,
                 sleep=time.sleep):
        if http is None:
            api_key = api_key or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ModelUnavailable("GEMINI_API_KEY is not set")
            http = httpx.Client(base_url=GEMINI_URL, headers={"x-goog-api-key": api_key}, timeout=120)
        self.http, self.max_retries, self.sleep = http, max_retries, sleep

    def complete(self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float = 0.0,
                 reasoning_effort: str | None = None, json_mode: bool = False) -> Completion:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        body: dict[str, Any] = {
            "contents": [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                         for m in messages if m["role"] != "system"],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens,
                                 **({"responseMimeType": "application/json"} if json_mode else {})}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        last = ""
        for attempt in range(self.max_retries):
            start = time.perf_counter()
            try:
                r = self.http.post(f"/models/{model}:generateContent", json=body)
            except httpx.HTTPError as e:
                last = type(e).__name__                   # never the request (it carries the key header)
                self.sleep(min(30, 3 * 2 ** attempt))
                continue
            ms = int(1000 * (time.perf_counter() - start))
            if r.status_code == 200:
                return self._completion(r.json(), model, ms)
            text = r.text[:300]
            if r.status_code == 429:
                if _daily_quota(r.text):
                    raise DailyLimitReached(f"gemini {model}: free-tier quota reached")
                self.sleep(min(60, 10 * 2 ** attempt))
                last = "429"
                continue
            if r.status_code in (400, 401, 403, 404):
                raise ModelUnavailable(f"gemini {model}: {r.status_code} {text}")
            last = f"{r.status_code}"
            self.sleep(min(30, 3 * 2 ** attempt))
        raise RuntimeError(f"gemini {model}: failed after {self.max_retries} attempts ({last})")

    @staticmethod
    def _completion(d: dict, model: str, ms: int) -> Completion:
        usage = d.get("usageMetadata") or {}
        cand = (d.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
        thoughts = usage.get("thoughtsTokenCount") or 0
        return Completion(content=text, model=f"gemini/{model}", input_tokens=usage.get("promptTokenCount", 0),
                          output_tokens=usage.get("candidatesTokenCount", 0) + thoughts,
                          reasoning_tokens=thoughts or None, latency_ms=ms,
                          finish_reason=(cand.get("finishReason") or "").lower() or None,
                          cached_tokens=usage.get("cachedContentTokenCount", 0))


def used_tokens(info: ModelInfo) -> int:
    from app.groq_budget import UsageLedger
    if info.provider == "groq":
        return UsageLedger().used(info.id.split("/", 1)[1])["tokens"]
    if info.provider == "cerebras":
        return UsageLedger(BACKEND_DIR.parent / "data" / "cerebras_usage.json").used(info.id)["tokens"]
    return 0


def check_budget(info: ModelInfo, estimated_tokens: int) -> None:
    """Refuse before a call that would take the model past BUDGET_FRACTION of its daily limit."""
    if info.daily_tokens and used_tokens(info) + estimated_tokens > BUDGET_FRACTION * info.daily_tokens:
        raise DailyLimitReached(f"{info.label}: Compare stays within {BUDGET_FRACTION:.0%} of the free daily "
                                f"limit ({info.daily_tokens:,} tokens); try again later or pick another model")


_clients: dict[str, Any] = {}


def client(info: ModelInfo):
    """A cached client per provider (each keeps its own pacing), recording usage in the shared ledgers."""
    if not info.available:
        raise ModelUnavailable(info.reason)
    if info.provider not in _clients:
        from app.groq_budget import UsageLedger
        if info.provider == "groq":
            from app.evaluation.llm import GroqChat
            _clients["groq"] = GroqChat(ledger=UsageLedger(), tag="compare")
        elif info.provider == "cerebras":
            from app.cerebras import CerebrasChat
            _clients["cerebras"] = CerebrasChat(
                ledger=UsageLedger(BACKEND_DIR.parent / "data" / "cerebras_usage.json"), tag="compare")
        elif info.provider == "gemini":
            _clients["gemini"] = GeminiChat()
    return _clients[info.provider]


def complete(info: ModelInfo, messages: list[dict[str, str]], **kw) -> Completion:
    model = info.id.split("/", 1)[1]
    return client(info).complete(model, messages, **kw)
