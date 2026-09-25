"""Stage A output: what is wrong with a prompt. Stage A records problems; it never changes the prompt."""
from typing import Literal

from pydantic import BaseModel, Field

from app.config import TASK_CATEGORIES

Category = Literal["closed_qa", "information_extraction", "classification", "summarization", "coding", "other"]
Constraint = Literal["length", "tone", "audience", "language"]

assert set(Category.__args__) == set(TASK_CATEGORIES), "Category literal out of sync with config.TASK_CATEGORIES"


class PromptFeatures(BaseModel):
    """Stage A result. `model_dump()` can be passed straight to `repository.save_features`."""

    task_type: Category
    confidence: float = Field(ge=0.0, le=1.0, description="confidence in task_type")
    category_scores: dict[str, float] = Field(default_factory=dict, description="score per category, sums to 1")
    classifier: str = Field(description="which classifier produced task_type: 'embedding' or 'keyword'")

    has_format_spec: bool = Field(description="the prompt states an output format (JSON, list, N sentences, ...)")
    format_evidence: list[str] = Field(default_factory=list)

    has_context: bool = Field(description="a passage, code or data to work on was supplied or embedded")

    constraints_present: list[Constraint] = Field(default_factory=list)
    missing_constraints: list[Constraint] = Field(
        default_factory=list, description="constraints relevant to task_type that the prompt does not state")

    redundant_phrases: list[str] = Field(default_factory=list, description="filler phrases and repeated text")
    ambiguous_refs: list[str] = Field(default_factory=list, description="references with nothing to refer to")

    word_count: int = Field(ge=0)
