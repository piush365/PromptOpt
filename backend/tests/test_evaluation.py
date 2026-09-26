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
def test_json_generation_failure_is_not_retried_unchanged():
    from app.evaluation.llm import JSONGenerationFailed

    err = _http_error(groq.BadRequestError, 400, "Error code: 400 - {'error': {'code': 'json_validate_failed', "
                                                  "'failed_generation': 'max completion tokens reached'}}")
    client = FakeClient([err, _response("never used", "m")])
    llm, _ = _chat(client)
    with pytest.raises(JSONGenerationFailed):
        llm.complete("m", [{"role": "user", "content": "q"}], max_tokens=50, json_mode=True)
    assert len(client.requests) == 1


def test_judge_retries_with_more_tokens_after_json_failure():
    from app.evaluation import run as run_mod

    err = _http_error(groq.BadRequestError, 400, "json_validate_failed: max completion tokens reached")
    good = _response('{"score": 8, "answers_correctly": true, "reason": "ok"}', run_mod.JUDGE_MODEL)
    client = FakeClient([err, good])
    llm, _ = _chat(client)
    j = run_mod._judge(llm, "closed_qa", "q", "", "ref", "resp")
    assert j.score == 8
    assert [r["max_completion_tokens"] for r in client.requests] == [run_mod.JUDGE_MAX_TOKENS,
                                                                      2 * run_mod.JUDGE_MAX_TOKENS]


def test_successful_calls_are_recorded_in_the_usage_ledger(tmp_path):
    from app.groq_budget import UsageLedger

    ledger = UsageLedger(tmp_path / "usage.json", clock=lambda: 1_000_000.0)
    client = FakeClient([_http_error(groq.RateLimitError, 429, "Rate limit reached (RPM)", {"retry-after": "1"}),
                         _response("hi", "m", prompt_tokens=30, completion_tokens=12)])
    llm, _ = _chat(client, ledger=ledger, tag="evaluation")
    llm.complete("m", [{"role": "user", "content": "q"}], max_tokens=50)
    assert ledger.used("m", "evaluation") == {"requests": 1, "tokens": 42}      # the failed attempt is not counted

    cached = _response("hi", "m", prompt_tokens=30, completion_tokens=12)
    cached.usage.prompt_tokens_details = SimpleNamespace(cached_tokens=25)
    llm2, _ = _chat(FakeClient([cached]), ledger=ledger, tag="generation")
    c = llm2.complete("m", [{"role": "user", "content": "q"}], max_tokens=50)
    assert c.cached_tokens == 25 and c.total_tokens == 42
    assert ledger.used("m", "generation") == {"requests": 1, "tokens": 42}      # cached input still counts per day


def test_json_validation_failure_is_charged_to_the_ledger(tmp_path):
    from app.evaluation.llm import JSONGenerationFailed
    from app.groq_budget import UsageLedger

    ledger = UsageLedger(tmp_path / "usage.json", clock=lambda: 1_000_000.0)
    err = _http_error(groq.BadRequestError, 400, "json_validate_failed")
    llm, _ = _chat(FakeClient([err]), ledger=ledger, tag="generation")
    with pytest.raises(JSONGenerationFailed):
        llm.complete("m", [{"role": "user", "content": "x" * 400}], max_tokens=50, json_mode=True)
    assert ledger.used("m") == {"requests": 1, "tokens": 100 + 50}             # prompt chars / 4 + max tokens


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
    msgs = judge.messages("summarization", "sum", "x" * 5000, "ref", "y" * 20000)
    assert len(msgs[1]["content"]) < judge.MAX_CONTEXT_CHARS + judge.MAX_RESPONSE_CHARS + 500


def test_long_responses_keep_their_end_and_say_who_cut_them():
    whole = "start " + "x" * 8600 + " END-OF-SCRIPT"            # val codealpaca-15059: 8,608 chars, complete
    assert judge.shorten_response(whole) == whole                # shown whole now
    long = "start " + "y" * 20000 + " END-OF-SCRIPT"
    short = judge.shorten_response(long)
    assert short.startswith("start ") and short.endswith("END-OF-SCRIPT")
    assert "omitted by the evaluator, not by the assistant" in short and len(short) < judge.MAX_RESPONSE_CHARS + 100
    assert "never count it as missing" in judge.messages("coding", "q", None, "r", long)[0]["content"]


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


