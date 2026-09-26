"""Cerebras client: request shape, usage and limit headers, retries, daily limit, JSON failures, ledger."""
import json

import httpx
import pytest

from app.cerebras import CerebrasChat
from app.evaluation.llm import DailyLimitReached, JSONGenerationFailed, ModelUnavailable
from app.groq_budget import UsageLedger

OK = {"choices": [{"message": {"content": '{"items": []}'}, "finish_reason": "stop"}],
      "usage": {"prompt_tokens": 934, "completion_tokens": 221, "total_tokens": 1155,
                "completion_tokens_details": {"reasoning_tokens": 133}, "prompt_tokens_details": {"cached_tokens": 0}}}
HEADERS = {"x-ratelimit-remaining-tokens-day": "998013", "x-ratelimit-remaining-requests-day": "2399",
           "x-ratelimit-remaining-requests-minute": "4"}


def client(responses, ledger=None):
    """responses: list of (status, body, headers); every request is kept in .sent."""
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        status, body, headers = responses.pop(0)
        return httpx.Response(status, json=body if isinstance(body, dict) else None,
                              text=body if isinstance(body, str) else None, headers=headers)

    http = httpx.Client(base_url="https://api.test/v1", transport=httpx.MockTransport(handler))
    sleeps = []
    c = CerebrasChat(http=http, min_interval=0.0, sleep=sleeps.append, ledger=ledger, tag="generation")
    return c, sent, sleeps


def test_request_usage_and_headers(tmp_path):
    led = UsageLedger(tmp_path / "u.json", clock=lambda: 1_000_000.0)
    c, sent, _ = client([(200, OK, HEADERS)], led)
    out = c.complete("gpt-oss-120b", [{"role": "user", "content": "q"}], max_tokens=2300, temperature=0.7,
                     reasoning_effort="low", json_mode=True)
    assert sent[0] == {"model": "gpt-oss-120b", "messages": [{"role": "user", "content": "q"}], "temperature": 0.7,
                       "max_completion_tokens": 2300, "response_format": {"type": "json_object"},
                       "reasoning_effort": "low"}
    assert out.model == "cerebras/gpt-oss-120b" and out.input_tokens == 934 and out.output_tokens == 221
    assert out.reasoning_tokens == 133 and out.total_tokens == 1155
    assert c.remaining["tokens-day"] == 998013 and c.remaining["requests-day"] == 2399
    assert led.used("cerebras/gpt-oss-120b") == {"requests": 1, "tokens": 1155}


def test_reasoning_none_is_not_sent():
    c, sent, _ = client([(200, OK, {})])
    c.complete("qwen-3.8-27b", [], max_tokens=10, reasoning_effort="none")
    assert "reasoning_effort" not in sent[0]


def test_rate_limit_waits_then_succeeds():
    c, sent, sleeps = client([(429, "Too many requests per minute", {"retry-after": "7"}), (200, OK, {})])
    c.complete("gpt-oss-120b", [], max_tokens=10)
    assert len(sent) == 2 and 7.0 in sleeps


def test_daily_limit_raises():
    c, _, _ = client([(429, "Tokens per day limit exceeded", {"x-ratelimit-remaining-tokens-day": "0"})])
    with pytest.raises(DailyLimitReached):
        c.complete("gpt-oss-120b", [], max_tokens=10)


def test_json_failure_is_not_retried_and_is_charged(tmp_path):
    led = UsageLedger(tmp_path / "u.json", clock=lambda: 1_000_000.0)
    c, sent, _ = client([(400, "Failed to generate JSON", {})], led)
    with pytest.raises(JSONGenerationFailed):
        c.complete("gpt-oss-120b", [{"role": "user", "content": "x" * 400}], max_tokens=50, json_mode=True)
    assert len(sent) == 1 and led.used("cerebras/gpt-oss-120b")["tokens"] == 150


def test_unknown_model_and_repeated_errors():
    c, _, _ = client([(404, "model not found", {})])
    with pytest.raises(ModelUnavailable):
        c.complete("nope", [], max_tokens=10)
    c, sent, _ = client([(500, "boom", {})] * 5)
    with pytest.raises(RuntimeError, match="failed after 5 attempts"):
        c.complete("gpt-oss-120b", [], max_tokens=10)
    assert len(sent) == 5


def test_calls_are_paced():
    clock = [0.0]
    sleeps = []
    http = httpx.Client(base_url="https://api.test/v1",
                        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=OK)))
    c = CerebrasChat(http=http, min_interval=24.5, sleep=lambda s: (sleeps.append(s), clock.__setitem__(0, clock[0] + s)),
                     clock=lambda: clock[0])
    c.complete("gpt-oss-120b", [], max_tokens=10)
    clock[0] += 4.5
    c.complete("gpt-oss-120b", [], max_tokens=10)
    assert sleeps == [pytest.approx(20.0)]
