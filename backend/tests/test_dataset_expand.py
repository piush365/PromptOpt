"""Dataset v1.2 expansion: cleaning, sampling, budgeted/resumable generation, quality checks, frozen splits."""
import json
import re
from collections import Counter
from types import SimpleNamespace

import pytest

from app import dataset_expand as x
from app.evaluation.llm import DailyLimitReached
from app.groq_budget import UsageLedger

CATS = x.CATEGORIES


def src(i, cat="closed_qa", instruction=None, context="", response="an answer here", dataset="dolly"):
    prefix = "codealpaca" if dataset == "codealpaca" else "dolly"
    return {"source_dataset": dataset, "source_id": f"{prefix}-{i}", "category": cat,
            "instruction": instruction or f"question number {i} about topic {i}?", "context": context,
            "response": response}


# ---- ledger and budget

def test_ledger_is_a_rolling_24_hour_window(tmp_path):
    now = [1_000_000.0]
    led = UsageLedger(tmp_path / "u.json", clock=lambda: now[0])
    led.record("m", "evaluation", 300)
    now[0] += 12 * 3600
    led.record("m", "generation", 400)
    led.record("m", "generation", 100)
    led.record("other", "generation", 50)
    assert led.used("m", "generation") == {"requests": 2, "tokens": 500}
    assert led.used("m") == {"requests": 3, "tokens": 800}
    now[0] += 12 * 3600 + 1                     # the first call is now more than 24 hours old
    assert led.used("m") == {"requests": 2, "tokens": 500}
    now[0] += 12 * 3600
    assert led.used("m") == {"requests": 0, "tokens": 0}
    led.record("m", "evaluation", 1)            # recording drops expired events from the file
    assert len(json.loads((tmp_path / "u.json").read_text())["events"]) == 1


def test_budget_fraction_and_global_cap(tmp_path):
    led = UsageLedger(tmp_path / "u.json", clock=lambda: 1_000_000.0)
    limits = {"m": {"requests": 10, "tokens": 1000}}
    b = x.Budget(led, fraction=0.7, global_cap=0.95, limits=limits)
    assert b.allows("m", 100)
    for _ in range(6):
        led.record("m", "generation", 100)
    assert b.allows("m", 100) and not b.allows("m", 101)        # 600 + 100 = 700 = 70% of tokens
    led.record("m", "generation", 100)
    assert not b.allows("m", 1)                                 # 7 requests = 70% of 10
    led2 = UsageLedger(tmp_path / "u2.json", clock=lambda: 1_000_000.0)
    for _ in range(9):
        led2.record("m", "evaluation", 100)                     # other tools used 900 of 1000
    b2 = x.Budget(led2, fraction=0.7, global_cap=0.95, limits=limits)
    assert not b2.allows("m", 100)                              # 900 + 100 > 950 even though generation used 0
    assert b2.left("m") == {"requests": 0.5, "tokens": 50.0}


def test_pace_keeps_under_the_per_minute_token_limit():
    assert x.pace_for(100) == x.MIN_INTERVAL
    assert x.pace_for(430) == pytest.approx(60 * 430 / 7200)


# ---- cleaning and sampling

def test_clean_pool_follows_the_notebook():
    rows = [src(i, "closed_qa", response="word " * 5) for i in range(40)]
    rows.append(src(40, "closed_qa", response="word " * 5000))                     # length outlier
    rows.append(src(41, "closed_qa", instruction="Question number 1 about topic 1?"))   # duplicate after normalize
    rows.append(src(42, "closed_qa", instruction="mail me at a.b@example.com"))
    rows.append(src(43, "brainstorming"))                                           # not one of our categories
    rows.append(src(44, "closed_qa", response=""))
    rows.append(src(0, "coding", instruction="sort a list", response="x.sort()", dataset="codealpaca"))  # trivial
    rows.append(src(1, "coding", instruction="sort a list in place", response="use sorted(x) here",
                    dataset="codealpaca"))
    pool = x.clean_pool(rows)
    ids = {r["source_id"] for r in pool}
    assert "dolly-40" not in ids and "dolly-41" not in ids and "dolly-43" not in ids and "dolly-44" not in ids
    assert "codealpaca-0" not in ids and "codealpaca-1" in ids
    assert next(r for r in pool if r["source_id"] == "dolly-42")["instruction"] == "mail me at [EMAIL]"
    buckets = Counter(r["complexity_bucket"] for r in pool if r["category"] == "closed_qa")
    assert set(buckets) == {"short", "medium", "long"} and max(buckets.values()) - min(buckets.values()) <= 1


