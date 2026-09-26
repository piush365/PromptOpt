"""Dataset v1.2: expand v1.1 to about TARGET_PER_CATEGORY rows per category (port of the Colab notebook).

    python -m app.dataset_expand plan                       # no Groq: sample the new rows, estimate calls/tokens/days
    python -m app.dataset_expand generate [--max-calls N]   # resumable; stays within the daily budget
    python -m app.dataset_expand build                      # checks + repair + frozen splits -> v1.2 files

Steps (the notebook's, plus the fixes found in v1.1):
1. Sources: Dolly-15k (data/dolly/) and CodeAlpaca-20k (data/codealpaca/, downloaded once). source_id is the row
   number in the original download (`dolly-{i}`, `codealpaca-{i}`); `check_source_ids` verifies that against v1.1.
2. Cleaning and attributes as in the notebook: 4 Dolly categories, no empty rows, no duplicate instruction+context,
   no response-length outliers, Dolly PII scrubbed, CodeAlpaca trivial outputs dropped, complexity tertiles.
3. Sampling: only rows never sent to Groq before (v1's sampled_for_degradation.csv), per category
   (TARGET - v1.1 rows) / v1 pass rate * SAMPLE_MARGIN, stratified by complexity and context. The sample is frozen
   in sample.jsonl, so every run works on the same rows.
4. Generation: one call per row returns both prompts (SYSTEM_PROMPT, with the rule that data written in the
   instruction is kept verbatim). Rows go round-robin over the categories; models rotate when one reaches its
   budget. Every result is appended to generation_checkpoint.jsonl at once, so a stopped run loses nothing.
5. Budget: generation uses at most --budget-fraction (default 0.7) of each model's daily requests and tokens, and
   never pushes a model's total (all tools, app.groq_budget ledger) above GLOBAL_CAP, so the evaluation harness can
   still run the same day. The per-call token estimate is DEFAULT_TOKENS_PER_CALL until MEASURE_AFTER calls are in
   the checkpoint, then the measured average.
6. Quality checks as in the notebook (sentence-embedding drift, format left in the degraded prompt, too long, ...),
   then app.dataset_repair on every passing row (dropped data put back, dropped subjects fixed with cached Groq
   edits made during `generate`).
7. Frozen splits: v1.1 rows keep their split and id. New rows go to train unless a held-out split of their category
   is short. Leakage guard: a new row repeating a held-out instruction goes to that held-out split, and a new row
   repeating any v1.1 instruction is never used to fill a held-out split. v1.1 stays untouched; output is v1.2.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from app import dataset_repair as repair
from app.config import BACKEND_DIR
from app.db import pii
from app.groq_budget import DAILY_LIMITS, TOKENS_PER_MINUTE, UsageLedger

DATA_DIR = BACKEND_DIR.parent / "data"
V1_SAMPLED = DATA_DIR / "promptopt_dataset_v1" / "sampled_for_degradation.csv"
V11_CSV = DATA_DIR / "promptopt_dataset_v1_1" / "promptopt_dataset_v1_1.csv"
V12_DIR = DATA_DIR / "promptopt_dataset_v1_2"
V12_CSV_NAME = "promptopt_dataset_v1_2.csv"
DOLLY_JSONL = DATA_DIR / "dolly" / "databricks-dolly-15k.jsonl"
CODEALPACA_JSON = DATA_DIR / "codealpaca" / "code_alpaca_20k.json"
CODEALPACA_URL = "https://huggingface.co/datasets/sahil2801/CodeAlpaca-20k/resolve/main/code_alpaca_20k.json"

SEED = "promptopt-expand-v1.2"
CATEGORIES = ["closed_qa", "information_extraction", "classification", "summarization", "coding"]
ABBREV = {"closed_qa": "CQA", "information_extraction": "IE", "classification": "CLS", "summarization": "SUM",
          "coding": "COD"}
TARGET_PER_CATEGORY = 1000
SAMPLE_MARGIN = 1.05          # sample 5% more than the v1 pass rate says, so a category still reaches the target
SPLIT_SIZES = {"benchmark": 10, "test": 40, "val": 30}     # per category, as in the notebook

# Cleaning (notebook Step 2-3)
OUTLIER_STD = 3
MIN_CODING_OUTPUT_WORDS = 3

# Generation (notebook Step 8)
GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
BUDGET_FRACTION = 0.7
GLOBAL_CAP = 0.95             # never push a model's total daily usage (every tool) above this share of its limit
DEFAULT_TOKENS_PER_CALL = 430 # rate-limited tokens, measured in the notebook runs (120b: 469 rows on 200K; 20b: 448)
MEASURE_AFTER = 20
MAX_CONTEXT_CHARS = 1000
MAX_COMPLETION_TOKENS = 1024
TEMPERATURE = 0.7
PARSE_ATTEMPTS = 3            # calls per row when the model returns unusable JSON
MIN_INTERVAL = 2.2

# Quality checks (notebook Step 9)
DEGRADED_DRIFT_THRESHOLD = 0.45
OPTIMIZED_DRIFT_THRESHOLD = 0.35

FINAL_COLUMNS = [
    "id", "split", "category", "source_dataset", "source_id",
    "degraded_prompt", "optimized_prompt", "original_instruction", "context", "reference_response",
    "has_context", "has_format_spec", "optimized_has_format_spec", "complexity_bucket",
    "instruction_word_count", "degraded_word_count", "optimized_word_count", "context_word_count",
    "response_word_count", "sim_degraded_vs_original", "sim_optimized_vs_original", "human_validated", "model",
]


# ---------------------------------------------------------------- helpers (notebook Step "Helper functions")
def word_count(text: str) -> int:
    return len(str(text).split())


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def _unit(*parts: str) -> float:
    h = hashlib.sha256(":".join((SEED,) + parts).encode()).hexdigest()
    return int(h[:15], 16) / 16 ** 15


_NUM = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|a few|a single|a)"
FORMAT_PATTERNS = [
    r"\b(?:in|as|into)\s+(?:a\s+|an\s+)?(?:json|yaml|xml|csv|markdown)\b",
    r"\b(?:as|in)\s+(?:a\s+)?(?:bullet(?:ed)?|numbered)(?:\s+point)?s?(?:\s+list)?\b",
    r"\bbullet(?:ed)?[- ]points?\b",
    r"\bas\s+(?:a\s+|an\s+)?(?:list|table|paragraph|single word|one word|comma[- ]separated list)\b",
    r"\bcomma[- ]separated\b",
    r"\bin\s+(?:tabular|table)\s+form(?:at)?\b",
    r"\b(?:answer|respond|reply|explain|describe|summari[sz]e|write|list|give)\b[^.?!\n]{0,40}?\b(?:in|within|under|using|with)\s+"
    + _NUM + r"\s+(?:words?|sentences?|lines?|paragraphs?|points?|bullets?)\b",
    r"\b(?:one|single|two|three|four|five|\d+)[- ](?:word|sentence|line|paragraph)s?\s+(?:answer|response|summary|description|explanation)\b",
    r"\bstep[- ]by[- ]step\b",
    r"\bformat(?:ted)?\s+(?:it\s+|them\s+|the\s+\w+\s+)?(?:as|in|like)\b",
    r"\brespond\s+(?:only\s+)?with\b",
    r"\b(?:only|just)\s+(?:return|output|give)\s+(?:the\s+)?(?:answer|label|name|number)\b",
    r"\b(?:output|respond|reply|answer|present|format)\b[^.?!\n]{0,40}?\b(?:json|yaml|csv|xml|markdown|table|"
    r"bullet(?:ed)?(?:[- ]points?)?(?:\s+list)?|numbered\s+list|code\s+block|single\s+word|one\s+word|"
    r"one\s+sentence|single\s+sentence|one\s+line)\b",
    r"\bcode\s+block\b",
]
FORMAT_RE = re.compile("|".join(FORMAT_PATTERNS), re.IGNORECASE)


def has_format_spec(text: str) -> bool:
    return bool(FORMAT_RE.search(str(text)))


def scrub_pii(text: str) -> str:
    """Same patterns as the notebook and the live pipeline (app.db.pii)."""
    return pii.scrub_pii(str(text))[0]


# ---------------------------------------------------------------- sources and cleaning (notebook Steps 1-5)
def load_sources(dolly_path: Path = DOLLY_JSONL, codealpaca_path: Path = CODEALPACA_JSON) -> list[dict[str, str]]:
    """Both datasets in one schema. CodeAlpaca's `input` plays the role of Dolly's `context`."""
    if not Path(codealpaca_path).exists():
        import urllib.request

        Path(codealpaca_path).parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(CODEALPACA_URL, codealpaca_path)
    out = []
    with open(dolly_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            out.append({"source_dataset": "dolly", "source_id": f"dolly-{i}", "category": r["category"],
                        "instruction": (r.get("instruction") or "").strip(), "context": (r.get("context") or "").strip(),
                        "response": (r.get("response") or "").strip()})
    for i, r in enumerate(json.loads(Path(codealpaca_path).read_text(encoding="utf-8"))):
        out.append({"source_dataset": "codealpaca", "source_id": f"codealpaca-{i}", "category": "coding",
                    "instruction": (r.get("instruction") or "").strip(), "context": (r.get("input") or "").strip(),
                    "response": (r.get("output") or "").strip()})
    return out


def check_source_ids(sources: list[dict[str, str]], v11_rows: list[dict[str, str]]) -> None:
    """Abort if a source file is numbered differently from the one v1 was built from."""
    by_id = {r["source_id"]: r for r in sources}
    bad = []
    for r in v11_rows:
        src = by_id.get(r["source_id"])
        if src is None or normalize(scrub_pii(src["instruction"])) != normalize(r["original_instruction"]):
            bad.append(r["source_id"])
    if len(bad) > len(v11_rows) * 0.01:
        raise SystemExit(f"{len(bad)} v1.1 rows do not match their source_id in the source files (e.g. {bad[:3]}). "
                         f"The source files are not the ones the dataset was built from.")


def _dedupe(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen, out = set(), []
    for r in rows:
        key = normalize(r["instruction"]) + " || " + normalize(r["context"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def clean_pool(sources: list[dict[str, str]]) -> list[dict[str, Any]]:
    """The notebook's cleaning, then the attribute columns. CodeAlpaca is not downsampled: new coding rows may come
    from any of it."""
    dolly = [r for r in sources if r["source_dataset"] == "dolly" and r["category"] in CATEGORIES[:4]
             and r["instruction"] and r["response"]]
    dolly = _dedupe(dolly)
    by_cat = defaultdict(list)
    for r in dolly:
        by_cat[r["category"]].append(word_count(r["response"]))
    cutoff = {c: statistics.median(w) + OUTLIER_STD * statistics.stdev(w) for c, w in by_cat.items()}
    dolly = [dict(r, **{k: scrub_pii(r[k]) for k in ("instruction", "context", "response")})
             for r in dolly if word_count(r["response"]) <= cutoff[r["category"]]]
    code = [r for r in sources if r["source_dataset"] == "codealpaca" and r["instruction"] and r["response"]]
    code = [r for r in _dedupe(code) if word_count(r["response"]) >= MIN_CODING_OUTPUT_WORDS]

    pool = []
    for r in dolly + code:
        pool.append(dict(r, has_context=bool(r["context"]), has_format_spec=has_format_spec(r["instruction"]),
                         instruction_word_count=word_count(r["instruction"]),
                         context_word_count=word_count(r["context"]), response_word_count=word_count(r["response"])))
    # complexity_bucket: tertile of prompt length within each category (rank order, ties by position)
    by_cat = defaultdict(list)
    for r in pool:
        by_cat[r["category"]].append(r)
    for rows in by_cat.values():
        ranked = sorted(range(len(rows)),
                        key=lambda i: (rows[i]["instruction_word_count"] + rows[i]["context_word_count"], i))
        for pos, i in enumerate(ranked):
            rows[i]["complexity_bucket"] = ("short", "medium", "long")[min(2, 3 * pos // len(rows))]
    return pool


# ---------------------------------------------------------------- sampling (notebook Step 7)
def stratified_pick(rows: list[dict[str, Any]], n: int, strata: tuple[str, ...], salt: str) -> list[dict[str, Any]]:
    """Proportional stratified sample of n rows (largest remainder), deterministic order within each stratum."""
    if n >= len(rows):
        return list(rows)
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(str(r[s]) for s in strata)].append(r)
    alloc = {k: len(g) / len(rows) * n for k, g in groups.items()}
    base = {k: math.floor(a) for k, a in alloc.items()}
    for k in sorted(alloc, key=lambda k: (-(alloc[k] - base[k]), str(k)))[:n - sum(base.values())]:
        base[k] += 1
    out = []
    for k, g in sorted(groups.items()):
        out += sorted(g, key=lambda r: _unit(salt, r["source_id"]))[:base[k]]
    return out


@dataclass
class CategoryPlan:
    category: str
    v11_rows: int
    pass_rate: float
    needed: int          # kept rows still needed to reach the target
    unused: int          # source rows never sent to Groq
    to_sample: int


def plan_categories(pool: list[dict[str, Any]], v11_rows: list[dict[str, str]], v1_sampled: list[dict[str, str]],
                    target: int = TARGET_PER_CATEGORY) -> dict[str, CategoryPlan]:
    used = {r["source_id"] for r in v1_sampled} | {r["source_id"] for r in v11_rows}
    have = Counter(r["category"] for r in v11_rows)
    tried = Counter(r["category"] for r in v1_sampled)
    out = {}
    for c in CATEGORIES:
        unused = sum(1 for r in pool if r["category"] == c and r["source_id"] not in used)
        rate = have[c] / tried[c] if tried[c] else 0.9
        needed = max(0, target - have[c])
        want = math.ceil(needed / rate * SAMPLE_MARGIN) if needed else 0
        out[c] = CategoryPlan(c, have[c], rate, needed, unused, min(unused, want))
    return out


def sample_rows(pool: list[dict[str, Any]], plans: dict[str, CategoryPlan], used: set[str],
                frozen: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Keep every frozen row; top each category up to its plan with rows not used before."""
    frozen = list(frozen or [])
    taken = used | {r["source_id"] for r in frozen}
    out = list(frozen)
    for c in CATEGORIES:
        have = sum(r["category"] == c for r in frozen)
        need = plans[c].to_sample - have
        if need <= 0:
            continue
        cands = [r for r in pool if r["category"] == c and r["source_id"] not in taken]
        out += stratified_pick(cands, need, ("complexity_bucket", "has_context"), f"sample-{c}")
    return out