def test_judge_gives_up_on_an_item_after_failing_in_two_runs(db, tmp_path):
    judge_calls = []

    def answer(kwargs):
        if kwargs["model"] == ev.JUDGE_MODEL:
            judge_calls.append(1)
            return _response("I refuse to use JSON", ev.JUDGE_MODEL)
        return _default_answer(kwargs)
    llm, _ = _chat(FakeClient(default=answer))
    cache = ev.Cache(tmp_path / "r.jsonl")
    for _ in range(ev.JUDGE_GIVE_UP_RUNS):
        ev.run(db, ROWS[:1], llm, DETECTOR, "t", "v", cache, variants=("degraded",), log=lambda s: None)
    n = len(judge_calls)
    stats = ev.run(db, ROWS[:1], llm, DETECTOR, "t", "v", ev.Cache(tmp_path / "r.jsonl"), variants=("degraded",),
                   log=lambda s: None)
    assert len(judge_calls) == n and stats["judge_given_up"] == 1 and stats["recorded"] == 0


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


def test_final_run_can_resume_but_not_repeat_on_another_dataset(db):
    from app.db import repository as repo
    from app.evaluation import run as run_mod

    run_mod.check_final_once(db, "final-benchmark", "v1-100-aaaa")                 # nothing yet: fine
    repo.record_evaluation(db, "final-benchmark", "v1-100-aaaa", "dolly-1", "closed_qa", "degraded",
                           "openai/gpt-oss-120b", 10)
    db.flush()
    run_mod.check_final_once(db, "final-benchmark", "v1-100-aaaa")                 # same dataset: resume
    with pytest.raises(SystemExit, match="run once"):
        run_mod.check_final_once(db, "final-benchmark", "v1-200-bbbb")


def test_cerebras_target_is_recorded_as_such(db):
    from app.evaluation import run as run_mod
    from app.llm_router import Router

    from pathlib import Path

    from app.evaluation.llm import _completion

    rows = [ROWS[0]]
    groq = FakeClient(default=lambda kw: _response('{"score": 7, "answers_correctly": null, "reason": "ok"}', "q"))
    target = SimpleNamespace(calls=[], complete=lambda model, msgs, **kw: (target.calls.append(model), _completion(
        _response("answer", "cerebras/gpt-oss-120b"), "cerebras/gpt-oss-120b", 5))[1])
    llm = Router(_chat(groq)[0], target)
    run_mod.run(db, rows, llm, DETECTOR, "dev-x", "v", run_mod.Cache(Path("/dev/null")), ("degraded",),
                log=lambda s: None, target_model=run_mod.TARGETS["cerebras"])
    assert target.calls == ["gpt-oss-120b"]



def test_refresh_redoes_changed_prompts_and_rejudges_long_responses(db, tmp_path):
    judged = []

    def answer(kwargs):
        if kwargs["model"] == ev.JUDGE_MODEL:
            judged.append(kwargs["messages"][1]["content"])
            return _response('{"score": 9, "answers_correctly": true, "reason": "ok"}', ev.JUDGE_MODEL)
        return _response("z" * 7000, ev.TARGET_MODEL)                       # a long answer
    llm, _ = _chat(FakeClient(default=answer))
    cache = ev.Cache(tmp_path / "r.jsonl")
    ev.run(db, ROWS[:1], llm, DETECTOR, "t", "v", cache, variants=("degraded",), log=lambda s: None)
    sid = ROWS[0]["source_id"]
    cache.add(sid, "degraded", judge_version=1)                               # as if judged by the old judge
    n_judged = len(judged)
    stats = ev.run(db, ROWS[:1], llm, DETECTOR, "t", "v", ev.Cache(tmp_path / "r.jsonl"), variants=("degraded",),
                   log=lambda s: None, refresh=True)
    assert stats["rejudged_long"] == 1 and stats["target_calls"] == 0 and len(judged) == n_judged + 1
    assert db.query(EvaluationRun).count() == 1
    again = ev.run(db, ROWS[:1], llm, DETECTOR, "t", "v", ev.Cache(tmp_path / "r.jsonl"), variants=("degraded",),
                   log=lambda s: None, refresh=True)
    assert "rejudged_long" not in again and len(judged) == n_judged + 1       # judged once, not every run

    c = ev.Cache(tmp_path / "r.jsonl")
    c.add(sid, "degraded", prompt="an older prompt")                           # a Stage B fix changed the prompt
    stats = ev.run(db, ROWS[:1], llm, DETECTOR, "t", "v", ev.Cache(tmp_path / "r.jsonl"), variants=("degraded",),
                   log=lambda s: None, refresh=True)
    assert stats["refreshed_prompt"] == 1 and stats["target_calls"] == 1 and db.query(EvaluationRun).count() == 1


