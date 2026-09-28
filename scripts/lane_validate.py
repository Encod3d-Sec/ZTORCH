#!/usr/bin/env python3
"""lane_validate.py - verify returned lane claims against their captures, mechanically.

The delegate contract (skills delegate, "Main-agent discipline") says: every lane line in
targets/<eng>/log.md carries `SUCCESS = <observable> | ... | capture <dir>`, and on return
the main agent must verify the observable actually appears in the capture before filing the
lane's claim. Under momentum that verification is skipped - this script IS that check:

    python3 scripts/lane_validate.py <eng-dir | log.md path>

For each lane line: `VERIFIED` when the criterion's checkable tokens (backtick literals,
structural tokens like uid=33(www-data) / THM{flag}, and named capture files) verify in
the capture dir, `NOT VERIFIED` when absent (the over-claim leak-through), `REVIEW-BY-EYE`
when the criterion is pure prose no tool can substring-match (dir stats printed instead -
a false NOT VERIFIED trains the agent to ignore the validator). `in flight` lines are
skipped (status, not guess). Exit 0 always - it prints verdicts, it does not gate; writing
the verdict line into the log stays the main agent's job.
"""
import os
import re
import sys

# `- lane <name> in flight: SUCCESS = <observable> | ... | capture <dir>` (delegate skill);
# on return the line is CLOSED by appending the result after the capture cell, so "in flight"
# stays in the text. The dispatch-time format also carries a trailing `| handle <agent-id>`
# cell, so a line with NOTHING (or only the handle cell) after the capture dir is the
# still-open one - anything else after it is the appended result.
# The tmux-win cell may be `tmux win -` for windowless lanes (offline/research/read
# passes): the cell stays mandatory so the shape parses (drift-guard lane-contact
# exemption + status.py aging keep working); a missing cell silently voids both.
_LANE_RE = re.compile(
    r"^- lane (\S+)(.*): SUCCESS = ([^|]+)\|\s*tmux win (?:-|\S+)\s*\|\s*capture (\S+)(.*)$",
    re.MULTILINE)
_HANDLE_ONLY = re.compile(r"^\|?\s*handle\s+\S+\s*$")
_MAX_FILE = 2 * 1024 * 1024      # ponytail: caps per-file read; a capture >2MB is raw log noise


def _still_open(tail, rest):
    """True when the line is 'in flight' with no result appended yet: after the
    capture cell there is nothing, or only the dispatch-time handle cell."""
    if "in flight" not in tail:
        return False
    r = rest.strip()
    return not r or bool(_HANDLE_ONLY.match(r))


def lanes_from_text(text):
    """[(name, observable, capture_dir)] for every CLOSED lane line with a criterion."""
    out = []
    for m in _LANE_RE.finditer(text):
        name, _tail, obs, cap, rest = m.groups()
        if _still_open(_tail, rest):
            continue                       # opened, never closed; status, not guess
        out.append((name, obs.strip(), cap.strip()))
    return out


def open_lanes_from_text(text):
    """[(name, tail)] for every still-OPEN lane line ('in flight', no result appended
    yet). tail is the raw mid-line remainder (carries the `(<asset>)` + `@<HH:MM>`
    cells when the delegate format includes them). status.py ages these."""
    out = []
    for m in _LANE_RE.finditer(text):
        name, tail, _obs, _cap, rest = m.groups()
        if _still_open(tail, rest):
            out.append((name, tail.strip()))
    return out