def round_robin(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Interleave the categories so a partial run stays balanced."""
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    longest = max((len(v) for v in by_cat.values()), default=0)
    return [by_cat[c][i] for i in range(longest) for c in CATEGORIES if i < len(by_cat[c])]


# ---------------------------------------------------------------- generation (notebook Step 8)
SYSTEM_PROMPT = '''You build training data for a prompt-optimization system.
You get a CLEAN instruction written for an AI assistant, its task category, and (optionally) a separate TEXT/INPUT it refers to.
Write TWO rewrites of the instruction and return them as JSON.

Data rule (both rewrites): data written INSIDE the clean instruction is part of the request, not the separate text.
The items to classify, a list, code, numbers, an expression, quoted strings and the named subject (person, place,
work, product) must appear in both rewrites, copied verbatim. Never drop them and never replace them with "the
listed items" or "the provided text".

1. "degraded_prompt": how a rushed, non-expert student would actually type the same request.
   - Same task and same intent. Never change what is being asked and never add new information.
   - Remove any explicit output format and constraints (length, tone, audience, language, label options) if present.
   - Casual and short is fine: lowercase, small grammar slips, vague references like "this" or "that text".
   - Realistic, not absurdly broken. Apart from the data kept by the data rule, it must NOT be longer than the clean instruction.
   - Do not copy the separate TEXT/INPUT into it.

2. "optimized_prompt": the best version of the instruction for an LLM.
   - Same task and same intent as the clean instruction. Do not add facts, answers or content from the text.
   - State the task clearly, then add an explicit output format and only the constraints that genuinely help.
   - Refer to the separate TEXT/INPUT as "the provided text" or "the given input". Do NOT copy it in.
   - Keep the instruction's data verbatim (data rule), e.g. end with "Items: a, b, c" for items to classify.
   - No filler or politeness. Keep it concise, usually under 60 words plus the data.

Category guidance for "optimized_prompt":
- closed_qa: answer only from the provided text; state how long the answer should be.
- information_extraction: say exactly what to extract and the output structure (e.g. a bulleted list, or JSON with named fields).
- classification: list the allowed labels explicitly when the instruction implies them; ask for the label only (or label plus a one-line reason).
- summarization: give a length (number of sentences or bullet points) and what to focus on.
- coding: name the programming language (keep the one stated; if none, use the one implied by the input, otherwise Python), describe the expected behaviour, inputs and outputs, and ask for the code in a single code block.

Return ONLY a JSON object with exactly these keys: {"degraded_prompt": "...", "optimized_prompt": "..."}'''


def build_messages(row: dict[str, Any]) -> list[dict[str, str]]:
    parts = [f"CATEGORY: {row['category']}", f"CLEAN INSTRUCTION: {row['instruction']}"]
    if row["context"]:
        parts.append("TEXT/INPUT IT REFERS TO (for understanding only, may be truncated):\n"
                     + row["context"][:MAX_CONTEXT_CHARS])
    else:
        parts.append("There is no accompanying text/input.")
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "\n\n".join(parts)}]


def parse_pair(content: str) -> tuple[str, str]:
    content = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL).strip()
    match = re.search(r"\{.*\}", content, re.DOTALL)
    try:
        data = json.loads(match.group(0) if match else content)
    except json.JSONDecodeError as e:
        raise ValueError(f"not JSON: {e}") from e
    degraded = str(data.get("degraded_prompt", "")).strip().strip('"')
    optimized = str(data.get("optimized_prompt", "")).strip().strip('"')
    if not degraded or not optimized:
        raise ValueError("missing degraded_prompt or optimized_prompt")
    return degraded, optimized


def reasoning_for(model: str) -> str | None:
    if model.startswith("openai/gpt-oss"):
        return "low"
    if model.startswith("qwen/"):
        return "none"      # skip the thinking step, saves tokens
    return None


class Checkpoint:
    """Append-only JSONL, one line per generated row, keyed by source_id."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.done: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.done[rec["source_id"]] = rec

    def add(self, rec: dict[str, Any]) -> None:
        self.done[rec["source_id"]] = rec
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def tokens_per_call(self) -> float:
        """Measured rate-limited tokens per call once MEASURE_AFTER rows have them, else the notebook's figure.
        (Rows from before cached tokens were recorded only have the raw total and are not used.)"""
        used = [r["rate_limited_tokens"] for r in self.done.values() if r.get("rate_limited_tokens")]
        return sum(used) / len(used) if len(used) >= MEASURE_AFTER else DEFAULT_TOKENS_PER_CALL


class Budget:
    """Generation may use `fraction` of each model's daily limits (its own usage, tag "generation"), and never push a
    model's total usage from every tool above `global_cap`."""

    def __init__(self, ledger: UsageLedger, fraction: float = BUDGET_FRACTION, global_cap: float = GLOBAL_CAP,
                 tag: str = "generation", limits: dict = DAILY_LIMITS):
        self.ledger, self.fraction, self.global_cap, self.tag, self.limits = ledger, fraction, global_cap, tag, limits

    def allows(self, model: str, est_tokens: float) -> bool:
        lim = self.limits[model]
        own, total = self.ledger.used(model, self.tag), self.ledger.used(model)
        return (own["requests"] + 1 <= self.fraction * lim["requests"]
                and own["tokens"] + est_tokens <= self.fraction * lim["tokens"]
                and total["requests"] + 1 <= self.global_cap * lim["requests"]
                and total["tokens"] + est_tokens <= self.global_cap * lim["tokens"])

    def left(self, model: str) -> dict[str, float]:
        lim = self.limits[model]
        own, total = self.ledger.used(model, self.tag), self.ledger.used(model)
        return {k: max(0.0, min(self.fraction * lim[k] - own[k], self.global_cap * lim[k] - total[k]))
                for k in ("requests", "tokens")}


def pace_for(tokens_per_call: float) -> float:
    """Seconds between calls that keep one model under 90% of its per-minute token limit."""
    return max(MIN_INTERVAL, 60 * tokens_per_call / (0.9 * TOKENS_PER_MINUTE))


def generate(sample: list[dict[str, Any]], ckpt: Checkpoint, llm: Any, budget: Budget,
             models: list[str] = GROQ_MODELS, max_calls: int | None = None,
             log: Callable[[str], None] = print) -> dict[str, Any]:
    """Generate the rows of `sample` not in the checkpoint, within the budget. Returns counters."""
    from app.evaluation.llm import DailyLimitReached, ModelUnavailable

    todo = [r for r in round_robin(sample) if r["source_id"] not in ckpt.done]
    stats: dict[str, Any] = {"generated": 0, "calls": 0, "parse_failures": 0, "errors": 0, "stopped": "",
                             "by_model": Counter()}
    exhausted: set[str] = set()
    for i, row in enumerate(todo, start=1):
        pair = None
        while pair is None:
            if max_calls is not None and stats["calls"] >= max_calls:
                stats["stopped"] = f"--max-calls {max_calls} reached"
                return stats
            est = ckpt.tokens_per_call()
            model = next((m for m in models if m not in exhausted and budget.allows(m, est)), None)
            if model is None:
                stats["stopped"] = "daily budget reached for every model"
                return stats
            try:
                stats["calls"] += 1
                c = llm.complete(model, build_messages(row), max_tokens=MAX_COMPLETION_TOKENS,
                                 temperature=TEMPERATURE, reasoning_effort=reasoning_for(model), json_mode=True)
            except (DailyLimitReached, ModelUnavailable) as e:
                exhausted.add(model)
                log(f"{model}: {type(e).__name__}, switching model. Groq: {str(e)[:300]}")
                continue
            except RuntimeError as e:          # repeated API errors: skip the row, it is retried next run
                stats["errors"] += 1
                log(f"  {row['source_id']}: {str(e)[:200]}")
                break
            try:
                pair = parse_pair(c.content)
            except ValueError:
                stats["parse_failures"] += 1
                row["_parse_failures"] = row.get("_parse_failures", 0) + 1
                if row["_parse_failures"] >= PARSE_ATTEMPTS:
                    log(f"  {row['source_id']}: unusable JSON {PARSE_ATTEMPTS} times, skipped until the next run")
                    break
                continue
            ckpt.add({"source_id": row["source_id"], "degraded_prompt": pair[0], "optimized_prompt": pair[1],
                      "model": c.model if c.model in models else model,
                      "tokens": c.input_tokens + c.output_tokens, "cached_tokens": c.cached_tokens,
                      "rate_limited_tokens": c.rate_limited_tokens})
            stats["generated"] += 1
            stats["by_model"][model] += 1
            llm.min_interval = pace_for(ckpt.tokens_per_call())
        if i % 25 == 0:
            log(f"[{i}/{len(todo)}] generated {stats['generated']}, calls {stats['calls']}, "
                f"{ckpt.tokens_per_call():.0f} tokens/call")
    return stats


# ---------------------------------------------------------------- quality checks (notebook Step 9)
_STOP_WORDS = set('''a an the of to in on for and or with from by about as at is are was were be this that these those
it its what which who whom how why when where me my you your i we our please pls give make tell write list create find
explain describe generate provide identify output return show using use based following given provided text input
answer question each all any some into only then than can could would should do does'''.split())
_CODE_WORDS = re.compile(r"\b(?:code|function|method|class|program|script|query|sql|regex|regular expression|html|css|"
                         r"javascript|typescript|python|java|c\+\+|c#|ruby|php|go|rust|swift|kotlin|bash|shell|"
                         r"algorithm|implement\w*|api|json|array|loop|recurs\w*)\b", re.IGNORECASE)


def _key_stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z0-9]+", str(text).lower()) if len(w) > 2 and w not in _STOP_WORDS}


