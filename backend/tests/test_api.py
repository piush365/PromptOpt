"""FastAPI endpoints, offline: in-memory DB, keyword classifier, Stage C off or faked."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import api
from app.db.base import Base, get_db
from app.db.seed import seed_rules
from app.stage_a.classifier import KeywordClassifier
from app.stage_a.detector import FeatureDetector


class FakeStageC:
    name, device = "fake", "cpu"

    def generate(self, messages):
        return json.dumps({"output_format": "Use bullet points.", "constraints": [], "category": "summarization"})


@pytest.fixture(params=[None, FakeStageC()], ids=["no_stage_c", "fake_stage_c"])
def client(request, monkeypatch):
    # one shared in-memory connection: TestClient runs the endpoints in another thread
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
    monkeypatch.setattr(api, "stage_c_model", lambda: request.param)
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def test_ui_and_options(client):
    assert "PromptOpt" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    opt = client.get("/api/options").json()
    assert opt["targets"] == ["claude", "gpt", "gemini"] and "spreadsheet" in opt["attachment_types"]
    assert opt["compare_enabled"] is False


def test_optimize_returns_everything_the_ui_shows(client):
    r = client.post("/api/optimize", json={"prompt": "hey can you summarize this report for me", "target": "claude",
                                           "category": "auto", "attachment_type": "pdf",
                                           "attachment_name": "q3.pdf"}).json()
    assert set(r["renderings"]) == {"claude", "gpt", "gemini"} and r["target"] == "claude"
    assert r["renderings"]["claude"].startswith("<context>") and "q3.pdf" in r["renderings"]["gpt"]
    assert r["tokens"]["gpt"]["tokens"] > 0 and r["tokens"]["claude"]["exact"] is False
    assert "B10_ATTACHMENT_PDF" in [x["code"] for x in r["rules"]]
    assert any(i["code"] == "A04" for i in r["issues"])                  # filler detected
    assert r["category"]["stage_a"] == r["stage_a"]["category"]


def test_user_category_disagreement_is_reported(client):
    r = client.post("/api/optimize", json={"prompt": "summarize this article in bullet points",
                                           "category": "coding", "context": "Some article."}).json()
    assert r["category"] == {"used": "coding", "source": "user", "requested": "coding", "stage_a": "summarization",
                             "disagreement": True, "uncertain": False, "guess": None}


def test_stage_c_routing_is_reported(client):
    r = client.post("/api/optimize", json={"prompt": "describe what is happening in the picture",
                                           "attachment_type": "image"}).json()
    s = r["stage_c"]
    assert s["routed"]
    if s["available"]:
        # keyword classifier: "other" with confidence 1.0, so Stage C's guess is outside Stage A's top two and the
        # category is left for the user; Stage C's format is still applied
        assert s["used"] and s["accepted"] and s["category_status"] == "uncertain"
        assert r["category"]["uncertain"] and r["category"]["guess"] == "summarization"
        assert r["category"]["source"] == "stage_a" and "Use bullet points." in r["renderings"]["gemini"]
    else:
        assert not s["used"] and r["category"]["source"] == "stage_a"


def test_history_and_compare(client):
    pid = client.post("/api/optimize", json={"prompt": "list the dates mentioned"}).json()["prompt_id"]
    assert client.get("/api/history").json()[0]["prompt_id"] == pid
    item = client.get(f"/api/history/{pid}").json()
    assert item["original_text"] == "list the dates mentioned" and item["results"][0]["renderings"]
    assert client.get("/api/history/999999").status_code == 404
    assert client.post("/api/compare").status_code == 501


def test_validation_errors(client):
    assert client.post("/api/optimize", json={"prompt": ""}).status_code == 422
    assert client.post("/api/optimize", json={"prompt": "x", "target": "llama"}).status_code == 422
    assert client.post("/api/optimize", json={"prompt": "x", "attachment_type": "zip"}).status_code == 422


def test_uncertain_category_is_reported_for_the_ui(monkeypatch):
    class Guess(FakeStageC):
        def generate(self, messages):
            return json.dumps({"output_format": "Output one label per line.", "constraints": [],
                               "category": "classification"})
    from app.stage_a.schema import PromptFeatures

    class Det:                                  # Stage A unsure, and classification not in its top two
        def detect(self, prompt, context=None):
            return PromptFeatures(task_type="coding", confidence=0.45, classifier="test", has_format_spec=False,
                                  has_context=False, word_count=len(prompt.split()),
                                  category_scores={"coding": 0.45, "summarization": 0.35, "classification": 0.2})
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as s:
        seed_rules(s)

    def session():
        with Session() as s:
            yield s
    api.app.dependency_overrides[get_db] = session
    monkeypatch.setattr(api, "detector", lambda: Det())
    monkeypatch.setattr(api, "stage_c_model", lambda: Guess())
    try:
        r = TestClient(api.app).post("/api/optimize", json={"prompt": "which season goes with snow"}).json()
    finally:
        api.app.dependency_overrides.clear()
    assert r["category"]["uncertain"] and r["category"]["guess"] == "classification"
    assert r["category"]["used"] == "coding" and "task category" in r["unresolved"]
    assert r["stage_c"]["category_status"] == "uncertain"
