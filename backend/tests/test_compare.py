"""Compare with recorded responses only: no live API calls in the tests."""
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import api
from app.coding import app_tests
from app.compare import providers, service
from app.db.base import Base, get_db
from app.db.seed import seed_rules
from app.evaluation.llm import Completion, DailyLimitReached, ModelUnavailable
from app.stage_a.classifier import KeywordClassifier
from app.stage_a.detector import FeatureDetector

REC = json.loads((Path(__file__).parent / "fixtures" / "compare_recorded.json").read_text())
CODING_ITEM = {"source_id": "codealpaca-test", "mode": "function", "entry": "square",
               "tests": ["assert square(3) == 9", "assert square(0) == 0", "assert square(-2) == 4"],
               "degraded_prompt": "py code for square of a number", "instruction": "Square of a number."}


def completion(rec: dict, model: str = "m") -> Completion:
    return Completion(rec["content"], model, rec.get("input_tokens", 10), rec.get("output_tokens", 10),
                      rec.get("reasoning_tokens"), rec.get("latency_ms", 100), rec.get("finish_reason", "stop"))


class Recorded:
    """Answers from the recording: the original prompt gets the 'original' answer, anything else 'optimized'."""

    def __init__(self, kind: str, original_prompt: str):
        self.kind, self.original_prompt, self.calls = kind, original_prompt, []

    def __call__(self, info, messages, **kw):
        self.calls.append((info.id, messages[-1]["content"], kw))
        variant = "original" if messages[-1]["content"].startswith(self.original_prompt) else "optimized"
        return completion(REC[self.kind][variant], info.id)


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(providers, "used_tokens", lambda info: 0)
    monkeypatch.setattr(service, "CACHE", tmp_path / "cache.jsonl")
    monkeypatch.setattr(app_tests, "_items", lambda: {app_tests._norm(CODING_ITEM["degraded_prompt"]): CODING_ITEM})
    return tmp_path


def test_coding_compare_runs_sandbox_tests_and_reports_changes(env, monkeypatch):
    rec = Recorded("coding", CODING_ITEM["degraded_prompt"])
    monkeypatch.setattr(providers, "complete", rec)
    r = service.compare(CODING_ITEM["degraded_prompt"], "### Task\nWrite a function square(n).", "groq/openai/gpt-oss-120b",
                        "gpt", category="coding", cache_path=env / "c.jsonl")
    assert r["answered_by"] == "groq/openai/gpt-oss-120b" and r["rendered_for"] == "gpt" and r["stand_in"]
    assert r["label"].startswith("GPT-rendered prompt, answered by gpt-oss-120b on Groq (a stand-in")
    assert r["original"]["total_tokens"] == 82 + 310 and r["optimized"]["reasoning_tokens"] == 60
    assert r["change_pct"]["total_tokens"] == round(100 * ((104 + 95) - (82 + 310)) / (82 + 310), 1)
    t = r["tests"]
    assert t["validated"] and t["original"]["outcome"] == "naming-only" and t["original"]["renamed"] == "sq"
    assert t["optimized"]["outcome"] == "pass" and t["optimized"]["passed"] == 3
    assert all(kw["temperature"] == 0.0 and kw["max_tokens"] == 2048 and kw["reasoning_effort"] == "low"
               for _, _, kw in rec.calls)                               # same settings for both variants
    # cached: the same comparison again makes no calls
    n = len(rec.calls)
    service.compare(CODING_ITEM["degraded_prompt"], "### Task\nWrite a function square(n).", "groq/openai/gpt-oss-120b",
                    "gpt", category="coding", cache_path=env / "c.jsonl")
    assert len(rec.calls) == n