def quality_flags(row: dict[str, Any], sim_deg: float, sim_opt: float) -> dict[str, bool]:
    """The notebook's hard flags for one generated pair. Any True flag fails the pair."""
    instr, deg, opt = row["instruction"], row["degraded_prompt"], row["optimized_prompt"]
    near_identical = normalize(deg) == normalize(instr) or sim_deg > 0.98
    shares = bool(_key_stems(instr) & _key_stems(opt))
    # data kept by the data rule may make the degraded prompt longer: measure it without that data
    payload = repair.extract_payload(instr, row["category"])
    deg_len = word_count(deg) - (word_count(payload.text) if payload and payload.text in deg else 0)
    return {
        "degraded_drifted": sim_deg < DEGRADED_DRIFT_THRESHOLD,
        "not_degraded": near_identical and row["has_format_spec"],
        "degraded_keeps_format_spec": has_format_spec(deg),
        "degraded_longer_than_original": deg_len > row["instruction_word_count"] * 1.25 + 3,
        "optimized_drifted": sim_opt < OPTIMIZED_DRIFT_THRESHOLD or (not shares and sim_opt < 0.50),
        "coding_target_not_code": row["category"] == "coding" and not _CODE_WORDS.search(opt),
        "optimized_too_long": word_count(opt) - (word_count(payload.text) if payload and payload.text in opt else 0)
                              > 120,
    }


