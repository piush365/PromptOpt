from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import repository as repo
from app.db.models import (OptimizationResult, Prompt, PromptFeatures, Rendering, TokenUsage, Transformation,
                           utcnow)

FEATURES = {"task_type": "summarization", "has_format_spec": False, "has_context": True,
            "missing_constraints": ["length", "format"], "redundant_phrases": ["could you please"],
            "ambiguous_refs": [], "confidence": 0.82}
IR = {"task": "summarization", "context": "the provided text", "constraints": {"length": "3 sentences"},
      "requirements": ["cover the main argument"], "output_format": "paragraph"}


def run_pipeline(db, text="could you please summarize this article for me", **kw):
    p = repo.create_prompt(db, text, **kw)
    repo.save_features(db, p.id, FEATURES)
    r = repo.save_optimization(db, p.id, "Summarize the provided text in 3 sentences.", IR, 0.82, [
        {"rule_code": "B01_REMOVE_FILLER", "before": text, "after": "summarize this article"},
        {"rule_code": "B04_ADD_LENGTH", "before": "summarize this article",
         "after": "Summarize the provided text in 3 sentences."},
    ], latency_ms=35)
    repo.save_renderings(db, r.id, {"gpt": "Task: summarize...", "claude": "<task>summarize</task>"})
    repo.save_token_usage(db, r.id, "gpt", "tiktoken:o200k_base", 10, 12, 180, 70)
    db.commit()
    return p, r


def test_full_flow_and_history(db):
    p, r = run_pipeline(db)
    h = repo.get_prompt_history(db, p.id)
    assert h["features"]["task_type"] == "summarization"
    assert h["features"]["missing_constraints"] == ["length", "format"]
    res = h["results"][0]
    assert [s["rule"] for s in res["steps"]] == ["B01_REMOVE_FILLER", "B04_ADD_LENGTH"]
    assert res["ir"]["constraints"]["length"] == "3 sentences"
    assert set(res["renderings"]) == {"gpt", "claude"}
    assert res["token_usage"][0]["net_change"] == (12 + 70) - (10 + 180)   # -108: net saving
    assert res["used_lora"] is False
    assert repo.get_prompt_history(db, 999999) is None


def test_pii_is_scrubbed_before_storage(db):
    p = repo.create_prompt(db, "mail rahul.k@example.com or call 98765 43210 / 555-123-4567 about the report")
    db.commit()
    stored = db.scalar(select(Prompt.original_text).where(Prompt.id == p.id))
    assert "example.com" not in stored and "98765" not in stored and "555-123" not in stored
    assert stored.count("[EMAIL]") == 1 and stored.count("[PHONE]") == 2
    assert p.pii_redactions == 3


def test_retention_purge_cascades(db):
    now = utcnow()
    old, _ = run_pipeline(db, retention_days=30, now=now - timedelta(days=31))
    fresh, _ = run_pipeline(db, text="summarize this, thanks", retention_days=30, now=now)
    assert repo.purge_expired(db, now=now) == 1
    assert db.get(Prompt, old.id) is None and db.get(Prompt, fresh.id) is not None
    # exactly one prompt's worth of derived rows is left in every child table
    for model, expected in [(PromptFeatures, 1), (OptimizationResult, 1), (Transformation, 2),
                            (Rendering, 2), (TokenUsage, 1)]:
        assert db.scalar(select(func.count()).select_from(model)) == expected, model.__tablename__


def test_lora_step_without_rule(db):
    p = repo.create_prompt(db, "what does this mean")
    lora = repo.register_lora_model(db, "stage-c-v1", "Qwen/Qwen2.5-0.5B-Instruct", 8, dataset_version="v1")
    r = repo.save_optimization(db, p.id, "Explain the meaning of the provided sentence.", IR, 0.55,
                               [{"stage": "C", "before": "what does this mean",
                                 "after": "Explain the meaning of the provided sentence.", "note": "resolved 'this'"}],
                               lora_model_id=lora.id)
    db.commit()
    assert r.used_lora and r.transformations[0].rule_id is None


@pytest.mark.parametrize("call", [
    lambda db: repo.create_prompt(db, "   "),
    lambda db: repo.save_features(db, repo.create_prompt(db, "x").id, {**FEATURES, "task_type": "poetry"}),
    lambda db: repo.save_features(db, repo.create_prompt(db, "x").id, {**FEATURES, "confidence": 1.4}),
    lambda db: repo.save_optimization(db, repo.create_prompt(db, "x").id, "y", IR, 0.5,
                                      [{"rule_code": "B99_NOPE", "before": "a", "after": "b"}]),
    lambda db: repo.save_optimization(db, repo.create_prompt(db, "x").id, "y", IR, 0.5,
                                      [{"before": "a", "after": "b"}]),
])
def test_validation_errors(db, call):
    with pytest.raises(repo.DataValidationError):
        call(db)


def test_database_constraints_hold(db):
    p, r = run_pipeline(db)
    # one rendering per target LLM
    db.add(Rendering(result_id=r.id, target_llm="gpt", rendered_text="dup"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    # category check constraint is enforced by the database itself, not only by Python
    p2 = repo.create_prompt(db, "x")
    db.add(PromptFeatures(prompt_id=p2.id, task_type="poetry", has_format_spec=False, has_context=False,
                          missing_constraints=[], redundant_phrases=[], ambiguous_refs=[], confidence=0.5))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_evaluation_summary(db):
    for item, variant, tin, tout, q in [("PO-CLS-0001", "original", 20, 150, 6.0),
                                         ("PO-CLS-0001", "optimized", 35, 60, 8.0),
                                         ("PO-CLS-0002", "original", 18, 170, 5.0),
                                         ("PO-CLS-0002", "optimized", 30, 50, 9.0)]:
        repo.record_evaluation(db, "baseline", "v1", item, "classification", variant, "gpt", tin, tout, 900, q)
    db.commit()
    rows = {r["variant"]: r for r in repo.evaluation_summary(db, "baseline")}
    assert rows["original"]["n"] == 2 and float(rows["optimized"]["avg_total_tokens"]) == 87.5
    assert float(rows["optimized"]["avg_quality"]) == 8.5
    # the same item/variant/LLM cannot be recorded twice in one run
    with pytest.raises(IntegrityError):
        repo.record_evaluation(db, "baseline", "v1", "PO-CLS-0001", "classification", "original", "gpt", 1)
    db.rollback()
