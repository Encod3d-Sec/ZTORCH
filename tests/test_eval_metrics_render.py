"""W2-14: tokens_in_window() computes "input" and "cache_creation" token counters, but render()
silently dropped both from the generated eval.md report -- undercutting the script's own stated
purpose ("how many tokens used per box, with REAL data"). Pass 7 adds bench_lines(): the
expected-coverage line for practice engagements named after a bench-labs.json scenario id."""
import importlib.util
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "eval_metrics", os.path.join(VAULT, "scripts", "eval_metrics.py"))
eval_metrics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eval_metrics)


def _fake_collected():
    now = datetime.now(timezone.utc)
    tk = Counter({"output": 111, "input": 222, "cache_read": 333, "cache_creation": 444, "turns": 5})
    return {
        "start": now, "end": now, "wall": None, "active": None, "tokens": tk,
        "tool_calls": 0, "tools": Counter(), "skill_calls": 0, "skills": Counter(),
        "hook_fires": 0, "hooks": Counter(), "drift_count": 0, "drifts": [],
        "transcripts": [],
    }


def test_render_includes_input_tokens():
    out = eval_metrics.render("demo", _fake_collected())
    assert "222" in out and "input tokens" in out.lower()


def test_render_includes_cache_creation_tokens():
    out = eval_metrics.render("demo", _fake_collected())
    assert "444" in out and "cache-creation" in out.lower()


def test_render_still_includes_existing_metrics():
    out = eval_metrics.render("demo", _fake_collected())
    assert "111" in out  # output tokens, pre-existing
    assert "333" in out  # cache-read tokens, pre-existing


def test_render_no_bench_line_for_plain_engagement():
    out = eval_metrics.render("demo", _fake_collected())
    assert "Bench vs expected" not in out


def test_bench_lines_score_named_engagement(tmp_path, monkeypatch):
    """Engagement dir named after a bench scenario id -> one coverage line; the naming
    convention is the whole link (no manifest state on the engagement side)."""
    sys.path.insert(0, os.path.join(VAULT, "scripts"))
    import bench
    eng = tmp_path / "ps-demo"
    eng.mkdir()
    (eng / "state.md").write_text("sqli confirmed in findings\n", encoding="utf-8")
    mp = tmp_path / "m.json"
    mp.write_text(json.dumps({"ps-demo": {"name": "t", "source": "s",
                                          "expected_classes": ["sqli"]}}), encoding="utf-8")
    monkeypatch.setattr(bench, "DEFAULT_MANIFEST", mp)
    lines = eval_metrics.bench_lines(str(eng))
    assert lines and "Bench vs expected (ps-demo)" in lines[0]
    assert "sqli=1" in lines[0] and "50.0%" in lines[0]   # tested, no poc artifact


def test_bench_lines_absent_for_unnamed_engagement(tmp_path):
    (tmp_path / "clientbox").mkdir()
    assert eval_metrics.bench_lines(str(tmp_path / "clientbox")) == []


def test_render_carries_bench_lines():
    c = _fake_collected()
    c["bench"] = ["**Bench vs expected (ps-demo):** coverage 50.0% -- sqli=1"]
    out = eval_metrics.render("demo", c)
    assert "Bench vs expected (ps-demo)" in out