def generated_rows(sample: list[dict[str, Any]], ckpt: Checkpoint,
                   embed: Callable[[list[str]], Any]) -> list[dict[str, Any]]:
    """Sample rows that have a generated pair, with similarity scores and quality flags."""
    rows = [dict(r, **{k: ckpt.done[r["source_id"]][k] for k in ("degraded_prompt", "optimized_prompt", "model")})
            for r in sample if r["source_id"] in ckpt.done]
    if not rows:
        return []
    e_o, e_d, e_p = (embed([r[k] for r in rows]) for k in ("instruction", "degraded_prompt", "optimized_prompt"))
    for r, o, d, p in zip(rows, e_o, e_d, e_p):
        r["sim_degraded_vs_original"] = round(float(sum(a * b for a, b in zip(o, d))), 3)
        r["sim_optimized_vs_original"] = round(float(sum(a * b for a, b in zip(o, p))), 3)
        r["flags"] = quality_flags(r, r["sim_degraded_vs_original"], r["sim_optimized_vs_original"])
        r["auto_pass"] = not any(r["flags"].values())
    return rows


def to_dataset_row(r: dict[str, Any]) -> dict[str, str]:
    """A generated row in the dataset's schema (id and split are set later)."""
    out = {"id": r["source_id"], "split": "train", "category": r["category"], "source_dataset": r["source_dataset"],
           "source_id": r["source_id"], "degraded_prompt": r["degraded_prompt"],
           "optimized_prompt": r["optimized_prompt"], "original_instruction": r["instruction"],
           "context": r["context"], "reference_response": r["response"], "has_context": str(r["has_context"]),
           "has_format_spec": str(r["has_format_spec"]),
           "optimized_has_format_spec": str(has_format_spec(r["optimized_prompt"])),
           "complexity_bucket": r["complexity_bucket"], "instruction_word_count": str(r["instruction_word_count"]),
           "degraded_word_count": str(word_count(r["degraded_prompt"])),
           "optimized_word_count": str(word_count(r["optimized_prompt"])),
           "context_word_count": str(r["context_word_count"]), "response_word_count": str(r["response_word_count"]),
           "sim_degraded_vs_original": str(r["sim_degraded_vs_original"]),
           "sim_optimized_vs_original": str(r["sim_optimized_vs_original"]), "human_validated": "False",
           "model": r["model"]}
    return out


