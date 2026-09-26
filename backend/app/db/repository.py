"""Data entry module: the only place the pipeline writes to or reads from the database.

Typical flow for one request:
    prompt  = create_prompt(db, raw_text)                                 # PII stripped, expiry set
    save_features(db, prompt.id, {...})                                   # Stage A
    result  = save_optimization(db, prompt.id, optimized_text, ir, confidence, steps)   # Stage B/C
    save_renderings(db, result.id, {"gpt": "...", "claude": "..."})
    save_token_usage(db, result.id, "gpt", "tiktoken:o200k_base", 12, 30)
    db.commit()

Functions flush (so ids are available) but do not commit; the caller commits once per request,
so a failure half-way leaves nothing behind.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.config import RETENTION_DAYS, TASK_CATEGORIES
from app.db.models import (
    EvaluationRun, LoRAModel, OptimizationResult, Prompt, PromptFeatures, Rendering, Rule, TokenUsage, Transformation,
    utcnow,
)
from app.db.pii import scrub_pii


class DataValidationError(ValueError):
    pass


def _check_confidence(value: float) -> float:
    if not 0.0 <= float(value) <= 1.0:
        raise DataValidationError(f"confidence must be between 0 and 1, got {value}")
    return float(value)


def _check_category(value: str) -> str:
    if value not in TASK_CATEGORIES:
        raise DataValidationError(f"unknown task category {value!r}; expected one of {TASK_CATEGORIES}")
    return value


# ---------------------------------------------------------------- prompts
def create_prompt(db: Session, raw_text: str, user_id: Optional[int] = None,
                  retention_days: int = RETENTION_DAYS, now: Optional[datetime] = None) -> Prompt:
    if not raw_text or not raw_text.strip():
        raise DataValidationError("prompt text is empty")
    if retention_days < 1:
        raise DataValidationError("retention_days must be at least 1")
    now = now or utcnow()
    text, redactions = scrub_pii(raw_text.strip())
    prompt = Prompt(user_id=user_id, original_text=text, pii_redactions=redactions,
                    created_at=now, expires_at=now + timedelta(days=retention_days))
    db.add(prompt)
    db.flush()
    return prompt


def save_features(db: Session, prompt_id: int, features: dict[str, Any]) -> PromptFeatures:
    """`features` is Stage A's output, e.g. PromptFeatures(...).model_dump() from the Pydantic model."""
    row = PromptFeatures(
        prompt_id=prompt_id,
        task_type=_check_category(features["task_type"]),
        has_format_spec=bool(features["has_format_spec"]),
        has_context=bool(features.get("has_context", False)),
        missing_constraints=list(features.get("missing_constraints", [])),
        redundant_phrases=list(features.get("redundant_phrases", [])),
        ambiguous_refs=list(features.get("ambiguous_refs", [])),
        confidence=_check_confidence(features["confidence"]),
    )
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------- optimization
def save_optimization(db: Session, prompt_id: int, optimized_text: str, ir: dict[str, Any], confidence: float,
                      steps: list[dict[str, Any]], lora_model_id: Optional[int] = None,
                      latency_ms: Optional[int] = None, pipeline_version: str = "0.1.0") -> OptimizationResult:
    """`steps` is the ordered list of applied changes:
        {"rule_code": "B03_ADD_OUTPUT_FORMAT", "before": "...", "after": "..."}   # Stage B
        {"stage": "C", "before": "...", "after": "...", "note": "resolved 'this'"}  # Stage C (LoRA), no rule
    """
    codes = {s["rule_code"] for s in steps if s.get("rule_code")}
    rule_ids = dict(db.execute(select(Rule.code, Rule.id).where(Rule.code.in_(codes))).all()) if codes else {}
    unknown = codes - rule_ids.keys()
    if unknown:
        raise DataValidationError(f"unknown rule codes: {sorted(unknown)} (run app.init_db to seed rules)")

    used_lora = any(s.get("stage") == "C" for s in steps)
    result = OptimizationResult(prompt_id=prompt_id, ir=ir, optimized_text=optimized_text,
                                confidence=_check_confidence(confidence), used_lora=used_lora,
                                lora_model_id=lora_model_id, latency_ms=latency_ms,
                                pipeline_version=pipeline_version)
    for i, s in enumerate(steps, start=1):
        stage = s.get("stage", "B")
        if stage == "B" and not s.get("rule_code"):
            raise DataValidationError(f"step {i}: a Stage B step needs a rule_code")
        result.transformations.append(Transformation(
            step_no=i, stage=stage, rule_id=rule_ids.get(s.get("rule_code")),
            before_text=s["before"], after_text=s["after"], note=s.get("note")))
    db.add(result)
    db.flush()
    return result


def save_renderings(db: Session, result_id: int, rendered: dict[str, str]) -> list[Rendering]:
    rows = [Rendering(result_id=result_id, target_llm=llm, rendered_text=text) for llm, text in rendered.items()]
    db.add_all(rows)
    db.flush()
    return rows


def save_token_usage(db: Session, result_id: int, target_llm: str, tokenizer: str,
                     original_input_tokens: int, optimized_input_tokens: int,
                     original_output_tokens: Optional[int] = None, optimized_output_tokens: Optional[int] = None,
                     est_cost_original_usd: Optional[float] = None,
                     est_cost_optimized_usd: Optional[float] = None) -> TokenUsage:
    row = TokenUsage(result_id=result_id, target_llm=target_llm, tokenizer=tokenizer,
                     original_input_tokens=original_input_tokens, optimized_input_tokens=optimized_input_tokens,
                     original_output_tokens=original_output_tokens, optimized_output_tokens=optimized_output_tokens,
                     est_cost_original_usd=est_cost_original_usd, est_cost_optimized_usd=est_cost_optimized_usd)
    db.add(row)
    db.flush()
    return row


