#!/usr/bin/env python3
"""curator.py - skill lifecycle curator for ZTORCH (hermes curator port).

No daemon: the SessionStart hook invokes it when skills/.curator-state.json
says the last run is older than INTERVAL_DAYS (7). Pure transitions, no LLM:
- anchor = max(last_used from telemetry, last ledger patch, frontmatter created)
- active -> stale at STALE_DAYS (14); stale -> archived (git mv to
  skills/.archive/YYYYMMDD-<name>) at ARCHIVE_DAYS (30); any fresh anchor
  reactivates. First sight of a skill with no lifecycle frontmatter seeds it
  (state active, created today) - seeding reanchors the clock to NOW.
- NEVER archived: pinned: true skills, skills the harness references
  (scripts/triggers.json, scripts/routing.json, skills/workflow/engage/SKILL.md),
  and young never-used skills (absence of use is not evidence).
Usage telemetry comes from targets/*/.events.jsonl (tool == "Skill" events,
written by tool-telemetry.py) and skills/.skill-ledger.jsonl (skill_manage
writes). LLM consolidation stays OFF (operator decision, per the port spec).

Usage: curator.py [--force] [--dry-run]
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(VAULT, "skills")
sys.path.insert(0, os.path.join(VAULT, "skills", "hooks"))
STATE = os.path.join(SKILLS, ".curator-state.json")
LEDGER = os.path.join(SKILLS, ".skill-ledger.jsonl")
INTERVAL_DAYS, STALE_DAYS, ARCHIVE_DAYS = 7, 14, 30
BACKUP_DIR = os.path.join(SKILLS, ".curator-backups")


def backup_skills():
    """P7: tar.gz snapshot before any mutating pass (hermes curator_backup port);
    keep 2, exclude .git/.archive/.locks/backups so the tar stays small."""
    import tarfile
    os.makedirs(BACKUP_DIR, exist_ok=True)
    out = os.path.join(BACKUP_DIR, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ".tar.gz")
    with tarfile.open(out, "w:gz") as t:
        for root, dirs, files in os.walk(SKILLS):
            dirs[:] = [d for d in dirs if d not in
                       (".git", ".archive", ".locks", "__pycache__", ".curator-backups")]
            for f in files:
                if f.endswith(".lock"):
                    continue
                p = os.path.join(root, f)
                t.add(p, arcname=os.path.relpath(p, SKILLS))
    olds = sorted(x for x in os.listdir(BACKUP_DIR) if x.endswith(".tar.gz"))
    for o in olds[:-2]:
        os.unlink(os.path.join(BACKUP_DIR, o))
    return out


def days_since(iso):
    if not iso:
        return None
    try:
        return (date.today() - datetime.strptime(iso[:10], "%Y-%m-%d").date()).days
    except ValueError:
        return None


def fm_of(path):
    txt = open(path, encoding="utf-8", errors="ignore").read()
    m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
    fm = {}
    if m:
        for ln in m.group(1).splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                fm[k.strip()] = v.strip()
    return fm, txt, (m.end() if m else 0)


def set_fm_fields(path, txt, end, fields):
    head, tail = txt[:end], txt[end:]
    lines = head.rstrip("\n").splitlines()
    for k, v in fields.items():
        for i, ln in enumerate(lines):
            if ln.startswith(k + ":"):
                lines[i] = f"{k}: {v}"
                break
        else:
            lines.append(f"{k}: {v}")
    tmp = path + ".cur"
    open(tmp, "w", encoding="utf-8").write("\n".join(lines) + "\n" + tail)
    os.replace(tmp, path)


def usage_index():
    """{skill_name: {"last": iso, "count": n}} from telemetry events + ledger."""
    idx = {}

    def bump(name, ts):
        e = idx.setdefault(name, {"last": "", "count": 0})
        e["count"] += 1
        if ts > e["last"]:
            e["last"] = ts

    for evf in glob.glob(os.path.join(VAULT, "targets", "*", ".events.jsonl")):
        try:
            for ln in open(evf, encoding="utf-8", errors="ignore"):
                try:
                    ev = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if ev.get("tool") == "Skill" and ev.get("skill"):
                    bump(ev["skill"], ev.get("ts", ""))
        except OSError:
            continue
    if os.path.exists(LEDGER):
        for ln in open(LEDGER, encoding="utf-8", errors="ignore"):
            try:
                rec = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if rec.get("skill"):
                bump(rec["skill"], rec.get("ts", ""))
    return idx


def referenced_names():
    import _protected
    names = set()
    for txt in _protected.referenced(VAULT).values():
        names.update(re.findall(r"\b([a-z][a-z0-9-]{2,30})\b", txt.lower()))
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    st = {"last_run": ""} if not os.path.exists(STATE) else json.load(open(STATE))
    if not args.force and days_since(st.get("last_run", "")) is not None \
            and days_since(st["last_run"]) < INTERVAL_DAYS:
        return 0  # silent: not due (SessionStart path stays quiet)
    if args.dry_run:
        print("curator DRY-RUN: no mutations")
    else:
        backup_skills()
    usage = usage_index()
    refs = referenced_names()
    actions = []
    for root, dirs, files in os.walk(SKILLS):
        dirs[:] = [d for d in dirs if d not in (".archive", ".locks", "__pycache__", ".git")]
        if "SKILL.md" not in files:
            continue
        name = os.path.basename(root)
        path = os.path.join(root, "SKILL.md")
        fm, txt, end = fm_of(path)
        u = usage.get(name, {"last": "", "count": 0})
        created = fm.get("created") or ""
        state = fm.get("state", "")
        if not state or not created:  # first sight: seed, reanchor clock to NOW
            if not args.dry_run:
                set_fm_fields(path, txt, end, {"state": "active", "created": time.strftime("%Y-%m-%d"),
                                               "last_used": u["last"][:10] or time.strftime("%Y-%m-%d")})
            actions.append(("would seed " if args.dry_run else "seeded ")
                           + f"{name} (state active, clock starts today)")
            continue
        anchors = [days_since(x) for x in (u["last"][:10], fm.get("last_used", "")[:10], created) if days_since(x) is not None]
        age = min(anchors) if anchors else 0  # youngest anchor = days since last activity
        pinned = fm.get("pinned", "false").lower() == "true"
        protected = pinned or name.lower() in refs
        new_state = state
        if age >= ARCHIVE_DAYS and state != "archived":
            new_state = "archived" if not protected and u["count"] > 0 else state
            if new_state == "archived":
                dest = os.path.join(SKILLS, ".archive", f"{time.strftime('%Y%m%d')}-{name}")
                if args.dry_run:
                    actions.append(f"would archive {name} (age {age}d, used {u['count']}x)")
                else:
                    os.makedirs(dest, exist_ok=True)
                    r = subprocess.run(["git", "-C", VAULT, "mv", os.path.relpath(root, VAULT),
                                        os.path.relpath(dest, VAULT)], capture_output=True, text=True)
                    if r.returncode != 0:
                        subprocess.run(["mv", root, dest])
                    actions.append(f"archived {name} -> {os.path.relpath(dest, VAULT)} (age {age}d)")
                continue
        elif age >= STALE_DAYS and state == "active":
            new_state = "stale"
        elif age < STALE_DAYS and state == "stale":
            new_state = "active"
        if new_state != state or fm.get("last_used", "") != (u["last"][:10] or fm.get("last_used", "")):
            if not args.dry_run:
                set_fm_fields(path, txt, end, {"state": new_state, "last_used": u["last"][:10] or fm.get("last_used", "")})
            actions.append(f"{name}: {state} -> {new_state} (age {age}d, used {u['count']}x)"
                           + (" [protected]" if protected else ""))
    if not args.dry_run:
        _tmp = STATE + ".tmp"
        json.dump({"last_run": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(_tmp, "w"))
        os.replace(_tmp, STATE)
    if actions:
        print("curator run " + time.strftime("%Y-%m-%d %H:%M"))
        for a in actions:
            print("- " + a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
