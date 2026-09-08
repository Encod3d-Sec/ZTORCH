#!/usr/bin/env python3
"""PreToolUse(Bash) hook: nudge confirm-worthy requests toward Burp. Advisory only.

AGENTS.md Burp-first: confirm-worthy requests (injection/SSRF/deser/auth-bypass
shapes) go to Burp Repeater via Skill(hunt-burp) so the operator can replay them;
brute/fuzz loops belong in Intruder. Real engagements ran everything as bare curl.
Fires a rate-limited advisory when: (a) a curl at command position (outer or inside
a vm.sh/ssh/vm-ssh wrapper) carries a body AND a payload signature or an auth
header, or (b) handroll.classify() fires (a breadth-y network loop -> Intruder).
Skips commands already routed to the Burp tooling. Fails open.
"""
import importlib.util
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))

VAULT = os.path.abspath(os.path.join(HERE, "..", ".."))
STAMP = os.path.join(VAULT, "session", ".burp-nudge-stamp")
INTERVAL = 900  # seconds; one nudge per 15 min

_spec = importlib.util.spec_from_file_location(
    "recon_capture", os.path.join(HERE, "recon-capture.py"))
_rc = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(_rc)
    invokes, inner_cmds, _invokes_any = _rc.invokes, _rc.inner_cmds, _rc._invokes_any
except Exception:                                   # fail open
    invokes = inner_cmds = _invokes_any = None

try:
    from handroll import classify
except Exception:
    classify = None

_BODY = re.compile(r"(--data|--json|--form\b|\s-F\b|\s-d'|\s-d\s|\s-d$|-X\s*(?:POST|PUT|PATCH|DELETE))", re.I)
# handroll's sqlmap payload signature, minus --data (body-ness is _BODY's job)
PAYLOAD = re.compile(r"('\s*or\s*'|union\s+select|sleep\(|benchmark\(|%27)", re.I)
_HDR = re.compile(r"Cookie:|Authorization:|\s-H\s'", re.I)
_VMSSH = re.compile(r"vm-ssh(?:\.sh)?\s+(['\"])(.+?)\1", re.S)
_REROUTED = ("hunt-burp", "burp-hunt", "capture.sh", "mcp__burp", "send_to_intruder")
_HINT = (
    "BURP-NUDGE (advisory): confirm-worthy request shape - send it to Burp Repeater via "
    "Skill(hunt-burp) / bash scripts/burp/burp-hunt.sh so the operator can replay it; "
    "brute/fuzz loops belong in Intruder (send_to_intruder), not a hand-rolled shell loop."
)


def _inners(cmd):
    out = list(inner_cmds(cmd or "")) if inner_cmds else []
    out += [m.group(2) for m in _VMSSH.finditer(cmd or "")]
    return out


def _curl_invoked(cmd):
    if invokes is None:
        return False
    return bool(_invokes_any(cmd, "curl") or any(invokes(ic, "curl") for ic in _inners(cmd)))


def _should_nudge(cmd):
    c = cmd or ""
    if any(r in c for r in _REROUTED):
        return False
    if classify is not None:
        fired, _tool, _reason = classify(c)
        if fired:
            return True
    if not _curl_invoked(c):
        return False
    return bool(_BODY.search(c) and (PAYLOAD.search(c) or _HDR.search(c)))


def _cooled_down():
    try:
        with open(STAMP, encoding="utf-8") as fh:
            if time.time() - float(fh.read().strip() or 0) < INTERVAL:
                return False
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(STAMP), exist_ok=True)
        with open(STAMP, "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except Exception:
        pass
    return True


def main():
    try:
        payload = json.load(sys.stdin)
        cmd = (payload.get("tool_input") or {}).get("command") or ""
        if not _should_nudge(cmd):
            return
        try:
            import _meta
            if _meta.is_framework_meta(cmd):
                return
        except Exception:
            pass
        if os.path.isdir(os.path.join(VAULT, "wiki")) and _cooled_down():
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": _HINT}}))
    except Exception:
        pass                              # fail open, always
    sys.exit(0)


if __name__ == "__main__":
    main()
