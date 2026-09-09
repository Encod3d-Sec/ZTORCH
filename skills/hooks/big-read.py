#!/usr/bin/env python3
"""PreToolUse(Read) advisory hook: the big-read guard.

A full Read of a file >200KB without offset/limit is usually an accident (a
bundled/minified JS file, a scan dump, a raw log) that floods context in one
call. ADVISES with the exact size and the locate-first ladder (zg across files,
grep -n inside this file, js-beautify for bundles), then a narrow Read around
the hit. Never blocks: "this locates, it does not replace the read" - the
read-first mandate still rules when the plan IS to read the whole file
(chunked via offset/limit so each call stays bounded).

Dedupe: one advisory per file per 15 min (session/.big-read-stamps/<path-hash>).
Fail-open silent: no vault, no read permission -> no output.
"""
import hashlib
import json
import os
import sys
import time

THRESHOLD = 200_000      # bytes; clone's pre-read stat gate uses 256KB, ours advises earlier
DEDUPE_S = 900


def _fmt(n):
    return "%dKB" % (n // 1024) if n < 1024 * 1024 else "%.1fMB" % (n / 1048576)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return
    if data.get("tool_name") != "Read":
        return
    ti = data.get("tool_input") or {}
    if ti.get("offset") or ti.get("limit"):
        return   # a deliberate narrow read is exactly the advised behavior
    p = str(ti.get("file_path") or "")
    if not p or not os.path.isfile(p):
        return
    try:
        size = os.path.getsize(p)
    except OSError:
        return
    if size <= THRESHOLD:
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import _engagement
        sdir = os.path.join(_engagement.VAULT, "session", ".big-read-stamps")
        os.makedirs(sdir, exist_ok=True)
        stamp = os.path.join(sdir, hashlib.sha1(p.encode()).hexdigest()[:16])
        if os.path.exists(stamp) and time.time() - os.path.getmtime(stamp) < DEDUPE_S:
            return
        open(stamp, "w").close()
    except Exception:
        pass
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "additionalContext":
            "big-read advisory: %s is %s - a full read floods context in one call. "
            "Locate first (zg across files, `grep -n` inside this file; js-beautify "
            "first for a bundled/minified JS), then Read with offset/limit around "
            "the hit. This locates, it does not replace the read: if the plan is to "
            "read it all, chunk it with offset/limit so each call stays bounded."
            % (p, _fmt(size))}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
