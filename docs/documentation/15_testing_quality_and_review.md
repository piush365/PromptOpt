# 15. Testing, quality assurance, and the 2026-10-10 review

[Back to the index](README.md)

---

## 15.1 The backend test suite

`python -m pytest -q` inside `backend/` (with `.venv` active): **777 tests, all passing**, about 25–35 seconds,
**offline** (no API calls: providers are faked or replayed from recordings; Stage A uses the keyword classifier unless
a test needs the index). Tests run on in-memory SQLite; set `TEST_POSTGRES_URL` to also run every database test on
PostgreSQL (that database's tables are dropped — use a dedicated test database).

| file | test functions | covers |
|---|---|---|
| `test_stage_a.py` | 27 | detectors A02–A05 on positive and negative examples, context detection, classifiers, the backstop |
| `test_stage_b.py` | 56 | every rule B01–B15 separately, rule order, the gate, B08 combinations, labels, single-item format, routing, confidence, ablation switches |
| `test_stage_c_contract.py` | 11 | requested fields, validation (each failure mode), patching, locked fields, category policy |
| `test_stage_c_parse.py` | 5 | the optimized-prompt parser |
| `test_rendering.py` | 15 | round-trip of every rendering, metadata never rendered, order, fences, token counting, pipeline storage incl. Stage C steps |
| `test_api.py` | 13 | endpoints with and without (fake) Stage C, image mode, coding tests, history, blank prompts (422), retention |
| `test_ui_api.py` | 8 | status, examples, token counter, results parsing, suite grid, history search/delete |
| `test_compare.py` | 9 | Compare with recorded answers, stand-in labels, budget refusal, Gemini client (key never in URL or errors), per-minute vs per-day 429, PII-scrubbed inputs |
| `test_db.py` | 7 | schema constraints, cascade, PII scrubbing, retention purge |
| `test_coding.py` | 16 | sandbox (timeout, memory, network, host files, output and fork limits, refusal without bwrap), harness, naming |
| `test_evaluation.py` | 39 | variants, judge parsing and shortening, task success, harness resumability, summaries and exclusions |
| `test_tokens_eval.py` | 2 | token report statistics |
| `test_cerebras.py` | 7 | Cerebras client pacing, limits, errors |
| `test_correctness.py` | 16 | case validation, scoring per category, McNemar |
| `test_image.py`, `test_image_v2.py` | 12, 10 | image detectors, v1 rules and renderers, v2 rules, suggestions, conflicts |
| `test_dataset_expand.py`, `test_dataset_repair.py`, `test_validation.py`, `test_reference_check.py` | 27, 14, 28, 4 | dataset tooling, agreement statistics |
| `test_rule_accuracy.py`, `test_attachment_eval.py`, `test_demo.py` | 7, 2, 5 | evaluation scripts and the demo |

(Parametrized tests run several cases per function, hence 777 tests from 340 functions.)

**Frontend:** `npx tsc -b` (strict type check) and the Playwright end-to-end suite (chapter 14.5).

**Freeze check:** `python -m app.freeze_check` (chapter 1.5.2) — byte-identical to `frozen-for-test` before and after
this review.

## 15.2 Conventions that keep the code testable (from `CLAUDE.md`)

* Every Stage B rule is a separate pure function with its own unit tests.
* The pipeline reads and writes the database only through `db/repository.py`; functions flush, the caller commits
  once per request.
* Secrets only in `backend/.env`; never hard-coded or committed.
* New features come with tests; the full suite is run before saying something works.
* After the freeze: no Stage A/B rule, threshold or judge change; bugs are reported, not fixed; post-freeze rules must
  prove (freeze check) that they act only with an attachment.

## 15.3 The 2026-10-10 review: method

1. Read every backend module (Stage A/B/C, rendering, pipeline, API, Compare, coding, image, evaluation, correctness,
   dataset tools) and the frontend's structure, API client and tests; cross-checked the existing docs against code
   and reports.
2. Baseline: full test suite (771 passed), freeze check (byte-identical), frontend type check (clean).
3. Probed suspected bugs with small scripts against the running app (FastAPI `TestClient`).
4. Fixed what is outside the frozen pipeline, with a test for each fix; re-ran the full suite (777 passed) and the
   freeze check (still byte-identical, `35f7d4dc…`).
5. Reported, without fixing, what would change the frozen pipeline or a committed artifact's hash.

## 15.4 Fixed in this review

| # | problem (severity) | evidence | fix | test |
|---|---|---|---|---|
| 1 | **Retention was never enforced** (privacy, high): the app promised "kept 30 days, then deleted", but only a manual `init_db --purge` deleted anything; expired prompts stayed listed and viewable in History | a 31-day-old prompt was returned by `/api/history`, `/api/ui/history` and `/api/history/{id}` | `app/retention.py`: a FastAPI dependency deletes expired prompts before every endpoint that stores, reads or lists prompts | `test_expired_prompts_are_deleted_before_history_is_shown` |
| 2 | **Blank prompt → HTTP 500** (robustness, medium): `"   "` passed Pydantic's `min_length=1`, then `create_prompt` raised `DataValidationError` | `POST /api/optimize` with a whitespace prompt returned 500 (text and image mode) | exception handler maps `DataValidationError` to **422** with the message | `test_blank_prompt_is_rejected_with_422_not_500` |
| 3 | **Compare sent un-scrubbed text to the provider** (privacy + fairness, high): the optimized prompt was built from the PII-scrubbed text, but the *original* variant sent the raw prompt and pasted text — emails/phone numbers left the machine and the two variants got different inputs | code path in `api.compare` | both variants use the stored (scrubbed) prompt and scrubbed pasted text | `test_api_compare_sends_both_prompts_pii_scrubbed` |
| 4 | **Gemini per-minute 429 treated as daily quota** (correctness, low): any 429 containing "quota" stopped Compare for the day | Gemini's per-minute and per-day 429s both say "Quota exceeded" | classify by the quota id (`…PerDay…` vs `…PerMinute…`); per-minute is waited out and retried | `test_gemini_per_minute_limit_is_retried_per_day_limit_stops` |
| 5 | **Tests wrote into the real Compare cache** (test isolation, medium): `compare()`'s default cache path was bound at import time, so the tests' monkeypatch had no effect and fixture answers were appended to `data/compare/cache.jsonl` — a user comparing the same prompt would have been served the fake answer | the cache held the fixture's answers (latency 980/610 ms, exactly `compare_recorded.json`) | the path is read at call time; the 4 test-written cache lines were removed (backup kept) | full suite run with a timestamp marker: nothing under `data/`, `evaluation/`, `docs/` is written |
| 6 | SQLite path relative to the working directory (low): a command run from another directory created a second, empty database | `sqlite:///./promptopt.db` | default is `backend/promptopt.db` as an absolute path | – |
| 7 | Judge budget used a literal 200,000 (maintainability, low) | `compare/service.py` | uses `DAILY_LIMITS[JUDGE_MODEL]` | existing tests |
| 8 | Stale texts (docs/UI): the unvalidated-tests note promised that Compare would run them; diagrams/report said the UI was HTML/JS; README said "about 700 tests" | – | corrected; diagram 01 (SVG + PNG) regenerated from its own SVG with the new label | – |

## 15.5 Reported, not fixed (frozen pipeline or committed hashes)

| issue | where | effect | why not fixed |
|---|---|---|---|
| **B06 label glue:** "Is a tomato a fruit or a vegetable?" → labels `"tomato a fruit"`, `"vegetable"` | `stage_b/rules.py`, third `LABEL_PATTERNS` entry | a wrong label set for single-item "is X a Y or Z" questions | frozen Stage B (freeze check would change) |
| **Curly-quote typo:** `_QUOTED = [\"“'']…` lists `'` twice where `‘ ’` were intended | `stage_a/rules.py`, `detect_embedded_context` | a 40+ character passage in curly single quotes is not recognized as context by this pattern (other signals usually fire) | frozen Stage A |
| **Leftover gradient accumulation across epochs:** the accumulation counter restarts each epoch without clearing gradients, so the last 8 micro-batches of an epoch add to the next epoch's first step | `stage_c/train.py` | one optimizer step per epoch boundary is 1.5× normal size before clipping; epochs have 278, not 279, steps | the script's SHA-256 is in the committed Stage C data manifest; the trained adapter is the evaluated artifact |
| Claude XML tags are not escaped | `rendering.py` | data containing `</input>` could be read as the end of the block | changing renderings changes stored outputs; low risk; documented |
| SQLite reuses the id of a deleted highest row | SQLite `INTEGER PRIMARY KEY` | after a purge/delete, a new prompt can get an old prompt's id (an old History link would show the new prompt); PostgreSQL sequences never reuse ids | would need `AUTOINCREMENT` and a schema migration for existing databases |
| `token_usage.est_cost_*` never filled | `db/models.py` | no money cost stored | free tiers cost 0; chapter 8.6 gives the formula |
| Regex detectors miss phrasings (e.g. tone in "a short formal email") | Stage A | missed constraints | frozen Stage A; documented limitation |

The B06 label issue and the tone-detection gap were already reported in `docs/HOW_IT_WORKS.md` under the freeze
rule; the others were found in this review.
