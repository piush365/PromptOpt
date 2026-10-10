"""Endpoints for the web UI (v2, the React app in app/static/ui). Read-only, except deleting one prompt from History.

    GET    /api/ui/status            providers (key present, 24-hour usage vs the daily limit), Stage C, retention
    GET    /api/ui/examples          the "Try an example" gallery (demo-script prompts; Hackpad passage from Compare)
    POST   /api/ui/tokens            input tokens of the raw prompt per target (live counter; nothing is stored)
    GET    /api/ui/results           evaluation/FINAL_RESULTS.md parsed into sections and tables, plus the token headline
    GET    /api/ui/suite-grid        correctness suite: every case's verdicts and tokens per model (results.json)
    GET    /api/ui/history           past prompts with search and paging, with category/target/compare runs
                                     (expired prompts are deleted first: app.retention)
    DELETE /api/ui/history/{id}      delete one prompt (cascade, like the retention purge)
    GET    /api/ui/compare-history   past Compare runs (token usage rows written by POST /api/compare)

Nothing here touches Stage A/B/C or the evaluation: it reads the files and tables they wrote.
"""
import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import BACKEND_DIR, RETENTION_DAYS
from app.db.base import get_db
from app.db.models import OptimizationResult, Prompt, TokenUsage
from app.rendering import TARGETS, count_tokens
from app.retention import enforce_retention

ROOT = BACKEND_DIR.parent
EVAL = ROOT / "evaluation"
FINAL_RESULTS = EVAL / "FINAL_RESULTS.md"
TOKEN_REPORT = EVAL / "tokens" / "token_test.md"
LIVE_EXAMPLES = EVAL / "compare" / "live_examples.json"
SUITE_RESULTS = EVAL / "correctness_suite" / "results.json"

router = APIRouter(prefix="/api/ui")


# ---------------------------------------------------------------- status
def _provider_status(m) -> dict:
    used = None
    try:
        if m.provider == "groq":
            from app.groq_budget import DAILY_LIMITS, UsageLedger
            name = m.id.split("/", 1)[1]
            used = {**UsageLedger().used(name), "limit_tokens": DAILY_LIMITS.get(name, {}).get("tokens")}
        elif m.provider == "cerebras":
            from app.cerebras import LIMITS
            from app.groq_budget import UsageLedger
            ledger = UsageLedger(ROOT / "data" / "cerebras_usage.json")
            used = {**ledger.used(m.id), "limit_tokens": LIMITS.get(m.id.split("/", 1)[1], {}).get("tokens")}
    except Exception:                                   # a missing or half-written ledger: no quota hint
        used = None
    return {"id": m.id, "label": m.label, "provider": m.provider, "family": m.family, "available": m.available,
            "reason": m.reason, "key_env": m.key_env, "usage_24h": used}


@router.get("/status")
def status():
    from app.api import stage_c_model
    from app.compare import providers
    from app.coding import app_tests
    from app.coding.sandbox import sandbox_kind
    model = stage_c_model()
    return {"providers": [_provider_status(m) for m in providers.MODELS],
            "stage_c": {"available": model is not None, "model": model.name if model else None,
                        "device": model.device if model else None},
            "coding_tests": {"can_generate": app_tests.can_generate(), "sandbox": sandbox_kind()},
            "retention_days": RETENTION_DAYS}


# ---------------------------------------------------------------- examples
def _hackpad() -> tuple[str, str]:
    try:
        ex = json.loads(LIVE_EXAMPLES.read_text(encoding="utf-8"))["closed_qa"]["original"]["prompt"]
        question, passage = ex.split("\n\n", 1)
        return question, passage
    except Exception:
        return "which company bought hackpad according to that text?", ""


