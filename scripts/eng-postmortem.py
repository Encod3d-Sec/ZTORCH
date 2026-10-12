#!/usr/bin/env python3
"""eng-postmortem.py --eng <name> - offline replay of a finished engagement's log.md.

Hermes port (docs/port-specs/proposals-aux-eval-guards.md #3): the close-out
drift-count eyeballed by Skill(learn), computed from the log grammar the harness
already records (docs/log-grammar.md). Read-only, deterministic, no LLM, no live
target. Emits:

  - per-lane durations: the in-flight `@HH:MM` cell to the NEXT timestamped line
    after the lane line (another lane's @cell or an audit `<TS> |` row); same-day
    clock only, so every duration carries `~` (approximate: the anchor is an upper
    bound, not the true close event)
  - failure-class tallies from `-> NOT VERIFIED: <why>` reasons (no-capture /
    absent-from-capture / other, with samples)
  - driver-tool usage counts: `tool <name> ok|fail|blocked|cancelled|background`
    tokens, plus audit-line `<category>` tallies (scope/roe/tool/finding/lane/
    wiki/oob/cleanup)
  - envelope-missing counts: `- lane` lines without the full delegate envelope
    (SUCCESS criterion | tmux win | capture), or closed with no verdict cell

Lane parsing reuses scripts/lane_validate.py's regex via import (single source of
truth for the lane line shape). Exit 0 always; it measures, it does not judge.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)

sys.path.insert(0, HERE)
import lane_validate as lv                     # noqa: E402  (repo-local, stdlib only)

_TOOL_TOKEN = re.compile(r"\btool (\S+) (ok|fail|blocked|cancelled|background)\b")
_AUDIT_LINE = re.compile(r"^[^|\n]{1,40}\| *([a-z]+) *\| *[^|\n]+\| *[^|\n]+", re.MULTILINE)
_TIME_CELL = re.compile(r"@(\d{1,2}):(\d{2})")
_AUDIT_TS = re.compile(r"^(?:\d{4}-\d{2}-\d{2}[T ])?(\d{1,2}):(\d{2})(?::\d{2})? *\|",
                       re.MULTILINE)
_VERDICT = re.compile(r"-> (VERIFIED|NOT VERIFIED)(?::\s*([^|]*))?")


def _anchors(text):
    """[(char_pos, minutes)] for every timestamped line/cell, in file order."""
    out = []
    for m in _TIME_CELL.finditer(text):
        out.append((m.start(), int(m.group(1)) * 60 + int(m.group(2))))
    for m in _AUDIT_TS.finditer(text):
        out.append((m.start(), int(m.group(1)) * 60 + int(m.group(2))))
    out.sort()
    return out


def _next_anchor(anchors, pos):
    """Minutes of the first anchor after pos, or None."""
    for p, mins in anchors:
        if p > pos:
            return mins
    return None


def parse(text):
    """Stats dict from one log.md body. Lane shapes come from lane_validate."""
    lines = text.splitlines()
    anchors = _anchors(text)
    lanes, missing = [], []
    for m in lv._LANE_RE.finditer(text):
        name, tail, _obs, _cap, rest = m.groups()
        opened = _TIME_CELL.search(tail)
        open_min = (int(opened.group(1)) * 60 + int(opened.group(2))) if opened else None
        closed = not lv._still_open(tail, rest)
        v = _VERDICT.search(rest)
        close_min = _next_anchor(anchors, m.end()) if closed else None
        dur = None
        if closed and open_min is not None and close_min is not None:
            dur = (close_min - open_min) % 1440          # same-day wrap heuristic
        reason = (v.group(2) or "").strip(" -") if v and v.group(1) == "NOT VERIFIED" else ""
        um = re.search(r"\| usage (\d+)t/(\d+)s", tail + " " + (rest or ""))
        lanes.append({"name": name, "closed": closed, "dur": dur,
                      "verified": bool(v and v.group(1) == "VERIFIED"),
                      "not_verified": bool(v and v.group(1) == "NOT VERIFIED"),
                      "reason": reason, "has_open_time": open_min is not None,
                      "tokens": int(um.group(1)) if um else 0,
                      "wall_s": int(um.group(2)) if um else 0})
        if closed and not v:
            missing.append("lane %s closed with no verdict cell" % name)

    # envelope-missing: a `- lane` line the full-envelope regex does not match at all
    # (missing SUCCESS / tmux win / capture cells)
    for i, line in enumerate(lines, start=1):
        if line.startswith("- lane ") and not lv._LANE_RE.match(line):
            missing.append("line %d: lane line missing envelope cells" % i)

    tools, fails = {}, {}
    for m in _TOOL_TOKEN.finditer(text):
        name, outcome = m.groups()
        tools[outcome] = tools.get(outcome, 0) + 1
        if outcome in ("fail", "blocked"):
            fails[name] = fails.get(name, 0) + 1
    cats = {}
    for m in _AUDIT_LINE.finditer(text):
        cats[m.group(1)] = cats.get(m.group(1), 0) + 1
    return {"lanes": lanes, "envelope_missing": missing, "tools": tools,
            "tool_fails": fails, "audit_cats": cats, "n_lines": len(lines)}


def _fmt_dur(d):
    if d is None:
        return "?"
    return "~%dmin" % d


def render(st):
    """The printed summary block."""
    out = ["eng-postmortem: %d log line(s) replayed (durations ~approximate, "
           "same-day clock)" % st["n_lines"]]
    lanes = st["lanes"]
    if not lanes:
        out.append("lanes: none recorded")
    else:
        nv = [l for l in lanes if l["not_verified"]]
        out.append("lanes: %d (%d verified, %d not verified, %d never closed)"
                   % (len(lanes), sum(1 for l in lanes if l["verified"]), len(nv),
                      sum(1 for l in lanes if not l["closed"])))
        for l in lanes:
            state = ("open" if not l["closed"]
                     else "VERIFIED" if l["verified"]
                     else "NOT VERIFIED" if l["not_verified"] else "closed, no verdict")
            dur = ("never closed" if not l["closed"] else _fmt_dur(l["dur"]))
            out.append("  lane %-20s %-18s %s" % (l["name"], state, dur))
        if nv:
            classes = {}
            for l in nv:
                r = (l["reason"] or "").lower()
                cls = ("no-capture" if "no capture" in r
                       else "absent-from-capture" if "absent" in r else "other")
                classes.setdefault(cls, []).append(l["reason"] or "(no reason text)")
            out.append("failure classes (-> NOT VERIFIED reasons):")
            for cls in sorted(classes):
                out.append("  %-20s %d  (e.g. %s)"
                           % (cls, len(classes[cls]), classes[cls][0][:60]))
    t = st["tools"]
    if t:
        tail = ""
        if st["tool_fails"]:
            tail = " | fails/blocked: " + ", ".join(
                "%s=%d" % kv for kv in sorted(st["tool_fails"].items()))
        out.append("driver tools: " + ", ".join(
            "%s=%d" % kv for kv in sorted(t.items())) + tail)
    if st["audit_cats"]:
        out.append("audit categories: " + ", ".join(
            "%s=%d" % kv for kv in sorted(st["audit_cats"].items())))
    toks = sum(l["tokens"] for l in lanes if l.get("tokens"))
    if toks:
        out.append("lane tokens: %d recorded on usage cells (avg %d/lane)"
                   % (toks, toks // max(1, sum(1 for l in lanes if l.get("tokens")))))
    if st["envelope_missing"]:
        out.append("lane envelope problems: %d (%s)"
                   % (len(st["envelope_missing"]), st["envelope_missing"][0]))
    else:
        out.append("lane envelope: OK (every `- lane` line parses, every closed line "
                   "carries a verdict)")
    return "\n".join(out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description="offline engagement postmortem from log.md")
    ap.add_argument("--eng", required=True,
                    help="engagement name (targets/<name>) or path")
    args = ap.parse_args(argv)
    eng = args.eng if os.path.isdir(args.eng) else os.path.join(VAULT, "targets", args.eng)
    log = os.path.join(eng, "log.md")
    try:
        text = open(log, encoding="utf-8", errors="ignore").read()
    except OSError:
        print("eng-postmortem: no log at %s" % log)
        return 0
    print(render(parse(text)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