def test_check_source_ids_catches_renumbered_sources():
    sources = [src(i) for i in range(200)]
    v11 = [{"source_id": f"dolly-{i}", "original_instruction": f"question number {i} about topic {i}?"}
           for i in range(200)]
    x.check_source_ids(sources, v11)
    shifted = [dict(r, source_id=f"dolly-{i + 1}") for i, r in enumerate(sources)]
    with pytest.raises(SystemExit, match="do not match"):
        x.check_source_ids(shifted, v11)


def test_plan_and_sample_use_only_unused_rows_and_stay_frozen():
    pool = x.clean_pool([src(i, c) for c in CATS for i in range(CATS.index(c) * 1000, CATS.index(c) * 1000 + 300)])
    v1_sampled = [{"source_id": r["source_id"], "category": r["category"]} for r in pool[::3]]
    v11 = [{"source_id": r["source_id"], "category": r["category"]} for r in v1_sampled[::2]]   # 50% pass rate
    plans = x.plan_categories(pool, v11, v1_sampled, target=100)
    p = plans["closed_qa"]
    assert p.v11_rows == 50 and p.pass_rate == pytest.approx(0.5) and p.needed == 50
    assert p.to_sample == 105 and p.unused == 200                  # 50 / 0.5 * 1.05
    used = {r["source_id"] for r in v1_sampled}
    sample = x.sample_rows(pool, plans, used)
    assert not {r["source_id"] for r in sample} & used
    assert Counter(r["category"] for r in sample)["closed_qa"] == 105
    again = x.sample_rows(pool, plans, used, frozen=sample[:10])
    assert again[:10] == sample[:10] and len(again) == len(sample)
    assert x.sample_rows(pool, plans, used) == sample              # deterministic


def test_round_robin_interleaves_categories():
    rows = [src(i, c) for c in ("coding", "closed_qa") for i in range(3)]
    assert [r["category"] for r in x.round_robin(rows)] == ["closed_qa", "coding"] * 3


# ---- generation

class FakeLLM:
    """Replies in order; a reply that is an exception is raised. A reply may be a callable taking the messages."""
    def __init__(self, replies, ledger=None):
        self.replies, self.calls, self.min_interval, self.ledger = list(replies), [], 2.2, ledger

    def complete(self, model, messages, **kw):
        self.calls.append((model, messages, kw))
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        if callable(r):
            r = r(messages)
        if self.ledger:
            self.ledger.record(model, "generation", 400)
        return SimpleNamespace(content=r, model=model, input_tokens=300, output_tokens=100, cached_tokens=0,
                               total_tokens=400, reasoning_tokens=60, finish_reason="stop")


def ids_in(messages):
    return re.findall(r"^ITEM ID: (\S+)$", messages[1]["content"], re.M)


def reply_all(messages, skip=(), reverse=False):
    """A well-formed reply for every item in the request (except positions in `skip`, 1-based), echoing each id."""
    ids = [sid for i, sid in enumerate(ids_in(messages), start=1) if i not in skip]
    items = [{"id": sid, "degraded_prompt": f"deg {sid}", "optimized_prompt": f"opt {sid}"} for sid in ids]
    return json.dumps({"items": items[::-1] if reverse else items})


def budget_for(led, **kw):
    limits = {m: {"requests": 100, "tokens": 10**6} for m in x.GROQ_MODELS}
    return x.Budget(led, fraction=1.0, global_cap=1.0, limits=limits, cerebras_fraction=kw.get("cerebras", 1.0),
                    cerebras_limits={"cerebras/gpt-oss-120b": {"requests": kw.get("c_req", 100), "tokens": 10**6}})


