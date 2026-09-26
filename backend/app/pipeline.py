"""One request through the pipeline: store the prompt -> Stage A -> Stage B -> IR renderings, all through the
repository (the FastAPI app will call `process_prompt`).

    out = process_prompt(db, "summarize this", category="auto", attachment=Attachment(type="pdf", name="a.pdf"),
                         target_llm="claude")
    db.commit()
    out.renderings["claude"]

`context` is text pasted next to the prompt. PII is scrubbed from it like from the prompt, because it ends up in the
stored renderings; those are deleted with the prompt when it expires.
"""
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db import repository as repo
from app.db.pii import scrub_pii
from app.rendering import render_all
from app.stage_a.schema import PromptFeatures
from app.stage_b.ir import Attachment, TargetLLM
from app.stage_b.optimizer import OptimizationOutput, optimize


@dataclass
class PipelineResult:
    prompt_id: int
    result_id: int
    features: PromptFeatures
    optimization: OptimizationOutput
    renderings: dict[str, str]


def process_prompt(db: Session, text: str, detector: Any, category: str = "auto",
                   attachment: Attachment | None = None, target_llm: TargetLLM | None = None,
                   context: str | None = None, disabled: frozenset[str] = frozenset()) -> PipelineResult:
    """Flushes but does not commit (the caller commits once per request)."""
    prompt = repo.create_prompt(db, text)
    context = scrub_pii(context)[0].strip() if context and context.strip() else None
    features = detector.detect(prompt.original_text, context)
    repo.save_features(db, prompt.id, features.model_dump())
    out = optimize(prompt.original_text, features, disabled, category=category, attachment=attachment,
                   target_llm=target_llm, separate_text=context is not None)
    result = repo.save_optimization(db, prompt.id, out.optimized_text, out.ir.model_dump(mode="json"),
                                    out.confidence, out.steps)
    renderings = render_all(out.ir, context_text=context)
    repo.save_renderings(db, result.id, renderings)
    return PipelineResult(prompt.id, result.id, features, out, renderings)
