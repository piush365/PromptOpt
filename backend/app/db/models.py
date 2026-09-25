"""PromptOpt database schema.

Live pipeline (one row chain per submitted prompt):
    users 1-* prompts 1-1 prompt_features
                      1-* optimization_results 1-* transformations *-1 rules
                                               1-* renderings
                                               1-* token_usage
                                               *-1 lora_models
Offline benchmark:
    evaluation_runs   (one row per dataset item x variant x target LLM)

Deleting a prompt deletes everything derived from it (ON DELETE CASCADE); the retention purge relies on this.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import TASK_CATEGORIES
from app.db.base import Base

# JSONB on PostgreSQL (indexable, binary), plain JSON on SQLite
JSONType = JSON().with_variant(JSONB(), "postgresql")

_CATEGORY_LIST = ", ".join(f"'{c}'" for c in TASK_CATEGORIES)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # No email or real name is stored: the system does not need them, and not storing them is the simplest privacy guarantee.
    display_name: Mapped[Optional[str]] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    prompts: Mapped[list["Prompt"]] = relationship(back_populates="user", passive_deletes=True)


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    original_text: Mapped[str] = mapped_column(Text, nullable=False)   # stored AFTER PII scrubbing
    pii_redactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[Optional[User]] = relationship(back_populates="prompts")
    features: Mapped[Optional["PromptFeatures"]] = relationship(
        back_populates="prompt", uselist=False, cascade="all, delete-orphan", passive_deletes=True)
    results: Mapped[list["OptimizationResult"]] = relationship(
        back_populates="prompt", cascade="all, delete-orphan", passive_deletes=True,
        order_by="OptimizationResult.id")

    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="ck_prompts_expiry_after_creation"),
        Index("ix_prompts_expires_at", "expires_at"),   # the retention purge filters on this
    )


class PromptFeatures(Base):
    """Stage A output: what is missing or wrong in the prompt."""
    __tablename__ = "prompt_features"

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), unique=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    has_format_spec: Mapped[bool] = mapped_column(Boolean, nullable=False)
    has_context: Mapped[bool] = mapped_column(Boolean, nullable=False)
    missing_constraints: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)  # e.g. ["length", "tone"]
    redundant_phrases: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    ambiguous_refs: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    prompt: Mapped[Prompt] = relationship(back_populates="features")

    __table_args__ = (
        CheckConstraint(f"task_type IN ({_CATEGORY_LIST})", name="ck_features_task_type"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_features_confidence_range"),
    )


class Rule(Base):
    """Catalogue of rule-based transformations (Stage B). Seeded by app.db.seed."""
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)   # e.g. "B03_ADD_OUTPUT_FORMAT"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    stage: Mapped[str] = mapped_column(String(1), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # switched off for ablation runs

    __table_args__ = (CheckConstraint("stage IN ('A', 'B')", name="ck_rules_stage"),)


class LoRAModel(Base):
    """Metadata for a Stage C fine-tuned adapter."""
    __tablename__ = "lora_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    base_model: Mapped[str] = mapped_column(String(120), nullable=False)   # e.g. "Qwen/Qwen2.5-0.5B-Instruct"
    lora_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    adapter_path: Mapped[Optional[str]] = mapped_column(String(255))
    dataset_version: Mapped[Optional[str]] = mapped_column(String(40))      # e.g. "promptopt_dataset_v1"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class OptimizationResult(Base):
    """Stage B/C output for one prompt, including the model-agnostic IR."""
    __tablename__ = "optimization_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False, index=True)
    ir: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)   # task, context, constraints, requirements, output_format
    optimized_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    used_lora: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lora_model_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lora_models.id", ondelete="SET NULL"))
    pipeline_version: Mapped[str] = mapped_column(String(20), default="0.1.0", nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    prompt: Mapped[Prompt] = relationship(back_populates="results")
    lora_model: Mapped[Optional[LoRAModel]] = relationship()
    transformations: Mapped[list["Transformation"]] = relationship(
        back_populates="result", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Transformation.step_no")
    renderings: Mapped[list["Rendering"]] = relationship(
        back_populates="result", cascade="all, delete-orphan", passive_deletes=True)
    token_usage: Mapped[list["TokenUsage"]] = relationship(
        back_populates="result", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_results_confidence_range"),
    )


class Transformation(Base):
    """One logged change (explainability): which rule changed what, in which order."""
    __tablename__ = "transformations"

    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("optimization_results.id", ondelete="CASCADE"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(1), nullable=False)
    rule_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rules.id", ondelete="SET NULL"))  # NULL when LoRA made the change
    before_text: Mapped[str] = mapped_column(Text, nullable=False)
    after_text: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(255))

    result: Mapped[OptimizationResult] = relationship(back_populates="transformations")
    rule: Mapped[Optional[Rule]] = relationship()

    __table_args__ = (
        UniqueConstraint("result_id", "step_no", name="uq_transformations_step"),
        CheckConstraint("stage IN ('B', 'C')", name="ck_transformations_stage"),
        CheckConstraint("stage = 'C' OR rule_id IS NOT NULL", name="ck_transformations_rule_required_for_b"),
    )


class Rendering(Base):
    """The IR rendered into a prompt for one target LLM family."""
    __tablename__ = "renderings"

    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("optimization_results.id", ondelete="CASCADE"), nullable=False)
    target_llm: Mapped[str] = mapped_column(String(40), nullable=False)   # e.g. "gpt", "claude", "gemini"
    rendered_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    result: Mapped[OptimizationResult] = relationship(back_populates="renderings")

    __table_args__ = (UniqueConstraint("result_id", "target_llm", name="uq_renderings_target"),)


class TokenUsage(Base):
    """Token and cost accounting. Output tokens are only known after the prompt is actually sent to an LLM."""
    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("optimization_results.id", ondelete="CASCADE"), nullable=False)
    target_llm: Mapped[str] = mapped_column(String(40), nullable=False)
    tokenizer: Mapped[str] = mapped_column(String(60), nullable=False)    # e.g. "tiktoken:o200k_base"
    original_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    optimized_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    original_output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    optimized_output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    est_cost_original_usd: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    est_cost_optimized_usd: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    result: Mapped[OptimizationResult] = relationship(back_populates="token_usage")

    __table_args__ = (
        CheckConstraint("original_input_tokens >= 0 AND optimized_input_tokens >= 0", name="ck_token_usage_nonnegative"),
    )

    @property
    def net_token_change(self) -> Optional[int]:
        """Optimized total minus original total (negative = tokens saved). None until output tokens are known."""
        if self.original_output_tokens is None or self.optimized_output_tokens is None:
            return None
        return (self.optimized_input_tokens + self.optimized_output_tokens) - (
            self.original_input_tokens + self.original_output_tokens)


class EvaluationRun(Base):
    """Offline benchmark / ablation result for one dataset item, one variant, one target LLM.

    Not linked to `prompts`: benchmark items come from PromptOpt Dataset v1 (kept as files), so they are
    never subject to the user-data retention purge.
    """
    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)   # e.g. "baseline-2026-09-30"
    dataset_version: Mapped[str] = mapped_column(String(40), nullable=False)
    dataset_item_id: Mapped[str] = mapped_column(String(20), nullable=False)          # e.g. "PO-CLS-0003"
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    variant: Mapped[str] = mapped_column(String(60), nullable=False)   # "original", "optimized", "ablation:no_stage_c", ...
    target_llm: Mapped[str] = mapped_column(String(40), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    quality_score: Mapped[Optional[float]] = mapped_column(Float)      # rubric score, 0-10
    task_success: Mapped[Optional[bool]] = mapped_column(Boolean)      # only for verifiable tasks
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("run_name", "dataset_item_id", "variant", "target_llm", name="uq_evaluation_runs_item"),
        CheckConstraint(f"category IN ({_CATEGORY_LIST})", name="ck_evaluation_runs_category"),
        CheckConstraint("quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 10)",
                        name="ck_evaluation_runs_quality_range"),
    )
