"""W2-14: tokens_in_window() computes "input" and "cache_creation" token counters, but render()
silently dropped both from the generated eval.md report -- undercutting the script's own stated
purpose ("how many tokens used per box, with REAL data")."""
import importlib.util
import os
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
