#!/usr/bin/env python3
"""skill_manage.py - guarded skill authoring for ZTORCH (hermes skill_manage port).

Skills are operator-owned markdown; this tool adds the hermes guardrails so a
mid-engagement skill write is safe: name rules, 60-char description rule (the
routing signal), lifecycle frontmatter seeding, read-before-write patching
(sha256 of the last view must match), allowed support subdirs only, traversal
refusal, atomic writes under a per-skill lock, delete only with
absorbed_into, never deleting skills the harness references (triggers.json,
routing.json, engage rows) or pinned ones. Archive (git mv to
skills/.archive/) is the maximum destructive action; nothing is ever rm'd.

Usage:
  skill_manage.py view <name>
  skill_manage.py create --name <slug> --desc "<=60 chars" [--body-file F] [--category dir]
  skill_manage.py patch  <name> --old "<text>" --new "<text>" --from-read <sha256>
  skill_manage.py write-file <name> --path references/foo.md [--body-file F]
  skill_manage.py delete <name> --absorbed-into <umbrella-name>
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(VAULT, "skills")
ARCHIVE = os.path.join(SKILLS, ".archive")
LEDGER = os.path.join(SKILLS, ".skill-ledger.jsonl")
ALLOWED_SUBDIRS = {"references", "templates", "scripts", "assets"}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DESC_LIMIT = 60          # the routing signal truncates at 60; longer = dead weight
MAX_BODY = 100_000
MAX_SUPPORT = 1024 * 1024
LIFECYCLE = [("state", "active"), ("created", None), ("created_by", "agent"), ("pinned", "false")]


def find_skill(name):
    for root, dirs, files in os.walk(SKILLS):
        dirs[:] = [d for d in dirs if d not in (".archive", ".locks", "__pycache__", ".git")]
        if "SKILL.md" in files:
            d = os.path.basename(root)
            if d == name:
                return os.path.join(root, "SKILL.md"), root
    return None, None


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def referenced(name):
    """Names the harness routes to are protected from delete/archive."""
    refs = []
    for f, pat in [("scripts/triggers.json", None), ("scripts/routing.json", None),
                   ("skills/workflow/engage/SKILL.md", None)]:
        p = os.path.join(VAULT, f)
        if os.path.exists(p) and name in open(p, encoding="utf-8", errors="ignore").read():
            refs.append(f)
    return refs


def ledger(op, name, extra=None):
    with open(LEDGER, "a", encoding="utf-8") as f:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "op": op, "skill": name}
        if extra:
            rec.update(extra)
        f.write(json.dumps(rec) + "\n")


def lock_for(name):
    os.makedirs(os.path.join(SKILLS, ".locks"), exist_ok=True)
    p = os.path.join(SKILLS, ".locks", hashlib.sha256(name.encode()).hexdigest() + ".lock")
    return open(p, "w")


def frontmatter_of(path):
    txt = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
    fm = {}
    if m:
        for ln in m.group(1).splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                fm[k.strip()] = v.strip()
    return txt, fm, (m.end() if m else 0)


def write_atomic(path, text):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".skm-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("view"); v.add_argument("name")
    c = sub.add_parser("create"); c.add_argument("--name", required=True)
    c.add_argument("--desc", required=True); c.add_argument("--body-file")
    c.add_argument("--category", help="optional parent dir under skills/ (e.g. workflow/exec)")
    p = sub.add_parser("patch"); p.add_argument("name")
    p.add_argument("--old", required=True); p.add_argument("--new", required=True)
    p.add_argument("--from-read", required=True, dest="from_read")
    w = sub.add_parser("write-file"); w.add_argument("name")
    w.add_argument("--path", required=True); w.add_argument("--body-file")
    d = sub.add_parser("delete"); d.add_argument("name")
    d.add_argument("--absorbed-into", required=True, dest="absorbed_into")
    args = ap.parse_args()

    if args.cmd == "view":
        path, _ = find_skill(args.name)
        if not path:
            print(f"no skill named {args.name}", file=sys.stderr)
            return 1
        txt = open(path, encoding="utf-8").read()
        print(txt)
        print(f"<!-- sha256={sha(path)} -->")
        return 0

    if args.cmd == "create":
        if not NAME_RE.match(args.name) or len(args.name) > 64:
            print("REFUSED: name must match [a-z0-9][a-z0-9._-]* and be <=64 chars", file=sys.stderr)
            return 1
        if len(args.desc) > DESC_LIMIT:
            print(f"REFUSED: description > {DESC_LIMIT} chars ({len(args.desc)}); the routing "
                  "signal truncates at 60 - count it and tighten", file=sys.stderr)
            return 1
        if find_skill(args.name)[0]:
            print(f"REFUSED: a skill named {args.name} already exists; patch it instead "
                  "(umbrella-first)", file=sys.stderr)
            return 1
        body = open(args.body_file, encoding="utf-8").read() if args.body_file else (
            f"# {args.name}\n\n(When to use, procedure, pitfalls; see docs/port-specs/self-improvement.md "
            "for authoring standards.)\n")
        if len(body) > MAX_BODY:
            print(f"REFUSED: body > {MAX_BODY} chars", file=sys.stderr)
            return 1
        parent = os.path.join(SKILLS, args.category) if args.category else SKILLS
        if not os.path.isdir(parent) or os.path.commonpath([parent, SKILLS]) != SKILLS:
            print("REFUSED: --category must be an existing dir under skills/", file=sys.stderr)
            return 1
        sdir = os.path.join(parent, args.name)
        os.makedirs(sdir, exist_ok=False)
        fm = ["---", f"name: {args.name}", f"description: {args.desc}",
              "state: active", f"created: {time.strftime('%Y-%m-%d')}",
              "created_by: agent", "pinned: false", "---", ""]
        write_atomic(os.path.join(sdir, "SKILL.md"), "\n".join(fm) + "\n" + body)
        ledger("create", args.name)
        print(f"created skills/{os.path.relpath(sdir, SKILLS)}/SKILL.md (state active, created_by agent)")
        return 0

    path, sdir = find_skill(args.name)
    if not path:
        print(f"no skill named {args.name}", file=sys.stderr)
        return 1
    lock = lock_for(args.name)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.cmd == "patch":
            actual = sha(path)
            if args.from_read != actual:
                print(f"REFUSED: file changed since your view (sha {actual[:12]}... != from-read); "
                      "view again and re-patch", file=sys.stderr)
                return 1
            txt = open(path, encoding="utf-8").read()
            if txt.count(args.old) == 0:
                print("REFUSED: --old not found in SKILL.md", file=sys.stderr)
                return 1
            if txt.count(args.old) > 1:
                print(f"REFUSED: --old matches {txt.count(args.old)} places; add context to disambiguate", file=sys.stderr)
                return 1
            new_txt = txt.replace(args.old, args.new, 1)
            if len(new_txt) > MAX_BODY:
                print("REFUSED: patched body exceeds size cap", file=sys.stderr)
                return 1
            before = actual
            write_atomic(path, new_txt)
            ledger("patch", args.name, {"sha_before": before, "sha_after": sha(path)})
            print(f"patched {args.name} ({before[:12]} -> {sha(path)[:12]})")
            return 0

        if args.cmd == "write-file":
            rel = args.path
            parts = rel.split("/")
            if parts[0] not in ALLOWED_SUBDIRS or ".." in parts or len(rel) > 200:
                print(f"REFUSED: path must be under one of {sorted(ALLOWED_SUBDIRS)}, no traversal", file=sys.stderr)
                return 1
            body = open(args.body_file, encoding="utf-8").read() if args.body_file else sys.stdin.read()
            if len(body) > MAX_SUPPORT:
                print(f"REFUSED: support file > 1MiB", file=sys.stderr)
                return 1
            dest = os.path.join(sdir, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.exists(dest) and os.path.realpath(dest).startswith(ARCHIVE):
                print("REFUSED: destination resolves inside the archive", file=sys.stderr)
                return 1
            write_atomic(dest, body)
            ledger("write_file", args.name, {"path": rel})
            print(f"wrote {args.name}/{rel} ({len(body)} chars)")
            return 0

        if args.cmd == "delete":
            _, fm, _ = frontmatter_of(path)
            if fm.get("pinned", "false").lower() == "true":
                print("REFUSED: pinned skill", file=sys.stderr)
                return 1
            refs = referenced(args.name)
            if refs:
                print(f"REFUSED: harness references this skill in {', '.join(refs)}; "
                      "unroute it first (engage row / triggers / routing)", file=sys.stderr)
                return 1
            if find_skill(args.absorbed_into)[0] is None:
                print(f"REFUSED: --absorbed-into names no existing skill ({args.absorbed_into})", file=sys.stderr)
                return 1
            os.makedirs(ARCHIVE, exist_ok=True)
            dest = os.path.join(ARCHIVE, f"{time.strftime('%Y%m%d')}-{args.name}")
            r = subprocess.run(["git", "-C", VAULT, "mv", os.path.relpath(sdir, VAULT),
                                os.path.relpath(dest, VAULT)], capture_output=True, text=True)
            if r.returncode != 0:
                shutil.move(sdir, dest)  # ponytail: non-git fallback, history lost for this move
            ledger("delete", args.name, {"absorbed_into": args.absorbed_into, "archived_to": dest})
            print(f"archived {args.name} -> {os.path.relpath(dest, VAULT)} (absorbed into {args.absorbed_into})")
            return 0
    finally:
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