def test_messages_number_the_items_carry_the_data_rule_and_truncate_context():
    msgs = x.build_messages([src(1, context="c" * 5000), src(2)])
    assert "copied verbatim" in msgs[0]["content"] and "Items: a, b, c" in msgs[0]["content"]
    assert '"items"' in msgs[0]["content"]
    user = msgs[1]["content"]
    assert ids_in(msgs) == ["dolly-1", "dolly-2"] and "No text/input." in user
    assert "copied exactly" in msgs[0]["content"]
    assert user.count("c" * 1000) == 1 and "c" * 1001 not in user


def test_system_prompt_keeps_every_rule():
    p = x.SYSTEM_PROMPT
    for rule in ("Same task and intent", "never add information", "Remove any output format and constraints",
                 "realistic, not absurdly broken", "not longer than the clean instruction",
                 "Do not copy the separate TEXT/INPUT", "add no facts, answers or content from the text",
                 "explicit output format", '"the provided text" or "the given input"', "copied verbatim",
                 "No filler", "under 60 words", "answer only from the provided text", "output structure",
                 "list the allowed labels", "a length (sentences or bullet points)", "name the language",
                 "single code block", "restate the full question or request", 'end with "Items: "'):
        assert rule in p, rule


def test_parse_items_matches_by_source_id_only():
    ids = ["dolly-1", "dolly-2", "dolly-3", "dolly-4"]
    got = x.parse_items('<think>hm</think>{"items": ['
                        '{"id": "dolly-2", "degraded_prompt": "d2", "optimized_prompt": "o2"},'
                        '{"id": "dolly-1", "degraded_prompt": "d1", "optimized_prompt": "o1"},'
                        '{"id": "dolly-99", "degraded_prompt": "d9", "optimized_prompt": "o9"},'
                        '{"id": "2", "degraded_prompt": "dx", "optimized_prompt": "ox"},'
                        '{"id": "dolly-3", "degraded_prompt": "", "optimized_prompt": "o3"},'
                        '{"id": "dolly-4", "degraded_prompt": "a", "optimized_prompt": "b"},'
                        '{"id": "dolly-4", "degraded_prompt": "c", "optimized_prompt": "d"}]}', ids)
    # order in the reply does not matter; unknown ids, positions, empty and duplicated ids are dropped
    assert got == {"dolly-1": ("d1", "o1"), "dolly-2": ("d2", "o2")}
    assert x.parse_items('{"id": "dolly-1", "degraded_prompt": "d", "optimized_prompt": "o"}', ["dolly-1"]) == \
        {"dolly-1": ("d", "o")}
    for bad in ("no json", '{"items": []}', '{"items": [{"id": "1", "degraded_prompt": "d", "optimized_prompt": "o"}]}'):
        with pytest.raises(ValueError):
            x.parse_items(bad, ids)


def test_a_reply_in_another_order_is_not_swapped(tmp_path):
    led = UsageLedger(tmp_path / "u.json", clock=lambda: 1_000_000.0)
    ckpt = x.Checkpoint(tmp_path / "ck.jsonl")
    x.generate([src(i) for i in range(5)], ckpt, FakeLLM([lambda m: reply_all(m, reverse=True)], led),
               budget_for(led), log=lambda s: None, batch_size=5)
    assert all(r["optimized_prompt"] == f"opt {sid}" and r["matched_by"] == "source_id" and r["prompt_rev"] == x.PROMPT_REV
               for sid, r in ckpt.done.items())


def test_router_sends_cerebras_models_to_cerebras():
    groq, cer = FakeLLM(["g"]), FakeLLM(["c"])
    r = x.Router(groq, cer)
    r.complete("cerebras/gpt-oss-120b", [], max_tokens=5)
    r.complete("openai/gpt-oss-20b", [], max_tokens=5)
    assert cer.calls[0][0] == "gpt-oss-120b" and groq.calls[0][0] == "openai/gpt-oss-20b"
    from app.evaluation.llm import ModelUnavailable
    with pytest.raises(ModelUnavailable):
        x.Router(groq, None).complete("cerebras/gpt-oss-120b", [], max_tokens=5)
    assert x.reasoning_for("cerebras/gpt-oss-120b") == "low" and x.reasoning_for("qwen/qwen3.8-27b") == "none"


