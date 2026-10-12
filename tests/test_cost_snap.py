#!/usr/bin/env python3
"""Tests for skills/hooks/cost-snap.py (always-on session cost logger)."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "zt_snap", os.path.join(HERE, "..", "skills", "hooks", "cost-snap.py"))


def run_once(vault, proj, sid=None):
    import json as _jj
    env = dict(os.environ, ZT_COST_VAULT=vault, ZT_COST_PROJDIR=proj)
    payload = _jj.dumps({"session_id": sid}) if sid else ""
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "skills", "hooks", "cost-snap.py")],
                       capture_output=True, text=True, env=env, input=payload)
    assert r.returncode == 0, r.stderr
    assert r.stdout == "", "hook must stay silent"
    return r


def fixture(tmp):
    proj = os.path.join(tmp, "proj")
    os.makedirs(proj)
    with open(os.path.join(proj, "t.jsonl"), "w") as f:
        for _ in range(3):
            f.write(json.dumps({"type": "assistant", "timestamp": "x",
                                "message": {"usage": {"input_tokens": 10, "output_tokens": 2,
                                                      "cache_read_input_tokens": 5,
                                                      "cache_creation_input_tokens": 1}}}) + "\n")
    eng = os.path.join(tmp, "targets", "demo")
    os.makedirs(eng)
    with open(os.path.join(eng, ".events.jsonl"), "w") as f:
        f.write(json.dumps({"ts": "1", "kind": "tool", "tool": "Bash"}) + "\n")
        f.write(json.dumps({"ts": "2", "kind": "tool", "tool": "Agent"}) + "\n")
    open(os.path.join(tmp, "targets", "active.md"), "w").write("demo")
    return proj


def test_rows_and_incremental_no_double_count():
    with tempfile.TemporaryDirectory() as tmp:
        proj = fixture(tmp)
        run_once(tmp, proj, sid="s1")
        auto = os.path.join(tmp, "session", "bench", "auto.jsonl")
        import json as _j
        rows = [_j.loads(l) for l in open(auto).read().strip().splitlines()]
        assert len(rows) == 1
        r = rows[0]
        assert r["turns"] == 3 and r["input"] == 30 and r["tokens_total"] == 54
        assert r["tool_calls"] == 2 and r["agent_launches"] == 1 and r["eng"] == "demo"
        assert r["session_id"] == "s1"
        # second run, same session, NO new data: row untouched
        run_once(tmp, proj, sid="s1")
        assert len(open(auto).read().strip().splitlines()) == 1
        # same session, ONE new turn: SAME row, totals accumulate
        with open(os.path.join(proj, "t.jsonl"), "a") as f:
            f.write(_j.dumps({"type": "assistant", "timestamp": "x",
                              "message": {"usage": {"input_tokens": 7, "output_tokens": 1,
                                                    "cache_read_input_tokens": 0,
                                                    "cache_creation_input_tokens": 0}}}) + "\n")
        run_once(tmp, proj, sid="s1")
        rows = [_j.loads(l) for l in open(auto).read().strip().splitlines()]
        assert len(rows) == 1
        assert rows[0]["turns"] == 4 and rows[0]["input"] == 37, rows[0]
        # a DIFFERENT session with new data: a NEW row
        with open(os.path.join(proj, "t.jsonl"), "a") as f:
            f.write(_j.dumps({"type": "assistant", "timestamp": "x",
                              "message": {"usage": {"input_tokens": 1, "output_tokens": 1,
                                                    "cache_read_input_tokens": 0,
                                                    "cache_creation_input_tokens": 0}}}) + "\n")
        run_once(tmp, proj, sid="s2")
        rows = [_j.loads(l) for l in open(auto).read().strip().splitlines()]
        assert len(rows) == 2 and rows[-1]["session_id"] == "s2"
        assert rows[-1]["turns"] == 1 and rows[-1]["input"] == 1


def test_silent_on_empty_vault():
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "proj"))
        run_once(tmp, os.path.join(tmp, "proj"), sid="sX")
        assert not os.path.exists(os.path.join(tmp, "session", "bench", "auto.jsonl"))


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok {fn.__name__}")
    print(f"{len(fns)} passed")
