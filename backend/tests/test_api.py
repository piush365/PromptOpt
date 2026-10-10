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
    assert isinstance(opt["compare_enabled"], bool)             # True when any Compare model has a key


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
    assert client.post("/api/compare", json={"prompt": "x", "model": "nope"}).status_code == 422


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


def test_coding_prompt_shows_dataset_tests_or_offers_generation(client, monkeypatch):
    from app.coding import app_tests
    item = {"degraded_prompt": "write fn to add two numbers", "tests": ["assert add(1, 2) == 3"], "entry": "add",
            "source_id": "codealpaca-1", "mode": "function"}
    monkeypatch.setattr(app_tests, "_items", lambda: {"write fn to add two numbers": item})
    monkeypatch.setattr(app_tests, "can_generate", lambda: False)
    r = client.post("/api/optimize", json={"prompt": "Write fn to add  two numbers", "category": "coding"}).json()
    assert r["coding_tests"]["tests"]["validated"] and r["coding_tests"]["tests"]["tests"] == item["tests"]
    r = client.post("/api/optimize", json={"prompt": "write a function that reverses a list",
                                           "category": "coding"}).json()
    assert r["coding_tests"] == {"tests": None, "can_generate": False}
    assert client.post("/api/coding-tests", json={"optimized_prompt": "x"}).status_code == 503
    r = client.post("/api/optimize", json={"prompt": "summarize this article", "category": "summarization",
                                           "context": "Text."}).json()
    assert r["coding_tests"] is None


def test_generated_tests_are_marked_unvalidated(tmp_path, monkeypatch):
    from app.coding import app_tests

    class LLM:
        def complete(self, *a, **k):
            from app.evaluation.llm import Completion
            return Completion('{"function": "rev", "signature": "def rev(xs):", "tests": '
                              '["assert rev([1, 2]) == [2, 1]", "print(1)"]}', "m", 1, 1, None, 1, "stop")
    monkeypatch.setattr(app_tests, "OUT_DIR", tmp_path)
    out = app_tests.generate("Write a function that reverses a list.", llm=LLM())
    assert out["validated"] is False and out["tests"] == ["assert rev([1, 2]) == [2, 1]"]
    assert "UNVALIDATED" in out["note"]
    assert app_tests.generate("Write a function that reverses a list.", llm=None)["tests"] == out["tests"]  # cached


def test_image_mode_is_separate_and_explicit(client):
    r = client.post("/api/optimize", json={"prompt": "can you make me a picture of a cat on a windowsill, no text",
                                           "category": "image_generation", "target": "stable_diffusion"}).json()
    assert r["mode"] == "image" and r["version"] == "v2" and r["target"] == "stable_diffusion"
    assert set(r["renderings"]) == {"dalle", "nano_banana", "stable_diffusion"}
    sd = r["renderings"]["stable_diffusion"]
    assert sd["prompt"] == "A cat on a windowsill" and sd["negative_prompt"] == "text"
    assert r["avoid_user"] == ["text"] and r["accepted"] == []
    offered = {s["attribute"] for s in r["suggestions"]}
    assert {"lighting", "style", "palette"} <= offered
    assert all(x["code"].startswith("I") for x in r["rules"]) and "stage_a" not in r
    item = client.get(f"/api/history/{r['prompt_id']}").json()
    assert item["results"][0]["ir"]["mode"] == "image" and "Negative prompt" in \
        item["results"][0]["renderings"]["stable_diffusion"]
    # never auto-detected: the same prompt in text mode goes through Stage A/B
    t = client.post("/api/optimize", json={"prompt": "a picture of a cat"}).json()
    assert t.get("mode") != "image" and "stage_a" in t
    # targets must match the mode
    assert client.post("/api/optimize", json={"prompt": "a cat", "category": "image_generation",
                                              "target": "gpt"}).status_code == 422
    assert client.post("/api/optimize", json={"prompt": "a cat", "target": "dalle"}).status_code == 422
    assert client.get("/api/options").json()["image_targets"] == ["dalle", "nano_banana", "stable_diffusion"]


