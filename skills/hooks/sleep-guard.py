#!/usr/bin/env python3
"""PreToolUse(Bash) hook: ENFORCING blind-sleep guard.

DENY a `sleep` of 10+ seconds when the command carries no while/until poll loop:
a timed wait either wastes minutes or fires before the condition is real, and the
condition (logfile appears, port opens, process dies) is always the actual signal.
Poll-on-condition is the discipline (the offensive-engagement workflow); this is
its deterministic half, same policy tier as scope-guard: no judgement, block costs
nothing. Anything with `while` or `until` anywhere in the command passes - the loop
IS the poll. Short sleeps (<10s, e.g. a retry backoff) pass.

SAFETY (this hook can block, so it must never trap the operator):
  - Fail-OPEN: any exception -> exit 0, allow.
  - Narrow match: only a literal `sleep` token with a plain numeric argument
    (optionally s/m/h suffixed). `vm-bg.sh --wait 120`, `timeout`, `ping -i` etc.
    are not sleeps.
  - Escape hatch: `skills/hooks/.enforce-off` downgrades the deny to an advisory
    warning, same as scope-guard.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SLEEP_RE = re.compile(r"(?<![\w-])sleep\s+([0-9]+(?:\.[0-9]+)?)([smh]?)\b", re.I)
MULT = {"": 1, "s": 1, "m": 60, "h": 3600}
THRESHOLD = 10
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def _blank_quotes(s):
    """Blank single/double-quoted spans (length-preserving) so a `sleep N` mentioned only
    INSIDE a quoted string (an echo, a grep pattern) is inert -- it is text, not an invoked
    command. Same technique as recon-capture.py's/tool-telemetry.py's own quote-blanking."""
    return _QUOTED.sub(lambda m: " " * len(m.group(0)), s)


def blind_sleeps(cmd):
    """Total seconds of sleeps in `cmd` that exceed THRESHOLD (list of the offending values).
    Quote-blanked first so a merely-mentioned "sleep N" inside a string is never flagged."""
    hits = []
    for m in SLEEP_RE.finditer(_blank_quotes(cmd)):
        secs = float(m.group(1)) * MULT[m.group(2).lower()]
        if secs >= THRESHOLD:
            hits.append(m.group(0).split()[-1])
    return hits


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
    # A while/until loop anywhere = poll-on-condition; the sleep inside it is a beat
    # between checks, not a blind wait.
    if re.search(r"(?<![\w-])(while|until)(?![\w-])", cmd):
        return
    hits = blind_sleeps(cmd)
    if not hits:
        return
    reason = "blind sleep (" + ", ".join(sorted(set(hits))) + ") with no while/until poll"
    try:
        import _telemetry
        _telemetry.drift("sleep-guard", ("blocked " if _enforcing() else "advised ") + reason)
        _telemetry.hook("sleep-guard", action=("deny" if _enforcing() else "advise"))
    except Exception:
        pass
    if _enforcing():
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": ("BLOCKED by harness enforcement: " + reason
                + ".\n\nPoll on a CONDITION instead (until-loop / output-file check) - e.g. "
                  "`until grep -q Ready app.log; do sleep 2; done`. (False block? create "
                  "skills/hooks/.enforce-off to downgrade enforcement to advisory.)"),
        }}))
    else:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": "HYGIENE (advisory; enforcement OFF via .enforce-off): " + reason,
        }}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
