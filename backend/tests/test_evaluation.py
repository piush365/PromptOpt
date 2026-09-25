"""Evaluation harness tests. No network: Groq is replaced by a fake client."""
import json
import sys
from types import SimpleNamespace

import groq
import httpx
import pytest

from app.db.models import EvaluationRun
from app.evaluation import judge
from app.evaluation import run as ev
from app.evaluation.llm import DailyLimitReached, GroqChat, ModelUnavailable
from app.evaluation.success import (assign_labels, classification_items, classification_labels,
                                    classification_success, coding_success)
from app.evaluation.variants import build_variants, with_context
from app.stage_a.classifier import KeywordClassifier
from app.stage_a.detector import FeatureDetector

DETECTOR = FeatureDetector(classifier=KeywordClassifier(), use_spacy=False)


def _response(content: str, model: str, prompt_tokens: int = 10, completion_tokens: int = 20,
              total_time: float | None = 0.25, finish: str = "stop", reasoning: int | None = 5):
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_time=total_time,
                            completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning))
    return SimpleNamespace(model=model, usage=usage,
                           choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)])


def _http_error(cls, status: int, message: str, headers: dict | None = None):
    resp = httpx.Response(status, headers=headers or {}, request=httpx.Request("POST", "https://api.groq.test"))
    return cls(message, response=resp, body=None)


class FakeClient:
    """Answers from a script: each entry is a response object or an exception to raise."""

    def __init__(self, script=None, default=None):
        self.script, self.default, self.requests = list(script or []), default, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        item = self.script.pop(0) if self.script else self.default(kwargs)
        if isinstance(item, Exception):
            raise item
        return item


def _chat(client, **kw):
    sleeps = []
    return GroqChat(client=client, min_interval=0.0, sleep=sleeps.append, **kw), sleeps


# ---------------------------------------------------------------- Groq client
def test_rate_limit_waits_retry_after_then_succeeds():
    client = FakeClient([_http_error(groq.RateLimitError, 429, "Rate limit reached (RPM)", {"retry-after": "3"}),
                         _response("hi", "m")])
    llm, sleeps = _chat(client)
    c = llm.complete("m", [{"role": "user", "content": "x"}], max_tokens=10)
    assert c.content == "hi" and sleeps == [3.0] and llm.calls == 2


def test_rate_limit_without_header_backs_off_exponentially():
    err = lambda: _http_error(groq.RateLimitError, 429, "Rate limit reached (TPM)")  # noqa: E731
    llm, sleeps = _chat(FakeClient([err(), err(), _response("ok", "m")]))
    assert llm.complete("m", [], max_tokens=10).content == "ok" and sleeps == [5, 10]


def test_daily_limit_stops_immediately():
    llm, _ = _chat(FakeClient([_http_error(groq.RateLimitError, 429, "Limit 1000, Used 1000: requests per day (RPD)")]))
    with pytest.raises(DailyLimitReached):
        llm.complete("m", [], max_tokens=10)


def test_missing_model_is_unavailable():
    llm, _ = _chat(FakeClient([_http_error(groq.NotFoundError, 404, "model_not_found")]))
    with pytest.raises(ModelUnavailable):
        llm.complete("m", [], max_tokens=10)


def test_reasoning_effort_is_dropped_when_rejected():
    client = FakeClient([_http_error(groq.BadRequestError, 400, "reasoning_effort is not supported"),
                         _response("ok", "m"), _response("ok again", "m")])
    llm, _ = _chat(client)
    llm.complete("m", [], max_tokens=10, reasoning_effort="low")
    llm.complete("m", [], max_tokens=10, reasoning_effort="low")
    assert "reasoning_effort" in client.requests[0]
    assert all("reasoning_effort" not in r for r in client.requests[1:])          # remembered for the run


def test_gives_up_after_max_retries():
    err = lambda: _http_error(groq.InternalServerError, 500, "boom")  # noqa: E731
    llm, _ = _chat(FakeClient([err() for _ in range(3)]), max_retries=3)
    with pytest.raises(RuntimeError, match="3 attempts"):
        llm.complete("m", [], max_tokens=10)


def test_completion_fields_and_request_settings():
    client = FakeClient([_response("a", "m", 12, 34, total_time=0.4567, reasoning=9)])
    llm, _ = _chat(client)
    c = llm.complete("m", [{"role": "user", "content": "q"}], max_tokens=77, temperature=0.0, json_mode=True)
    assert (c.input_tokens, c.output_tokens, c.reasoning_tokens, c.latency_ms) == (12, 34, 9, 457)
    req = client.requests[0]
    assert req["temperature"] == 0.0 and req["max_completion_tokens"] == 77
    assert req["response_format"] == {"type": "json_object"}


