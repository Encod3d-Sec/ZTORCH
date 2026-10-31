#!/usr/bin/env python3
"""merge_append.py - the ONE way a lane's output merges into a state file.

R10 (2026-10-31 retro): state.md / log.md appends go through here - never
Edit-on-prose-anchor. That ritual corrupted state.md twice in one run
(glue-onto-last-line, duplicate merges after compaction, non-ASCII drift);
this script makes each failure a refused exit-1 instead of a repair.

  python3 scripts/merge_append.py state.md --tag lane-42 <<'EOF'
  | 10.0.0.1 | api | anon | 200 | evidence |
  EOF

Guards:
  glue        file's last line never fuses with the block's first line
  --id ID     refuse if ID already appears anywhere in the file (duplicate
              merge after a lane re-run / compaction replay)
  --tag TAG   same refusal, looser key (lane tag)
  ASCII       block must be pure ASCII; --allow-nonascii overrides (a stray
              em-dash in a merged row broke rendering twice)
  read-back   after the write the last line is printed and must equal the
              block's last line, or exit 1
"""
import argparse
import sys


def main():
    ap = argparse.ArgumentParser(
        description="append a block to a state file (single-writer merge)")
    ap.add_argument("file")
    ap.add_argument("block", nargs="?",
                    help="text to append; '-' or omitted reads stdin")
    ap.add_argument("--id", help="row id that must not already be present")
    ap.add_argument("--tag", help="lane tag that must not already be present")
    ap.add_argument("--allow-nonascii", action="store_true")
    a = ap.parse_args()

    raw = a.block if a.block not in (None, "-") else sys.stdin.read()
    lines = [l.rstrip("\r\n") for l in raw.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        print("merge_append: empty block, nothing written", file=sys.stderr)
        return 1
    block = "\n".join(lines) + "\n"

    if not a.allow_nonascii:
        for i, l in enumerate(lines, 1):
            if any(ord(c) > 127 for c in l):
                print("merge_append: non-ASCII in block line %d (%r); fix it "
                      "or pass --allow-nonascii" % (i, l[:60]), file=sys.stderr)
                return 1

    try:
        with open(a.file, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    except FileNotFoundError:
        body = ""
    for needle, label in ((a.id, "--id"), (a.tag, "--tag")):
        if needle and needle in body:
            print("merge_append: %s %r already in %s - duplicate merge "
                  "refused" % (label, needle, a.file), file=sys.stderr)
            return 1

    prefix = body
    while prefix.endswith("\n\n"):
        prefix = prefix[:-1]
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    with open(a.file, "w", encoding="utf-8") as fh:
        fh.write(prefix + block)

    with open(a.file, encoding="utf-8", errors="replace") as fh:
        tail = [l for l in fh.read().splitlines() if l.strip()]
    last = tail[-1] if tail else ""
    print("merge_append: +%d lines -> %s" % (len(lines), a.file))
    print("  last: %s" % last)
    if last != lines[-1]:
        print("merge_append: read-back mismatch - last line is not the "
              "block's last line", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
