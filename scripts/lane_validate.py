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
import json
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


def _iter_lanes(text):
    """Yield (name, tail, obs, cap, rest) for every lane line; callers filter open/closed.
    Kept internal so the public lanes_from_text/open_lanes_from_text tuple shapes
    (imported by close-out.py / status.py) never shift."""
    for m in _LANE_RE.finditer(text):
        name, tail, obs, cap, rest = m.groups()
        yield name, tail, obs.strip(), cap.strip(), rest


def lanes_from_text(text):
    """[(name, observable, capture_dir)] for every CLOSED lane line with a criterion."""
    out = []
    for name, tail, obs, cap, rest in _iter_lanes(text):
        if _still_open(tail, rest):
            continue                       # opened, never closed; status, not guess
        out.append((name, obs, cap))
    return out


def open_lanes_from_text(text):
    """[(name, tail)] for every still-OPEN lane line ('in flight', no result appended
    yet). tail is the raw mid-line remainder (carries the `(<asset>)` + `@<HH:MM>`
    cells when the delegate format includes them). status.py ages these."""
    out = []
    for name, tail, _obs, _cap, rest in _iter_lanes(text):
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
        # A structural token needs word chars on the left of the '=' (uid=33(www-data),
        # id=0, THM{...}); a bare comparison like "(>=28" or "<=5" is criterion prose
        # ("at least 28 lines"), not an observable - substring-checking it false-negatives
        # an honest lane (seen: lane-apipl-sqli, 2026-09-29).
        if not (re.search(r"\w=", tok) or "{" in tok):
            continue
        if ("str", tok) not in lits:
            lits.append(("str", tok))
    return lits


def _cap_dir(base, cap):
    """Resolve a lane line's capture cell against the log's dir; a
    vault-root-spelled cell (capture targets/<eng>/poc/lane-x) resolves nowhere
    under the eng dir, so strip that prefix once and retry. Shared by the
    verdict loop and --envelope mode so both age on the same resolution."""
    capdir = cap if os.path.isabs(cap) else os.path.normpath(os.path.join(base, cap))
    if not os.path.isdir(capdir):
        eng = os.path.basename(base)
        alt = re.sub(r"^targets/%s/" % re.escape(eng), "", cap)
        if alt != cap and os.path.isdir(os.path.join(base, alt)):
            capdir = os.path.join(base, alt)
    return capdir


def envelope_report(base, text):
    """--envelope mode (P1, docs/port-specs/proposals-delegation.md): for each
    CLOSED lane line, schema-check the capture dir's envelope.json. An INVALID
    or MISSING envelope NEVER flips the lane's log verdict and never discards
    the run: it earns exactly ONE same-handle re-prompt carrying the reasons
    verbatim (hermes build_retry_message shape); a second miss files the lane
    NOT VERIFIED, raw capture kept. Exit 0 always, like every mode here."""
    import lane_envelope
    n = 0
    for name, _obs, cap in lanes_from_text(text):
        n += 1
        capdir = _cap_dir(base, cap)
        if not os.path.isdir(capdir):
            # dir-less lines (scribe/draft lanes, closed-by-brain) can carry no
            # envelope; the normal-mode verdict governs them
            print("lane %s: no capture dir at %s - envelope check n/a" % (name, cap))
            continue
        path = os.path.join(capdir, "envelope.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            print("lane %s: ENVELOPE-MISSING (%s) - one same-handle re-prompt due"
                  % (name, path))
            continue
        except (json.JSONDecodeError, OSError) as e:
            print("lane %s: ENVELOPE-INVALID (%s unreadable: %s) - one same-handle "
                  "re-prompt due" % (name, path, e))
            continue
        errs = lane_envelope.validate(data)
        if errs:
            print("lane %s: ENVELOPE-INVALID (%s: %s) - one same-handle re-prompt due"
                  % (name, path, "; ".join(errs)))
            continue
        obs_raw = data.get("result", {}).get("success_observable_raw", "")
        if has_checkable(obs_raw) and not criterion_met(capdir, obs_raw):
            print("lane %s: ENVELOPE VALID (%s) - advisory: success_observable_raw "
                  "tokens not found in the capture, verify by eye" % (name, path))
        else:
            print("lane %s: ENVELOPE VALID (%s)" % (name, path))
    if not n:
        print("lane_validate: no returned lane lines with a SUCCESS criterion")
    return 0


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


def _file_mtime(dirpath, name):
    """mtime of the named file anywhere under dirpath (recursive), else None."""
    for root, _dirs, files in os.walk(dirpath):
        if name in files:
            try:
                return os.path.getmtime(os.path.join(root, name))
            except OSError:
                return None
    return None