def test_calls_are_spaced_out():
    now = [0.0]
    sleeps = []
    llm = GroqChat(client=FakeClient(default=lambda kw: _response("x", "m")), min_interval=2.2,
                   sleep=lambda s: (sleeps.append(s), now.__setitem__(0, now[0] + s)), clock=lambda: now[0])
    llm.complete("m", [], max_tokens=5)
    now[0] += 1.0
    llm.complete("m", [], max_tokens=5)
    assert sleeps == [pytest.approx(1.2)]


# ---------------------------------------------------------------- variants
ROWS = [
    {"source_id": "dolly-1", "category": "closed_qa", "split": "val", "degraded_prompt": "who built it",
     "optimized_prompt": "Based on the provided text, who built the tower? Answer in one sentence.",
     "original_instruction": "Who built the Eiffel Tower?", "context": "Gustave Eiffel's company built the tower.",
     "reference_response": "Gustave Eiffel's company."},
    {"source_id": "dolly-2", "category": "classification", "split": "val",
     "degraded_prompt": "which is string or percussion: tombak, cizhonghlu",
     "optimized_prompt": 'Classify each instrument as "string" or "percussion".',
     "original_instruction": "Identify which instrument is string or percussion: Tombak, Cizhonghlu", "context": "",
     "reference_response": "Cizhonghlu is string, Tombak is percussion."},
    {"source_id": "codealpaca-3", "category": "coding", "split": "val", "degraded_prompt": "python fn to add 2 nums",
     "optimized_prompt": "Write a Python function that returns the sum of two numbers, in one code block.",
     "original_instruction": "Write a Python function to add two numbers.", "context": "",
     "reference_response": "def add(a, b):\n    return a + b"},
]


def test_every_variant_gets_the_same_context_appended():
    v = build_variants(ROWS[0], DETECTOR)
    assert set(v) == {"degraded", "stage_b", "dataset_target"}
    for x in v.values():
        assert x["prompt"] == with_context(x["request"], ROWS[0]["context"])
        assert x["prompt"].endswith("\n\nGustave Eiffel's company built the tower.")
    assert v["degraded"]["request"] == "who built it"
    assert "rules_applied" in v["stage_b"]["meta"]


def test_no_context_means_prompt_is_the_request():
    v = build_variants(ROWS[1], DETECTOR)
    assert all(x["prompt"] == x["request"] for x in v.values())


# ---------------------------------------------------------------- judge
def test_judge_is_blind_to_the_variant():
    msgs = judge.messages("closed_qa", "who built it", "some text", "ref", "resp")
    text = json.dumps(msgs).lower()
    assert not any(w in text for w in ("degraded", "stage_b", "optimized", "dataset_target", "variant"))
    assert "answers_correctly" in msgs[0]["content"]
    assert "answers_correctly" not in judge.messages("summarization", "r", None, "ref", "resp")[0]["content"]


@pytest.mark.parametrize("content, score, correct", [
    ('{"score": 8, "answers_correctly": true, "reason": "fine"}', 8.0, True),
    ('<think>hmm</think>\nHere: {"score": "7.5", "answers_correctly": "false", "reason": "x"}', 7.5, False),
    ('{"score": 14, "answers_correctly": false, "reason": "x"}', 10.0, False),
])
def test_judge_parse(content, score, correct):
    j = judge.parse(content, "closed_qa")
    assert j.score == score and j.answers_correctly is correct


@pytest.mark.parametrize("content", ["no json here", '{"reason": "no score"}',
                                     '{"score": 5, "reason": "closed_qa needs a verdict"}'])
def test_judge_parse_rejects_unusable_output(content):
    with pytest.raises(ValueError):
        judge.parse(content, "closed_qa")


def test_long_context_and_response_are_shortened_for_the_judge():
    msgs = judge.messages("summarization", "sum", "x" * 5000, "ref", "y" * 9000)
    assert len(msgs[1]["content"]) < judge.MAX_CONTEXT_CHARS + judge.MAX_RESPONSE_CHARS + 500


