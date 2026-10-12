#!/usr/bin/env python3
"""checkpoint.py - shadow-git checkpoint manager for engagement dirs (hermes port, design 1).

Snapshots an engagement dir (targets/<eng>/ below) into a shared shadow git store
<vault>/.checkpoints/ before write-heavy driver phases, then list/restore/prune.
Every git call passes GIT_DIR=<store> GIT_WORK_TREE=<eng dir>
GIT_INDEX_FILE=<store>/idx/<snapshot id> explicitly, so no git state is ever
created inside the vault working tree; on first init the store also excludes
itself from the vault repo's status via one line in the vault's
.git/info/exclude (a local-only file, never committed).

Each snapshot is a commit reachable only via ref refs/zt/<eng>/<id> (id =
<timestamp>-<label>; engagement name on commit line 1, label on line 2), which
makes per-engagement list/prune exact without rev-list --grep guesswork.
Restore rewrites snapshot files in place; files created after the snapshot are
preserved, not deleted. Restore refuses (exit 1) when current files differ from
the snapshot unless --force, and after MAX_FAILS consecutive FAILED restores of
the same id (repair ledger .restore-attempts.jsonl in the store; a success
resets the streak - bounded retry, not a brickwall).

    python3 scripts/checkpoint.py snapshot <eng> <label>
    python3 scripts/checkpoint.py list <eng>
    python3 scripts/checkpoint.py restore <eng> <id> [--force]
    python3 scripts/checkpoint.py prune <eng> [--keep N] [--max-mb MB]
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime

VAULT = os.environ.get("ZTORCH_VAULT") or os.path.dirname(
    os.path.dirname(os.path.realpath(__file__)))
STORE_NAME = ".checkpoints"
IDX_SUBDIR = "idx"
LEDGER = ".restore-attempts.jsonl"
KEEP_DEFAULT = 20          # prune: snapshots kept per engagement
MAX_MB_DEFAULT = 200       # prune: total store size cap
MAX_FAILS = 3              # repair ledger: consecutive failed restores allowed
_ENG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def _git(store, work, index, *args):
    """Run git against the shadow store; the vault's own git is never touched."""
    env = dict(os.environ, GIT_DIR=store,
               GIT_WORK_TREE=work or store,
               GIT_INDEX_FILE=index or os.path.join(store, IDX_SUBDIR, ".default"))
    return subprocess.run(
        ["git", "-c", "user.name=zt-checkpoint",
         "-c", "user.email=checkpoint@ztorch.local"] + list(args),
        env=env, capture_output=True, text=True)


def _ok(r, what):
    """stdout of a plumbing call that must succeed, or None after printing why."""
    if r.returncode != 0:
        print("%s failed: %s" % (what, (r.stderr or r.stdout).strip()))
        return None
    return r.stdout.strip()


def _ensure_store():
    store = os.path.join(VAULT, STORE_NAME)
    os.makedirs(os.path.join(store, IDX_SUBDIR), exist_ok=True)
    if not os.path.exists(os.path.join(store, "HEAD")):
        subprocess.run(["git", "init", "-q", "--bare", store],
                       capture_output=True, text=True)
        _git(store, None, None, "config", "core.bare", "false")
    vgit = os.path.join(VAULT, ".git")
    if os.path.isdir(vgit):
        # keep the store out of the vault repo's `git status` (local-only file)
        excl = os.path.join(vgit, "info", "exclude")
        os.makedirs(os.path.dirname(excl), exist_ok=True)
        cur = open(excl, encoding="utf-8").read() if os.path.exists(excl) else ""
        if "/%s/" % STORE_NAME not in cur:
            sep = "" if not cur or cur.endswith("\n") else "\n"
            with open(excl, "a", encoding="utf-8") as f:
                f.write(sep + "/%s/\n" % STORE_NAME)
    return store


def _engdir(eng):
    return os.path.join(VAULT, "targets", eng)


def _ref(eng, sid):
    return "refs/zt/%s/%s" % (eng, sid)


