#!/usr/bin/env python3
"""tells.py - small-indicator battery over local source/response files.

Greps a file or directory tree for the curated tell table (tells.json, the
single source of truth; add rows as you learn them) and prints one line per
hit: path:line [class] snippet -> Skill(x) | note. An accelerator, NOT a
substitute for the read-first mandate: read the hit blocks first, then the
full read where the mandate applies (post-foothold source review).

Usage:
  python3 scripts/tells.py <path> [<path> ...]   # scan files/dirs
  python3 scripts/tells.py --list                # dump the tracked table

Python 3 stdlib only. Always exits 0 (a lens, not a gate).
"""
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TABLE = SCRIPT_DIR / "tells.json"

MAX_FILE = 50 * 1024 * 1024   # skip files above 50MB
SNIPPET = 100                 # printed line cap
SKIP_DIRS = {".git", "node_modules", "__pycache__"}


def load_tells(path=TABLE):
    """Tell rows (dicts) from the table file; [] on any problem."""
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8")).get("tells", [])
    except (OSError, ValueError):
        return []
    return rows


def compile_tells(rows):
    """Rows -> [(compiled_re, row)], dropping un-compilable rows (warn once).
    A row carries `re` (content pattern) or `fname` (path pattern); either way
    it compiles the same. A bad regex must degrade that one row, never the run."""
    out = []
    for row in rows:
        pat = row.get("re") or row.get("fname")
        if not pat:
            print("tells: skipping row with no re/fname: %s" % row, file=sys.stderr)
            continue
        try:
            out.append((re.compile(pat), row))
        except re.error as e:
            print("tells: skipping bad row (%s): %s" % (e, pat), file=sys.stderr)
    return out


def _files(paths):
    for p in map(Path, paths):
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not (SKIP_DIRS & set(f.parts)):
                    yield f
        elif p.is_file():
            yield p


def scan(paths, table, out=print):
    """Print one line per tell hit across paths. Binary files are skipped for
    CONTENT rows; fname rows match the path itself and always fire."""
    for f in _files(paths):
        for rx, row in table:
            if row.get("fname") and rx.search(str(f)):
                skill = "Skill(%s)" % row["skill"] if row.get("skill") else "no skill"
                out("%s  [%s] FILENAME %s  -> %s | %s"
                    % (f, row.get("class", "?"), rx.pattern, skill, row.get("note", "")))
        try:
            if f.stat().st_size > MAX_FILE:
                continue
            raw = f.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:8192]:
            continue                                  # binary
        for i, line in enumerate(raw.decode("utf-8", errors="ignore").splitlines(), 1):
            for rx, row in table:
                if row.get("fname"):
                    continue                          # path row, already handled
                if rx.search(line):
                    snippet = line.strip()[:SNIPPET]
                    skill = "Skill(%s)" % row["skill"] if row.get("skill") else "no skill"
                    out("%s:%d  [%s] %s  -> %s | %s"
                        % (f, i, row.get("class", "?"), snippet, skill,
                           row.get("note", "")))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    table = compile_tells(load_tells())
    if "--list" in argv or not argv:
        for _rx, row in table:
            kind = "FILENAME" if row.get("fname") else "CONTENT"
            print("-> [%s] %s /%s/ Skill(%s) | %s"
                  % (row.get("class", "?"), kind,
                     row.get("re") or row.get("fname", ""),
                     row.get("skill", ""), row.get("note", "")))
        return 0
    scan(argv, table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
