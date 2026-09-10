#!/usr/bin/env python3
"""PreToolUse Write|Edit checkpoint hook (F-GO1, pass 14).

A direct Write/Edit on a file under targets/<eng>/ bypasses the driver, whose own
mutations each leave a _ckpt shadow-commit restore point. Checkpoint the CURRENT
(pre-edit) state before the edit lands, so a bad hand-edit or a post-compact
re-entry rolls back exactly like a driver mistake (git -C targets/<eng> log).
Advisory-free enforcement-free: fail-open silent on any error; only fires on a
dir that already holds driver state (.offensive.json)."""
import json
import os
import sys
from pathlib import Path


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("tool_name") not in ("Write", "Edit"):
        return
    fp = (data.get("tool_input") or {}).get("file_path") or ""
    if not fp:
        return
    # Anchor on the FILE path, not this hook's repo: walk up to the dir whose parent
    # is named targets/ and that holds driver state. Works for any vault location.
    p = Path(fp).resolve()
    eng = p.parent
    while eng.parent.name != "targets" and eng != eng.parent:
        eng = eng.parent
    if eng == eng.parent or eng.parent.name != "targets":
        return                                   # not under any targets/<x>/ tree
    if not (eng / ".offensive.json").is_file():
        return                                   # not a driver engagement
    here = Path(__file__).resolve().parent
    try:
        sys.path.insert(0, str((here / ".." / ".." / "scripts").resolve()))
        import offensive
        offensive._ckpt(eng, "pre-edit %s" % p.relative_to(eng))
    except Exception:
        pass                                     # fail-open: never block the edit


main()
