"""FastAPI app: the optimizer behind a small web UI (plain HTML/JS in app/static, no build step).

    uvicorn app.api:app --reload            # inside backend/, then open http://127.0.0.1:8000

Endpoints
    GET  /                      the UI
    GET  /api/options           targets, categories, attachment types, whether Stage C is loaded
    POST /api/optimize          prompt -> Stage A result, issues, rules fired, Stage C, renderings + input tokens;
                                category "image_generation" -> the separate image mode (app.image), image targets
    GET  /api/history           recent prompts (kept RETENTION_DAYS, then purged)
    GET  /api/history/{id}      one prompt with everything the system did to it
    POST /api/coding-tests      unvalidated tests for a coding prompt (Cerebras; 503 without CEREBRAS_API_KEY)
    GET  /api/compare/models    models Compare can run on, with availability ("add GEMINI_API_KEY", ...)
    POST /api/compare           original vs optimized prompt on one model: answers, tokens, latency, sandbox tests
                                for dataset coding items, optional blind judge (app.compare)
    GET  /api/suite             correctness suite: the 50 cases and each model's headline (app.correctness)
    GET  /api/suite/{id}        one case: material, vague vs optimized prompt, both answers, gold, verdicts, tokens
    POST /api/suite/{id}/run    the same, run live on a model now (cached)

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
from app.coding import app_tests
from app.compare import providers
from app.compare import service as compare_service
from app.evaluation.llm import DailyLimitReached, ModelUnavailable
from app.image.attributes import ATTRIBUTES as IMAGE_ATTRIBUTES
from app.image.optimizer import IMAGE_TARGETS, RULES as IMAGE_RULES
from app.image.v2 import RULE_DOCS_V2, optimize_image_v2, parse_accepted, render_all_v2
from app.db.models import Prompt
from app.pipeline import process_prompt
from app.rendering import TARGETS
from app.stage_b.ir import Attachment
from app.stage_b.rules import RULES

STATIC = Path(__file__).parent / "static"
CATEGORIES = ("auto", "closed_qa", "information_extraction", "classification", "summarization", "coding",
              "image_generation")
TEXT_TARGETS = ("gpt", "gemini", "claude")
ATTACHMENTS = ("none", "image", "pdf", "pptx", "docx", "spreadsheet", "code", "other")
RULE_DOCS = {code: (fn.__doc__ or "").strip().split("\n")[0] for code, fn in [*RULES, *IMAGE_RULES]}
RULE_DOCS.update({code: doc.strip().split("\n")[0] for code, doc in RULE_DOCS_V2.items()})

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
    target: Literal["claude", "gpt", "gemini", "dalle", "nano_banana", "stable_diffusion"] = "gpt"
    category: Literal[CATEGORIES] = "auto"
    attachment_type: Literal[ATTACHMENTS] = "none"
    attachment_name: str | None = Field(default=None, max_length=255)
    context: str | None = Field(default=None, max_length=50000, description="text pasted next to the prompt")
    accepted_suggestions: list[str] = Field(default_factory=list, max_length=20,
                                            description="image mode: suggestions the user clicked, 'lighting:soft daylight'")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/options")
def options():
    model = stage_c_model()
    return {"targets": TARGETS, "image_targets": IMAGE_TARGETS, "categories": CATEGORIES,
            "attachment_types": ATTACHMENTS,
            "stage_c": {"available": model is not None, "model": model.name if model else None,
                        "device": model.device if model else None},
            "retention_days": RETENTION_DAYS, "compare_enabled": any(m.available for m in providers.MODELS)}


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


def optimize_image_prompt(req: OptimizeRequest, db: Session) -> dict:
    """Image mode (optimizer v2): chosen explicitly by the user, never auto-detected; Stage A/B/C are not involved.
    Adds only what cannot conflict with the request; other missing attributes come back as suggestions, and the
    ones the user clicks are sent back in `accepted_suggestions`. Stored like a text prompt (PII scrubbed,
    retention) with the image IR and its rule log in the result's IR JSON (the rules table holds the text
    pipeline's rules only)."""
    if req.target not in IMAGE_TARGETS:
        raise HTTPException(422, f"image generation targets are {list(IMAGE_TARGETS)}")
    try:
        accepted = parse_accepted(req.accepted_suggestions)
    except ValueError as e:
        raise HTTPException(422, str(e))
    prompt = repo.create_prompt(db, req.prompt)
    out = optimize_image_v2(prompt.original_text, [f"{a}:{v}" for a, v in accepted], target=req.target)
    rendered = render_all_v2(out.ir)
    result = repo.save_optimization(db, prompt.id, rendered[req.target]["prompt"],
                                    {"mode": "image", **out.ir.model_dump(mode="json"), "steps": out.steps}, 1.0, [])
    repo.save_renderings(db, result.id, {t: r["prompt"] + (f"\n\nNegative prompt: {r['negative_prompt']}"
                                                           if r.get("negative_prompt") else "")
                                         for t, r in rendered.items()})
    db.commit()
    ir = out.ir
    auto = [{"what": "negatives", "value": ", ".join(ir.avoid_default)}] if ir.avoid_default else []
    if ir.quality:
        auto.append({"what": "quality", "value": ir.quality})
    if ir.aspect_ratio and not any(a == "aspect_ratio" for a, _ in accepted):
        auto.append({"what": "aspect ratio (from your prompt)", "value": ir.aspect_ratio})
    if ir.style_first:
        auto.append({"what": "style moved to the front (Stable Diffusion)", "value": ", ".join(ir.style_first)})
    return {"mode": "image", "version": "v2", "prompt_id": prompt.id, "target": req.target,
            "pii_redactions": prompt.pii_redactions,
            "stated": {a: out.detected[a] for a in IMAGE_ATTRIBUTES if out.detected[a]},
            "avoid_user": list(ir.avoid_user), "auto_added": auto,
            "accepted": [f"{a}:{v}" for a, v in accepted],
            "suggestions": [s.model_dump() for s in out.suggestions],
            "aspect_ratio": ir.aspect_ratio,
            "rules": [{"code": s["rule_code"], "what": RULE_DOCS.get(s["rule_code"], ""), "before": s["before"],
                       "after": s["after"]} for s in out.steps],
            "ir": ir.model_dump(mode="json"), "renderings": rendered}