def test_closed_qa_with_context_and_blind_judge(env, monkeypatch):
    rec = Recorded("closed_qa", "when did the eiffel tower open")
    monkeypatch.setattr(providers, "complete", rec)

    class Judge:
        def complete(self, model, messages, **kw):
            assert "original" not in messages[1]["content"].lower().split("response:")[0]   # blind to the variant
            assert messages[1]["content"].startswith("USER'S REQUEST:\nwhen did the eiffel tower open")
            return completion(REC["judge"])
    monkeypatch.setattr(providers, "client", lambda info: Judge())
    r = service.compare("when did the eiffel tower open", "<task>\nWhen did it open?\n</task>", "cerebras/gpt-oss-120b",
                        "claude", context="The Eiffel Tower opened in 1889.", category="closed_qa", judge_answers=True,
                        cache_path=env / "c.jsonl")
    assert rec.calls[0][1] == "when did the eiffel tower open\n\nThe Eiffel Tower opened in 1889."   # pasted text added
    assert r["tests"] is None and r["judge"]["blind"] and r["judge"]["original"]["score"] == 8.0
    assert r["change_pct"]["output_tokens"] < -80 and "Claude-rendered prompt" in r["label"]


def test_budget_and_availability(env, monkeypatch):
    monkeypatch.setattr(providers, "used_tokens", lambda info: 199_000)
    with pytest.raises(DailyLimitReached, match="70%"):
        providers.check_budget(providers.BY_ID["groq/openai/gpt-oss-120b"], 2000)
    for mid, key in (("openai/gpt", "OPENAI_API_KEY"), ("anthropic/claude", "ANTHROPIC_API_KEY")):
        info = providers.BY_ID[mid]
        assert not info.available and key in info.reason
        with pytest.raises(ModelUnavailable):
            service.compare("x", "y", mid, "gpt")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert not providers.BY_ID["openai/gpt"].available            # a key alone is not enough: no client yet
    assert not [m for m in providers.MODELS if m.provider == "gemini"][0].available


# ---------------------------------------------------------------- Gemini adapter (recorded HTTP)
def test_gemini_adapter_header_key_usage_and_thoughts():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["key"] = str(request.url), request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=REC["gemini_response"])
    http = httpx.Client(base_url=providers.GEMINI_URL, headers={"x-goog-api-key": "secret-key"},
                        transport=httpx.MockTransport(handler))
    c = providers.GeminiChat(http=http).complete("gemini-2.5-flash", [{"role": "system", "content": "Be brief."},
                                                                      {"role": "user", "content": "When?"}],
                                                 max_tokens=2048)
    assert "secret-key" not in seen["url"] and seen["key"] == "secret-key"           # key in the header only
    assert seen["body"]["generationConfig"] == {"temperature": 0.0, "maxOutputTokens": 2048}
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "Be brief."
    assert c.content == "1889." and c.input_tokens == 70 and c.output_tokens == 28 and c.reasoning_tokens == 25


def test_gemini_quota_and_errors_do_not_leak_the_key():
    def quota(request):
        return httpx.Response(429, json={"error": {"message": "Quota exceeded for requests per day"}})
    http = httpx.Client(base_url=providers.GEMINI_URL, headers={"x-goog-api-key": "secret-key"},
                        transport=httpx.MockTransport(quota))
    with pytest.raises(DailyLimitReached) as e:
        providers.GeminiChat(http=http, sleep=lambda s: None).complete("m", [{"role": "user", "content": "x"}], 10)
    assert "secret-key" not in str(e.value)

    def boom(request):
        raise httpx.ConnectError("connection failed", request=request)
    http = httpx.Client(base_url=providers.GEMINI_URL, headers={"x-goog-api-key": "secret-key"},
                        transport=httpx.MockTransport(boom))
    with pytest.raises(RuntimeError) as e:
        providers.GeminiChat(http=http, sleep=lambda s: None).complete("m", [{"role": "user", "content": "x"}], 10)
    assert "secret-key" not in str(e.value)


