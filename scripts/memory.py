#!/usr/bin/env python3
"""memory.py - the two-store persistent memory for ZTORCH (hermes memory port).

session/memory.md holds two sections: `## Operator` (who the operator is,
preferences, style, expectations; budget 1375 chars) and `## Environment`
(tool quirks, conventions, config gotchas, paths; budget 2200 chars). Entries
are `- ` bullets; declarative facts, never instructions to self. The snapshot
is injected once at SessionStart (frozen semantics: writes land on disk for
the NEXT session, never hot-injected mid-session).

Store semantics ported from hermes (memory_tool_store.py):
- add is idempotent (exact-duplicate refused with a note, not an error)
- an over-budget single add is refused with the "retry as ONE batch" hint;
  a batch is checked on its FINAL state only
- a batch may not empty a store
- old_text locates an entry typography-folded (curly/straight quotes, dashes,
  ellipsis fold); zero match returns the 3 closest entries instead of failing;
  multiple matches refuse listing the candidates
- drift guard: a single entry larger than the whole budget -> .bak + refuse
- atomic temp+rename write under flock
- threat-scan advisory on write (exfil/injection shapes): advisory only, the
  vault is operator-owned

Usage:
  memory.py view  [--store operator|environment]     render with budget header
  memory.py check                                      budgets + counts, rc!=0 over
  memory.py add  --store S "fact"
  memory.py replace --store S --old "..." --new "..."
  memory.py remove --store S --old "..."
  memory.py batch --ops '[{"op":"add","store":"environment","new":"..."},
                          {"op":"remove","store":"operator","old":"..."}]'
"""
import argparse
import difflib
import fcntl
import json
import os
import re
import shutil
import sys
import tempfile
import time

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMFILE = os.path.join(VAULT, "session", "memory.md")
LIMITS = {"operator": 1375, "environment": 2200}  # hermes USER/MEMORY budgets
SECTIONS = {"operator": "## Operator", "environment": "## Environment"}

THREAT_PATTERNS = [
    (r"(curl|wget)[^|;]*\|\s*(ba)?sh", "pipe-to-shell exfil shape"),
    (r"(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}", "embedded secret"),
    (r"ignore (all )?(previous|prior) instructions", "prompt-injection shape"),
    (r"[​‎‏‪-‮]", "invisible/bidi unicode"),
]

FOLD = {"‘": "'", "’": "'", "“": '"', "”": '"',
        "–": "-", "—": "-", "…": "..."}


def fold(s):
    for k, v in FOLD.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s).strip().lower()


def parse(path=None):
    path = path or MEMFILE
    """Return {store: [entries]} preserving file order."""
    stores = {k: [] for k in SECTIONS}
    if not os.path.exists(path):
        return stores, []
    cur, pre = None, []
    for ln in open(path, encoding="utf-8").read().splitlines():
        if ln.startswith("## "):
            cur = next((k for k, h in SECTIONS.items() if ln.startswith(h)), "other")
            continue
        if cur is None:
            pre.append(ln)
        elif ln.startswith("- ") and ln[2:].strip():
            stores[cur].append(ln[2:].strip())
    return {k: v for k, v in stores.items() if k in SECTIONS}, pre


def render(stores):
    out = ["# Session memory (two stores; see scripts/memory.py)", ""]
    for key in ("operator", "environment"):
        out.append(SECTIONS[key])
        used = sum(len(e) + 1 for e in stores.get(key, []))
        pct = 100 * used // LIMITS[key] if LIMITS[key] else 0
        out.append(f"<!-- [{pct}% - {used}/{LIMITS[key]} chars] -->")
        out += [f"- {e}" for e in stores.get(key, [])] or ["- (empty)"]
        out.append("")
    return "\n".join(out) + "\n"


def atomic_write(text):
    os.makedirs(os.path.dirname(MEMFILE), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MEMFILE), prefix=".memory-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        lock = open(os.path.dirname(MEMFILE) + "/.memory.lock", "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            shutil.move(tmp, MEMFILE)
        finally:
            lock.close()
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def used(stores, key):
    return sum(len(e) + 1 for e in stores[key])


def find(stores, key, old):
    """Typography-folded locator; returns (exact, matches, closest3)."""
    tgt = fold(old)
    entries = stores[key]
    matches = [e for e in entries if fold(e) == tgt or tgt in fold(e)]
    closest = difflib.get_close_matches(tgt, [fold(e) for e in entries], n=3, cutoff=0.3)
    return matches, closest