@router.get("/examples")
def examples():
    q, passage = _hackpad()
    ex = [
        {"id": "permutations", "title": "Permutations of a string", "kind": "coding", "category": "auto",
         "target": "gpt", "prompt": "write code to get all permutations of a string",
         "why": "A coding prompt with no language and no format. Watch B05 and B03 fill them in.", "demo": True},
        {"id": "hackpad", "title": "Who bought Hackpad?", "kind": "closed_qa", "category": "auto",
         "target": "claude", "prompt": q, "context": passage,
         "why": "A question about a pasted passage. The honest case: the answer was already short.", "demo": True},
        {"id": "extract", "title": "Pull out names and dates", "kind": "information_extraction", "category": "auto",
         "target": "gpt", "prompt": "get me the names and dates from this",
         "context": "The workshop on 12 March 2026 was led by Dr. Asha Kulkarni. A follow-up session on "
                    "2 April 2026 was run by Prof. Rohan Deshmukh.",
         "why": "Extraction with an unclear 'this': the pasted text resolves it."},
        {"id": "classify", "title": "Sort reviews by mood", "kind": "classification", "category": "auto",
         "target": "gemini",
         "prompt": "classify these reviews as positive or negative: 'battery died in a day', "
                   "'best purchase this year', 'arrived late but works fine'",
         "why": "Classification: the label set is made explicit and the answer format is fixed."},
        {"id": "summarize", "title": "Summarise an article", "kind": "summarization", "category": "auto",
         "target": "claude", "prompt": "hey can you just summarize this article for me",
         "why": "Filler words and an unclear 'this article': sent to Stage C when it is installed."},
        {"id": "attachment", "title": "Describe a picture", "kind": "attachment", "category": "auto",
         "target": "gpt", "prompt": "describe what is happening in the picture", "attachment_type": "image",
         "why": "Stage A is unsure, so you are asked to confirm the category. The image rule adds what to look at."},
        {"id": "image", "title": "Oil painting of a sailboat", "kind": "image_generation",
         "category": "image_generation", "target": "stable_diffusion",
         "prompt": "oil painting of a sailboat in a storm",
         "why": "Image mode keeps your words first and offers suggestions instead of adding defaults."},
    ]
    return {"examples": ex}


# ---------------------------------------------------------------- live token counter
class TokensRequest(BaseModel):
    text: str = Field(default="", max_length=70000)


@router.post("/tokens")
def tokens(req: TokensRequest):
    return {t: count_tokens(req.text, t) for t in TARGETS}


# ---------------------------------------------------------------- results (parsed from the reports)
_PLAIN = re.compile(r"\*\*|`")


def _clean(s: str) -> str:
    return _PLAIN.sub("", s).strip()


def _table(lines: list[str]) -> dict:
    rows = [[_clean(c) for c in ln.strip().strip("|").split("|")] for ln in lines]
    bold = [("**" in ln) for ln in lines[2:]]
    return {"headers": rows[0], "rows": rows[2:], "bold": bold}


