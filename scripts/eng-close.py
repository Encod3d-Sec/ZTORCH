#!/usr/bin/env python3
"""eng-close.py <SOLVED|SUSPEND|OWNED|ROOTED|COMPLETE> [engagement] - append the ## STATUS
close-out marker to state.md in ONE command.

Why this exists: the entire close-out chain (eval-metrics write, walkthrough build, learn
harvest) keys on that marker, and every engagement to date closed unmarked with an empty
eval.md because the last step was "edit state.md by hand" - a step skipped under momentum.
This is the cheap-path fix: one command, idempotent, refuses to double-mark.

  SOLVED/OWNED/ROOTED/COMPLETE  -> full chain (eval metrics, walkthrough, learn)
  SUSPEND                       -> measured park (eval metrics only; chain resumes on reopen)

Usage:
  python3 scripts/eng-close.py SOLVED              # active engagement (targets/active.md)
  python3 scripts/eng-close.py SUSPEND oldbox      # a named engagement
"""
import os
import re
import sys

STATUSES = ("SOLVED", "SUSPEND", "OWNED", "ROOTED", "COMPLETE")
_ANY_STATUS_RE = re.compile(r"^##\s*STATUS\s*:", re.IGNORECASE | re.MULTILINE)

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = (os.environ.get("ZTORCH_VAULT") or os.environ.get("OBSIDIAN_VAULT")
         or os.environ.get("CLAUDEBRAIN_VAULT") or os.path.dirname(HERE))


def _active_name():
    """Engagement name from targets/active.md (first non-empty non-header line), or ''."""
    p = os.path.join(VAULT, "targets", "active.md")
    try:
        for line in open(p, encoding="utf-8", errors="ignore"):
            s = line.strip()
            if s and not s.startswith(("#", "<!--", "-", "*")):
                return s
    except OSError:
        pass
    return ""


def _rollback_script(eng_dir):
    """rollback.sh from changelog.md data rows, REVERSE row order (undo last
    write first). Empty/absent table -> None (nothing generated)."""
    import os
    rows = []
    p = os.path.join(eng_dir, "changelog.md")
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8", errors="ignore"):
            s = line.strip()
            if not s.startswith("|") or set(s) <= {"|", "-", " ", ":"}:
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) < 8 or cells[0] in ("#", ""):
                continue
            rows.append(cells)
    cmds = [(c[6], c[1], c[2]) for c in rows if c[6]]
    if not cmds:
        return None
    out = ["#!/bin/sh", "# rollback for %s - reverse changelog order; verify each step" %
           os.path.basename(eng_dir), "set -x"]
    out += ["# %s %s" % (t, h) + ("\n" + rb.replace("`", "")) for rb, t, h in reversed(cmds)]
    return "\n".join(out) + "\n"


def main(argv):
    args = [a for a in argv[1:] if a]
    if not args or args[0].upper() not in STATUSES:
        print("usage: eng-close.py <%s> [engagement]" % "|".join(STATUSES), file=sys.stderr)
        return 2
    status = args[0].upper()
    name = args[1] if len(args) > 1 else _active_name()
    if not name:
        print("eng-close: no engagement named and targets/active.md holds no pointer",
              file=sys.stderr)
        return 1
    state_p = os.path.join(VAULT, "targets", name, "state.md")
    if not os.path.isfile(state_p):
        print("eng-close: no state.md at %s" % state_p, file=sys.stderr)
        return 1
    text = open(state_p, encoding="utf-8", errors="ignore").read()
    if _ANY_STATUS_RE.search(text):
        print("eng-close: %s/state.md already carries a ## STATUS heading; refusing to "
              "double-mark (edit by hand if you truly need to change it)." % name,
              file=sys.stderr)
        return 1
    if text and not text.endswith("\n"):
        text += "\n"
    with open(state_p, "w", encoding="utf-8") as fh:
        fh.write(text + "\n## STATUS: %s\n" % status)
    print("targets/%s/state.md marked '## STATUS: %s'. The close-out chain fires at the next "
          "Stop: eval-metrics write%s. Do NOT remove the marker." %
          (name, status,
           ", then walkthrough build + Skill(learn)" if status != "SUSPEND"
           else " only (parked; walkthrough/learn resume when reopened)"))
    eng_dir = os.path.join(VAULT, "targets", name)
    rb = _rollback_script(eng_dir)
    if rb:
        with open(os.path.join(eng_dir, "rollback.sh"), "w", encoding="utf-8") as fh:
            fh.write(rb)
        print("rollback: targets/%s/rollback.sh written (reverse changelog order)." % name)
    try:
        sys.path.insert(0, HERE)
        from offensive import changelog_pending
        n, rows = changelog_pending(eng_dir)
    except Exception:
        n, rows = 0, []
    if n:
        print("CLEANUP UNCONFIRMED - %d changelog rows lack verified rollback:" % n)
        for r in rows:
            print("  - %s" % r)
        with open(state_p, "a", encoding="utf-8") as fh:
            fh.write("cleanup_unconfirmed: true\n")
    wt = os.path.join(eng_dir, "walkthrough.md")
    if os.path.isfile(wt):
        t = open(wt, encoding="utf-8", errors="ignore").read()
        if "## Cleanup" in t and "- [ ]" in t.split("## Cleanup", 1)[1].split("##", 1)[0]:
            print("advisory: walkthrough has unchecked cleanup items (## Cleanup).")
    # advisory (pass 11 L6): nothing in the close-out chain kills the engagement's tmux
    # session on the VM - leftover scan/listener tabs silently persist into the next box.
    # Advise the operator-named kill (NEVER kill-server; VPN lives outside tmux but the
    # rule stands). The AUTOCARD_ALL sweep at close-out cards everything first.
    print("advisory: once the close-out chain finishes, kill the VM session for this box: "
          "bash /root/vm.sh \"tmux kill-session -t %s\" (named session ONLY, never "
          "kill-server)." % name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