# ---------------------------------------------------------------- task success
def test_classification_items_and_labels():
    ins = "Identify which instrument is string or percussion: Tombak, Cizhonghlu"
    assert classification_labels(ins, "x") == ["string", "percussion"]
    assert classification_items(ins) == ["Tombak", "Cizhonghlu"]
    ins = "Classify these animals by either a mammal or reptile; \nLizard, Lion"
    assert classification_labels(ins, "Yes, I grouped these animals as mammals and reptiles.") == ["mammal", "reptile"]
    assert classification_items(ins) == ["Lizard", "Lion"]
    assert classification_labels("Is Shantaram a book?", "yes") == ["yes", "no"]
    assert classification_labels("what is yellow long fruit?", "banana") == []


@pytest.mark.parametrize("text", [
    "Cizhonghlu is string, Tombak is percussion.",
    "Tombak: percussion\nCizhonghlu: string",
    "- **Percussion**: Tombak\n- **String**: Cizhonghlu",
    "Cizhonghlu and Kanun are strings. Tombak is percussion.",
])
def test_assign_labels_reads_common_answer_shapes(text):
    got = assign_labels(text, ["Tombak", "Cizhonghlu"], ["string", "percussion"])
    assert got == {"Tombak": "percussion", "Cizhonghlu": "string"}


def test_assign_labels_items_waiting_for_a_label():
    text = "Golf, boxing and running are individual sports. Basketball is a team sport"
    got = assign_labels(text, ["Golf", "boxing", "running", "Basketball"], ["individual", "team"])
    assert got == {"Golf": "individual", "boxing": "individual", "running": "individual", "Basketball": "team"}


def test_classification_success():
    ins, ref = ROWS[1]["original_instruction"], ROWS[1]["reference_response"]
    assert classification_success(ins, ref, "Tombak: percussion\nCizhonghlu: string") is True
    assert classification_success(ins, ref, "Tombak: string\nCizhonghlu: string") is False
    assert classification_success(ins, ref, "I am not sure.") is False
    assert classification_success("Is Shantaram a book?", "yes", "Yes, it is a novel.") is True
    assert classification_success("Is Shantaram a book?", "yes", "No.") is False
    assert classification_success("what is yellow long fruit?", "banana", "banana") is None


@pytest.mark.parametrize("instruction, response, ok", [
    ("Write a Python function to add two numbers.", "```python\ndef add(a, b):\n    return a + b\n```", True),
    ("Write a Python function to add two numbers.", "```python\ndef add(a, b)\n    return a + b\n```", False),
    ("Write a Python function to add two numbers.", "```\ndef add(a, b):\n    return a+b\n```", True),
    ("Write a Python function to add two numbers.", "def add(a, b): return a + b", False),      # no code block
    ("Write a JavaScript function to add numbers.", "```\nfunction add(a, b) { return a + b }\n```", True),
    ("Write a function to add numbers.", "```js\nfunction add(a, b) { return a + b }\n```", True),
])
def test_coding_success(instruction, response, ok):
    assert coding_success(instruction, response) is ok


# ---------------------------------------------------------------- harness
def _default_answer(kwargs):
    if kwargs["model"] == ev.JUDGE_MODEL:
        return _response('{"score": 8, "answers_correctly": true, "reason": "matches"}', ev.JUDGE_MODEL, 50, 10)
    prompt = kwargs["messages"][0]["content"]
    if "string" in prompt:
        content = "Tombak: percussion\nCizhonghlu: string"
    elif "nums" in prompt or "sum" in prompt.lower():
        content = "```python\ndef add(a, b):\n    return a + b\n```"
    else:
        content = "Gustave Eiffel's company."
    return _response(content, ev.TARGET_MODEL, len(prompt.split()), 30)


def test_run_records_every_item_and_summary(db, tmp_path):
    client = FakeClient(default=_default_answer)
    llm, _ = _chat(client)
    cache = ev.Cache(tmp_path / "r.jsonl")
    stats = ev.run(db, ROWS, llm, DETECTOR, "t", "v1-test", cache, log=lambda s: None)
    assert stats["recorded"] == 9 and stats["target_calls"] == 9 and stats["judge_calls"] == 9
    rows = db.query(EvaluationRun).filter_by(run_name="t").all()
    assert {r.dataset_item_id for r in rows} == {"dolly-1", "dolly-2", "codealpaca-3"}      # source_id, not id
    by = {(r.dataset_item_id, r.variant): r for r in rows}
    assert by[("dolly-1", "degraded")].task_success is True                                # judge verdict
    assert by[("dolly-2", "stage_b")].task_success is True                                 # label match
    assert by[("codealpaca-3", "dataset_target")].task_success is True                     # code parses
    assert by[("dolly-1", "degraded")].latency_ms == 250 and by[("dolly-1", "degraded")].quality_score == 8.0
    text = ev.summary(db, "t", cache)
    assert "| **all** | stage_b | 3 |" in text and "| classification | degraded | 1 |" in text


