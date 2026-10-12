#!/usr/bin/env python3
"""session_search.py - search ZTORCH session/engagement history (hermes port).

Four shapes over the harness's own history files (engagement log.md/state.md/
decisions.md, session/log.md, session/hot-archive.md):

  session_search.py query <text> [--eng NAME] [--all] [--n 10]
  session_search.py scroll <file> <line-no> [--window 5]
  session_search.py read <file>
  session_search.py browse

Ported semantics (hermes session_search tool):
- automation DEMOTED below operator turns: lane lines (`- lane ...`) and
  log-grammar tool lines (`| tool |`) score x0.3 before ranking
- lineage dedup: a lane line and its appended verdict line are ONE hit
- top-hit-only hydration: only the best hit gets surrounding context
- 2000-char cap per displayed line
- results print to stdout only (client-data boundary: nothing is copied out)
"""
import argparse
import glob
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP = 2000
AUTOMATION = re.compile(r"^- lane |lane .*in flight|\| tool \||\| lane \|")


def history_files(eng=None, search_all=False):
    files = []
    if search_all or eng:
        engs = [eng] if eng else sorted(
            os.path.basename(d) for d in glob.glob(os.path.join(VAULT, "targets", "*")) if os.path.isdir(d))
        for e in engs:
            for f in ("log.md", "state.md", "decisions.md", "Killchain.md", "Deadends.md"):
                p = os.path.join(VAULT, "targets", e, f)
                if os.path.exists(p):
                    files.append(p)
    else:
        active = os.path.join(VAULT, "targets", "active.md")
        e = open(active).read().strip() if os.path.exists(active) else None
        if e and os.path.isdir(os.path.join(VAULT, "targets", e)):
            for f in ("log.md", "state.md", "decisions.md", "Killchain.md", "Deadends.md"):
                p = os.path.join(VAULT, "targets", e, f)
                if os.path.exists(p):
                    files.append(p)
    for f in ("session/log.md", "session/hot-archive.md"):
        p = os.path.join(VAULT, f)
        if os.path.exists(p):
            files.append(p)
    return files


def score(line, terms):
    low = line.lower()
    hits = sum(low.count(t) for t in terms)
    if not hits:
        return 0.0
    s = hits / (len(line) ** 0.3)
    if AUTOMATION.search(line):
        s *= 0.3
    return s


def cap(s):
    return s if len(s) <= CAP else s[:CAP - 13] + " ...[capped]"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("query"); q.add_argument("text")
    q.add_argument("--eng"); q.add_argument("--all", action="store_true"); q.add_argument("--n", type=int, default=10)
    sc = sub.add_parser("scroll"); sc.add_argument("file"); sc.add_argument("line", type=int)
    sc.add_argument("--window", type=int, default=5)
    r = sub.add_parser("read"); r.add_argument("file")
    sub.add_parser("browse")
    args = ap.parse_args()

    if args.cmd == "browse":
        for p in history_files(search_all=True):
            n = sum(1 for _ in open(p, encoding="utf-8", errors="ignore"))
            print(f"{os.path.relpath(p, VAULT)}  ({n} lines)")
        return 0

    if args.cmd == "read":
        p = args.file if os.path.isabs(args.file) else os.path.join(VAULT, args.file)
        if not os.path.exists(p):
            print(f"no such file: {args.file}", file=sys.stderr)
            return 1
        txt = open(p, encoding="utf-8", errors="ignore").read()
        print(cap(txt))
        return 0

    if args.cmd == "scroll":
        p = args.file if os.path.isabs(args.file) else os.path.join(VAULT, args.file)
        if not os.path.exists(p):
            print(f"no such file: {args.file}", file=sys.stderr)
            return 1
        lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
        lo, hi = max(0, args.line - args.window), min(len(lines), args.line + args.window + 1)
        for i in range(lo, hi):
            print(f"{i + 1}: {cap(lines[i])}")
        return 0

    # query
    terms = [t for t in re.split(r"\s+", args.text.lower()) if t]
    files = history_files(eng=args.eng, search_all=args.all)
    hits = []
    for p in files:
        try:
            lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
        except OSError:
            continue
        # lineage dedup: a lane emits a dispatch line, later closed by appending
        # the verdict to a NEW line; only the closed (verdict-bearing) line counts
        lane_verdict = {}
        for i, ln in enumerate(lines):
            if ln.startswith("- lane ") and ("-> VERIFIED" in ln or "-> NOT VERIFIED" in ln):
                m = re.match(r"^- lane (\S+)", ln)
                if m:
                    lane_verdict[m.group(1)] = i
        for i, ln in enumerate(lines):
            s = score(ln, terms)
            if s <= 0:
                continue
            m = re.match(r"^- lane (\S+)", ln)
            if m and m.group(1) in lane_verdict and lane_verdict[m.group(1)] != i:
                continue  # superseded by its own verdict line
            hits.append((s, os.path.relpath(p, VAULT), i + 1, ln))
    hits.sort(key=lambda h: -h[0])
    shown = hits[:args.n]
    if not shown:
        print(f"no hits for {args.text!r} across {len(files)} files "
              "(thin results are not ground truth: the file set may be incomplete)")
        return 1
    for rank, (s, rel, no, ln) in enumerate(shown, 1):
        print(f"{rank}. {rel}:{no}  (score {s:.1f})")
        print(f"   {cap(ln)}")
        if rank == 1:  # top-hit-only hydration
            p = os.path.join(VAULT, rel)
            all_lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
            for j in range(max(0, no - 3), min(len(all_lines), no + 2)):
                print(f"   | {j + 1}: {cap(all_lines[j])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
