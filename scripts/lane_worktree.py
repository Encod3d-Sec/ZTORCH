#!/usr/bin/env python3
"""lane_worktree.py - opt-in git worktree isolation for code-editing lanes (P5
port of hermes subagent_worktree; docs/port-specs/proposals-delegation.md).

DEFAULT OFF. Reach for it only when two lanes would otherwise edit one
checkout (the vault repo during harness work, or a raw/research project
workspace): each lane gets its own worktree at <eng>/worktrees/<lane>/ (run
from the engagement dir, like lane-run.sh) on branch ztorch-lane/<lane> off a
CLEAN source HEAD; the brain reviews and merges, then prunes. raw/git clones
are read-only by vault rule and are REFUSED as sources (a worktree add writes
admin files into the clone's .git); raw/assets likewise; raw/research
workspaces are the allowed non-vault source.

Prune removes ONLY on affirmative proof (zero commits beyond source HEAD AND
clean status AND no untracked files); any probe failure or non-empty state
REFUSES with the reason and keeps the worktree (hermes inspection_failed
rule: UNKNOWN is not ZERO).

    python3 scripts/lane_worktree.py create <lane> --src <repo-or-tree>
    python3 scripts/lane_worktree.py prune <lane>
    python3 scripts/lane_worktree.py list
"""
import os
import re
import subprocess
import sys

_BRANCH = "ztorch-lane/%s"
_LANE_NAME = re.compile(r"[A-Za-z0-9._-]+\Z")   # lane id ends up in a path + branch
# hardened non-interactive git (hermes GHSA-7x36-8jrh-v4pw posture): no
# terminal prompt, no system config; a lane never hangs on credential auth
_GIT_ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1")


def _git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                          text=True, env=_GIT_ENV)


def _refused(p):
    """True when p sits in the read-only half of raw/ (raw/git clones,
    raw/assets). raw/research workspaces stay legitimate lane sources."""
    parts = os.path.realpath(os.path.abspath(p)).split(os.sep)
    try:
        i = parts.index("raw")
    except ValueError:
        return False
    nxt = parts[i + 1] if i + 1 < len(parts) else ""
    return nxt != "research"      # raw/git, raw/assets, bare raw/: all refused


def _wt_path(base, lane):
    return os.path.join(base, "worktrees", lane)


def _src_of(wt):
    """Source repo backing a worktree (dirname of its git common dir), or None."""
    r = _git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=wt)
    if r.returncode != 0:
        return None
    cd = r.stdout.strip()
    if cd.endswith("/.git"):
        return os.path.dirname(cd)
    return cd if os.path.isdir(os.path.join(cd, "objects")) else None


def create(lane, src, base=None):
    base = base or os.getcwd()
    if not _LANE_NAME.match(lane):
        print("lane_worktree: bad lane name '%s' (want [A-Za-z0-9._-]+)" % lane)
        return 2
    src = os.path.abspath(src)
    if _refused(src):
        print("lane_worktree: refusing %s - raw/git and raw/assets are read-only "
              "by vault rule; sources are the vault repo or raw/research "
              "workspaces" % src)
        return 2
    if _git(["rev-parse", "--is-inside-work-tree"], cwd=src).returncode != 0:
        print("lane_worktree: %s is not a git working tree" % src)
        return 2
    st = _git(["status", "--porcelain"], cwd=src)
    if st.returncode != 0:
        print("lane_worktree: cannot inspect %s (git status failed: %s); refusing"
              % (src, st.stderr.strip()))
        return 2
    if st.stdout.strip():
        print("lane_worktree: refusing - source %s is dirty (%d changed path(s)); "
              "commit or stash first so the lane branches off a clean HEAD"
              % (src, len(st.stdout.splitlines())))
        return 2
    wt = _wt_path(base, lane)
    if _refused(wt):
        print("lane_worktree: refusing worktree location %s (under raw/)" % wt)
        return 2
    if os.path.exists(wt):
        print("lane_worktree: %s already exists" % wt)
        return 2
    branch = _BRANCH % lane
    if _git(["rev-parse", "--verify", "--quiet", branch], cwd=src).returncode == 0:
        print("lane_worktree: branch %s already exists in %s (prune it first)"
              % (branch, src))
        return 2
    r = _git(["worktree", "add", "-b", branch, wt, "HEAD"], cwd=src)
    if r.returncode != 0:
        print("lane_worktree: worktree add failed: %s" % r.stderr.strip())
        return 2
    print("worktree %s (branch %s off %s HEAD; work ONLY there, commit to the "
          "branch - the brain reviews and merges)" % (wt, branch, src))
    return 0