def test_image_suggestions_are_added_only_when_accepted(client):
    body = {"prompt": "a dog", "category": "image_generation", "target": "dalle"}
    r = client.post("/api/optimize", json=body).json()
    assert r["renderings"]["dalle"]["prompt"] == "A dog."
    assert "lighting" in {s["attribute"] for s in r["suggestions"]}
    r = client.post("/api/optimize", json={**body, "accepted_suggestions": ["lighting:soft daylight",
                                                                            "aspect_ratio:16:9"]}).json()
    assert "Lighting: soft daylight." in r["renderings"]["dalle"]["prompt"]
    assert r["renderings"]["dalle"]["params"] == {"size": "1792x1024"} and r["accepted"] == [
        "lighting:soft daylight", "aspect_ratio:16:9"]
    assert "lighting" not in {s["attribute"] for s in r["suggestions"]}
    assert client.post("/api/optimize", json={**body, "accepted_suggestions": ["lighting:laser show"]}
                       ).status_code == 422


def test_blank_prompt_is_rejected_with_422_not_500(client):
    for body in ({"prompt": "   \n ", "target": "gpt"},
                 {"prompt": "  ", "target": "dalle", "category": "image_generation"}):
        r = client.post("/api/optimize", json=body)
        assert r.status_code == 422 and "empty" in r.json()["detail"]


def test_expired_prompts_are_deleted_before_history_is_shown(client):
    from datetime import timedelta

    from sqlalchemy import func, select

    from app.db import repository as repo
    from app.db.models import Prompt, utcnow
    fresh = client.post("/api/optimize", json={"prompt": "summarize this", "target": "gpt"}).json()["prompt_id"]
    session = next(api.app.dependency_overrides[get_db]())
    old = repo.create_prompt(session, "an old prompt", now=utcnow() - timedelta(days=31))
    session.commit()
    assert old.id != fresh
    assert client.get(f"/api/history/{old.id}").status_code == 404
    assert [h["prompt_id"] for h in client.get("/api/history").json()] == [fresh]
    assert [h["prompt_id"] for h in client.get("/api/ui/history").json()["items"]] == [fresh]
    session.rollback()
    assert session.scalar(select(func.count()).where(Prompt.id == old.id)) == 0      # deleted, not just hidden


def test_spelling_suggestions_and_b16_in_the_app(client):
    from app import spelling
    r = client.post("/api/optimize", json={"prompt": "frm the list tell me prog lang or animal panda pythom java sanke bunny",
                                           "target": "gpt", "category": "classification"}).json()
    if spelling.available():
        assert [t["word"] for t in r["spelling"]] == ["frm", "pythom", "sanke"]
    assert any(x["code"] == "B16_LABELS_WIDER" and x["what"] for x in r["rules"])     # app path runs the extensions
    assert '"prog lang", "animal"' in r["renderings"]["gpt"]
    steps = client.get(f"/api/history/{r['prompt_id']}").json()["results"][0]["steps"]
    assert any(s["rule"] == "B16_LABELS_WIDER" for s in steps)                         # stored with its seeded rule
    assert "spelling_available" in client.get("/api/options").json()


def test_network_password_only_for_other_machines(client, monkeypatch):
    import base64
    remote = TestClient(api.app, client=("192.168.1.50", 50000))
    local = TestClient(api.app, client=("127.0.0.1", 50000))
    assert remote.get("/api/options").status_code == 200                 # no password configured: open
    monkeypatch.setenv("PROMPTOPT_PASSWORD", "s3cret")
    r = remote.get("/api/options")
    assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Basic")
    good = {"Authorization": "Basic " + base64.b64encode(b"anyone:s3cret").decode()}
    bad = {"Authorization": "Basic " + base64.b64encode(b"anyone:wrong").decode()}
    assert remote.get("/api/options", headers=good).status_code == 200
    assert remote.get("/api/options", headers=bad).status_code == 401
    assert remote.get("/", headers={"Authorization": "Basic !!!"}).status_code == 401
    assert local.get("/api/options").status_code == 200                  # this machine never needs it
