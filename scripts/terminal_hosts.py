#!/usr/bin/env python3
"""Terminal-host exclusion list for multi-host sweep briefs (D19).

Scans the engagement's state.md and Deadends.md for host rows carrying a
terminal marker (no-upstream, unresolvable, NXDOMAIN, SEALED) and prints one
`EXCLUDE: <host> (<marker>)` line per host. Sweep-brief composition pastes
this list and drops the hosts instead of re-probing recorded terminal states.
"""
import os
import re
import sys

MARKERS = ("no-upstream", "unresolv", "nxdomain", "sealed")
HOST_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.IGNORECASE)


def scan_text(text):
    found = {}
    for line in text.splitlines():
        low = line.lower()
        marker = next((m for m in MARKERS if m in low), None)
        if marker is None:
            continue
        for host in HOST_RE.findall(line):
            found.setdefault(host.lower(), marker)
    return found


def main():
    if "--self-test" in sys.argv:
        sample = (
            "| mesa.example.com | sweep | 12 paths | no-upstream proxy error |\n"
            "| api.example.com | sweep | clean, all catch-all |\n"
            "- [!] vnc host vnc.example.com SEALED 2026-10-27 (gate at root)\n"
        )
        got = scan_text(sample)
        assert got == {"mesa.example.com": "no-upstream",
                       "vnc.example.com": "sealed"}, got
        print("self-test OK")
        return 0
    eng = None
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        eng = args[0]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if eng is None:
        with open(os.path.join(root, "targets", "active.md"), encoding="utf-8") as fh:
            eng = fh.read().splitlines()[0].strip()
    found = {}
    for name in ("state.md", "Deadends.md"):
        path = os.path.join(root, "targets", eng, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for host, marker in scan_text(fh.read()).items():
                found.setdefault(host, marker)
    if not found:
        print("no terminal hosts recorded")
        return 0
    for host in sorted(found):
        print("EXCLUDE: %s (%s)" % (host, found[host]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
