#!/usr/bin/env python3
"""Discovered-surface hunt feed (WS9). Driver-owned machine state at
targets/<eng>/.surface-backlog.json. Idempotent import dedupes on
(surface, class_hint) regardless of status; cleared rows never reopen."""
import argparse, datetime, json, os, sys


def _path(eng):
    return os.path.join("targets", eng, ".surface-backlog.json")


def _load(p):
    if not os.path.isfile(p):
        return []
    return json.load(open(p, encoding="utf-8"))["rows"]


def _save(p, rows):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"rows": rows}, f, indent=1, ensure_ascii=True)
        f.write("\n")
    os.replace(tmp, p)


def _now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


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


def cmd_open(eng, cls):
    for r in _load(_path(eng)):
        if r["status"] == "open" and (not cls or r["class_hint"] == cls):
            print(json.dumps(r))
    return 0


def cmd_claim(eng, rid, lane):
    p = _path(eng)
    rows = _load(p)
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


def cmd_clear(eng, rid):
    p = _path(eng)
    rows = _load(p)
    for r in rows:
        if r["id"] == rid:
            r["status"] = "cleared"
            r["cleared_at"] = _now()
    _save(p, rows)
    print("cleared %d" % rid)
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
    d.add_argument("--id", type=int, required=True)
    a = ap.parse_args()
    if a.cmd == "import-jsonl":
        return cmd_import(a.eng, a.source, a.file)
    if a.cmd == "open":
        return cmd_open(a.eng, a.cls)
    if a.cmd == "claim":
        return cmd_claim(a.eng, a.id, a.lane)
    return cmd_clear(a.eng, a.id)


if __name__ == "__main__":
    sys.exit(main())
