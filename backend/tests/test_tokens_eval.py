"""Token evaluation statistics and report, on a synthetic cache (no API calls)."""
import random

import pytest

from app.evaluation import tokens as T
from app.evaluation.run import Cache


def test_reduction_bootstrap_and_wilcoxon():
    assert T.reduction(200, 50) == 75.0 and T.reduction(100, 120) == -20.0 and T.reduction(0, 5) is None
    lo, hi = T.bootstrap_ci([10.0] * 30, random.Random(1))
    assert lo == hi == 10.0
    lo, hi = T.bootstrap_ci([0.0, 100.0] * 50, random.Random(1), n=2000)
    assert 35 < lo < 50 < hi < 65
    assert T.wilcoxon_p([100] * 20, [100] * 20) is None
    assert T.wilcoxon_p(list(range(100, 120)), list(range(10, 30))) < 0.001


@pytest.fixture
def rows_and_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "CACHE", tmp_path / "t.jsonl")
    cache = Cache(T.CACHE)
    rows = []
    for k in range(20):
        cat = "coding" if k % 2 else "classification"
        r = {"source_id": f"s{k}", "category": cat, "original_instruction": "Classify: a, b", "reference_response": "x"}
        rows.append(r)
        for v, (i, o) in {"degraded": (100, 600), "stage_b": (140, 150)}.items():
            cache.add(r["source_id"], v, category=cat, prompt="p", response="```python\nx = 1\n```",
                      target={"input_tokens": i, "output_tokens": o, "reasoning_tokens": 20,
                              "finish_reason": "length" if (v == "degraded" and k == 0) else "stop"})
    cache.add("s1", "stage_c", category="coding", prompt="p", response="ok", stage_c={"accepted": True},
              target={"input_tokens": 150, "output_tokens": 100, "reasoning_tokens": 10, "finish_reason": "stop"})
    return rows


def test_report_headline_input_grows_output_falls(rows_and_cache):
    text, data = T.report(rows_and_cache)
    t = data["overall"]["total"]
    assert data["overall"]["n"] == 20 and t["mean_reduction"] == pytest.approx(100 * (700 - 290) / 700)
    assert data["headline"].startswith("Optimized prompts reduce total tokens by 58.6% (95% CI 58.6-58.6%, n = 20)")
    assert "**Input grows, the saving comes from output.**" in text
    assert "input tokens 100 -> 140" in text and "output tokens 600 -> 150" in text
    assert "degraded 1, A+B 0" in text                              # truncation counted
    assert "## Routed prompts: A+B vs A+B+C" in text and "accepted for 1" in text
    assert "| coding |" in text                                     # task success where checkable