# ---------------------------------------------------------------- frozen splits and ids (notebook Step 11)
def assign_splits(old: list[dict[str, str]], new: list[dict[str, str]]) -> None:
    """Set `split` on the new rows in place. Old rows are never changed."""
    held = {normalize(r["original_instruction"]): r["split"] for r in old if r["split"] != "train"}
    old_groups = {normalize(r["original_instruction"]) for r in old}
    for r in new:
        r["split"] = held.get(normalize(r["original_instruction"]), "train")      # leakage guard
    for c in CATEGORIES:
        for split, size in SPLIT_SIZES.items():
            have = sum(r["category"] == c and r["split"] == split for r in old + new)
            if have >= size:
                continue
            cands = [r for r in new if r["category"] == c and r["split"] == "train"
                     and normalize(r["original_instruction"]) not in old_groups]
            for r in stratified_pick(cands, size - have, ("complexity_bucket",), f"split-{c}-{split}"):
                r["split"] = split
    # copies of an instruction that a new row just took into a held-out split go with it
    held.update({normalize(r["original_instruction"]): r["split"] for r in new if r["split"] != "train"})
    for r in new:
        if r["split"] == "train":
            r["split"] = held.get(normalize(r["original_instruction"]), "train")


def assign_ids(old: list[dict[str, str]], new: list[dict[str, str]]) -> None:
    """New ids continue each category's numbering after the highest v1.1 id."""
    top = Counter()
    for r in old:
        top[r["category"]] = max(top[r["category"]], int(r["id"].rsplit("-", 1)[1]))
    order = {"train": 0, "val": 1, "test": 2, "benchmark": 3}
    for r in sorted(new, key=lambda r: (r["category"], order[r["split"]], r["source_id"])):
        top[r["category"]] += 1
        r["id"] = f"PO-{ABBREV[r['category']]}-{top[r['category']]:04d}"


