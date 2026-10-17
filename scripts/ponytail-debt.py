#!/usr/bin/env python3
"""ponytail-debt.py - harvest `ponytail:` marker comments (the debt ledger).

Close-out nudges this sweep when framework files change since the last stamp
(.ponytail-debt-stamp, the .wiki-stamp mtime pattern). Lists every marker with
file:line so the ceiling debt is visible before it compounds.

Usage:
  python3 scripts/ponytail-debt.py            # list markers (exit 1 if any)
  python3 scripts/ponytail-debt.py --stamp    # list, then refresh the stamp
"""
import argparse
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAMP = os.path.join(ROOT, ".ponytail-debt-stamp")
SCAN_DIRS = ("scripts", "skills", "setup")
# ponytail: skip binary/cache noise; pygments do not carry markers anyway
SKIP = ("__pycache__", ".git", "node_modules", ".pytest_cache")
MARK = re.compile(r"(shortcut|ponytail):")


def markers():
    out = []
    for d in SCAN_DIRS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, d)):
            dirnames[:] = [x for x in dirnames if x not in SKIP]
            for fn in sorted(filenames):
# ponytail: markers live in CODE comments; .md prose describes the convention.
# .ps1 scanned too (skills carry PowerShell helpers - junction-sweep.ps1 was
# invisible to the ledger until this tuple grew).
                if not fn.endswith((".py", ".sh", ".js", ".ps1")):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        for i, line in enumerate(fh, 1):
                            if MARK.search(line):
                                out.append((os.path.relpath(p, ROOT), i,
                                            line.strip()[:120]))
                except OSError:
                    pass
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ponytail-debt.py")
    ap.add_argument("--stamp", action="store_true",
                    help="refresh .ponytail-debt-stamp after listing")
    a = ap.parse_args(argv)
    rows = markers()
    if not rows:
        print("ponytail debt: 0 markers. Clean.")
    else:
        print("ponytail debt: %d marker(s):" % len(rows))
        for f, i, txt in rows:
            print("  %s:%d: %s" % (f, i, txt))
    if a.stamp:
        with open(STAMP, "w") as fh:
            fh.write(str(time.time()))
        print("stamp refreshed: %s" % STAMP)
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