def test_refresh_is_refused_for_final_runs(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run", "--split", "benchmark", "--final", "--refresh"])
    with pytest.raises(SystemExit, match="dev runs"):
        ev.main()



def test_summary_lists_wrong_references_separately(db, tmp_path):
    llm, _ = _chat(FakeClient(default=_default_answer))
    cache = ev.Cache(tmp_path / "r.jsonl")
    ev.run(db, ROWS[:2], llm, DETECTOR, "t", "v", cache, variants=("degraded",), log=lambda s: None)
    bad = ROWS[0]["source_id"]
    text = ev.summary(db, "t", cache, wrong_references={bad: "prints the wrong split", "not-in-run": "x"})
    assert "Excluded after the run** (1 items, left out for ALL variants" in text
    assert f"`{bad}`: wrong reference: prints the wrong split" in text
    assert "with and without the exclusions" in text
    assert "not-in-run" not in text
    rows = [l for l in text.splitlines() if l.startswith("| **all** | degraded")]
    assert rows and rows[0].split("|")[3].strip() == "1"                        # n counts only the good item
    plain = ev.summary(db, "t", cache, wrong_references={})
    assert [l for l in plain.splitlines() if l.startswith("| **all** | degraded")][0].split("|")[3].strip() == "2"



def test_an_item_the_judge_could_not_score_is_excluded_for_every_variant(db, tmp_path):
    bad_prompt = ROWS[0]["degraded_prompt"]

    def answer(kwargs):
        content = kwargs["messages"][-1]["content"]
        if kwargs["model"] == ev.JUDGE_MODEL:
            if "BAD-ANSWER" in content:
                return _response("no json here", ev.JUDGE_MODEL)
            return _response('{"score": 6, "answers_correctly": true, "reason": "ok"}', ev.JUDGE_MODEL)
        return _response("BAD-ANSWER" if content.startswith(bad_prompt) else "fine", ev.TARGET_MODEL)
    llm, _ = _chat(FakeClient(default=answer))
    for _ in range(ev.JUDGE_GIVE_UP_RUNS):
        ev.run(db, ROWS[:2], llm, DETECTOR, "t", "v", ev.Cache(tmp_path / "r.jsonl"),
               variants=("degraded", "dataset_target"), log=lambda s: None)
    cache = ev.Cache(tmp_path / "r.jsonl")
    sid = ROWS[0]["source_id"]
    assert cache.get(sid, "degraded").get("judgment") is None                  # the degraded answer is unscorable
    assert cache.get(sid, "dataset_target").get("judgment") is not None        # the other variant was scored
    text = ev.summary(db, "t", cache, wrong_references={})
    assert f"`{sid}`: judge could not score the degraded response" in text
    counted = {l.split("|")[2].strip(): l.split("|")[3].strip() for l in text.splitlines() if l.startswith("| **all** |")}
    assert counted == {"degraded": "1", "dataset_target": "1"}                 # row 0 out of BOTH variants


def test_headline_comparison_warns_above_one_point():
    def rows(q, succ):
        return [{"category": "coding", "variant": "stage_b", "n": 10, "avg_quality": q, "task_success_rate": succ,
                 "n_success_checked": 10, "avg_total_tokens": 100, "avg_latency_ms": 50}]
    quiet = "\n".join(ev.headline_comparison(rows(9.0, 0.90), rows(9.05, 0.905)))
    assert "change no headline number by more than 1 point" in quiet
    loud = "\n".join(ev.headline_comparison(rows(9.0, 0.90), rows(8.5, 0.80)))
    assert "Warning: the exclusions change headline numbers" in loud
    assert "stage_b quality 8.50 -> 9.00" in loud and "stage_b task success 80.0% -> 90.0%" in loud