# ---------------------------------------------------------------- build
@dataclass
class BuildResult:
    rows: list[dict[str, str]]
    new_rows: list[dict[str, str]]
    counts: Counter = field(default_factory=Counter)
    flag_counts: Counter = field(default_factory=Counter)
    repair_log: list[dict[str, str]] = field(default_factory=list)


def build(v11: list[dict[str, str]], generated: list[dict[str, Any]], nlp: Any = None,
          regen_cache: dict[str, str] | None = None) -> BuildResult:
    res = BuildResult(rows=[], new_rows=[])
    old_ids = {r["source_id"] for r in v11}
    passing = []
    for g in generated:
        if g["source_id"] in old_ids:
            continue
        res.counts[(g["category"], "generated")] += 1
        for name, hit in g["flags"].items():
            res.flag_counts[(g["category"], name)] += hit
        if g["auto_pass"]:
            res.counts[(g["category"], "auto_pass")] += 1
            passing.append(to_dataset_row(g))
    rep = repair.run(passing, nlp, regen_cache)
    for (c, k), n in rep.counts.items():
        if k != "total":
            res.counts[(c, k)] += n
    new = rep.rows
    assign_splits(v11, new)
    assign_ids(v11, new)
    final = {r["source_id"]: r for r in new}
    for e in rep.log:
        r = final.get(e["id"])          # the log was written with the temporary id (= source_id)
        res.repair_log.append(dict(e, id=r["id"] if r else e["id"], split=r["split"] if r else "removed"))
    for r in new:
        res.counts[(r["category"], "added")] += 1
    res.new_rows = new
    res.rows = [dict(r) for r in v11] + sorted(new, key=lambda r: r["id"])
    return res