def test_generate_batches_checkpoints_rotates_and_resumes(tmp_path):
    led = UsageLedger(tmp_path / "u.json", clock=lambda: 1_000_000.0)
    budget = budget_for(led)
    sample = [src(i, "closed_qa") for i in range(6)] + [src(i, "coding", dataset="codealpaca") for i in range(6)]
    ckpt = x.Checkpoint(tmp_path / "ck.jsonl")
    llm = FakeLLM([reply_all, DailyLimitReached("day"), lambda m: reply_all(m, skip={2}), "not json"], led)
    stats = x.generate(sample, ckpt, llm, budget, max_calls=4, log=lambda s: None, batch_size=5)
    assert [c[0] for c in llm.calls] == ["cerebras/gpt-oss-120b", "cerebras/gpt-oss-120b",
                                         "openai/gpt-oss-120b", "openai/gpt-oss-120b"]
    assert [len(ids_in(c[1])) for c in llm.calls] == [5, 5, 5, 3]      # 2 left + 1 retried
    assert stats["generated"] == 9 and stats["parse_failures"] == 1 and stats["stopped"].startswith("--max-calls")
    assert llm.calls[0][2]["max_tokens"] == x.max_tokens_for(5) and llm.calls[0][2]["json_mode"]
    rec = next(iter(ckpt.done.values()))
    assert rec["model"] == "cerebras/gpt-oss-120b" and rec["batch"] == 5 and rec["tokens"] == 80   # 400 / 5 rows

    resumed = x.Checkpoint(tmp_path / "ck.jsonl")
    assert len(resumed.done) == 9
    llm2 = FakeLLM([reply_all], led)
    stats2 = x.generate(sample, resumed, llm2, budget, log=lambda s: None, batch_size=5)
    assert stats2["generated"] == 3 and stats2["stopped"] == "" and len(resumed.done) == 12


def test_rows_a_reply_leaves_out_are_retried_then_skipped(tmp_path):
    led = UsageLedger(tmp_path / "u.json", clock=lambda: 1_000_000.0)
    ckpt = x.Checkpoint(tmp_path / "ck.jsonl")
    always_skip_first = lambda m: reply_all(m, skip={1})              # noqa: E731
    llm = FakeLLM([always_skip_first] * 3 + [reply_all] * 3, led)
    stats = x.generate([src(i) for i in range(3)], ckpt, llm, budget_for(led), log=lambda s: None, batch_size=3)
    assert "dolly-0" not in ckpt.done and {"dolly-1", "dolly-2"} <= set(ckpt.done)
    assert stats["calls"] == 3                                       # dolly-0 tried 3 times, then left for next run


def test_groq_json_failures_count_as_parse_failures(tmp_path):
    from app.evaluation.llm import JSONGenerationFailed

    led = UsageLedger(tmp_path / "u.json", clock=lambda: 1_000_000.0)
    ckpt = x.Checkpoint(tmp_path / "ck.jsonl")
    bad = JSONGenerationFailed("json_validate_failed")
    llm = FakeLLM([bad, reply_all], led)
    stats = x.generate([src(1), src(2)], ckpt, llm, budget_for(led), log=lambda s: None, batch_size=2)
    assert stats["parse_failures"] == 1 and stats["generated"] == 2


