"""tool-telemetry _spend_update: incremental transcript->spend_usd accumulation at
eval_metrics pricing (imported, not forked), offset advance (delta-only on re-run),
rotation reset, and the opt-in ZT_MAX_ENG_USD advisory with its 15-min stamp dedup."""
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "tool_telemetry_spend", ROOT / "skills" / "hooks" / "tool-telemetry.py")
tt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tt)


def _usage_line(model, **kw):
    u = {"input_tokens": 0, "output_tokens": 0,
         "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    u.update(kw)
    return json.dumps({"message": {"model": model, "usage": u}})


def test_accumulates_and_advances_offset(monkeypatch, tmp_path):
    monkeypatch.delenv("ZT_MAX_ENG_USD", raising=False)
    p = tmp_path / "t.jsonl"
    p.write_text(_usage_line("claude-opus-4-1", input_tokens=1000000,
                             output_tokens=100000) + "\n"
                 + _usage_line("mystery-model", input_tokens=1000000) + "\n",
                 encoding="utf-8")
    assert tt._spend_update(str(p), str(tmp_path)) is None   # no cap set -> silent
    m = json.load(open(tmp_path / ".metrics.json", encoding="utf-8"))
    # opus 1M in + 100K out = 15.0 + 7.5; default 1M in = 3.0
    assert m["spend_usd"] == 25.5
    assert m["spend_state"][str(p)] == p.stat().st_size
    # append one haiku line: only the DELTA is priced on the second run
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(_usage_line("claude-3-5-haiku", input_tokens=1000000) + "\n")
    tt._spend_update(str(p), str(tmp_path))
    m = json.load(open(tmp_path / ".metrics.json", encoding="utf-8"))
    assert m["spend_usd"] == 26.5                            # +1.0 haiku, not a re-walk
    assert m["spend_state"][str(p)] == p.stat().st_size


def test_rotated_transcript_rereads_whole(monkeypatch, tmp_path):
    monkeypatch.delenv("ZT_MAX_ENG_USD", raising=False)
    p = tmp_path / "t.jsonl"
    p.write_text(_usage_line("mystery-model-with-a-long-name", input_tokens=1000000) + "\n",
                 encoding="utf-8")
    tt._spend_update(str(p), str(tmp_path))
    # rotation: file SHRINKS below the recorded offset -> offset resets and the whole
    # file is re-priced once (shorter model name guarantees a smaller file)
    p.write_text(_usage_line("m", input_tokens=2000000) + "\n", encoding="utf-8")
    tt._spend_update(str(p), str(tmp_path))
    m = json.load(open(tmp_path / ".metrics.json", encoding="utf-8"))
    assert m["spend_usd"] == 3.0 + 6.0


def test_cap_advisory_and_stamp_dedup(monkeypatch, tmp_path):
    monkeypatch.setenv("ZT_MAX_ENG_USD", "1.0")
    p = tmp_path / "t.jsonl"
    p.write_text(_usage_line("mystery-model", input_tokens=1000000) + "\n",
                 encoding="utf-8")
    # while ENFORCING (no .enforce-off marker) drift-guard already DENIES Bash over this
    # cap on PreToolUse - the PostToolUse advisory must stay silent, not echo the deny
    monkeypatch.delenv("ENFORCE_OFF_MARKER", raising=False)
    assert not (tmp_path / ".enforce-off").exists()
    tt._spend_update(str(p), str(tmp_path))
    assert tt._spend_update(str(p), str(tmp_path)) is None
    m = json.load(open(tmp_path / ".metrics.json", encoding="utf-8"))
    assert m["spend_usd"] == 3.0                       # spend kept accumulating silently
    # under the hatch the advisory is the ONLY budget signal left: it fires, then the
    # fresh .budget-stamp suppresses the next one (15-min dedup)
    hatch = tmp_path / "hatch"
    hatch.write_text("", encoding="utf-8")
    monkeypatch.setenv("ENFORCE_OFF_MARKER", str(hatch))
    (tmp_path / ".budget-stamp").unlink(missing_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(_usage_line("mystery-model", input_tokens=1000000) + "\n")
    a = tt._spend_update(str(p), str(tmp_path))
    assert a and "$6.00" in a and "$1.00" in a               # over-cap advisory fires
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(_usage_line("mystery-model", input_tokens=1000000) + "\n")
    assert tt._spend_update(str(p), str(tmp_path)) is None
    m = json.load(open(tmp_path / ".metrics.json", encoding="utf-8"))
    assert m["spend_usd"] == 9.0


def test_failopen(monkeypatch, tmp_path):
    monkeypatch.delenv("ZT_MAX_ENG_USD", raising=False)
    assert tt._spend_update(str(tmp_path / "missing.jsonl"), str(tmp_path)) is None
    p = tmp_path / "bad.jsonl"
    p.write_text("not json\n", encoding="utf-8")
    assert tt._spend_update(str(p), str(tmp_path)) is None    # garbage lines skipped
    m = json.load(open(tmp_path / ".metrics.json", encoding="utf-8"))
    assert m["spend_usd"] == 0.0                              # delta 0, nothing priced