@app.post("/api/optimize")
def optimize_prompt(req: OptimizeRequest, db: Session = Depends(get_db)):
    if req.category == "image_generation":
        return optimize_image_prompt(req, db)
    if req.target not in TEXT_TARGETS:
        raise HTTPException(422, f"text targets are {list(TEXT_TARGETS)}; pick the image_generation category for "
                                 f"image models")
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
        "coding_tests": {"tests": app_tests.lookup(req.prompt), "can_generate": app_tests.can_generate()}
        if "coding" in (res.category, f.task_type, (c.category_guess if c else None)) else None,
    }


class CodingTestsRequest(BaseModel):
    optimized_prompt: str = Field(min_length=1, max_length=20000)


@app.post("/api/coding-tests")
def coding_tests(req: CodingTestsRequest):
    if not app_tests.can_generate():
        raise HTTPException(503, "Generating tests needs CEREBRAS_API_KEY in backend/.env.")
    return app_tests.generate(req.optimized_prompt)


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


class CompareRequest(OptimizeRequest):
    model: str = Field(description="a model id from /api/compare/models")
    judge: bool = False


@app.get("/api/compare/models")
def compare_models():
    return {"default": next((m.id for m in providers.MODELS if m.available and m.provider == "groq"),
                            next((m.id for m in providers.MODELS if m.available), None)),
            "models": [{"id": m.id, "label": m.label, "provider": m.provider, "family": m.family,
                        "available": m.available, "reason": m.reason} for m in providers.MODELS]}


@app.post("/api/compare")
def compare(req: CompareRequest, db: Session = Depends(get_db)):
    if req.category == "image_generation":
        raise HTTPException(422, "Compare runs text prompts; image models are not wired up for Compare.")
    info = providers.BY_ID.get(req.model)
    if info is None:
        raise HTTPException(422, f"unknown model {req.model!r}")
    if not info.available:
        raise HTTPException(503, info.reason)
    optimized = optimize_prompt(OptimizeRequest(**req.model_dump(exclude={"model", "judge"})), db)
    try:
        result = compare_service.compare(req.prompt, optimized["renderings"][req.target], req.model, req.target,
                                         context=req.context, category=optimized["category"]["used"],
                                         judge_answers=req.judge)
    except DailyLimitReached as e:
        raise HTTPException(429, str(e))
    except ModelUnavailable as e:
        raise HTTPException(503, str(e))
    history = repo.get_prompt_history(db, optimized["prompt_id"])
    result_id = history["results"][-1]["result_id"]
    repo.save_token_usage(db, result_id, req.target, f"compare:{req.model}", result["original"]["input_tokens"],
                          result["optimized"]["input_tokens"], result["original"]["output_tokens"],
                          result["optimized"]["output_tokens"])
    db.commit()
    return {"prompt_id": optimized["prompt_id"], "category": optimized["category"], **result}


# ---------------------------------------------------------------- correctness suite (Test suite view)
class SuiteRunRequest(BaseModel):
    model: str = Field(description="a model id from /api/suite")


@app.get("/api/suite")
def suite():
    from app.correctness import view
    return view.overview()


@app.get("/api/suite/{case_id}")
def suite_case(case_id: str, model: str = "cerebras/gpt-oss-120b"):
    from app.correctness import view
    try:
        return view.case_view(case_id, model)
    except KeyError:
        raise HTTPException(404, f"no case {case_id!r}")
    except (ValueError, LookupError) as e:
        raise HTTPException(422, str(e))


@app.post("/api/suite/{case_id}/run")
def suite_run(case_id: str, req: SuiteRunRequest):
    from app.correctness import view
    try:
        return view.case_view(case_id, req.model, live=True)
    except KeyError:
        raise HTTPException(404, f"no case {case_id!r}")
    except (ValueError, LookupError) as e:
        raise HTTPException(422, str(e))
    except DailyLimitReached as e:
        raise HTTPException(429, str(e))
    except ModelUnavailable as e:
        raise HTTPException(503, str(e))
