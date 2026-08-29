#!/usr/bin/env python3
"""PreToolUse(Bash) hook: ENFORCING blind-sleep guard.

DENY a shell command that waits a LONG fixed time (`sleep N` with N >= 10) without
any condition/loop structure. A timed wait either wastes minutes (fires late) or
fires early (condition not yet true); the actual signal is the CONDITION, so the
command should be `until <check>; do sleep 2; done`. This cost a real CTF box
minutes of blind 120s waits while job output sat readable on disk.

Deterministic, so it enforces (same boundary as scope-guard): "sleep >= 10 with no
until/while present" needs no judgement, and the fix is mechanical (wrap the check
in an until-loop), so a false block costs one rephrase and teaches the right shape.

NOT denied:
  - short settling sleeps (N < 10): `restart; sleep 2; status` is a settle, not a
    timed wait for a condition.
  - any command containing `until`/`while` (the poll pattern, whatever the sleep).
  - heredoc BODIES: a `cat <<EOF > job.sh` payload whose script sleeps is content
    being written, not this shell waiting.

SAFETY (can block, so it must never trap):
  - Fail-OPEN: any exception -> exit 0, allow.
  - Escape hatch: `skills/hooks/.enforce-off` downgrades every deny to advisory
    (shared with scope-guard).
Any error exits 0 silent.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# sleep with a numeric arg (10, 10.0, 10s). Word-boundary so `asleep`/`--sleep` skip.
_SLEEP = re.compile(r"(?<![-\w])sleep\s+(\d+(?:\.\d+)?)(?:s)?\b", re.I)
# the condition/loop structures that make any sleep legitimate (poll pattern)
_LOOP = re.compile(r"\b(while|until)\b")


def _strip_heredocs(cmd):
    """Drop heredoc bodies: from the line introducing `<<WORD` to the terminator line.
    A payload being WRITTEN to a file is content, not a wait this command performs."""
    out, in_heredoc, term = [], False, ""
    for line in cmd.splitlines():
        if in_heredoc:
            if line.strip() == term:
                in_heredoc = False
            continue
        m = re.search(r"<<-?\s*['\"]?(\w+)", line)
        if m:
            term = m.group(1)
            in_heredoc = True
            out.append(line)   # keep the introducer; its own sleep (rare) still counts
            continue
        out.append(line)
    return "\n".join(out)


def blind_sleeps(cmd):
    """[(seconds, ...)] for long fixed sleeps in `cmd` outside heredocs. Empty when the
    command carries a while/until poll (any sleep inside a polling loop is fine)."""
    scan = _strip_heredocs(cmd)
    if _LOOP.search(scan):
        return []
    return [(float(s),) for s in _SLEEP.findall(scan) if float(s) >= 10]


def _enforcing():
    marker = os.environ.get("ENFORCE_OFF_MARKER") or os.path.join(HERE, ".enforce-off")
    return not os.path.exists(marker)


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        return
    if data.get("tool_name") != "Bash":
        return
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not cmd:
        return
    hits = blind_sleeps(cmd)
    if not hits:
        return
    worst = max(s for (s,) in hits)
    body = ("blind wait: `sleep %g` with no while/until poll in the command" % worst)
    try:
        import _telemetry
        reason = ("blocked " if _enforcing() else "advised ") + "blind-sleep"
        _telemetry.drift("sleep-guard", reason)
        _telemetry.hook("sleep-guard", action=("deny" if _enforcing() else "advise"))
    except Exception:
        pass
    fix = ("\n\nPoll on the CONDITION instead - the condition is the actual signal:\n"
           "  until <check that the thing landed>; do sleep 2; done\n"
           "  e.g. until grep -q DONE /tmp/poc/out.log 2>/dev/null; do sleep 2; done")
    if _enforcing():
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": ("BLOCKED by harness enforcement:\n- " + body + fix
                + "\n\n(False block? create skills/hooks/.enforce-off to downgrade "
                  "enforcement to advisory.)"),
        }}))
    else:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": "SLEEP HYGIENE (advisory; enforcement OFF via .enforce-off):\n- "
                                 + body + fix,
        }}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
