"""tool-telemetry _context_low: the context-remainder advisory fires only past 75% of
the window (clone formula), dedupes 15 min, and fail-opens to silence."""
import importlib.util
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "tool_telemetry", ROOT / "skills" / "hooks" / "tool-telemetry.py")
tt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tt)


def _transcript(tmp_path, used):
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({"message": {"usage": {
        "input_tokens": used // 2,
        "cache_read_input_tokens": used // 2,
        "cache_creation_input_tokens": 0,
        "output_tokens": 0}}}) + "\n", encoding="utf-8")
    return str(p)


def test_fires_past_75pct(monkeypatch, tmp_path):
    monkeypatch.setenv("ZT_CONTEXT_WINDOW", "200000")
    assert tt._context_low(_transcript(tmp_path, 180000), str(tmp_path)) == 10


def test_silent_below_75pct(monkeypatch, tmp_path):
    monkeypatch.setenv("ZT_CONTEXT_WINDOW", "200000")
    assert tt._context_low(_transcript(tmp_path, 50000), str(tmp_path)) is None


def test_dedupe_via_stamp(monkeypatch, tmp_path):
    monkeypatch.setenv("ZT_CONTEXT_WINDOW", "200000")
    tr = _transcript(tmp_path, 190000)
    assert tt._context_low(tr, str(tmp_path)) == 5
    (tmp_path / ".ctx-low-stamp").write_text("", encoding="utf-8")
    assert tt._context_low(tr, str(tmp_path)) is None   # fresh stamp -> suppressed


def test_failopen_on_garbage(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text("not json at all\n" * 10, encoding="utf-8")
    assert tt._context_low(str(p), str(tmp_path)) is None
    assert tt._context_low(str(tmp_path / "missing.jsonl"), str(tmp_path)) is None
