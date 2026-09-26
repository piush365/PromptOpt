"""Stage B: deterministic, rule-based optimization. See optimizer.py."""
from app.stage_b.ir import Attachment, PromptIR, render_plain
from app.stage_b.optimizer import OptimizationOutput, optimize

__all__ = ["Attachment", "OptimizationOutput", "PromptIR", "optimize", "render_plain"]