def test_run_is_resumable_without_repeating_api_calls(db, tmp_path):
    daily = _http_error(groq.RateLimitError, 429, "requests per day (RPD)")
    client = FakeClient([_default_answer({"model": ev.TARGET_MODEL, "messages": [{"content": "who"}]}), daily],
                        default=_default_answer)
    llm, _ = _chat(client)
    cache = ev.Cache(tmp_path / "r.jsonl")
    first = ev.run(db, ROWS, llm, DETECTOR, "t", "v1-test", cache, log=lambda s: None)
    assert first.get("stopped") == 1 and first["recorded"] == 0 and first["target_calls"] == 1

    client2 = FakeClient(default=_default_answer)
    llm2, _ = _chat(client2)
    second = ev.run(db, ROWS, llm2, DETECTOR, "t", "v1-test", ev.Cache(tmp_path / "r.jsonl"), log=lambda s: None)
    assert second["recorded"] == 9 and second["target_calls"] == 8               # the cached target call is reused

    client3 = FakeClient(default=_default_answer)
    llm3, _ = _chat(client3)
    third = ev.run(db, ROWS, llm3, DETECTOR, "t", "v1-test", ev.Cache(tmp_path / "r.jsonl"), log=lambda s: None)
    assert third["recorded"] == 0 and third["skipped"] == 9 and client3.requests == []


def test_unusable_judge_output_is_retried_and_not_recorded(db, tmp_path):
    def answer(kwargs):
        if kwargs["model"] == ev.JUDGE_MODEL:
            return _response("I refuse to use JSON", ev.JUDGE_MODEL)
        return _default_answer(kwargs)
    llm, _ = _chat(FakeClient(default=answer))
    stats = ev.run(db, ROWS[:1], llm, DETECTOR, "t", "v", ev.Cache(tmp_path / "r.jsonl"), variants=("degraded",),
                   log=lambda s: None)
    assert stats["judge_failures"] == 1 and stats["recorded"] == 0
    assert db.query(EvaluationRun).count() == 0                                  # retried on the next run


def test_select_rows_is_fixed_balanced_and_interleaved():
    rows = [{"source_id": f"{c}-{i}", "category": c} for c in ev.CATEGORIES for i in range(20)]
    a, b = ev.select_rows(rows, 5), ev.select_rows(list(reversed(rows)), 5)
    assert [r["source_id"] for r in a] == [r["source_id"] for r in b]
    assert [r["category"] for r in a[:5]] == ev.CATEGORIES and len(a) == 25


@pytest.mark.parametrize("split", ["test", "benchmark"])
def test_held_out_splits_need_final(monkeypatch, split):
    monkeypatch.setattr(sys, "argv", ["run", "--split", split])
    with pytest.raises(SystemExit, match="held out"):
        ev.main()


def test_classification_ignores_unicode_spaces_and_dashes():
    ins = "Which characters belong to DC or Marvel Universe? Catwoman, Black Cat"
    ref = "Catwoman is DC, Black Cat is Marvel"
    resp = "**Catwoman** – *DC Comics*\n\n**Black Cat** – *Marvel Universe*"
    assert classification_success(ins, ref, resp) is True


def test_changed_prompt_is_called_and_judged_again(db, tmp_path):
    cache = ev.Cache(tmp_path / "r.jsonl")
    row = ROWS[0]
    old = {"prompt": "an older stage_b prompt", "request": "older", "category": "closed_qa", "meta": {},
           "response": "old answer", "target": {"input_tokens": 1, "output_tokens": 1, "latency_ms": 1},
           "judgment": {"score": 1.0, "reason": "old", "answers_correctly": False}}
    cache.add(row["source_id"], "stage_b", **old)
    client = FakeClient(default=_default_answer)
    llm, _ = _chat(client)
    stats = ev.run(db, [row], llm, DETECTOR, "t", "v", cache, variants=("stage_b",), log=lambda s: None)
    assert stats["target_calls"] == 1 and stats["judge_calls"] == 1
    rec = db.query(EvaluationRun).one()
    assert rec.quality_score == 8.0 and rec.task_success is True                 # the new judgment, not the old one
    reloaded = ev.Cache(tmp_path / "r.jsonl").get(row["source_id"], "stage_b")
    assert reloaded["response"] != "old answer" and reloaded["judgment"]["score"] == 8.0
