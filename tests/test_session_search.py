#!/usr/bin/env python3
"""Tests for scripts/session_search.py."""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "zt_ss", os.path.join(HERE, "..", "scripts", "session_search.py"))
ss = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ss)


def fixture(tmp):
    ss.VAULT = tmp
    eng = os.path.join(tmp, "targets", "demo")
    os.makedirs(eng, exist_ok=True)
    open(os.path.join(tmp, "targets", "active.md"), "w").write("demo")
    open(os.path.join(eng, "log.md"), "w").write(
        "## 2026-10-01\n"
        "- lane laneA (host) in flight @10:00: SUCCESS = flag THM{demo} | tmux win 1 | capture poc/laneA\n"
        "- lane laneA ... | handle x -> VERIFIED: poc/laneA/flag.txt THM{demo}\n"
        "operator decided to pivot to the api surface because THM{demo} expired\n")
    os.makedirs(os.path.join(tmp, "session"), exist_ok=True)
    open(os.path.join(tmp, "session", "log.md"), "w").write("framework note about wordwrap helpers\n")
    return eng


def run(capsys):
    import io, contextlib
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        rc = ss.main()
    return rc, buf.getvalue(), err.getvalue()


def test_query_demotes_automation_and_dedups():
    with tempfile.TemporaryDirectory() as tmp:
        fixture(tmp)
        sys.argv = ["ss", "query", "THM{demo}"]
        rc, out, _ = run(None)
        assert rc == 0
        # operator line (score 1.0 base) ranks above the lane lines; lane line +
        # its VERIFIED continuation collapse to one hit
        first = out.splitlines()[1]
        assert "operator decided" in first
        lane_hits = [l for l in out.splitlines() if l.startswith("   - lane laneA")]
        assert len(lane_hits) == 1


def test_scroll_read_browse():
    with tempfile.TemporaryDirectory() as tmp:
        eng = fixture(tmp)
        sys.argv = ["ss", "scroll", os.path.join(eng, "log.md"), "4", "--window", "1"]
        rc, out, _ = run(None)
        assert rc == 0 and "operator decided" in out
        sys.argv = ["ss", "read", os.path.join(eng, "log.md")]
        rc, out, _ = run(None)
        assert rc == 0 and "THM{demo}" in out
        sys.argv = ["ss", "browse"]
        rc, out, _ = run(None)
        assert rc == 0 and "targets/demo/log.md" in out and "session/log.md" in out


def test_no_hits_message():
    with tempfile.TemporaryDirectory() as tmp:
        fixture(tmp)
        sys.argv = ["ss", "query", "zzz-not-present"]
        rc, _, _ = run(None)
        assert rc == 1


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok {fn.__name__}")
    print(f"{len(fns)} passed")
