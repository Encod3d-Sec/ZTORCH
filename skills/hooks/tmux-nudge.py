#!/usr/bin/env python3
"""PreToolUse(Bash) hook: nudge heavy tool runs into named tmux windows. Advisory only.

The tmux rule (one window per evidence-worthy action, output visible in-pane) lost to
one-shot SSH on real engagements because nothing pushed commands into tmux. Fires a
rate-limited advisory when a HEAVY tool sits at command position (outer command or
inside a vm.sh/ssh/vm-ssh wrapper) with no tmux token anywhere. Skips:
  - commands already routed through the tmux-aware drivers (vm-scan/vm-bg/vm-rsh/
    vm-handler/vm-stabilize/stager/win-rsh): those ARE the rule.
  - pane readbacks (capture-pane/list-windows/show-pane) and --version/--help lookups.
  - framework-meta commands (_meta.is_framework_meta).
Rate-limited to one nudge per 15 min via a stamp under session/. Fails open.
"""
import importlib.util
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

VAULT = os.path.abspath(os.path.join(HERE, "..", ".."))
STAMP = os.path.join(VAULT, "session", ".tmux-nudge-stamp")
INTERVAL = 900  # seconds; one nudge per 15 min

_spec = importlib.util.spec_from_file_location(
    "recon_capture", os.path.join(HERE, "recon-capture.py"))
_rc = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(_rc)
    invokes, inner_cmds, _invokes_any = _rc.invokes, _rc.inner_cmds, _rc._invokes_any
except Exception:                                   # fail open: no nudge without matchers
    invokes = inner_cmds = _invokes_any = None

HEAVY = ("nmap|masscan|rustscan|ffuf|feroxbuster|gobuster|dirb|dirsearch|nuclei|nikto|"
         "wpscan|sqlmap|hydra|medusa|patator|john|hashcat|msfconsole|msfvenom|"
         "evil-winrm|responder")
_LISTENER = re.compile(r"\b(nc|ncat|netcat|socat)\b[^\n;|]*\s-l")
_VMSSH = re.compile(r"vm-ssh(?:\.sh)?\s+(['\"])(.+?)\1", re.S)
_TMUX = re.compile(r"\btmux\b")
_READBACK = re.compile(r"capture-pane|list-windows|show-pane")
_HELP = re.compile(r"--version|--help\b|(?<!\S)-h(?!\S)")
_DRIVERS = ("vm-scan.sh", "vm-bg.sh", "vm-rsh.sh", "win-rsh.sh", "vm-handler.sh",
            "vm-stabilize.sh", "stager.sh", "autocard.sh")
_HINT = (
    "TMUX-NUDGE (advisory): evidence-worthy tool runs belong in a named tmux window so "
    "the output stays in-pane (autocard cards it, shot.py --tmux screenshots it, the "
    "operator can review live): bash scripts/vm-scan.sh --win <tool> <eng> <target> '<cmd>' "
    "(scans), bash scripts/vm-bg.sh <eng> <win> '<cmd>' (output-needed), "
    "bash scripts/vm-rsh.sh --create --win <name> <eng> '<cmd>' (run + return output)."
)


def _inners(cmd):
    """inner_cmds plus the vm-ssh.sh driver arg (vm-ssh is not in inner_cmds' shapes)."""
    out = list(inner_cmds(cmd or "")) if inner_cmds else []
    out += [m.group(2) for m in _VMSSH.finditer(cmd or "")]
    return out


def _should_nudge(cmd):
    if invokes is None:
        return False
    c = cmd or ""
    if _TMUX.search(c) or _READBACK.search(c) or _HELP.search(c):
        return False
    if any(d in c for d in _DRIVERS):
        return False
    if _invokes_any(c, HEAVY):
        return True
    if any(invokes(ic, HEAVY) for ic in _inners(c)):
        return True
    if _LISTENER.search(_rc._blank_quotes(c)):
        return True
    return any(_LISTENER.search(_rc._blank_quotes(ic)) for ic in _inners(c))


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
