"""One request through the pipeline: store the prompt -> Stage A -> Stage B -> IR renderings, all through the
repository (the FastAPI app will call `process_prompt`).

    out = process_prompt(db, "summarize this", category="auto", attachment=Attachment(type="pdf", name="a.pdf"),
                         target_llm="claude")
    db.commit()
    out.renderings["claude"]

Category: "auto" uses Stage A; a category the user picks overrides it. Stage A's own prediction is still stored (the
features) and returned, and `category_disagreement` says when the user's choice differs from it, so the UI can show
it. `token_counts` gives the input tokens of each rendering (exact for GPT, approximate and labelled for the others).

`context` is text pasted next to the prompt. PII is scrubbed from it like from the prompt, because it ends up in the
stored renderings; those are deleted with the prompt when it expires.
"""
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db import repository as repo
from app.db.pii import scrub_pii
from app.rendering import render_all, token_counts
from app.stage_a.schema import PromptFeatures
from app.stage_b.ir import Attachment, TargetLLM
from app.stage_b.optimizer import OptimizationOutput, optimize

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    prompt_id: int
    result_id: int
    features: PromptFeatures
    optimization: OptimizationOutput
    renderings: dict[str, str]
    token_counts: dict[str, dict]

    @property
    def stage_a_category(self) -> str:
        return self.features.task_type

    @property
    def category(self) -> str:
        """The category Stage B used: the user's choice, or Stage A's."""
        return self.optimization.ir.category

    @property
    def category_disagreement(self) -> bool:
        """The user picked a category and Stage A predicted a different one."""
        return self.optimization.ir.category_source == "user" and self.category != self.stage_a_category


def process_prompt(db: Session, text: str, detector: Any, category: str = "auto",
                   attachment: Attachment | None = None, target_llm: TargetLLM | None = None,
                   context: str | None = None, disabled: frozenset[str] = frozenset()) -> PipelineResult:
    """Flushes but does not commit (the caller commits once per request)."""
    prompt = repo.create_prompt(db, text)
    context = scrub_pii(context)[0].strip() if context and context.strip() else None
    features = detector.detect(prompt.original_text, context)
    repo.save_features(db, prompt.id, features.model_dump())
    log.info("Stage A category %s (%.2f); requested %s", features.task_type, features.confidence, category)
    out = optimize(prompt.original_text, features, disabled, category=category, attachment=attachment,
                   target_llm=target_llm, separate_text=context is not None)
    result = repo.save_optimization(db, prompt.id, out.optimized_text, out.ir.model_dump(mode="json"),
                                    out.confidence, out.steps)
    renderings = render_all(out.ir, context_text=context)
    repo.save_renderings(db, result.id, renderings)
    return PipelineResult(prompt.id, result.id, features, out, renderings, token_counts(renderings))