def test_usage_breakdown_is_logged_for_the_first_calls(tmp_path):
    import csv

    led = UsageLedger(tmp_path / "u.json", clock=lambda: 1_000_000.0)
    path = tmp_path / "usage.csv"
    x.generate([src(i, context="c" * 3000) for i in range(4)], x.Checkpoint(tmp_path / "ck.jsonl"),
               FakeLLM([reply_all] * 2, led), budget_for(led), log=lambda s: None, usage_log=1, usage_path=path,
               batch_size=2)
    rows = list(csv.DictReader(open(path)))
    assert len(rows) == 1
    r = rows[0]
    assert (r["items"], r["prompt_tokens"], r["cached_tokens"], r["completion_tokens"], r["reasoning_tokens"]) == \
        ("2", "300", "0", "100", "60")
    assert r["context_chars_sent"] == "2000" and r["rows_returned"] == "2" and r["reasoning_effort"] == "low"
    assert int(r["system_prompt_chars"]) == len(x.SYSTEM_PROMPT)


def test_ledger_keeps_cached_tokens_separately(tmp_path, monkeypatch):
    from app import groq_budget

    led = UsageLedger(tmp_path / "u.json", clock=lambda: 1_000_000.0)
    led.record("m", "generation", 1000, cached=400)
    assert led.used("m")["tokens"] == 1000                           # conservative default: cached counts
    monkeypatch.setattr(groq_budget, "COUNT_CACHED", False)
    assert led.used("m")["tokens"] == 600


def test_generate_stops_at_the_budget(tmp_path):
    led = UsageLedger(tmp_path / "u.json", clock=lambda: 1_000_000.0)
    budget = x.Budget(led, fraction=0.5, limits={m: {"requests": 4, "tokens": 10**6} for m in x.GROQ_MODELS},
                      cerebras_fraction=0.5, cerebras_limits={"cerebras/gpt-oss-120b": {"requests": 2,
                                                                                        "tokens": 10**6}})
    stats = x.generate([src(i) for i in range(20)], x.Checkpoint(tmp_path / "ck.jsonl"),
                       FakeLLM([reply_all] * 20, led), budget, log=lambda s: None, batch_size=1)
    assert stats["by_model"]["cerebras/gpt-oss-120b"] == 1 and stats["generated"] == 7    # 1 + 2 per Groq model
    assert stats["stopped"] == "budget reached for every model"


def test_generation_version():
    assert x.generation_version({"batch": 5}) == "v1.2-batch5"
    assert x.generation_version({}) == "v1.2-single" and x.generation_version({"batch": 1}) == "v1.2-single"


def test_tokens_per_row_switches_to_measured(tmp_path):
    ckpt = x.Checkpoint(tmp_path / "ck.jsonl")
    for i in range(x.MEASURE_AFTER - 1):
        ckpt.add({"source_id": f"s{i}", "tokens": 300, "batch": 5})
    ckpt.add({"source_id": "single", "tokens": 1000})                 # batch 1: not counted for batch 5
    assert ckpt.tokens_per_row(5) == x.DEFAULT_TOKENS_PER_CALL / 2
    ckpt.add({"source_id": "last", "tokens": 300, "batch": 5})
    assert ckpt.tokens_per_row(5) == 300


# ---- quality checks, splits, build

def gen_row(i, cat="classification", instruction=None, degraded="which is fruit", optimized=None, split=None, **kw):
    r = dict(src(i, cat, instruction or "Classify each as fruit or vegetable: apple, carrot"), has_context=False,
             has_format_spec=False, instruction_word_count=9, context_word_count=0, response_word_count=3,
             complexity_bucket=kw.get("bucket", "short"), degraded_prompt=degraded,
             optimized_prompt=optimized or 'Label each item "fruit" or "vegetable".', model="openai/gpt-oss-120b",
             sim_degraded_vs_original=0.8, sim_optimized_vs_original=0.7)
    r["flags"] = x.quality_flags(r, 0.8, 0.7)
    r["auto_pass"] = not any(r["flags"].values())
    return r


def test_quality_flags():
    ok = gen_row(1)
    assert not any(ok["flags"].values())
    assert x.quality_flags(ok, 0.3, 0.7)["degraded_drifted"]
    assert x.quality_flags(dict(ok, degraded_prompt="answer as a bulleted list"), 0.8, 0.7)["degraded_keeps_format_spec"]
    assert x.quality_flags(dict(ok, category="coding", optimized_prompt="Say hello."), 0.8, 0.7)["coding_target_not_code"]
    # items kept by the data rule do not count toward "degraded longer than original"
    long_items = ", ".join(f"item{i}" for i in range(30))
    r = dict(ok, instruction=f"Classify as fruit or not: {long_items}", instruction_word_count=36,
             degraded_prompt=f"fruit or not? {long_items}")
    assert not x.quality_flags(r, 0.8, 0.7)["degraded_longer_than_original"]


