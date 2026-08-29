"""sleep-guard.py: long fixed waits (sleep N, N >= 10) with no while/until poll are DENIED;
short settling sleeps, any polling loop, and heredoc bodies (payload content, not a wait)
pass. Advisory when the .enforce-off escape hatch is set."""
import os

from hookrunner import run_hook

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(cmd, env=None):
    # env kept for call-site compatibility; enforcement-off is switched via ENFORCE_OFF_MARKER
    # (read at call time by _enforcing), pointed at a nonexistent tmp path by default.
    return run_hook("sleep-guard", command=cmd)


def test_long_blind_sleep_denied(vault):
    out = _run("curl -s -T /tmp/job.sh ftp://10.0.0.5/incoming/; sleep 120; curl -s ftp://10.0.0.5/pub/uploads/pwned.txt")
    assert out.get("permissionDecision") == "deny"
    assert "sleep 120" in out["permissionDecisionReason"]
    assert "until" in out["permissionDecisionReason"]   # carries the fix


def test_short_settling_sleep_allowed(vault):
    assert _run("systemctl restart ssh; sleep 2; systemctl status ssh") == {}
    assert _run("sleep 9.5") == {}


def test_poll_loop_allowed(vault):
    # any while/until structure makes every sleep in the command legitimate
    assert _run("until grep -q DONE /tmp/out.log 2>/dev/null; do sleep 2; done") == {}
    assert _run("while ! curl -s ftp://10.0.0.5/pub/uploads/x.txt; do sleep 5; done") == {}
    # even a long sleep inside a poll loop passes (the loop is the signal)
    assert _run("until [ -f /tmp/flag ]; do sleep 15; done") == {}


def test_heredoc_body_not_treated_as_a_wait(vault):
    # the payload being WRITTEN contains sleep; the command itself does not wait
    cmd = ("cat > /tmp/job.sh <<EOF\n#!/bin/bash\nsleep 30\nid > /tmp/o.txt\nEOF\n"
           "curl -s -T /tmp/job.sh ftp://10.0.0.5/incoming/")
    assert _run(cmd) == {}


def test_heredoc_introducer_line_still_scanned(vault):
    # a sleep ON the introducer line is a real wait in this shell
    out = _run("echo start; sleep 45 <<EOF\nx\nEOF")
    assert out.get("permissionDecision") == "deny"


def test_non_bash_tool_ignored(vault):
    assert run_hook("sleep-guard", tool_name="Write", command="sleep 120") == {}
    assert run_hook("sleep-guard", tool_name="Bash", command="") == {}


def test_enforce_off_downgrades_to_advisory(vault, monkeypatch):
    marker = os.path.join(str(vault), "enforce-off-marker")
    open(marker, "w").close()          # marker EXISTS = enforcement off (scope-guard semantics)
    monkeypatch.setenv("ENFORCE_OFF_MARKER", marker)
    out = _run("sleep 120")
    assert "additionalContext" in out
    assert "permissionDecision" not in out
