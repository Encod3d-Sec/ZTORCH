#!/usr/bin/env python3
"""Tests for scripts/cost-log.py (harness token/cost accounting)."""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def load(vault, projdir):
    spec = importlib.util.spec_from_file_location(
        "zt_cl", os.path.join(HERE, "..", "scripts", "cost-log.py"))
    m = importlib.util.module_from_spec(spec)
    m.VAULT, m.PROJDIR = vault, projdir
    spec.loader.exec_module(m)
    m.VAULT, m.PROJDIR = vault, projdir
    return m


def fixture(tmp):
    proj = os.path.join(tmp, "proj")
    os.makedirs(proj)
    with open(os.path.join(proj, "s1.jsonl"), "w") as f:
        for i, ts in enumerate(["2026-10-12T10:00:00Z", "2026-10-12T10:05:00Z",
                                "2026-10-12T11:00:00Z"]):
            f.write(json.dumps({"type": "assistant", "timestamp": ts,
                                "message": {"usage": {
                                    "input_tokens": 100, "output_tokens": 10,
                                    "cache_read_input_tokens": 50,
                                    "cache_creation_input_tokens": 5}}}) + "\n")
    eng = os.path.join(tmp, "targets", "demo")
    os.makedirs(eng)
    with open(os.path.join(eng, ".events.jsonl"), "w") as f:
        for i, tool in enumerate(["Bash", "Bash", "Agent", "Skill", "Read"]):
            ts = "2026-10-12T10:0%d:00+00:00" % (1 if i < 2 else 2)
            f.write(json.dumps({"ts": ts, "kind": "tool",
                                "tool": tool, "skill": "hunt-xss" if tool == "Skill" else None,
                                "out_bytes": 100}) + "\n")
    open(os.path.join(eng, "state.md"), "w").write(
        "# State\n\n## STATUS: SOLVED\n\n### FIND-001 title\n### FIND-002 title\n- flag THM{abc123} captured\n")
    return tmp, proj


def test_tokens_window():
    with tempfile.TemporaryDirectory() as tmp:
        m = load(*fixture(tmp))
        tot = m.tokens_since("2026-10-12T09:00:00", "2026-10-12T10:30:00")
        assert tot["turns"] == 2, tot
        assert tot["input"] == 200 and tot["output"] == 20
        assert tot["cache_read"] == 100 and tot["cache_write"] == 10
        assert tot["total"] == 330


def test_activity_counts():
    with tempfile.TemporaryDirectory() as tmp:
        m = load(*fixture(tmp))
        a = m.activity("demo")
        assert a["agent_launches"] == 1 and a["bash_commands"] == 2
        assert a["skills_fired"] == 1 and a["skill_names"] == ["hunt-xss"]
        assert a["tool_calls"] == 5 and a["out_bytes"] == 500
        w = m.activity("demo", since="2026-10-12T10:01:30")
        assert w["tool_calls"] == 3  # window drops the two 10:01:00 events


def test_challenges():
    with tempfile.TemporaryDirectory() as tmp:
        m = load(*fixture(tmp))
        c = m.challenges("demo")
        assert c["status"] == "SOLVED" and c["flags"] == 1
        assert c["finds"] == 2


def test_report_renders_all_sections():
    with tempfile.TemporaryDirectory() as tmp:
        m = load(*fixture(tmp))
        out = m.report("demo", "2026-10-12T09:00:00", "2026-10-12T23:00:00")
        for needle in ("tokens", "turns", "Agent launches", "flags", "FIND", "SOLVED"):
            assert needle in out, needle


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok {fn.__name__}")
    print(f"{len(fns)} passed")
