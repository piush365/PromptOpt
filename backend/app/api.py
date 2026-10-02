"""FastAPI app: the optimizer behind a small web UI (plain HTML/JS in app/static, no build step).

    uvicorn app.api:app --reload            # inside backend/, then open http://127.0.0.1:8000

Endpoints
    GET  /                      the UI
    GET  /api/options           targets, categories, attachment types, whether Stage C is loaded
    POST /api/optimize          prompt -> Stage A result, issues, rules fired, Stage C, renderings + input tokens
    GET  /api/history           recent prompts (kept RETENTION_DAYS, then purged)
    GET  /api/history/{id}      one prompt with everything the system did to it
    POST /api/compare           501 until API keys for the real target LLMs are configured

Everything runs offline. Stage C is used when its adapter is installed (config.STAGE_C_ADAPTER) and
STAGE_C_ENABLED is not "0"; otherwise the UI says Stage C is unavailable and Stage B's result is shown.
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import RETENTION_DAYS
from app.db import repository as repo
from app.db.base import get_db
from app.db.models import Prompt
from app.pipeline import process_prompt
from app.rendering import TARGETS
from app.stage_b.ir import Attachment
from app.stage_b.rules import RULES

STATIC = Path(__file__).parent / "static"
CATEGORIES = ("auto", "closed_qa", "information_extraction", "classification", "summarization", "coding")
ATTACHMENTS = ("none", "image", "pdf", "pptx", "docx", "spreadsheet", "code", "other")
RULE_DOCS = {code: (fn.__doc__ or "").strip().split("\n")[0] for code, fn in RULES}

app = FastAPI(title="PromptOpt", version="0.2.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@lru_cache(maxsize=1)
def detector():
    from app.stage_a.detector import default_detector
    return default_detector()


@lru_cache(maxsize=1)
def stage_c_model():
    """The Stage C model, or None (not installed, disabled, or failed to load)."""
    if os.getenv("STAGE_C_ENABLED", "1") == "0":
        return None
    from app.stage_c import runtime
    try:
        return runtime.default_model()
    except Exception:                                   # missing packages, broken adapter, ...: run without it
        return None


class OptimizeRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    target: Literal["claude", "gpt", "gemini"] = "gpt"
    category: Literal[CATEGORIES] = "auto"
    attachment_type: Literal[ATTACHMENTS] = "none"
    attachment_name: str | None = Field(default=None, max_length=255)
    context: str | None = Field(default=None, max_length=50000, description="text pasted next to the prompt")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/options")
def options():
    model = stage_c_model()
    return {"targets": TARGETS, "categories": CATEGORIES, "attachment_types": ATTACHMENTS,
            "stage_c": {"available": model is not None, "model": model.name if model else None,
                        "device": model.device if model else None},
            "retention_days": RETENTION_DAYS, "compare_enabled": False}


def issues(f) -> list[dict]:
    """Stage A's findings in plain words, for the 'detected issues' list."""
    out = []
    if not f.has_format_spec:
        out.append({"code": "A02", "issue": "No output format stated"})
    for c in f.missing_constraints:
        out.append({"code": "A03", "issue": f"No {c} stated"})
    if f.redundant_phrases:
        out.append({"code": "A04", "issue": "Filler or repetition: " + ", ".join(f"'{p}'" for p in f.redundant_phrases)})
    if f.ambiguous_refs:
        out.append({"code": "A05", "issue": "Unclear reference: " + ", ".join(f"'{r}'" for r in f.ambiguous_refs)})
    return out


@app.post("/api/optimize")
def optimize_prompt(req: OptimizeRequest, db: Session = Depends(get_db)):
    attachment = None if req.attachment_type == "none" else Attachment(type=req.attachment_type,
                                                                       name=req.attachment_name or None)
    model = stage_c_model()
    res = process_prompt(db, req.prompt, detector(), category=req.category, attachment=attachment,
                         target_llm=req.target, context=req.context, stage_c=model.generate if model else None)
    db.commit()
    f, out, c = res.features, res.optimization, res.stage_c
    return {
        "prompt_id": res.prompt_id,
        "stage_a": {"category": f.task_type, "confidence": f.confidence, "scores": f.category_scores,
                    "has_context": f.has_context, "format_evidence": f.format_evidence,
                    "constraints_present": f.constraints_present},
        "category": {"used": res.category, "source": res.ir.category_source, "requested": req.category,
                     "stage_a": res.stage_a_category, "disagreement": res.category_disagreement,
                     "uncertain": bool(c and c.category_status == "uncertain"),
                     "guess": c.category_guess if c else None},
        "issues": issues(f),
        "rules": [{"code": s["rule_code"], "what": RULE_DOCS.get(s["rule_code"], ""), "before": s["before"],
                   "after": s["after"]} for s in out.steps],
        "unresolved_after_b": list(out.unresolved),
        "stage_c": {"available": model is not None, "routed": out.needs_stage_c, "reasons": out.stage_c_reasons,
                    "used": bool(c and c.used), "accepted": bool(c and c.accepted), "fields": c.fields if c else [],
                    "errors": c.errors if c else [], "seconds": round(c.seconds, 2) if c and c.used else None,
                    "category_status": c.category_status if c else None,
                    "raw": c.raw if c else None},
        "unresolved": list(res.ir.unresolved),
        "ir": res.ir.model_dump(mode="json"),
        "optimized_plain": (c.optimized_text if c else out.optimized_text),
        "renderings": res.renderings,
        "tokens": res.token_counts,
        "target": req.target,
    }


@app.get("/api/history")
def history(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.scalars(select(Prompt).order_by(Prompt.id.desc()).limit(min(max(limit, 1), 100))).all()
    return [{"prompt_id": p.id, "text": p.original_text[:200], "created_at": p.created_at,
             "expires_at": p.expires_at} for p in rows]


@app.get("/api/history/{prompt_id}")
def history_item(prompt_id: int, db: Session = Depends(get_db)):
    item = repo.get_prompt_history(db, prompt_id)
    if item is None:
        raise HTTPException(404, "prompt not found (it may have expired)")
    return item


@app.post("/api/compare", status_code=501)
def compare():
    raise HTTPException(501, "Compare needs API keys for the real target LLMs; not configured yet.")
