#!/usr/bin/env python3
"""Discovered-surface hunt feed (WS9). Driver-owned machine state at
targets/<eng>/.surface-backlog.json. Idempotent import dedupes on
(surface, class_hint) regardless of status; cleared rows never reopen."""
import argparse, datetime, json, os, sys


VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _path(eng):
    return os.path.join(VAULT, "targets", eng, ".surface-backlog.json")


class BacklogCorrupt(Exception):
    """The .surface-backlog.json store is truncated or re-shaped (WS1.3).
    str(e) is the operator hint. In-process callers (offensive.py WS4.1)
    catch this and degrade; the CLI wrappers convert it to a clean exit-2."""


def load_rows(p):
    """Raw rows of the store, [] when the store is absent. Raises
    BacklogCorrupt on a truncated/re-shaped store."""
    if not os.path.isfile(p):
        return []
    try:
        return json.load(open(p, encoding="utf-8"))["rows"]
    except (ValueError, KeyError, TypeError, OSError) as e:
        raise BacklogCorrupt(
            "backlog corrupt: move aside and re-import (%s): %s" % (p, str(e)[:80]))


def _die_corrupt(e):
    print(str(e), file=sys.stderr)
    sys.exit(2)


def _load(p):
    try:
        return load_rows(p)
    except BacklogCorrupt as e:
        _die_corrupt(e)


def _save(p, rows):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"rows": rows}, f, indent=1, ensure_ascii=True)
        f.write("\n")
    os.replace(tmp, p)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_import(eng, source, file):
    p = _path(eng)
    rows = _load(p)
    seen = {(r["surface"], r["class_hint"]) for r in rows}
    nxt = max([r["id"] for r in rows], default=0) + 1
    added = 0
    for line in open(file, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        key = (row.get("surface", ""), row.get("class_hint", ""))
        if key in seen:
            continue
        seen.add(key)
        rows.append({"id": nxt, "surface": key[0], "host": row.get("host", ""),
                     "source": source, "class_hint": key[1],
                     "found_at": _now(), "status": "open"})
        nxt += 1
        added += 1
    _save(p, rows)
    print("added=%d total=%d" % (added, len(rows)))
    return 0


def open_rows(eng, cls=""):
    """Open rows matching cls ("" = all), as dicts - the in-process API the
    driver uses (WS4.1). Raises BacklogCorrupt on a corrupt store; cmd_open
    keeps the CLI's exit-2 for its own callers."""
    return [r for r in load_rows(_path(eng))
            if r["status"] == "open" and (not cls or r["class_hint"] == cls)]


def cmd_open(eng, cls):
    try:
        return open_rows(eng, cls)
    except BacklogCorrupt as e:
        _die_corrupt(e)


def claim_row(eng, rid, lane):
    """Claim one row for a lane - the in-process API (WS4.1). Raises
    BacklogCorrupt on a corrupt store; returns 1 on refusal, 0 on claim."""
    p = _path(eng)
    rows = load_rows(p)
    hit = None
    for r in rows:
        if r["id"] == rid:
            hit = r
    if hit is None:
        print("REFUSED: no row %d" % rid)
        return 1
    if hit["status"] != "open":
        print("REFUSED: row %d is %s" % (rid, hit["status"]))
        return 1
    hit["status"] = "claimed"
    hit["lane"] = lane
    _save(p, rows)
    print("claimed %d -> %s" % (rid, lane))
    return 0


def cmd_claim(eng, rid, lane):
    try:
        return claim_row(eng, rid, lane)
    except BacklogCorrupt as e:
        _die_corrupt(e)


def cmd_clear(eng, rids):
    p = _path(eng)
    rows = _load(p)
    for r in rows:
        if r["id"] in rids:
            r["status"] = "cleared"
            r["cleared_at"] = _now()
    _save(p, rows)
    print("cleared %s" % ",".join(str(i) for i in sorted(rids)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("eng")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("import-jsonl")
    i.add_argument("file")
    i.add_argument("--source", required=True)
    o = sub.add_parser("open")
    o.add_argument("--class", dest="cls", default="")
    c = sub.add_parser("claim")
    c.add_argument("--id", type=int, required=True)
    c.add_argument("--lane", required=True)
    d = sub.add_parser("clear")
    d.add_argument("--id", type=int, required=True, nargs="+")
    a = ap.parse_args()
    if a.cmd == "import-jsonl":
        return cmd_import(a.eng, a.source, a.file)
    if a.cmd == "open":
        for r in cmd_open(a.eng, a.cls):
            print(json.dumps(r))
        return 0
    if a.cmd == "claim":
        return cmd_claim(a.eng, a.id, a.lane)
    return cmd_clear(a.eng, a.id)

if __name__ == "__main__":
    sys.exit(main())
