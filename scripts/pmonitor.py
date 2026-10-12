#!/usr/bin/env python3
"""Watch-pattern process monitor (hermes port design 5) for background runs (VM
scans, long fuzzers, spray jobs): a named-PID registry with per-process regex
watch patterns evaluated against a rolling 64KB output tail. `tick` reads only
NEW tail bytes since the last tick, appends one log-grammar line to the
engagement log.md per match

    - 2026-10-12T09:00:00+00:00 | pmon | nmap-full | watch-hit | `Nmap scan report`

records each process heartbeat (last_tick/alive) in the registry, and prunes
dead PIDs to .pmon.dead.json. The registry targets/<eng>/.pmon.json is the
crash-recovery checkpoint, saved after EVERY tick. Default inert until invoked.

    python3 scripts/pmonitor.py add nmap-full --pid 1234 --watch 'Nmap scan report' --logfile /tmp/nmap.out
    python3 scripts/pmonitor.py tick          # poll all registered procs (or name some)
    python3 scripts/pmonitor.py list
    python3 scripts/pmonitor.py rm nmap-full
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(VAULT, "skills", "hooks"))
import _engagement

REG = ".pmon.json"
DEAD = ".pmon.dead.json"
TAIL_CAP = 64 * 1024


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(tmp, path)


def _log(d, name, action, detail):
    """Append one `- ts | pmon | name | action | detail` line to log.md. Detail
    (a regex pattern) is backticked by callers: a bare angle-bracket token would
    break Obsidian rendering."""
    p = os.path.join(d, "log.md")
    prefix = ""
    try:
        with open(p, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            if fh.read(1) != b"\n":
                prefix = "\n"
    except OSError:
        pass
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("%s- %s | pmon | %s | %s | %s\n" % (prefix, _now(), name, action, detail))


def _new_tail(path, offset):
    """(new_tail_text, new_offset): bytes past `offset`, capped to the last
    TAIL_CAP bytes when a burst exceeded it; a shrunk file (rotated) re-reads
    from 0. Missing file: no new bytes."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return "", offset
    if size < offset:
        offset = 0
    start = max(offset, size - TAIL_CAP)
    with open(path, "rb") as fh:
        fh.seek(start)
        chunk = fh.read(size - start)
    return chunk.decode("utf-8", "ignore"), size


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True   # EPERM etc.: exists, just not ours


def cmd_add(a, d):
    reg = _load(os.path.join(d, REG), {"procs": {}})
    if a.name in reg["procs"]:
        print("pmon: %s already registered (pid %s)" % (a.name, reg["procs"][a.name]["pid"]),
              file=sys.stderr)
        return 1
    p = {"pid": a.pid, "watch": a.watch or [], "logfile": a.logfile or "",
         "offset": 0, "added": _now(), "last_tick": None, "alive": True}
    if a.logfile and os.path.isfile(a.logfile):
        p["offset"] = os.path.getsize(a.logfile)   # only future output fires watches
    reg["procs"][a.name] = p
    _save(os.path.join(d, REG), reg)
    print("pmon: registered %s (pid %d, %d watch(es)%s)"
          % (a.name, a.pid, len(p["watch"]), ", tailing" if p["logfile"] else ""))
    return 0


def cmd_tick(a, d):
    reg = _load(os.path.join(d, REG), {"procs": {}})
    procs = reg["procs"]
    dead = []
    for name in (a.names or list(procs)):
        p = procs.get(name)
        if p is None:
            continue
        p["last_tick"] = _now()                    # heartbeat entry
        if not _alive(p["pid"]):
            p["alive"] = False
            _log(d, name, "dead", "pid=%d" % p["pid"])
            dead.append({"name": name, "pid": p["pid"], "ts": _now()})
            continue
        p["alive"] = True
        if p.get("logfile") and p.get("watch"):
            chunk, size = _new_tail(p["logfile"], p.get("offset", 0))
            p["offset"] = size
            for pat in p["watch"]:
                try:
                    hit = bool(re.search(pat, chunk))
                except re.error as e:
                    _log(d, name, "watch-error", "`%s` (%s)" % (pat, e))
                    continue
                if hit:
                    _log(d, name, "watch-hit", "`%s`" % pat)
    for rec in dead:
        del procs[rec["name"]]
    _save(os.path.join(d, REG), reg)               # checkpoint after every tick
    if dead:
        dl = _load(os.path.join(d, DEAD), [])
        dl.extend(dead)
        _save(os.path.join(d, DEAD), dl)
    print("pmon: ticked %d proc(s), %d pruned" % (len(a.names or procs), len(dead)))
    return 0


def cmd_list(a, d):
    reg = _load(os.path.join(d, REG), {"procs": {}})
    if not reg["procs"]:
        print("pmon: no processes registered")
        return 0
    for name, p in sorted(reg["procs"].items()):
        print("%-16s pid %-7d %-5s %s" % (name, p["pid"],
              "alive" if p.get("alive") else "dead",
              " ".join("`%s`" % w for w in p.get("watch", []))))
    return 0


def cmd_rm(a, d):
    reg = _load(os.path.join(d, REG), {"procs": {}})
    if a.name not in reg["procs"]:
        print("pmon: %s not registered" % a.name, file=sys.stderr)
        return 1
    del reg["procs"][a.name]
    _save(os.path.join(d, REG), reg)
    print("pmon: removed %s" % a.name)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="watch-pattern process monitor for background runs")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--eng", help="engagement name under targets/ (default: active)")
    common.add_argument("--eng-dir", help="explicit engagement dir (overrides --eng)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("add", parents=[common], help="register a named pid")
    sp.add_argument("name")
    sp.add_argument("--pid", type=int, required=True)
    sp.add_argument("--watch", action="append", metavar="REGEX",
                    help="watch pattern fired on new tail bytes (repeatable)")
    sp.add_argument("--logfile", help="output file tailed for watch evaluation")
    sp = sub.add_parser("tick", parents=[common], help="poll all (or named) procs once")
    sp.add_argument("names", nargs="*", help="optional subset of process names")
    sub.add_parser("list", parents=[common], help="list registered processes")
    sp = sub.add_parser("rm", parents=[common], help="unregister a process")
    sp.add_argument("name")
    a = ap.parse_args(argv)
    if a.eng_dir:
        d = a.eng_dir
    elif a.eng:
        d = os.path.join(_engagement.TARGETS, a.eng)
    else:
        d = _engagement.active_dir()
    if not d or not os.path.isdir(d):
        print("pmon: no engagement dir", file=sys.stderr)
        return 1
    return {"add": cmd_add, "tick": cmd_tick, "list": cmd_list, "rm": cmd_rm}[a.cmd](a, d)


if __name__ == "__main__":
    sys.exit(main())