# ---------------------------------------------------------------- API
@pytest.fixture
def client(env, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as s:
        seed_rules(s)

    def session():
        with Session() as s:
            yield s
    api.app.dependency_overrides[get_db] = session
    monkeypatch.setattr(api, "detector", lambda: FeatureDetector(classifier=KeywordClassifier(), use_spacy=False))
    monkeypatch.setattr(api, "stage_c_model", lambda: None)
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def test_api_models_and_errors(client):
    m = client.get("/api/compare/models").json()
    assert m["default"] == "groq/openai/gpt-oss-120b"
    by = {x["id"]: x for x in m["models"]}
    assert not by["openai/gpt"]["available"] and "OPENAI_API_KEY" in by["openai/gpt"]["reason"]
    assert "test-key" not in json.dumps(m)                                           # keys never returned
    body = {"prompt": "a cat", "model": "anthropic/claude"}
    assert client.post("/api/compare", json=body).status_code == 503
    assert client.post("/api/compare", json={**body, "model": "nope"}).status_code == 422
    assert client.post("/api/compare", json={"prompt": "a cat", "category": "image_generation", "target": "dalle",
                                             "model": "groq/openai/gpt-oss-120b"}).status_code == 422


def test_api_compare_end_to_end(client, monkeypatch):
    rec = Recorded("coding", CODING_ITEM["degraded_prompt"])
    monkeypatch.setattr(providers, "complete", rec)
    r = client.post("/api/compare", json={"prompt": CODING_ITEM["degraded_prompt"], "category": "coding",
                                          "target": "gemini", "model": "cerebras/gpt-oss-120b"}).json()
    assert r["label"].startswith("Gemini-rendered prompt, answered by gpt-oss-120b on Cerebras (a stand-in")
    assert r["optimized"]["prompt"].startswith("Task:")                              # the Gemini rendering was sent
    assert r["tests"]["optimized"]["outcome"] == "pass"
    usage = client.get(f"/api/history/{r['prompt_id']}").json()["results"][0]["token_usage"]
    assert any(u["target_llm"] == "gemini" and u["optimized_input"] == 104 for u in usage)


def test_gemini_per_minute_limit_is_retried_per_day_limit_stops():
    minute = {"error": {"message": "You exceeded your current quota. Quota exceeded for metric: generate_content_free_"
                                   "tier_requests", "details": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel"
                                                                            "-FreeTier"}]}}
    calls = []

    def first_minute_then_ok(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json=minute)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                                         "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 1}})
    http = httpx.Client(base_url=providers.GEMINI_URL, transport=httpx.MockTransport(first_minute_then_ok))
    c = providers.GeminiChat(http=http, sleep=lambda s: None).complete("m", [{"role": "user", "content": "x"}], 10)
    assert c.content == "ok" and len(calls) == 2                                      # waited out, not "daily"
    day = {"error": {"message": "Quota exceeded", "details": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel"
                                                                          "-FreeTier"}]}}
    http = httpx.Client(base_url=providers.GEMINI_URL,
                        transport=httpx.MockTransport(lambda request: httpx.Response(429, json=day)))
    with pytest.raises(DailyLimitReached):
        providers.GeminiChat(http=http, sleep=lambda s: None).complete("m", [{"role": "user", "content": "x"}], 10)


def test_api_compare_sends_both_prompts_pii_scrubbed(client, monkeypatch):
    seen = []

    def fake(info, messages, **kw):
        seen.append(messages[-1]["content"])
        return completion({"content": "Sure."}, info.id)
    monkeypatch.setattr(providers, "complete", fake)
    r = client.post("/api/compare", json={"prompt": "email ravi@example.com the summary of this", "target": "gpt",
                                          "context": "Call 555-123-4567 about the launch on Friday.",
                                          "model": "groq/openai/gpt-oss-120b"})
    assert r.status_code == 200
    assert len(seen) == 2
    for sent in seen:                                    # original and optimized: same scrubbed input
        assert "ravi@example.com" not in sent and "555-123-4567" not in sent
        assert "[PHONE]" in sent
    assert "[EMAIL]" in r.json()["original"]["prompt"]