def write(res: BuildResult, out_dir: Path = V12_DIR) -> None:
    rep = repair.Report(rows=res.rows, log=res.repair_log)
    repair.write(rep, out_dir, csv_name=V12_CSV_NAME, columns=FINAL_COLUMNS)
    (out_dir / "build_report.md").write_text(report_text(res), encoding="utf-8")


def report_text(res: BuildResult) -> str:
    cols = ["generated", "auto_pass", "rows_repaired", "subject_dropped", "regenerated", "removed", "added"]
    lines = ["# Dataset v1.2 build", "", "## New rows", "", "| category | " + " | ".join(cols) + " |",
             "|---" * (len(cols) + 1) + "|"]
    for c in CATEGORIES:
        lines.append(f"| {c} | " + " | ".join(str(res.counts[(c, k)]) for k in cols) + " |")
    flags = sorted({k for _, k in res.flag_counts})
    lines += ["", "## Quality flags (new rows that hit each flag)", "", "| category | " + " | ".join(flags) + " |",
              "|---" * (len(flags) + 1) + "|"]
    for c in CATEGORIES:
        lines.append(f"| {c} | " + " | ".join(str(res.flag_counts[(c, f)]) for f in flags) + " |")
    splits = ["train", "val", "test", "benchmark"]
    lines += ["", "## Rows per split (v1.1 + new)", "", "| category | " + " | ".join(splits) + " | total |",
              "|---" * (len(splits) + 2) + "|"]
    for c in CATEGORIES:
        n = Counter(r["split"] for r in res.rows if r["category"] == c)
        lines.append(f"| {c} | " + " | ".join(str(n[s]) for s in splits) + f" | {sum(n.values())} |")
    models = Counter(r["model"] for r in res.new_rows)
    lines += ["", "New rows per generating model: " + ", ".join(f"{m} {n}" for m, n in models.most_common())]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- CLI
def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_or_make_sample(out_dir: Path) -> tuple[list[dict[str, Any]], dict[str, CategoryPlan]]:
    v11, v1_sampled = _read_csv(V11_CSV), _read_csv(V1_SAMPLED)
    sources = load_sources()
    check_source_ids(sources, v11)
    pool = clean_pool(sources)
    plans = plan_categories(pool, v11, v1_sampled)
    path = out_dir / "sample.jsonl"
    frozen = _read_jsonl(path) if path.exists() else []
    used = {r["source_id"] for r in v1_sampled} | {r["source_id"] for r in v11}
    sample = sample_rows(pool, plans, used, frozen)
    if len(sample) != len(frozen):
        _write_jsonl(path, sample)
    return sample, plans