def prune(lane, base=None):
    base = base or os.getcwd()
    if not _LANE_NAME.match(lane):
        print("lane_worktree: bad lane name '%s'" % lane)
        return 2
    wt = _wt_path(base, lane)
    if not os.path.isdir(wt):
        print("lane_worktree: no worktree for lane '%s' at %s" % (lane, wt))
        return 2
    src = _src_of(wt)
    if src is None:
        print("lane_worktree: %s: git inspection failed - keeping the worktree "
              "(commits/dirty UNKNOWN, not proven safe to drop)" % wt)
        return 1
    head = _git(["rev-parse", "HEAD"], cwd=src)
    commits = status = None
    if head.returncode == 0:
        # commits on the lane branch NOT reachable from the source repo's HEAD
        # (a merged lane also counts 0: its work already lives in the source)
        commits = _git(["rev-list", "--count", "HEAD", "--not",
                        head.stdout.strip()], cwd=wt)
        status = _git(["status", "--porcelain"], cwd=wt)
    if head.returncode != 0 or commits is None or commits.returncode != 0 \
            or status is None or status.returncode != 0:
        print("lane_worktree: %s: git inspection failed - keeping the worktree "
              "(commits/dirty UNKNOWN, not proven safe to drop)" % wt)
        return 1
    n = int(commits.stdout.strip() or "0")
    lines = status.stdout.splitlines()
    if n > 0:
        print("lane_worktree: refusing - %d commit(s) on the lane branch beyond "
              "source HEAD %s; review/merge, then prune" % (n, head.stdout.strip()[:12]))
        return 1
    if lines:
        untracked = [l for l in lines if l.startswith("?? ")]
        kind = ("dirty tree" if not untracked else
                "untracked files" if len(untracked) == len(lines) else
                "dirty tree + untracked files")
        print("lane_worktree: refusing - %s in %s (%d path(s)); keep or clean "
              "it, then prune" % (kind, wt, len(lines)))
        return 1
    r = _git(["worktree", "remove", wt], cwd=src)
    if r.returncode != 0:
        print("lane_worktree: worktree remove failed: %s (nothing pruned)"
              % r.stderr.strip())
        return 1
    branch = _BRANCH % lane
    d = _git(["branch", "-d", branch], cwd=src)   # zero-commit branch: safe
    note = "" if d.returncode == 0 else " (branch %s lingered: %s)" % (
        branch, d.stderr.strip())
    print("pruned %s - proven: 0 commits beyond HEAD, clean, no untracked%s"
          % (wt, note))
    return 0


def list_wts(base=None):
    base = base or os.getcwd()
    root = os.path.join(base, "worktrees")
    if not os.path.isdir(root):
        print("lane_worktree: no worktrees dir at %s (run from the engagement "
              "dir)" % root)
        return 0
    found = False
    for lane in sorted(os.listdir(root)):
        wt = os.path.join(root, lane)
        if not os.path.isdir(wt):
            continue
        found = True
        br = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=wt)
        st = _git(["status", "--porcelain"], cwd=wt)
        if br.returncode != 0 or st.returncode != 0:
            print("  %s  %s  INSPECTION FAILED (kept)" % (lane, wt))
            continue
        state = "clean" if not st.stdout.strip() else "%d changed" % len(
            st.stdout.splitlines())
        print("  %s  %s  %s  %s" % (lane, wt, br.stdout.strip(), state))
    if not found:
        print("lane_worktree: no worktrees under %s" % root)
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) >= 2 and argv[0] == "create":
        src = ""
        if "--src" in argv[2:] and argv.index("--src") + 1 < len(argv):
            src = argv[argv.index("--src") + 1]
        if not src:
            print("usage: lane_worktree.py create <lane> --src <repo-or-tree>")
            return 2
        return create(argv[1], src)
    if len(argv) == 2 and argv[0] == "prune":
        return prune(argv[1])
    if argv and argv[0] == "list":
        return list_wts()
    print("usage: lane_worktree.py create <lane> --src <repo> | prune <lane> | list")
    return 2


if __name__ == "__main__":
    sys.exit(main())
