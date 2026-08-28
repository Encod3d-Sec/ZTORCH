#!/usr/bin/env python3
"""SessionStart hook: auto-register vault skills + inject the session hot cache.

Python-only on purpose: ZCode hook commands run through whatever shell the seat
has (cmd/Git Bash on Windows), so this hook must not depend on bash. The
install-skills subprocess is best-effort (fails open when bash is absent);
everything else is pure python.

ZCode parses hook stdout as strict hook JSON, so the hot cache is emitted as
SessionStart additionalContext via _emit (plain text would be discarded).
Fail open: any error -> empty output, exit 0.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _emit  # noqa: E402

VAULT = os.path.dirname(os.path.dirname(HERE))


def main():
    # Auto-register vault skills so a freshly-authored skill is invocable without a
    # manual setup/install-skills.sh run. Idempotent; best-effort (bash may be
    # absent on some seats); the harness rescans on session start.
    try:
        subprocess.run(
            ["bash", os.path.join(VAULT, "setup", "install-skills.sh")],
            cwd=VAULT, timeout=90,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL)
    except Exception:
        pass

    # Inject the session hot cache into context.
    try:
        hot = os.path.join(VAULT, "session", "hot.md")
        if os.path.isfile(hot):
            with open(hot, encoding="utf-8", errors="replace") as f:
                txt = f.read().strip()
            if txt:
                _emit.emit(txt)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    try:
        _emit.flush("SessionStart")
    except Exception:
        pass
    sys.exit(0)
