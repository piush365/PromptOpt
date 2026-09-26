"""Dataset v1.2 expansion: cleaning, sampling, budgeted/resumable generation, quality checks, frozen splits."""
import json
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

def test_ledger_tracks_per_day_model_and_tag(tmp_path):
    day = ["2026-09-26"]
    led = UsageLedger(tmp_path / "u.json", clock=lambda: day[0])
    led.record("m", "evaluation", 300)
    led.record("m", "generation", 400)
    led.record("m", "generation", 100)
    assert led.used("m", "generation") == {"requests": 2, "tokens": 500}
    assert led.used("m") == {"requests": 3, "tokens": 800}
    day[0] = "2026-09-27"
    assert led.used("m") == {"requests": 0, "tokens": 0}


def test_budget_fraction_and_global_cap(tmp_path):
    led = UsageLedger(tmp_path / "u.json", clock=lambda: "d")
    limits = {"m": {"requests": 10, "tokens": 1000}}
    b = x.Budget(led, fraction=0.7, global_cap=0.95, limits=limits)
    assert b.allows("m", 100)
    for _ in range(6):
        led.record("m", "generation", 100)
    assert b.allows("m", 100) and not b.allows("m", 101)        # 600 + 100 = 700 = 70% of tokens
    led.record("m", "generation", 100)
    assert not b.allows("m", 1)                                 # 7 requests = 70% of 10
    led2 = UsageLedger(tmp_path / "u2.json", clock=lambda: "d")
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
    """Replies in order; a reply that is an exception is raised."""
    def __init__(self, replies, ledger=None):
        self.replies, self.calls, self.min_interval, self.ledger = list(replies), [], 2.2, ledger

    def complete(self, model, messages, **kw):
        self.calls.append((model, messages, kw))
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        if self.ledger:
            self.ledger.record(model, "generation", 400)
        return SimpleNamespace(content=r, model=model, input_tokens=300, output_tokens=100, cached_tokens=200,
                               rate_limited_tokens=200)


def pair(d="deg", o="opt"):
    return json.dumps({"degraded_prompt": d, "optimized_prompt": o})


def test_messages_carry_the_data_rule_and_truncate_context():
    msgs = x.build_messages(src(1, context="c" * 5000))
    assert "copied verbatim" in msgs[0]["content"] and "Items: a, b, c" in msgs[0]["content"]
    assert msgs[1]["content"].count("c" * 1000) == 1 and "c" * 1001 not in msgs[1]["content"]
    assert "no accompanying" in x.build_messages(src(1))[1]["content"]


def test_parse_pair():
    assert x.parse_pair('<think>hmm</think>{"degraded_prompt": "d", "optimized_prompt": "o"}') == ("d", "o")
    with pytest.raises(ValueError):
        x.parse_pair('{"degraded_prompt": "d"}')
    with pytest.raises(ValueError):
        x.parse_pair("no json")


def test_generate_checkpoints_rotates_models_and_resumes(tmp_path):
    led = UsageLedger(tmp_path / "u.json", clock=lambda: "d")
    budget = x.Budget(led, fraction=1.0, global_cap=1.0,
                      limits={m: {"requests": 100, "tokens": 10**6} for m in x.GROQ_MODELS})
    sample = [src(i, "closed_qa") for i in range(3)] + [src(i, "coding", dataset="codealpaca") for i in range(3)]
    ckpt = x.Checkpoint(tmp_path / "ck.jsonl")
    llm = FakeLLM([pair(), "not json", pair(), DailyLimitReached("per day"), pair(), pair()], led)
    stats = x.generate(sample, ckpt, llm, budget, max_calls=6, log=lambda s: None)
    assert stats["generated"] == 4 and stats["parse_failures"] == 1 and stats["calls"] == 6
    assert stats["stopped"].startswith("--max-calls")
    assert [c[0] for c in llm.calls] == [x.GROQ_MODELS[0]] * 4 + [x.GROQ_MODELS[1]] * 2
    assert llm.calls[0][2]["reasoning_effort"] == "low" and llm.calls[0][2]["json_mode"]

    resumed = x.Checkpoint(tmp_path / "ck.jsonl")                  # a new run reads the checkpoint
    assert len(resumed.done) == 4
    llm2 = FakeLLM([pair(), pair()], led)
    stats2 = x.generate(sample, resumed, llm2, budget, log=lambda s: None)
    assert stats2["generated"] == 2 and stats2["stopped"] == "" and len(resumed.done) == 6
    assert x.generate(sample, resumed, FakeLLM([]), budget, log=lambda s: None)["calls"] == 0


def test_generate_stops_at_the_budget(tmp_path):
    led = UsageLedger(tmp_path / "u.json", clock=lambda: "d")
    budget = x.Budget(led, fraction=0.5, limits={m: {"requests": 4, "tokens": 10**6} for m in x.GROQ_MODELS})
    sample = [src(i) for i in range(20)]
    stats = x.generate(sample, x.Checkpoint(tmp_path / "ck.jsonl"), FakeLLM([pair()] * 20, led), budget,
                       log=lambda s: None)
    assert stats["generated"] == 6 and stats["stopped"] == "daily budget reached for every model"   # 2 per model


def test_tokens_per_call_switches_to_measured(tmp_path):
    ckpt = x.Checkpoint(tmp_path / "ck.jsonl")
    ckpt.add({"source_id": "old", "tokens": 5000})                  # no cache info: ignored
    for i in range(x.MEASURE_AFTER - 1):
        ckpt.add({"source_id": f"s{i}", "tokens": 900, "rate_limited_tokens": 400})
    assert ckpt.tokens_per_call() == x.DEFAULT_TOKENS_PER_CALL
    ckpt.add({"source_id": "last", "tokens": 900, "rate_limited_tokens": 400})
    assert ckpt.tokens_per_call() == 400


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
    assert res.counts[("classification", "generated")] == 2 and res.counts[("classification", "auto_pass")] == 1
    assert res.counts[("classification", "added")] == 1
    assert res.repair_log and res.repair_log[0]["id"] == new["id"]

    x.write(res, tmp_path)
    import csv
    with open(tmp_path / x.V12_CSV_NAME, newline="") as f:
        written = list(csv.DictReader(f))
    assert list(written[0])[:3] == ["id", "split", "category"] and len(written) == len(res.rows)
    assert written[-1]["optimized_prompt"] == new["optimized_prompt"]
    assert "Dataset v1.2 build" in (tmp_path / "build_report.md").read_text()
