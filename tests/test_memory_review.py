#!/usr/bin/env python3
"""Tests for scripts/memory-review.py (hermes-faithful background memory reviewer)."""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def load(vault):
    spec = importlib.util.spec_from_file_location(
        "zt_mr", os.path.join(HERE, "..", "scripts", "memory-review.py"))
    m = importlib.util.module_from_spec(spec)
    m.VAULT = vault
    spec.loader.exec_module(m)
    m.VAULT = vault
    return m


def fixture(tmp, msgs=None):
    os.makedirs(os.path.join(tmp, "session"), exist_ok=True)
    open(os.path.join(tmp, "session", "memory.md"), "w").write(
        "# m\n\n## Operator\n- (empty)\n\n## Environment\n- (empty)\n")
    t = os.path.join(tmp, "transcript.jsonl")
    with open(t, "w") as f:
        for typ, txt in (msgs or [
                ("user", "the qmd index drops when the MCP restarts, restart it with zg server on"),
                ("assistant", "noted, restarting the index"),
                ("user", "also I prefer short reports, no tables"),
                ("tool_result", "irrelevant noise"),
                ("assistant", "done")]):
            if typ == "tool_result":
                f.write(json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "content": txt}]}}) + "\n")
            else:
                f.write(json.dumps({"type": typ, "message": {"content": txt}}) + "\n")
    return t


def test_extract_conversation_skips_tool_noise():
    with tempfile.TemporaryDirectory() as tmp:
        mr = load(tmp)
        t = fixture(tmp)
        lines = mr.extract_conversation(t, max_msgs=30, max_chars=100000)
        assert any("qmd index drops" in l for l in lines)
        assert any("short reports" in l for l in lines)
        assert not any("irrelevant noise" in l for l in lines)
        assert all(l.startswith(("USER:", "ASSISTANT:")) for l in lines)


def test_digest_collapses_old_turns():
    with tempfile.TemporaryDirectory() as tmp:
        mr = load(tmp)
        msgs = [(("user", "old %d" % i), ("assistant", "resp %d" % i)) for i in range(20)]
        flat = [m for pair in msgs for m in pair]
        t = fixture(tmp, flat)
        lines = mr.extract_conversation(t, max_msgs=24, max_chars=100000)
        assert any("Earlier conversation digest" in l for l in lines)
        assert sum(1 for l in lines if not l.startswith("[")) <= 24


def test_review_with_canned_response_applies_ops():
    with tempfile.TemporaryDirectory() as tmp:
        mr = load(tmp)
        t = fixture(tmp)
        canned = os.path.join(tmp, "resp.json")
        open(canned, "w").write(json.dumps({
            "ops": [{"store": "environment", "new": "qmd index drops when the MCP restarts; fix is zg server on"},
                    {"store": "operator", "new": "prefers short reports without tables"},
                    {"store": "bogus", "new": "should be dropped"}],
            "skills": ["restart-qmd-index procedure"],
            "note": ""}))
        out = mr.review(t, response_file=canned, write=True)
        mem = open(os.path.join(tmp, "session", "memory.md")).read()
        assert "qmd index drops" in mem and "short reports" in mem
        assert "should be dropped" not in mem
        ideas = os.path.join(tmp, "session", "skill-ideas.md")
        assert os.path.exists(ideas) and "restart-qmd-index" in open(ideas).read()
        assert out["written"] == 2
        # second run same canned response: dedupe -> 0 new
        out2 = mr.review(t, response_file=canned, write=True)
        assert out2["written"] == 0
        assert out2["duplicates"] == 2


def test_nothing_to_save_is_respected():
    with tempfile.TemporaryDirectory() as tmp:
        mr = load(tmp)
        t = fixture(tmp)
        canned = os.path.join(tmp, "resp.json")
        open(canned, "w").write(json.dumps({"ops": [], "skills": [], "note": "Nothing to save."}))
        out = mr.review(t, response_file=canned, write=True)
        assert out["written"] == 0 and out["nothing_to_save"]
        mem = open(os.path.join(tmp, "session", "memory.md")).read()
        assert "qmd index drops" not in mem


def test_prompt_carries_routing_block():
    with tempfile.TemporaryDirectory() as tmp:
        mr = load(tmp)
        p = mr.build_prompt(["USER: hi"])
        for needle in ("TWO distinct stores", "who the user is",
                       "facts about the ENVIRONMENT", "One fact goes to ONE store"):
            assert needle in p, needle


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok {fn.__name__}")
    print(f"{len(fns)} passed")