def parse_report(text: str) -> list[dict]:
    """Markdown -> [{id, title, level, intro, bullets, tables}] for every ## / ### heading."""
    sections, cur = [], None
    lines = re.sub(r"<!--.*?-->", "", text).splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(#{2,3})\s+(.*)$", ln)
        if m:
            title = _clean(m.group(2))
            num = re.match(r"^([0-9]+[a-z]?(?:\.[0-9]+)?)\.?\s", title)
            cur = {"id": num.group(1) if num else re.sub(r"\W+", "-", title.lower()).strip("-"),
                   "title": title, "level": len(m.group(1)), "intro": [], "bullets": [], "tables": []}
            sections.append(cur)
        elif cur is not None and ln.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            cur["tables"].append(_table(block))
            continue
        elif cur is not None and ln.startswith("* "):
            item = ln[2:]
            while i + 1 < len(lines) and lines[i + 1].startswith("  ") and lines[i + 1].strip():
                i += 1
                item += " " + lines[i].strip()
            cur["bullets"].append(_clean(item))
        elif cur is not None and ln.strip() and not ln.startswith("```"):
            if cur["intro"] and lines[i - 1].strip():
                cur["intro"][-1] += " " + _clean(ln)
            else:
                cur["intro"].append(_clean(ln))
        i += 1
    return sections


def token_headline(text: str) -> dict | None:
    m = re.search(r"reduce total tokens by ([0-9.]+)% \(95% CI ([0-9.]+)[–-]([0-9.]+)%, n = ([0-9]+)\)", text)
    if not m:
        return None
    out = {"reduction_pct": float(m.group(1)), "ci_low": float(m.group(2)), "ci_high": float(m.group(3)),
           "n": int(m.group(4))}
    io = re.search(r"Input tokens ([0-9]+) -> ([0-9]+).*?output tokens ([0-9]+) -> ([0-9]+)", text, re.S)
    if io:
        out.update(input_before=int(io.group(1)), input_after=int(io.group(2)), output_before=int(io.group(3)),
                   output_after=int(io.group(4)))
    more = re.search(r"([0-9]+) of ([0-9]+) prompts \(([0-9.]+)%\) individually cost more", text)
    if more:
        out.update(cost_more=int(more.group(1)), cost_more_pct=float(more.group(3)))
    return out


@router.get("/results")
def results():
    if not FINAL_RESULTS.exists():
        raise HTTPException(404, "evaluation/FINAL_RESULTS.md is missing")
    text = FINAL_RESULTS.read_text(encoding="utf-8")
    token_text = TOKEN_REPORT.read_text(encoding="utf-8") if TOKEN_REPORT.exists() else text
    from app.correctness import view
    suite = view.overview()
    return {"source": "evaluation/FINAL_RESULTS.md", "token_source": "evaluation/tokens/token_test.md",
            "tokens": token_headline(text) or token_headline(token_text),
            "sections": parse_report(text),
            "suite": {"generated": suite["generated"], "models": suite["models"]}}


# ---------------------------------------------------------------- correctness suite grid
def _status(v: bool, o: bool) -> str:
    return {(False, True): "fixed", (True, False): "hurt", (True, True): "both", (False, False): "neither"}[(v, o)]


@router.get("/suite-grid")
def suite_grid():
    from app.correctness import view
    ov = view.overview()
    stored = json.loads(SUITE_RESULTS.read_text(encoding="utf-8")) if SUITE_RESULTS.exists() else {"models": {}}
    per_model = {}
    for mid, res in stored.get("models", {}).items():
        rows = {}
        for cid, r in res["cases"].items():
            v, o = r["vague"], r["optimized"]
            rows[cid] = {"vague": bool(v["correct"]), "optimized": bool(o["correct"]),
                         "status": _status(bool(v["correct"]), bool(o["correct"])),
                         "tokens": {"vague": v["total_tokens"], "optimized": o["total_tokens"]}}
        per_model[mid] = rows
    cases = []
    by_id = {c["id"]: c for c in __import__("app.correctness.cases", fromlist=["load_cases"]).load_cases()}
    for c in ov["cases"]:
        full = by_id.get(c["id"], {})
        cases.append({**c, "difficulty": full.get("difficulty", []), "vague_prompt": full.get("vague_prompt", "")})
    return {"categories": ov["categories"], "models": ov["models"], "generated": ov["generated"],
            "cases": cases, "verdicts": per_model}


# ---------------------------------------------------------------- history
def _summary(p: Prompt) -> dict:
    r = p.results[-1] if p.results else None
    ir = (r.ir if r else None) or {}
    compares = [{"model": u.tokenizer.removeprefix("compare:"), "target": u.target_llm,
                 "original_total": u.original_input_tokens + (u.original_output_tokens or 0),
                 "optimized_total": u.optimized_input_tokens + (u.optimized_output_tokens or 0),
                 "created_at": u.created_at}
                for u in (r.token_usage if r else []) if u.tokenizer.startswith("compare:")]
    return {"prompt_id": p.id, "text": p.original_text, "created_at": p.created_at, "expires_at": p.expires_at,
            "mode": "image" if ir.get("mode") == "image" else "text",
            "category": ir.get("category"), "category_source": ir.get("category_source"),
            "target": ir.get("target_llm") or ir.get("target"),
            "attachment": (ir.get("attachment") or {}).get("type") if isinstance(ir.get("attachment"), dict) else None,
            "changes": len(r.transformations) if r else 0, "used_stage_c": bool(r and r.used_lora),
            "optimized": r.optimized_text if r else None, "compares": compares}


@router.get("/history", dependencies=[Depends(enforce_retention)])
def history(q: str = "", limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    stmt = select(Prompt)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Prompt.original_text.ilike(like),
                              Prompt.results.any(OptimizationResult.optimized_text.ilike(like))))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Prompt.id.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 200))
                      .options(selectinload(Prompt.results).selectinload(OptimizationResult.transformations),
                               selectinload(Prompt.results).selectinload(OptimizationResult.token_usage))).all()
    return {"total": total, "items": [_summary(p) for p in rows]}


@router.delete("/history/{prompt_id}")
def delete_history(prompt_id: int, db: Session = Depends(get_db)):
    deleted = db.execute(delete(Prompt).where(Prompt.id == prompt_id)).rowcount
    db.commit()
    if not deleted:
        raise HTTPException(404, "prompt not found (it may have expired)")
    return {"deleted": prompt_id}


@router.get("/compare-history", dependencies=[Depends(enforce_retention)])
def compare_history(limit: int = 30, db: Session = Depends(get_db)):
    rows = db.execute(select(TokenUsage, OptimizationResult.prompt_id, Prompt.original_text)
                      .join(OptimizationResult, TokenUsage.result_id == OptimizationResult.id)
                      .join(Prompt, OptimizationResult.prompt_id == Prompt.id)
                      .where(TokenUsage.tokenizer.like("compare:%"))
                      .order_by(TokenUsage.id.desc()).limit(min(max(limit, 1), 100))).all()
    out = []
    for u, pid, text in rows:
        before = u.original_input_tokens + (u.original_output_tokens or 0)
        after = u.optimized_input_tokens + (u.optimized_output_tokens or 0)
        out.append({"prompt_id": pid, "text": text, "model": u.tokenizer.removeprefix("compare:"),
                    "target": u.target_llm, "created_at": u.created_at,
                    "original": {"input": u.original_input_tokens, "output": u.original_output_tokens,
                                 "total": before},
                    "optimized": {"input": u.optimized_input_tokens, "output": u.optimized_output_tokens,
                                  "total": after},
                    "change_pct": round(100 * (after - before) / before, 1) if before else None})
    return out
