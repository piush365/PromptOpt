"""The v2 UI's endpoints (app.ui_api) and page routes: offline, in-memory DB, keyword classifier, Stage C off."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import api, ui_api
from app.db.base import Base, get_db
from app.db.seed import seed_rules
from app.stage_a.classifier import KeywordClassifier
from app.stage_a.detector import FeatureDetector


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as s:
        seed_rules(s)

    def session():
        with Session() as s:
            yield s
    api.app.dependency_overrides[get_db] = session
    monkeypatch.setattr(api, "detector", lambda: FeatureDetector(classifier=KeywordClassifier(), use_spacy=False))
    monkeypatch.setattr(api, "stage_c_model", lambda: None)
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def optimize(client, prompt, **kw):
    return client.post("/api/optimize", json={"prompt": prompt, "target": "gpt", **kw}).json()


def test_pages_classic_and_unknown(client):
    assert "PromptOpt" in client.get("/").text
    assert "PromptOpt" in client.get("/classic").text and "/static/app.js" in client.get("/classic").text
    if api.UI_INDEX.exists():                                # the built v2 UI is committed in app/static/ui
        for page in api.UI_PAGES:
            assert client.get(f"/{page}").text == client.get("/").text
        assert client.get("/favicon.ico").status_code == 200
    assert client.get("/no-such-page").status_code == 404


def test_tokens_counts_the_raw_prompt_per_target(client):
    r = client.post("/api/ui/tokens", json={"text": "write code to get all permutations of a string"}).json()
    assert set(r) == {"claude", "gpt", "gemini"}
    assert r["claude"]["exact"] is False and r["claude"]["tokens"] == round(46 / 4)
    assert client.post("/api/ui/tokens", json={"text": ""}).json()["gemini"]["tokens"] == 0


def test_examples_are_valid_requests(client):
    ex = client.get("/api/ui/examples").json()["examples"]
    assert {e["kind"] for e in ex} >= {"coding", "closed_qa", "information_extraction", "classification",
                                       "summarization", "attachment", "image_generation"}
    hackpad = next(e for e in ex if e["id"] == "hackpad")
    assert "Dropbox" in hackpad["context"] and hackpad["prompt"].startswith("which company bought hackpad")
    for e in ex:                                             # every example is accepted by /api/optimize
        body = {"prompt": e["prompt"], "target": e["target"], "category": e["category"],
                "attachment_type": e.get("attachment_type", "none"), "context": e.get("context")}
        assert client.post("/api/optimize", json=body).status_code == 200, e["id"]


def test_parse_report_sections_tables_and_headline():
    md = """# Title

<!-- TOKEN:x:start -->
**Optimized prompts reduce total tokens by 39.2% (95% CI 35.9–42.5%, n = 482)** (`x`)
<!-- TOKEN:x:end -->

## 1. Headline numbers (test)

| what | result |
|---|---|
| Stage A accuracy | **74.7%** |
| B07 `structure` | 3.1% -> 95.0% |

### 4.1 Per-rule accuracy

Intro line one
continues here.

* a bullet
  wrapped
"""
    s = ui_api.parse_report(md)
    assert [x["id"] for x in s] == ["1", "4.1"]
    t = s[0]["tables"][0]
    assert t["headers"] == ["what", "result"] and t["rows"][0] == ["Stage A accuracy", "74.7%"]
    assert t["bold"] == [True, False] and t["rows"][1][0] == "B07 structure"
    assert s[1]["intro"] == ["Intro line one continues here."] and s[1]["bullets"] == ["a bullet wrapped"]
    assert ui_api.token_headline(md) == {"reduction_pct": 39.2, "ci_low": 35.9, "ci_high": 42.5, "n": 482}


def test_results_come_from_the_report(client):
    r = client.get("/api/ui/results").json()
    text = ui_api.FINAL_RESULTS.read_text(encoding="utf-8")
    assert r["tokens"]["n"] == 482 and f'{r["tokens"]["reduction_pct"]}%' in text
    ids = [s["id"] for s in r["sections"]]
    assert {"1", "3", "4", "4.1", "5.1", "5.2", "9a"} <= set(ids)
    headline = next(s for s in r["sections"] if s["id"] == "1")["tables"][0]
    assert all(row[1] and row[1] in text.replace("**", "") for row in headline["rows"])


def test_suite_grid_matches_the_stored_run(client):
    g = client.get("/api/ui/suite-grid").json()
    assert len(g["cases"]) == 50 and all(c["vague_prompt"] for c in g["cases"])
    for mid, rows in g["verdicts"].items():
        summary = next(m["summary"] for m in g["models"] if m["id"] == mid)
        assert sum(r["vague"] for r in rows.values()) == summary["vague"]
        assert sum(r["optimized"] for r in rows.values()) == summary["optimized"]
        assert sum(r["status"] == "fixed" for r in rows.values()) == summary["only_optimized"]
        assert sum(r["status"] == "hurt" for r in rows.values()) == summary["only_vague"]


def test_history_search_paging_and_delete(client):
    a = optimize(client, "write code to reverse a string")
    b = optimize(client, "summarize this article for me, email me at x@example.com")
    img = client.post("/api/optimize", json={"prompt": "a red fox, watercolor", "target": "dalle",
                                             "category": "image_generation"}).json()
    h = client.get("/api/ui/history").json()
    assert h["total"] == 3 and [i["prompt_id"] for i in h["items"]] == [img["prompt_id"], b["prompt_id"], a["prompt_id"]]
    first = h["items"][-1]
    assert first["category"] == "coding" and first["target"] == "gpt" and first["changes"] > 0
    assert h["items"][0]["mode"] == "image"
    assert "x@example.com" not in h["items"][1]["text"]                    # stored after PII scrubbing
    assert [i["prompt_id"] for i in client.get("/api/ui/history?q=REVERSE").json()["items"]] == [a["prompt_id"]]
    assert client.get("/api/ui/history?q=Use%20Python").json()["total"] == 1   # searches the optimized text too
    assert len(client.get("/api/ui/history?limit=1&offset=1").json()["items"]) == 1
    assert client.delete(f"/api/ui/history/{a['prompt_id']}").json() == {"deleted": a["prompt_id"]}
    assert client.get(f"/api/history/{a['prompt_id']}").status_code == 404
    assert client.delete(f"/api/ui/history/{a['prompt_id']}").status_code == 404
    assert client.get("/api/ui/history").json()["total"] == 2


def test_compare_history_and_status(client):
    assert client.get("/api/ui/compare-history").json() == []
    s = client.get("/api/ui/status").json()
    assert s["stage_c"] == {"available": False, "model": None, "device": None}
    ids = [p["id"] for p in s["providers"]]
    assert "openai/gpt" in ids and "anthropic/claude" in ids
    for p in s["providers"]:
        assert p["available"] or p["reason"]
        assert "key" not in {k.lower() for k in p} and not any(str(v).startswith(("gsk_", "csk-")) for v in p.values())