def _snap_ids(store, eng):
    """Snapshot ids for eng, oldest first (the timestamp prefix sorts chrono)."""
    pre = "refs/zt/%s/" % eng
    r = _git(store, None, None, "for-each-ref", "--format=%(refname)", pre)
    if r.returncode != 0:
        return []
    return sorted(ln[len(pre):] for ln in r.stdout.splitlines()
                  if ln.startswith(pre))


def _new_id(store, eng, label):
    now = datetime.now()
    # the .%06d microsecond component keeps lexicographic id order chronological
    # within a same-second snapshot burst (plain seconds sort by label instead)
    base = "%s.%06d-%s" % (now.strftime("%Y%m%dT%H%M%S"), now.microsecond, label)
    have = set(_snap_ids(store, eng))
    sid, n = base, 0
    while sid in have:
        n += 1
        sid = "%s-%d" % (base, n)
    return sid


def cmd_snapshot(a):
    work = _engdir(a.eng)
    if not os.path.isdir(work):
        print("no engagement dir at %s" % work)
        return 1
    label = re.sub(r"[^A-Za-z0-9._-]", "-", a.label) or "snap"
    store = _ensure_store()
    sid = _new_id(store, a.eng, label)
    idx = os.path.join(store, IDX_SUBDIR, sid)
    r = _git(store, work, idx, "add", "-A")
    if r.returncode != 0:
        print("snapshot add failed: %s" % r.stderr.strip())
        return 1
    tree = _ok(_git(store, work, idx, "write-tree"), "write-tree")
    if tree is None:
        return 1
    parent = ""
    prev = _snap_ids(store, a.eng)
    if prev:
        parent = _ok(_git(store, None, None, "rev-parse", "--verify",
                          _ref(a.eng, prev[-1])), "rev-parse")
        if parent is None:
            return 1
    ct = ["commit-tree", tree] + (["-p", parent] if parent else [])
    ct += ["-m", "%s\n%s" % (a.eng, label)]
    commit = _ok(_git(store, work, idx, *ct), "commit-tree")
    if commit is None:
        return 1
    if _git(store, None, None, "update-ref", _ref(a.eng, sid),
            commit).returncode != 0:
        print("update-ref failed")
        return 1
    n = len(_git(store, work, idx, "ls-files").stdout.splitlines())
    print("snapshot %s (%d files, commit %.12s)" % (sid, n, commit))
    return 0


def cmd_list(a):
    store = _ensure_store()
    ids = _snap_ids(store, a.eng)
    if not ids:
        print("no snapshots for %s" % a.eng)
        return 0
    for sid in ids:
        rp = _git(store, None, None, "rev-parse", "--verify", _ref(a.eng, sid))
        commit = rp.stdout.strip()
        out = _git(store, None, None, "show", "-s", "--format=%P%n%B",
                   commit).stdout.splitlines()
        parents = out[0].strip() if out else "?"
        label = out[2].strip() if len(out) > 2 else sid
        chg = _git(store, None, None, "diff-tree", "--no-commit-id", "--root",
                   "-r", "--name-only", commit).stdout.splitlines()
        try:
            ts = datetime.strptime(sid[:15], "%Y%m%dT%H%M%S").strftime(
                "%Y-%m-%d %H:%M:%S")
        except ValueError:
            ts = "?"
        tail = ("%d files changed since previous" % len(chg) if parents
                else "%d files" % len(chg))
        print("%s  %s  %s  %s" % (sid, ts, label, tail))
    return 0


def _ledger_path(store):
    return os.path.join(store, LEDGER)


def _ledger_append(store, eng, sid, commit, ok):
    fp = hashlib.sha256(("%s/%s@%s" % (eng, sid, commit)).encode()).hexdigest()[:16]
    with open(_ledger_path(store), "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"),
                            "eng": eng, "id": sid, "ok": ok,
                            "fingerprint": fp}) + "\n")


def _consec_fails(store, eng, sid):
    """Length of the trailing ok=false run for (eng, sid) in the ledger."""
    try:
        lines = open(_ledger_path(store), encoding="utf-8").read().splitlines()
    except OSError:
        return 0
    n = 0
    for ln in reversed(lines):
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if d.get("eng") != eng or d.get("id") != sid:
            continue
        if d.get("ok"):
            break
        n += 1
    return n


