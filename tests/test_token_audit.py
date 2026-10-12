#!/usr/bin/env python3
"""Tests for scripts/token-audit.py (context/token cost report)."""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "zt_ta", os.path.join(HERE, "..", "scripts", "token-audit.py"))


def _load(vault):
    spec = importlib.util.spec_from_file_location(
        "zt_ta", os.path.join(HERE, "..", "scripts", "token-audit.py"))
    m = importlib.util.module_from_spec(spec)
    m.VAULT = vault  # reroot before exec uses it
    spec.loader.exec_module(m)
    m.VAULT = vault
    return m


def _vault(tmp):
    os.makedirs(os.path.join(tmp, "skills", "big-skill"), exist_ok=True)
    open(os.path.join(tmp, "skills", "big-skill", "SKILL.md"), "w").write(
        "---\nname: big-skill\ndescription: d\n---\n# x\n" + "a" * 25000)
    os.makedirs(os.path.join(tmp, "skills", "small-skill"), exist_ok=True)
    open(os.path.join(tmp, "skills", "small-skill", "SKILL.md"), "w").write(
        "---\nname: small-skill\ndescription: d\n---\n# x\nshort")
    os.makedirs(os.path.join(tmp, "session"), exist_ok=True)
    open(os.path.join(tmp, "session", "memory.md"), "w").write(
        "# m\n\n## Operator\n- op fact\n\n## Environment\n- " + "e" * 100 + "\n")
    return tmp


def test_skill_sizes_flags_oversized():
    with tempfile.TemporaryDirectory() as tmp:
        ta = _load(_vault(tmp))
        sizes = ta.skill_sizes()
        assert sizes["skills/big-skill/SKILL.md"] > 24000
        oversized = [p for p, n in sizes.items() if n > ta.OVERSIZED]
        assert any("big-skill" in p for p in oversized)
        assert not any("small-skill" in p for p in oversized)


def test_memory_usage_percent():
    with tempfile.TemporaryDirectory() as tmp:
        ta = _load(_vault(tmp))
        used_op, used_env = ta.memory_usage()
        assert used_op > 0 and used_env >= 100


def test_report_contains_sections_and_tokens():
    with tempfile.TemporaryDirectory() as tmp:
        ta = _load(_vault(tmp))
        out = ta.report()
        for needle in ("SessionStart", "skills", "OVERSIZED", "memory",
                       "tokens", "big-skill"):
            assert needle in out, needle
        # token estimate: chars/4 noted in output
        assert "~6" in out or "chars" in out


def test_turn_bytes_summary_handles_missing_metrics():
    with tempfile.TemporaryDirectory() as tmp:
        ta = _load(_vault(tmp))
        s = ta.turn_bytes_summary()
        assert "no turn_bytes" in s
        os.makedirs(os.path.join(tmp, "targets", "e"), exist_ok=True)
        with open(os.path.join(tmp, "targets", "e", ".metrics.json"), "w") as f:
            json.dump({"turn_bytes": [{"ts": "1", "b": 100}, {"ts": "2", "b": 900}]}, f)
        s = ta.turn_bytes_summary()
        assert "1000" in s and "e" in s


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok {fn.__name__}")
    print(f"{len(fns)} passed")
