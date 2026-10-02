"""One request through the pipeline: store the prompt -> Stage A -> Stage B -> IR renderings, all through the
repository (the FastAPI app will call `process_prompt`).

    out = process_prompt(db, "summarize this", category="auto", attachment=Attachment(type="pdf", name="a.pdf"),
                         target_llm="claude")
    db.commit()
    out.renderings["claude"]

Category: "auto" uses Stage A; a category the user picks overrides it. Stage A's own prediction is still stored (the
features) and returned, and `category_disagreement` says when the user's choice differs from it, so the UI can show
it. `token_counts` gives the input tokens of each rendering (exact for GPT, approximate and labelled for the others).

Stage C: pass `stage_c` (a `generate(messages) -> str`, e.g. `runtime.default_model().generate`) and prompts that
Stage B routes to Stage C get their unresolved fields filled under the contract (app.stage_c.contract); a rejected
answer keeps Stage B's result. Without `stage_c`, the pipeline is Stage A + Stage B only.

`context` is text pasted next to the prompt. PII is scrubbed from it like from the prompt, because it ends up in the
stored renderings; those are deleted with the prompt when it expires.
"""
import logging
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.db import repository as repo
from app.db.pii import scrub_pii
from app.rendering import count_tokens, render_all, token_counts
from app.stage_a.schema import PromptFeatures
from app.stage_b.ir import Attachment, TargetLLM
from app.stage_b.ir import render_plain
from app.stage_b.optimizer import OptimizationOutput, optimize
from app.stage_c.contract import StageCResult, apply_stage_c

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    prompt_id: int
    result_id: int
    features: PromptFeatures
    optimization: OptimizationOutput
    renderings: dict[str, str]
    token_counts: dict[str, dict]
    stage_c: StageCResult | None = None          # None: Stage C not available; .used False: not routed

    @property
    def ir(self):
        """The final IR (after Stage C, if it was used and accepted)."""
        return self.stage_c.ir if self.stage_c is not None else self.optimization.ir

    @property
    def stage_a_category(self) -> str:
        return self.features.task_type

    @property
    def category(self) -> str:
        """The category Stage B used: the user's choice, or Stage A's."""
        return self.ir.category

    @property
    def category_disagreement(self) -> bool:
        """The user picked a category and Stage A predicted a different one."""
        return self.ir.category_source == "user" and self.category != self.stage_a_category


def process_prompt(db: Session, text: str, detector: Any, category: str = "auto",
                   attachment: Attachment | None = None, target_llm: TargetLLM | None = None,
                   context: str | None = None, disabled: frozenset[str] = frozenset(),
                   stage_c: Callable[[list[dict]], str] | None = None) -> PipelineResult:
    """Flushes but does not commit (the caller commits once per request)."""
    prompt = repo.create_prompt(db, text)
    context = scrub_pii(context)[0].strip() if context and context.strip() else None
    features = detector.detect(prompt.original_text, context)
    repo.save_features(db, prompt.id, features.model_dump())
    log.info("Stage A category %s (%.2f); requested %s", features.task_type, features.confidence, category)
    out = optimize(prompt.original_text, features, disabled, category=category, attachment=attachment,
                   target_llm=target_llm, separate_text=context is not None)
    ir, steps, c = out.ir, list(out.steps), None
    if stage_c is not None:
        c = apply_stage_c(prompt.original_text, features, out, stage_c)
        if c.accepted:
            ir = c.ir
            steps.append({"stage": "C", "before": out.optimized_text, "after": render_plain(ir),
                          "note": "Stage C filled " + ", ".join(c.fields)})
        elif c.used:
            log.info("Stage C answer rejected (%s); keeping Stage B's result", "; ".join(c.errors))
    result = repo.save_optimization(db, prompt.id, render_plain(ir), ir.model_dump(mode="json"), out.confidence,
                                    steps, latency_ms=round(1000 * c.seconds) if c and c.used else None)
    renderings = render_all(ir, context_text=context)
    repo.save_renderings(db, result.id, renderings)
    counts = token_counts(renderings)
    for target, n in counts.items():
        original = count_tokens(prompt.original_text + (f"\n\n{context}" if context else ""), target)["tokens"]
        repo.save_token_usage(db, result.id, target, counts[target]["method"], original, n["tokens"])
    return PipelineResult(prompt.id, result.id, features, out, renderings, counts, c)