def old_row(i, cat, split, instruction=None):
    return {"id": f"PO-{x.ABBREV[cat]}-{i:04d}", "source_id": f"old-{cat}-{i}", "category": cat, "split": split,
            "original_instruction": instruction or f"old instruction {cat} {i}"}


def test_assign_splits_fills_short_held_out_and_guards_leakage():
    old = [old_row(i, "classification", "val") for i in range(1, 30)]                 # val short by one
    old += [old_row(100, "classification", "test", "Shared test instruction")]
    old += [old_row(101, "classification", "train", "Old train instruction")]
    new = [dict(x.to_dataset_row(gen_row(i)), original_instruction=f"new {i}") for i in range(200, 260)]
    new[0]["original_instruction"] = "Shared test instruction"                      # repeats a held-out one
    new[1]["original_instruction"] = "Old train instruction"                        # repeats a v1.1 train one
    before = [dict(r) for r in old]
    x.assign_splits(old, new)
    assert old == before                                                             # v1.1 never changes
    assert new[0]["split"] == "test" and new[1]["split"] == "train"
    split = Counter(r["split"] for r in new)
    assert split["val"] == 1 and split["benchmark"] == 10 and split["test"] == 39    # 38 filled + the leak copy
    x.assign_ids(old, new)
    ids = [r["id"] for r in new]
    assert len(set(ids)) == len(ids) and min(ids) == "PO-CLS-0102"


def test_build_repairs_new_rows_and_keeps_v11(tmp_path):
    v11 = [dict(old_row(i, c, "train"), degraded_prompt="d", optimized_prompt="o", context="",
                reference_response="r", model="m") for c in CATS for i in range(1, 3)]
    items = gen_row(1, optimized='Label each item "fruit" or "vegetable".')         # dropped the items
    failed = gen_row(2)
    failed["auto_pass"], failed["flags"]["degraded_drifted"] = False, True
    dup = gen_row(3)
    dup["source_id"] = v11[0]["source_id"]                                            # already in v1.1
    res = x.build(v11, [items, failed, dup])
    assert [r["id"] for r in res.rows[:len(v11)]] == [r["id"] for r in v11]
    (new,) = res.new_rows
    assert new["optimized_prompt"].endswith("Items: apple, carrot") and new["id"].startswith("PO-CLS-")
    assert new["generation_version"] == "v1.2-single"
    assert {r["generation_version"] for r in res.rows[:len(v11)]} == {"v1"}
    assert res.counts[("classification", "generated")] == 2 and res.counts[("classification", "auto_pass")] == 1
    assert res.counts[("classification", "added")] == 1
    assert res.repair_log and res.repair_log[0]["id"] == new["id"]

    qa = gen_row(9, "closed_qa", instruction="Who directed Lost in Translation?", degraded="who directed it",
                 optimized="Name the director of Lost in Translation from the provided text. Items: Lost in Translation")
    res2 = x.build(v11, [qa])
    assert res2.new_rows[0]["optimized_prompt"] == "Name the director of Lost in Translation from the provided text."
    assert res2.counts[("closed_qa", "items_line_removed")] == 1
    assert res2.repair_log[0]["action"] == "items_line_removed" and res2.repair_log[0]["id"].startswith("PO-CQA-")

    x.write(res, tmp_path)
    import csv
    with open(tmp_path / x.V12_CSV_NAME, newline="") as f:
        written = list(csv.DictReader(f))
    assert list(written[0])[:3] == ["id", "split", "category"] and len(written) == len(res.rows)
    assert written[-1]["optimized_prompt"] == new["optimized_prompt"]
    assert "Dataset v1.2 build" in (tmp_path / "build_report.md").read_text()