def register_lora_model(db: Session, name: str, base_model: str, lora_rank: int,
                        adapter_path: Optional[str] = None, dataset_version: Optional[str] = None) -> LoRAModel:
    row = LoRAModel(name=name, base_model=base_model, lora_rank=lora_rank,
                    adapter_path=adapter_path, dataset_version=dataset_version)
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------- evaluation
def record_evaluation(db: Session, run_name: str, dataset_version: str, dataset_item_id: str, category: str,
                      variant: str, target_llm: str, input_tokens: int, output_tokens: Optional[int] = None,
                      latency_ms: Optional[int] = None, quality_score: Optional[float] = None,
                      task_success: Optional[bool] = None) -> EvaluationRun:
    row = EvaluationRun(run_name=run_name, dataset_version=dataset_version, dataset_item_id=dataset_item_id,
                        category=_check_category(category), variant=variant, target_llm=target_llm,
                        input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms,
                        quality_score=quality_score, task_success=task_success)
    db.add(row)
    db.flush()
    return row


def delete_evaluation(db: Session, run_name: str, dataset_item_id: str, variant: str, target_llm: str) -> int:
    """Remove one recorded result (a dev run redoing an out-of-date item). Returns the number of rows deleted."""
    n = db.execute(delete(EvaluationRun).where(
        EvaluationRun.run_name == run_name, EvaluationRun.dataset_item_id == dataset_item_id,
        EvaluationRun.variant == variant, EvaluationRun.target_llm == target_llm)).rowcount
    db.flush()
    return n or 0


def evaluation_summary(db: Session, run_name: str) -> list[dict[str, Any]]:
    """Averages per category and variant for one run (feeds the results table/charts)."""
    total_tokens = EvaluationRun.input_tokens + func.coalesce(EvaluationRun.output_tokens, 0)
    success = case((EvaluationRun.task_success.is_(True), 1.0), (EvaluationRun.task_success.is_(False), 0.0))
    q = (select(EvaluationRun.category, EvaluationRun.variant, func.count().label("n"),
                func.avg(EvaluationRun.input_tokens).label("avg_input_tokens"),
                func.avg(EvaluationRun.output_tokens).label("avg_output_tokens"),
                func.avg(total_tokens).label("avg_total_tokens"),
                func.avg(success).label("task_success_rate"),                 # over checkable items only
                func.count(EvaluationRun.task_success).label("n_success_checked"),
                func.avg(EvaluationRun.quality_score).label("avg_quality"),
                func.avg(EvaluationRun.latency_ms).label("avg_latency_ms"))
         .where(EvaluationRun.run_name == run_name)
         .group_by(EvaluationRun.category, EvaluationRun.variant)
         .order_by(EvaluationRun.category, EvaluationRun.variant))
    return [dict(r._mapping) for r in db.execute(q)]


# ---------------------------------------------------------------- reading
def get_prompt_history(db: Session, prompt_id: int) -> Optional[dict[str, Any]]:
    """Everything the system did to one prompt, for the 'what changed and why' view in the UI."""
    prompt = db.scalar(
        select(Prompt).where(Prompt.id == prompt_id).options(
            selectinload(Prompt.features),
            selectinload(Prompt.results).selectinload(OptimizationResult.transformations)
            .selectinload(Transformation.rule),
            selectinload(Prompt.results).selectinload(OptimizationResult.renderings),
            selectinload(Prompt.results).selectinload(OptimizationResult.token_usage)))
    if prompt is None:
        return None
    f = prompt.features
    return {
        "prompt_id": prompt.id,
        "original_text": prompt.original_text,
        "pii_redactions": prompt.pii_redactions,
        "expires_at": prompt.expires_at,
        "features": None if f is None else {
            "task_type": f.task_type, "has_format_spec": f.has_format_spec, "has_context": f.has_context,
            "missing_constraints": f.missing_constraints, "redundant_phrases": f.redundant_phrases,
            "ambiguous_refs": f.ambiguous_refs, "confidence": f.confidence},
        "results": [{
            "result_id": r.id, "optimized_text": r.optimized_text, "ir": r.ir, "confidence": r.confidence,
            "used_lora": r.used_lora,
            "steps": [{"step": t.step_no, "stage": t.stage, "rule": t.rule.code if t.rule else None,
                       "before": t.before_text, "after": t.after_text, "note": t.note} for t in r.transformations],
            "renderings": {x.target_llm: x.rendered_text for x in r.renderings},
            "token_usage": [{"target_llm": u.target_llm, "original_input": u.original_input_tokens,
                             "optimized_input": u.optimized_input_tokens, "net_change": u.net_token_change}
                            for u in r.token_usage],
        } for r in prompt.results],
    }


# ---------------------------------------------------------------- retention
def purge_expired(db: Session, now: Optional[datetime] = None) -> int:
    """Delete prompts past their expiry date. Features, results, transformations, renderings and token
    usage go with them through ON DELETE CASCADE. Commits, and returns the number of prompts deleted."""
    now = now or datetime.now(timezone.utc)
    deleted = db.execute(delete(Prompt).where(Prompt.expires_at <= now)).rowcount
    db.commit()
    return deleted or 0