def lane_lines(d, stale_min=45):
    """Open (in-flight) lane lines from log.md, aged off the @HH:MM cell. A lane open
    past stale_min was likely lost (compaction ate it or the subagent died) - surfaced
    as resume-or-close instead of the driver silently re-serving its work forever.
    Lives HERE (beside _LANE_RE) so every consumer imports it plainly; status.py and
    close-out.py re-export/call it without exec-ing a module by path."""
    from datetime import datetime
    try:
        text = open(os.path.join(d, "log.md"), encoding="utf-8", errors="ignore").read()
    except Exception:
        return []
    now = datetime.now()
    out = []
    for name, tail in open_lanes_from_text(text):
        age = ""
        m = re.search(r"@(\d{1,2}:\d{2})", tail)
        if m:
            try:
                t = datetime.strptime(m.group(1), "%H:%M").replace(
                    year=now.year, month=now.month, day=now.day)
                mins = int((now - t).total_seconds() // 60)
                if mins < 0:
                    mins += 1440                     # opened before midnight
                age = " (%dmin)" % mins
                if mins >= stale_min:
                    age += " STALE - resume via its handle or close the lane line"
            except ValueError:
                pass
        out.append("  - lane %s %s%s" % (name, tail, age))
    return out


def fresh_lane_open(d, max_min=45):
    """True when an OPEN lane line is younger than max_min (its @HH:MM cell; midnight
    wrap handled like lane_lines). A line with no parsable cell counts as NOT fresh: an
    un-timestamped line must not become a permanent drift exemption. Shared by
    drift-guard's lane-contact check so the exemption expires on the same clock
    status.py ages by - a forgotten open line stops exempting once stale."""
    from datetime import datetime
    try:
        text = open(os.path.join(d, "log.md"), encoding="utf-8", errors="ignore").read()
    except Exception:
        return False
    now = datetime.now()
    for _name, tail in open_lanes_from_text(text):
        m = re.search(r"@(\d{1,2}:\d{2})", tail)
        if not m:
            continue
        try:
            t = datetime.strptime(m.group(1), "%H:%M").replace(
                year=now.year, month=now.month, day=now.day)
        except ValueError:
            continue
        mins = (now - t).total_seconds() // 60
        if mins < 0:
            mins += 1440                         # opened before midnight
        if mins < max_min:
            return True
    return False


def _search(dirpath, needle):
    """True when needle appears in any file under dirpath (recursive, fail-open False)."""
    if not os.path.isdir(dirpath):
        return False
    for root, _dirs, files in os.walk(dirpath):
        for f in files:
            p = os.path.join(root, f)
            try:
                if os.path.getsize(p) > _MAX_FILE:
                    continue
                if needle in open(p, encoding="utf-8", errors="ignore").read():
                    return True
            except OSError:
                continue
    return False


_FILE_TOKEN = re.compile(r"\b[\w.-]+\.(?:txt|md|json|jsonl|html|log|csv)\b")
_QUOTED = re.compile(r"`([^`]+)`")
_STRUCT = re.compile(r"[{}=<>\[\]]")


def _checkable_lits(obs):
    """Tokens the validator can mechanically verify: backtick literals (substring),
    named capture files (existence + non-empty), and bare structural tokens like
    `uid=33(www-data)` / `THM{zzz}` (substring). Everything else is prose - a prose
    criterion substring-match would false-negative every honest lane and train the
    agent to ignore the validator. Returns [(kind, token)]."""
    lits = [("str", m) for m in _QUOTED.findall(obs)]
    for m in _FILE_TOKEN.findall(obs):
        lits.append(("file", m))
    for tok in obs.replace("`", " ").split():
        if _FILE_TOKEN.fullmatch(tok) or len(tok) < 4 or _STRUCT.search(tok) is None:
            continue
        if ("str", tok) not in lits:
            lits.append(("str", tok))
    return lits


def _stats(dirpath):
    n = b = 0
    for root, _dirs, files in os.walk(dirpath):
        for f in files:
            p = os.path.join(root, f)
            try:
                n += 1
                b += os.path.getsize(p)
            except OSError:
                pass
    return n, b


def _file_present(dirpath, name):
    for root, _dirs, files in os.walk(dirpath):
        for f in files:
            if f == name:
                try:
                    return os.path.getsize(os.path.join(root, f)) > 0
                except OSError:
                    return False
    return False


def criterion_met(cap, obs):
    """True when every CHECKABLE token of the criterion verifies in the capture:
    backtick literals and structural tokens as substrings, named files as existing
    non-empty captures. The delegate skill teaches compound criteria (`hostname` = x
    AND `id` = y); those split on AND, and each fragment's checkable tokens must all
    be present."""
    for frag in obs.split(" AND "):
        for kind, tok in _checkable_lits(frag):
            if kind == "file":
                if not _file_present(cap, tok):
                    return False
            elif not _search(cap, tok):
                return False
    return True


def has_checkable(obs):
    return bool(_checkable_lits(obs))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__.strip().splitlines()[-2])
        return 0
    target = argv[0]
    log = target if target.endswith(".md") else os.path.join(target, "log.md")
    try:
        text = open(log, encoding="utf-8", errors="ignore").read()
    except OSError:
        print("lane_validate: no log at %s" % log)
        return 0
    base = os.path.dirname(os.path.abspath(log))
    n_ok = n_fail = 0
    for name, obs, cap in lanes_from_text(text):
        capdir = cap if os.path.isabs(cap) else os.path.normpath(os.path.join(base, cap))
        if not os.path.isdir(capdir):
            print("lane %s: NOT VERIFIED - no capture dir at %s" % (name, cap))
            n_fail += 1
        elif not has_checkable(obs):
            n, b = _stats(capdir)
            print("lane %s: REVIEW-BY-EYE - descriptive criterion \"%s\" (mechanically "
                  "uncheckable); %d files %dB in %s, read the raws yourself" % (name, obs, n, b, cap))
            n_ok += 1
        elif criterion_met(capdir, obs):
            print("lane %s: VERIFIED (\"%s\" present in %s)" % (name, obs, cap))
            n_ok += 1
        else:
            print("lane %s: NOT VERIFIED - \"%s\" absent from %s (over-claim; treat the "
                  "lane claim as a hypothesis)" % (name, obs, cap))
            n_fail += 1
    if n_ok == n_fail == 0:
        print("lane_validate: no returned lane lines with a SUCCESS criterion in %s" % log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