def plan_text(plans: dict[str, CategoryPlan], sample: list[dict[str, Any]], ckpt: Checkpoint, budget: Budget,
              models: list[str]) -> str:
    per_call = ckpt.tokens_per_call()
    measured = sum(1 for r in ckpt.done.values() if r.get("tokens")) >= MEASURE_AFTER
    lines = ["| category | v1.1 rows | v1 pass rate | still needed | unused source rows | sampled | generated | "
             "expected rows |", "|---|---|---|---|---|---|---|---|"]
    remaining = 0
    for c in CATEGORIES:
        p = plans[c]
        n = sum(r["category"] == c for r in sample)
        done = sum(r["category"] == c and r["source_id"] in ckpt.done for r in sample)
        remaining += n - done
        lines.append(f"| {c} | {p.v11_rows} | {100 * p.pass_rate:.1f}% | {p.needed} | {p.unused} | {n} | {done} | "
                     f"~{p.v11_rows + round(n * p.pass_rate)} |")
    regen_calls = math.ceil(len(sample) * 0.03 / repair.ROWS_PER_CALL)      # v1.1: ~3% subject drops
    calls = remaining + regen_calls
    tokens = calls * per_call
    daily = sum(budget.fraction * DAILY_LIMITS[m]["tokens"] for m in models)
    today = sum(budget.left(m)["tokens"] for m in models)
    lines += ["", f"Tokens per call: {per_call:.0f} ({'measured' if measured else 'notebook estimate'}).",
              f"Remaining: {remaining} generation calls + ~{regen_calls} subject-repair calls = ~{calls} calls, "
              f"~{tokens / 1e6:.2f}M tokens.",
              f"Budget: {budget.fraction:.0%} of {len(models)} models x 200K tokens = {daily / 1e3:.0f}K tokens/day "
              f"(~{daily / per_call:.0f} calls); left today: {today / 1e3:.0f}K tokens (~{today / per_call:.0f} calls).",
              f"Estimated days: {tokens / daily:.1f}. Pace: {pace_for(per_call):.1f} s between calls "
              f"(8K tokens/min per model)."]
    return "\n".join(lines)


def _embedder() -> Callable[[list[str]], Any]:
    from sentence_transformers import SentenceTransformer

    from app.config import SENTENCE_MODEL

    model = SentenceTransformer(SENTENCE_MODEL)
    return lambda texts: model.encode(list(texts), batch_size=64, normalize_embeddings=True, show_progress_bar=False)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=V12_DIR)
    ap.add_argument("--budget-fraction", type=float, default=BUDGET_FRACTION,
                    help="share of each model's daily limit generation may use (default 0.7)")
    ap.add_argument("--models", nargs="+", default=GROQ_MODELS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan", help="sample the new rows and estimate Groq usage (no Groq calls)")
    g = sub.add_parser("generate", help="generate pairs within today's budget (resumable)")
    g.add_argument("--max-calls", type=int, help="stop after this many generation calls")
    g.add_argument("--max-repair-calls", type=int, default=20, help="Groq calls for subject repairs after generation")
    sub.add_parser("build", help="quality checks, repair, splits -> v1.2 files (works on a partial run)")
    args = ap.parse_args(argv)

    ledger = UsageLedger()
    budget = Budget(ledger, args.budget_fraction)
    ckpt = Checkpoint(args.out / "generation_checkpoint.jsonl")
    sample, plans = load_or_make_sample(args.out)

    if args.cmd == "plan":
        print(plan_text(plans, sample, ckpt, budget, args.models))
        return

    if args.cmd == "generate":
        from app.evaluation.llm import GroqChat

        llm = GroqChat(min_interval=pace_for(ckpt.tokens_per_call()), ledger=ledger, tag="generation")
        stats = generate(sample, ckpt, llm, budget, args.models, args.max_calls)
        print(f"Generation: {stats['generated']} rows in {stats['calls']} calls "
              f"({dict(stats['by_model'])}); parse failures {stats['parse_failures']}, errors {stats['errors']}. "
              f"Stopped: {stats['stopped'] or 'all sampled rows generated'}")
        _repair_subjects(sample, ckpt, args, budget, llm)
        print(plan_text(plans, sample, ckpt, budget, args.models))
        return

    import spacy

    gen = generated_rows(sample, ckpt, _embedder())
    cache_path = args.out / "regenerated.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    res = build(_read_csv(V11_CSV), gen, spacy.load("en_core_web_sm"), cache)
    write(res, args.out)
    print(report_text(res))
    print(f"wrote {len(res.rows)} rows ({len(res.new_rows)} new) to {args.out}")


def _repair_subjects(sample, ckpt, args, budget, llm) -> None:
    """Groq edits for new rows whose optimized prompt dropped the subject (cached for `build`), within the budget."""
    import spacy

    gen = [g for g in generated_rows(sample, ckpt, _embedder()) if g["auto_pass"]]
    rows = [to_dataset_row(g) for g in gen]
    cands = repair.subject_candidates(rows, spacy.load("en_core_web_sm"))
    cache_path = args.out / "regenerated.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    todo = [c for c in cands if c["id"] not in cache]
    model = repair.REGEN_MODEL
    calls_left = int(budget.left(model)["requests"])
    per_call = 5 * ckpt.tokens_per_call()               # a batch of 5 rows costs about 5 generation calls
    calls = min(args.max_repair_calls, calls_left, int(budget.left(model)["tokens"] // per_call))
    if not todo or calls <= 0:
        print(f"Subject repairs: {len(todo)} pending, {calls} calls available now")
        return
    made = repair.regenerate(todo, llm, cache, calls, model)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Subject repairs: {made} calls for {min(len(todo), made * repair.ROWS_PER_CALL)} of {len(todo)} rows")


if __name__ == "__main__":
    main()
