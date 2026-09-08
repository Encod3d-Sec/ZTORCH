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
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