def stale_evidence(capdir, obs, tail, now=None):
    """[filenames] named in the criterion whose mtime predates the lane line's
    `in flight @HH:MM` open time (same-day): the capture existed BEFORE the lane ran,
    so the verified claim may rest on pre-existing artifacts (hermes over-claim
    guard, port P3). Advisory only - never flips a verdict. No parsable @HH:MM or
    no capture dir -> []. Fail-open [] on any error."""
    try:
        from datetime import datetime
        m = re.search(r"@(\d{1,2}:\d{2})", tail or "")
        if not m or not os.path.isdir(capdir):
            return []
        opened = datetime.strptime(m.group(1), "%H:%M")
        now = now or datetime.now()
        opened = opened.replace(year=now.year, month=now.month, day=now.day)
        opened_ts = opened.timestamp()
        seen, out = set(), []
        for frag in obs.split(" AND "):
            for kind, tok in _checkable_lits(frag):
                if kind != "file" or tok in seen:
                    continue
                seen.add(tok)
                mt = _file_mtime(capdir, tok)
                if mt is not None and mt < opened_ts:
                    out.append(tok)
        return out
    except Exception:
        return []


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


def brief_warnings(text):
    """Warn when a lane brief's SUCCESS criterion names no capture path."""
    warns = []
    for line in text.splitlines():
        if "SUCCESS" in line and "=" in line:
            rhs = line.split("=", 1)[1]
            # ponytail: poc/ literal matches the vault capture convention (capture poc/<lane>);
            # widen the check if briefs start capturing outside poc/
            if "poc/" not in rhs:
                warns.append(
                    "WARN: SUCCESS criterion names no capture path: " + line.strip()
                )
    return warns


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--brief":
        # warn mode: read a lane brief file, flag capture-less SUCCESS criteria; exit 0 always
        if len(argv) < 2:
            print("usage: lane_validate.py --brief <brief-file>")
            return 0
        try:
            brief_text = open(argv[1], encoding="utf-8", errors="ignore").read()
        except OSError:
            print("lane_validate: no brief at %s" % argv[1])
            return 0
        warns = brief_warnings(brief_text)
        for w in warns:
            print(w)
        if not warns:
            print("brief OK: every SUCCESS criterion names a capture path")
        return 0
    if argv and argv[0] == "--envelope":
        # P1 envelope mode: schema-check each CLOSED lane's capture envelope.json
        if len(argv) < 2:
            print("usage: lane_validate.py --envelope <eng-dir | log.md path>")
            return 0
        target = argv[1]
        log = target if target.endswith(".md") else os.path.join(target, "log.md")
        try:
            text = open(log, encoding="utf-8", errors="ignore").read()
        except OSError:
            print("lane_validate: no log at %s" % log)
            return 0
        return envelope_report(os.path.dirname(os.path.abspath(log)), text)
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
    for name, tail, obs, cap, rest in _iter_lanes(text):
        if _still_open(tail, rest):
            continue
        capdir = _cap_dir(base, cap)
        # over-claim guard (P3): a named capture file whose mtime PREDATES the lane's
        # open time was not produced by this lane - flag it next to the verdict,
        # advisory only (never flips VERIFIED to NOT VERIFIED).
        stale = stale_evidence(capdir, obs, tail)
        suffix = ("  STALE-EVIDENCE: %s predates lane open (claim rests on pre-existing "
                  "artifacts)" % ", ".join(stale)) if stale else ""
        if not os.path.isdir(capdir):
            # scribe/draft lanes declare `capture <dir> (none; edits in <dir>)` and carry
            # the brain's own `-> VERIFIED:` verdict naming where the check happened;
            # the dir-less line is closed-by-brain, not an over-claim.
            m2 = re.search(r"^- lane %s\b.*capture \S+\s*\(.*-> VERIFIED:" % re.escape(name),
                           text, re.MULTILINE)
            if m2:
                print("lane %s: CLOSED-BY-BRAIN - no capture dir (annotated none; verdict "
                      "text documents the check)" % name)
                n_ok += 1
            else:
                print("lane %s: NOT VERIFIED - no capture dir at %s" % (name, cap))
                n_fail += 1
        elif not has_checkable(obs):
            n, b = _stats(capdir)
            print("lane %s: REVIEW-BY-EYE - descriptive criterion \"%s\" (mechanically "
                  "uncheckable); %d files %dB in %s, read the raws yourself%s"
                  % (name, obs, n, b, cap, suffix))
            n_ok += 1
        elif criterion_met(capdir, obs):
            print("lane %s: VERIFIED (\"%s\" present in %s)%s" % (name, obs, cap, suffix))
            n_ok += 1
        else:
            print("lane %s: NOT VERIFIED - \"%s\" absent from %s (over-claim; treat the "
                  "lane claim as a hypothesis)%s" % (name, obs, cap, suffix))
            n_fail += 1
    if n_ok == n_fail == 0:
        print("lane_validate: no returned lane lines with a SUCCESS criterion in %s" % log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