def threat_scan(text):
    return [f"{name}: {pat}" for pat, name in THREAT_PATTERNS if re.search(pat, text, re.I)]


def op_add(stores, op):
    key, new = op["store"], op["new"].strip()
    if key not in SECTIONS:
        raise ValueError(f"bad store: {key}")
    if any(fold(e) == fold(new) for e in stores[key]):
        return "duplicate (no change)"
    if len(new) + 1 > LIMITS[key]:
        raise ValueError(f"entry alone exceeds the {key} budget; split or shorten it")
    stores[key].append(new)
    return None


def op_remove(stores, op):
    key, old = op["store"], op["old"]
    matches, closest = find(stores, key, old)
    if not matches:
        raise ValueError("no match; closest entries: " + "; ".join(closest) if closest else "no match (store empty)")
    if len(matches) > 1:
        raise ValueError("ambiguous, matches:\n  " + "\n  ".join(matches))
    stores[key].remove(matches[0])
    return None


def apply_ops(stores, ops, batch=False):
    """Apply all ops; on any error nothing is written. Budget checked on final state."""
    msgs = []
    for op in ops:
        kind = op.get("op")
        fn = {"add": op_add, "remove": op_remove,
              "replace": lambda s, o: (op_remove(s, o), op_add(s, {"store": o["store"], "new": o["new"]}))[1]}[kind]
        m = fn(stores, op)
        if m:
            msgs.append(m)
    for key in SECTIONS:
        u = used(stores, key)
        if u > LIMITS[key]:
            raise ValueError(
                f"{key} over budget ({u}/{LIMITS[key]}): retry as ONE batch that "
                "removes or shortens stale entries AND adds the new one")
        if batch and not stores[key]:
            raise ValueError(f"batch may not empty the {key} store")
    return msgs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("view"); v.add_argument("--store", choices=SECTIONS)
    sub.add_parser("check")
    a = sub.add_parser("add"); a.add_argument("--store", required=True, choices=SECTIONS); a.add_argument("new")
    r = sub.add_parser("replace"); r.add_argument("--store", required=True, choices=SECTIONS)
    r.add_argument("--old", required=True); r.add_argument("--new", required=True)
    rm = sub.add_parser("remove"); rm.add_argument("--store", required=True, choices=SECTIONS); rm.add_argument("--old", required=True)
    b = sub.add_parser("batch"); b.add_argument("--ops", required=True)
    args = ap.parse_args()

    stores, _ = parse()
    if args.cmd == "view":
        if args.store:
            print(f"[{100*used(stores,args.store)//LIMITS[args.store]}% - "
                  f"{used(stores,args.store)}/{LIMITS[args.store]} chars]")
            print("\n".join(f"- {e}" for e in stores[args.store]) or "- (empty)")
        else:
            sys.stdout.write(render(stores))
        return 0
    if args.cmd == "check":
        rc = 0
        for key in SECTIONS:
            u = used(stores, key)
            flag = "OK " if u <= LIMITS[key] else "OVER"
            if u > LIMITS[key]:
                rc = 1
            print(f"{flag} {key}: {u}/{LIMITS[key]} chars, {len(stores[key])} entries")
        return rc

    # drift guard before any write path
    for key in SECTIONS:
        for e in stores[key]:
            if len(e) + 1 > LIMITS[key]:
                bak = MEMFILE + ".bak"
                if os.path.exists(MEMFILE):
                    shutil.copy2(MEMFILE, bak)
                    print(f"drift guard: oversized entry found, snapshot at {bak}", file=sys.stderr)
                return 2

    if args.cmd == "add":
        ops = [{"op": "add", "store": args.store, "new": args.new}]
    elif args.cmd == "replace":
        ops = [{"op": "replace", "store": args.store, "old": args.old, "new": args.new}]
    elif args.cmd == "remove":
        ops = [{"op": "remove", "store": args.store, "old": args.old}]
    else:
        ops = json.loads(args.ops)
    batch = args.cmd == "batch"
    try:
        msgs = apply_ops(stores, ops, batch=batch)
    except (ValueError, KeyError, TypeError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    hits = threat_scan(json.dumps(ops))
    atomic_write(render(stores))
    for m in msgs:
        print(m)
    for h in hits:
        print(f"ADVISORY threat-shape in written entry ({h}) - operator review", file=sys.stderr)
    print(f"memory written {time.strftime('%Y-%m-%d %H:%M')}; operator "
          f"{used(stores,'operator')}/{LIMITS['operator']}, environment "
          f"{used(stores,'environment')}/{LIMITS['environment']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
