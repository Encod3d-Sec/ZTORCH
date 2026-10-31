#!/usr/bin/env python3
"""disk_verify.py - deterministic post-write check (R10, 2026-10-31 retro).

Replaces the ad-hoc tick-count / `cat -A` ritual run after every state-file
write: one command, one exit code, every check prints its own line.

  python3 scripts/disk_verify.py lane-42/envelope.md --contains lane-42 --tail 3
  python3 scripts/disk_verify.py state.md --ascii --min-bytes 200

Checks (all must hold, else exit 1):
  --contains SUB      file contains SUB (repeatable, AND semantics)
  --not-contains SUB  file must NOT contain SUB (repeatable)
  --ascii             whole file is ASCII
  --tail N            print the last N non-empty lines (read-back echo);
                      fail if the file has fewer
  --min-bytes N       file is at least N bytes
A missing file always fails.
"""
import argparse
import os
import sys


def main():
    ap = argparse.ArgumentParser(
        description="verify a file landed whole on disk")
    ap.add_argument("file")
    ap.add_argument("--contains", action="append", default=[], metavar="SUB")
    ap.add_argument("--not-contains", action="append", default=[], metavar="SUB")
    ap.add_argument("--ascii", action="store_true")
    ap.add_argument("--tail", type=int, metavar="N",
                    help="echo the last N non-empty lines; fail if fewer")
    ap.add_argument("--min-bytes", type=int, metavar="N")
    a = ap.parse_args()

    if not os.path.isfile(a.file):
        print("FAIL absent: %s" % a.file)
        return 1
    size = os.path.getsize(a.file)
    with open(a.file, encoding="utf-8", errors="replace") as fh:
        body = fh.read()

    fails = []
    for sub in a.contains:
        if sub not in body:
            fails.append("contains: %r not found" % sub)
    for sub in a.not_contains:
        if sub in body:
            fails.append("not-contains: %r found" % sub)
    if a.ascii:
        bad = next((c for c in body if ord(c) > 127), None)
        if bad is not None:
            fails.append("ascii: non-ASCII %r" % bad)
    if a.min_bytes is not None and size < a.min_bytes:
        fails.append("min-bytes: %d < %d" % (size, a.min_bytes))

    lines = [l for l in body.splitlines() if l.strip()]
    if a.tail is not None:
        if len(lines) < a.tail:
            fails.append("tail: %d non-empty lines, want >= %d"
                         % (len(lines), a.tail))
        else:
            for l in lines[-a.tail:]:
                print("  | %s" % l)

    if fails:
        for f in fails:
            print("FAIL %s" % f)
        return 1
    print("OK %s (%d bytes)" % (a.file, size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
