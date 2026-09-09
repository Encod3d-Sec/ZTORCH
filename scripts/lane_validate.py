#!/usr/bin/env python3
"""lane_validate.py - verify returned lane claims against their captures, mechanically.

The delegate contract (skills delegate, "Main-agent discipline") says: every lane line in
targets/<eng>/log.md carries `SUCCESS = <observable> | ... | capture <dir>`, and on return
the main agent must verify the observable actually appears in the capture before filing the
lane's claim. Under momentum that verification is skipped - this script IS that check:

    python3 scripts/lane_validate.py <eng-dir | log.md path>

For each lane line: `VERIFIED` when the stated observable appears (plain substring) in any
file under the capture dir, `NOT VERIFIED` when absent (the over-claim leak-through), `in
flight` lines are skipped (status, not guess). Exit 0 always - it prints verdicts, it does
not gate; writing the verdict line into the log stays the main agent's job.
"""
import os
import re
import sys

# `- lane <name> in flight: SUCCESS = <observable> | ... | capture <dir>` (delegate skill);
# on return the line is CLOSED by appending the result after the capture cell, so "in flight"
# stays in the text - a line with NOTHING after the capture dir is the still-open one.
_LANE_RE = re.compile(
    r"^- lane (\S+)(.*): SUCCESS = ([^|]+)\|\s*tmux win \S+\s*\|\s*capture (\S+)(.*)$",
    re.MULTILINE)
_MAX_FILE = 2 * 1024 * 1024      # ponytail: caps per-file read; a capture >2MB is raw log noise


def lanes_from_text(text):
    """[(name, observable, capture_dir)] for every CLOSED lane line with a criterion."""
    out = []
    for m in _LANE_RE.finditer(text):
        name, _tail, obs, cap, rest = m.groups()
        if "in flight" in _tail and not rest.strip():
            continue                       # opened, never closed; status, not guess
        out.append((name, obs.strip(), cap.strip()))
    return out


def _search(dirpath, needle):
    """True when needle appears in any file under dirpath (recursive, fail-open False)."""
    if not os.path.isdir(dirpath):
        return False
    for root, _dirs, files in os.walk(dirpath):
        for f in files:
            p = os.path.join(root, f)
            try:
                if os.path.getsize(p) > _MAX_FILE:
                    continue
                if needle in open(p, encoding="utf-8", errors="ignore").read():
                    return True
            except OSError:
                continue
    return False


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__.strip().splitlines()[-2])
        return 0
    target = argv[0]
    log = target if target.endswith(".md") else os.path.join(target, "log.md")
    try:
        text = open(log, encoding="utf-8", errors="ignore").read()
    except OSError:
        print("lane_validate: no log at %s" % log)
        return 0
    base = os.path.dirname(os.path.abspath(log))
    n_ok = n_fail = 0
    for name, obs, cap in lanes_from_text(text):
        capdir = cap if os.path.isabs(cap) else os.path.normpath(os.path.join(base, cap))
        if not os.path.isdir(capdir):
            print("lane %s: NOT VERIFIED - no capture dir at %s" % (name, cap))
            n_fail += 1
        elif _search(capdir, obs):
            print("lane %s: VERIFIED (\"%s\" present in %s)" % (name, obs, cap))
            n_ok += 1
        else:
            print("lane %s: NOT VERIFIED - \"%s\" absent from %s (over-claim; treat the "
                  "lane claim as a hypothesis)" % (name, obs, cap))
            n_fail += 1
    if n_ok == n_fail == 0:
        print("lane_validate: no returned lane lines with a SUCCESS criterion in %s" % log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