def cmd_restore(a):
    work = _engdir(a.eng)
    if not os.path.isdir(work):
        print("no engagement dir at %s" % work)
        return 1
    store = _ensure_store()
    ref = _ref(a.eng, a.id)
    rp = _git(store, None, None, "rev-parse", "--verify", ref)
    if rp.returncode != 0:
        have = _snap_ids(store, a.eng)
        print("no snapshot %s for %s%s" % (
            a.id, a.eng, ("; have: " + ", ".join(have)) if have else ""))
        return 1
    commit = rp.stdout.strip()
    if _consec_fails(store, a.eng, a.id) >= MAX_FAILS:
        print("refusing: %d consecutive failed restores of %s (repair ledger); "
              "inspect the store manually" % (MAX_FAILS, a.id))
        return 1
    ridx = os.path.join(store, IDX_SUBDIR, ".restore")
    if _git(store, work, ridx, "read-tree", ref).returncode != 0:
        print("read-tree failed for %s" % a.id)
        return 1
    conf = [l for l in _git(store, work, ridx, "diff",
                            "--name-only").stdout.splitlines() if l.strip()]
    if conf and not a.force:
        print("restore refused: files differ from snapshot (use --force):")
        for p in conf:
            print("  " + p)
        return 1
    co = _git(store, work, ridx, "checkout-index", "-a", "-f")
    if co.returncode != 0:
        _ledger_append(store, a.eng, a.id, commit, False)
        print("restore FAILED: %s" % (co.stderr or co.stdout).strip())
        return 1
    _ledger_append(store, a.eng, a.id, commit, True)
    n = len(_git(store, work, ridx, "ls-files").stdout.splitlines())
    note = "" if not conf else " (overwrote %d conflicting)" % len(conf)
    print("restored %s (%d files)%s" % (a.id, n, note))
    return 0


def _dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def cmd_prune(a):
    store = _ensure_store()
    ids = _snap_ids(store, a.eng)
    drop = set(ids) if a.keep <= 0 else set(ids[:max(0, len(ids) - a.keep)])
    keep = [i for i in ids if i not in drop]
    cap = a.max_mb * 1024 * 1024
    while keep and _dir_size(store) > cap:
        drop.add(keep.pop(0))            # oldest first until under the cap
    for sid in sorted(drop):
        _git(store, None, None, "update-ref", "-d", _ref(a.eng, sid))
        try:
            os.remove(os.path.join(store, IDX_SUBDIR, sid))
        except OSError:
            pass
    if drop:
        _git(store, None, None, "gc", "--prune=now", "--quiet")
    print("pruned %d, kept %d, store %.1fMB" % (
        len(drop), len(keep), _dir_size(store) / 1e6))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="checkpoint.py",
        description="shadow-git checkpoint manager for engagement dirs")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("snapshot", help="snapshot the engagement dir now")
    p.add_argument("eng")
    p.add_argument("label")
    p.set_defaults(fn=cmd_snapshot)
    p = sub.add_parser("list", help="list snapshots (id, time, label, delta)")
    p.add_argument("eng")
    p.set_defaults(fn=cmd_list)
    p = sub.add_parser("restore", help="restore a snapshot into the engagement dir")
    p.add_argument("eng")
    p.add_argument("id")
    p.add_argument("--force", action="store_true",
                   help="overwrite files that differ from the snapshot")
    p.set_defaults(fn=cmd_restore)
    p = sub.add_parser("prune", help="drop oldest snapshots (count + size caps)")
    p.add_argument("eng")
    p.add_argument("--keep", type=int, default=KEEP_DEFAULT,
                   help="snapshots to keep (default %d)" % KEEP_DEFAULT)
    p.add_argument("--max-mb", type=int, default=MAX_MB_DEFAULT,
                   help="store size cap in MB (default %d)" % MAX_MB_DEFAULT)
    p.set_defaults(fn=cmd_prune)
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 1
    if not _ENG_RE.fullmatch(a.eng) or ".." in a.eng:
        print("bad engagement name %r" % a.eng)
        return 1
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
