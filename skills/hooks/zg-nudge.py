#!/usr/bin/env python3
"""PreToolUse(Bash) hook: nudge cross-file locating onto zg (zvec-grep). Advisory only.

zg is the harness's workspace/text search layer (AGENTS.md Search rule). This hook fires a
rate-limited advisory when a Bash command OPENS with a recursive grep/rg - the recurring
"locate across files" shape zg ranks better - and never denies. Skips:
  - grep/rg further into a pipeline (`cat x | grep y`): that is stream filtering, not locating.
  - single-file greps (no -r/-R and no directory argument): read-first allows grep inside one file.
  - remote/VM contexts (vm.sh / vm-ssh / win-vm / ssh / capture.sh): zg does not exist on the target.
  - framework-meta commands (_meta.is_framework_meta): harness self-dev sessions stay quiet.
Rate-limited to one nudge per 15 min via a stamp under session/ (gitignored). Fails open.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

VAULT = os.path.abspath(os.path.join(HERE, "..", ".."))
STAMP = os.path.join(VAULT, "session", ".zg-nudge-stamp")
INTERVAL = 900  # seconds; one nudge per 15 min

_RECURSIVE = ("-r", "-R", "--recursive")
_REMOTE = ("vm.sh", "vm-ssh", "win-vm", "vm-rsh", "win-rsh", "ssh ", "capture.sh")
_HINT = (
    "ZG-NUDGE (advisory): cross-file grep - zg ranks this better: "
    "zg query --human '<terms>' --limit 5 (or the zvec_grep_search MCP tool; "
    "run `zg server on` if it errors). Grep stays fine inside a single file."
)


def _vault_root():
    """Hook scripts live in <vault>/skills/hooks; trust the script location over cwd."""
    return VAULT if os.path.isdir(os.path.join(VAULT, "wiki")) else None


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


def _should_nudge(cmd):
    first = cmd.strip().split()
    if not first or first[0] not in ("grep", "rg"):
        return False                      # not an opening grep/rg (pipes -> stream filtering)
    if any(low in cmd.lower() for low in _REMOTE):
        return False                      # remote/VM context: zg is not on the target
    if "-r" in first or "-R" in first or "--recursive" in first:
        return True
    for a in first[1:]:
        if a.startswith("-"):
            continue
        if os.path.isdir(a):
            return True                   # directory argument = cross-file shape
        break                             # first non-flag is a single file -> read-first grep
    return False


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
        if _vault_root() and _cooled_down():
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": _HINT}}))
    except Exception:
        pass                              # fail open, always
    sys.exit(0)


if __name__ == "__main__":
    main()
