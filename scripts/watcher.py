#!/usr/bin/env python3
"""Engagement digest watcher (hermes port design 4): tails the active engagement's
log.md + oob.md and turns new log-grammar events (lane completions `-> VERIFIED`,
OOB HIT rows, FIND mentions) into operator digests. DEFAULT OFF: nothing schedules
it; it only acts when run explicitly.

    python3 scripts/watcher.py            # 60s tick loop (foreground)
    python3 scripts/watcher.py --once     # single tick, cron/gateway friendly
    python3 scripts/watcher.py --status   # heartbeat + pending queue depth
    python3 scripts/watcher.py --eng NAME | --eng-dir PATH

Delivery: ZT_WATCH_TELEGRAM_TOKEN + ZT_WATCH_CHAT_ID set -> POST to
api.telegram.org sendMessage (entries joined, 4000-char cap). Without them: DRY
mode, digests print to stdout and are still marked delivered, so a missing env
var never stalls or crashes an engagement. Single ticker per engagement via flock
on targets/<eng>/.watcher.lock (mtime touched every tick; a busy lock whose file
is older than 15 min is a hung ticker and gets overridden). Delivery is
CLAIM-ONCE: the digest id is appended to .watcher-state.json `sent` BEFORE
sending, so a death after claim leaves the entry marked sent (outcome unknown,
never retried; losing one delivery beats duplicating). Every tick writes
.watcher-heartbeat.json {ts, last_error, deliveries}: a dead ticker stops
updating it, a failing one keeps heartbeating with last_error set.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(VAULT, "skills", "hooks"))
import _engagement

LOCK = ".watcher.lock"
HEARTBEAT = ".watcher-heartbeat.json"
STATE = ".watcher-state.json"
STALE_S = 15 * 60
GRAMMAR_RE = re.compile(r"-> VERIFIED|OOB HIT|\bFIND\b")
OOB_HIT_ROW_RE = re.compile(r"\|\s*HIT\s*\|")


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


def send_telegram(token, chat_id, text):
    """One sendMessage POST; True on HTTP 200, False on any failure (never raises,
    so a delivery failure degrades to a heartbeat error, not a crash)."""
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    body = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def _eid(fname, off, line):
    return hashlib.sha1(("%s:%d:%s" % (fname, off, line))
                        .encode("utf-8", "ignore")).hexdigest()[:12]


def _new_entries(d, fname, last, extra_re=None):
    """(entries, size) for grammar-matching lines among the bytes past `last`.
    A shrunk file (rotated/truncated) re-diffs from offset 0."""
    p = os.path.join(d, fname)
    try:
        size = os.path.getsize(p)
    except OSError:
        return [], 0
    if size < last:
        last = 0
    with open(p, "rb") as fh:
        fh.seek(last)
        chunk = fh.read().decode("utf-8", "ignore")
    out = []
    off = last
    for line in chunk.splitlines():
        s = line.strip()
        if s and (GRAMMAR_RE.search(s) or (extra_re and extra_re.search(s))):
            out.append({"id": _eid(fname, off, s), "text": "[%s] %s" % (fname, s)})
        off += len(line) + 1
    return out, size


def tick(d):
    """One diff+deliver pass. Returns (delivered_count, error_or_None)."""
    st = _load(os.path.join(d, STATE),
               {"last_size": 0, "last_oob_size": 0, "sent": []})
    log_e, size = _new_entries(d, "log.md", st.get("last_size", 0))
    oob_e, oob_size = _new_entries(d, "oob.md", st.get("last_oob_size", 0),
                                   OOB_HIT_ROW_RE)
    st["last_size"], st["last_oob_size"] = size, oob_size
    pending = [e for e in log_e + oob_e if e["id"] not in st["sent"]]
    if pending:
        # CLAIM-ONCE: persist the claim before any send attempt, so a crash after
        # claim never duplicates the delivery on restart.
        st["sent"] = list(st.get("sent", [])) + [e["id"] for e in pending]
    _save(os.path.join(d, STATE), st)
    err = None
    if pending:
        text = "\n".join(e["text"] for e in pending)[:4000]
        token = os.environ.get("ZT_WATCH_TELEGRAM_TOKEN")
        chat = os.environ.get("ZT_WATCH_CHAT_ID")
        if token and chat:
            if not send_telegram(token, chat, text):
                err = "telegram send failed for %d claimed entri(es)" % len(pending)
        else:
            print(text)   # dry mode: stdout, still marked delivered above
    return len(pending), err


def _heartbeat(d, err):
    st = _load(os.path.join(d, STATE), {})
    _save(os.path.join(d, HEARTBEAT),
          {"ts": _now(), "last_error": err,
           "deliveries": len(st.get("sent", []))})


def run_tick(d):
    try:
        _, err = tick(d)
    except Exception as e:                      # never crash the engagement
        err = "%s: %s" % (type(e).__name__, e)
    _heartbeat(d, err)
    return 0 if err is None else 1


def _acquire(d):
    """flock the ticker lock; None when proceeding unlocked (stale holder).
    Exits 0 when a fresh ticker already owns the engagement."""
    p = os.path.join(d, LOCK)
    fh = open(p, "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close()
        try:
            stale = time.time() - os.path.getmtime(p) > STALE_S
        except OSError:
            stale = False
        if stale:
            print("watcher: lock busy but stale (>15 min, hung ticker); "
                  "proceeding unlocked", file=sys.stderr)
            return None
        print("watcher: another ticker owns this engagement; nothing to do",
              file=sys.stderr)
        sys.exit(0)


def status(d):
    hb = _load(os.path.join(d, HEARTBEAT), None)
    print("heartbeat: %s" % (json.dumps(hb) if hb else "none (never ticked)"))
    sent = set(_load(os.path.join(d, STATE), {}).get("sent", []))
    log_e, _ = _new_entries(d, "log.md", 0)
    oob_e, _ = _new_entries(d, "oob.md", 0, OOB_HIT_ROW_RE)
    print("queue depth: %d" % sum(1 for e in log_e + oob_e if e["id"] not in sent))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="engagement digest watcher (dry unless telegram env is set)")
    ap.add_argument("--once", action="store_true", help="single tick (cron-style)")
    ap.add_argument("--status", action="store_true",
                    help="print heartbeat + pending queue depth")
    ap.add_argument("--eng", help="engagement name under targets/ (default: active)")
    ap.add_argument("--eng-dir", help="explicit engagement dir (overrides --eng)")
    a = ap.parse_args(argv)
    if a.eng_dir:
        d = a.eng_dir
    elif a.eng:
        d = os.path.join(_engagement.TARGETS, a.eng)
    else:
        d = _engagement.active_dir()
    if not d or not os.path.isdir(d):
        print("watcher: no engagement dir to watch", file=sys.stderr)
        return 1
    if a.status:
        return status(d)
    lock = _acquire(d)
    try:
        if a.once:
            return run_tick(d)
        while True:   # 60s tick loop
            if lock is not None:
                os.utime(os.path.join(d, LOCK), None)
            run_tick(d)
            time.sleep(60)
    except KeyboardInterrupt:
        return 0
    finally:
        if lock is not None:
            lock.close()


if __name__ == "__main__":
    sys.exit(main())
