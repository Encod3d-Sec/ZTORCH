#!/usr/bin/env python3
"""On-demand engagement status dashboard -- one consolidated glance for operator observability.

Composes the active engagement's counts (_engagement.summary), kill-chain phase (the board),
evidence actually captured (poc/ + recon/ shots), recent dead-ends, and the ranked next moves
(ranking stays in scripts/next_move.py -- not duplicated here). Read-only; never edits the
engagement. Run any time:

    python3 scripts/status.py
    python3 scripts/status.py --coverage   # full uncapped asset x vuln-class coverage matrix

The same render is surfaced compactly at SessionStart by engagement-init; this is the full
on-demand view (evidence + dead-ends included) the operator can pull mid-engagement. The
--coverage flag prints the per-asset coverage grid (offensive.py coverage) instead of the dashboard.
"""
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(VAULT, "skills", "hooks"))


def evidence_counts(d):
    """(poc_shots, poc_cards, recon_cards, died_scans): PoC images under poc/ (recursive) +
    poc/ .md evidence cards (excluding poc/scripts/ preserved-exploit .md) + auto recon
    shots + the subset of recon shots whose slug marks a DIED scan (-x<rc>, written by
    autocard from the pane's __ZT_RC marker) - the operator wants died scans visible,
    not folded into "done"."""
    poc = len(glob.glob(os.path.join(d, "poc", "**", "*.png"), recursive=True))
    cards = len([p for p in glob.glob(os.path.join(d, "poc", "**", "*.md"), recursive=True)
                 if os.sep + "scripts" + os.sep not in p])
    recon_shots = glob.glob(os.path.join(d, "recon", "*.png"))
    died = sum(1 for p in recon_shots if re.search(r"-x\d+", os.path.basename(p)))
    return poc, cards, len(recon_shots), died


def deadend_lines(d, limit=3):
    """The most recent Dead-ends.md table rows (asset x class -- what/why), formatted
    as one-line summaries. Deadends.md is a markdown table (asset|class|what was
    tried|why exhausted|date|reopen-if), not a bullet list."""
    import _engagement
    rows = _engagement._parse_table(os.path.join(d, "Deadends.md"))
    out = []
    for r in rows:
        asset = (r.get("asset") or "").strip()
        cls = (r.get("class") or "").strip()
        if not asset or not cls:
            continue
        bits = [b for b in ((r.get("what was tried") or "").strip(),
                             (r.get("why exhausted") or "").strip()) if b]
        out.append("%s x %s -- %s" % (asset, cls, "; ".join(bits)) if bits
                    else "%s x %s" % (asset, cls))
    return out[-limit:]


def board_phase(d):
    """(where, open_n, dead_n) from Approach.md: highest-numbered phase with an open item,
    or the explicit `current_phase` frontmatter field when set and in-scope (see
    _engagement.phase_explicit). Mirrors engagement-init.board_status; kept here so
    status.py has no hook dependency."""
    import _engagement
    p = os.path.join(d, "Approach.md")
    if not os.path.isfile(p):
        return None
    open_n = dead_n = 0
    phase = cur = None
    for line in open(p, encoding="utf-8", errors="ignore"):
        s = line.rstrip()
        hm = re.match(r"##\s+(\d+)\.\s+([^(]+)", s)
        if hm:
            phase = (int(hm.group(1)), hm.group(2).strip())
            continue
        if "[ ]" in s or "[~]" in s:
            open_n += 1
            if phase and (cur is None or phase[0] >= cur[0]):
                cur = phase
        elif "[!]" in s:
            dead_n += 1
    where = _engagement.phase_explicit(d) or (("Phase %d %s" % cur) if cur else "complete")
    return where, open_n, dead_n


def lane_lines(d, stale_min=45):
    """Open (in-flight) lane lines from log.md, aged off the @HH:MM cell. A lane open
    past stale_min was likely lost (compaction ate it or the subagent died) - surfaced
    as resume-or-close instead of the driver silently re-serving its work forever."""
    import importlib.util
    from datetime import datetime
    try:
        spec = importlib.util.spec_from_file_location(
            "lane_validate", os.path.join(HERE, "lane_validate.py"))
        lv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lv)
        text = open(os.path.join(d, "log.md"), encoding="utf-8", errors="ignore").read()
    except Exception:
        return []
    now = datetime.now()
    out = []
    for name, tail in lv.open_lanes_from_text(text):
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


def render_coverage(base, assets, tested_by_asset):
    """Pure formatter -> the full asset x vuln-class coverage grid (x=tested . =untested),
    UNCAPPED (unlike next_move's top-5 per-asset shortlist), so the coverage skill sees every
    in-scope asset against every base class instead of eyeballing Approach.md. `tested_by_asset`
    maps an asset name -> its set of tested class names (lowercased). Deterministic."""
    if not base or not assets:
        return "coverage: no in-scope assets or no class checklist for this engagement type."
    lines = ["coverage matrix (x=tested . =untested), %d classes:" % len(base)]
    for a in assets:
        tested = tested_by_asset.get(a, set())
        cells = " ".join("x" if c.lower() in tested else "." for c in base)
        n = sum(1 for c in base if c.lower() in tested)
        lines.append("  %-22s %s  (%d/%d)" % (a[:22], cells, n, len(base)))
    lines.append("  class order: " + " ".join(base))
    return "\n".join(lines)


def coverage_data(d, etype):
    """Gather (base_classes, in_scope_assets, {asset: tested_set}) for render_coverage.
    Read-only; reuses the exact helpers next_move.py consumes (in_scope_assets +
    _engagement.tested_classes) so the uncapped matrix and the ranked [gap] moves agree.
    Any missing piece degrades to empty. Import is lazy so module load stays dependency-light."""
    import json
    import _engagement
    import next_move
    try:
        base = json.load(open(os.path.join(VAULT, "scripts", "coverage-classes.json"),
                              encoding="utf-8")).get(etype, [])
    except Exception:
        base = []
    if not base:
        return base, [], {}
    sc = _engagement.scope(d)
    state = _engagement._parse_table(os.path.join(d, "state.md"))
    assets = next_move.in_scope_assets(state, etype, sc)
    glob_l, norm = next_move.tested_lookup(d, etype, base)
    tested_by_asset = {a: next_move.tested_for_asset(a, glob_l, norm) for a in assets}
    return base, assets, tested_by_asset


def spend_line(d):
    """One 'spend: $X.XX' line from .metrics.json's live spend_usd (accumulated by the
    tool-telemetry hook), or None when telemetry has not written it yet. Reading the
    transcripts here would be too heavy for a dashboard; the hook keeps the running total."""
    import json
    try:
        m = json.load(open(os.path.join(d, ".metrics.json"), encoding="utf-8"))
        v = float(m.get("spend_usd", 0) or 0)
    except Exception:
        return None
    return "spend: $%.2f" % v if v > 0 else None


def render(name, etype, solved, summ, board, poc, cards, recon, deads, moves_text, lanes=(),
           died=0, spend=None):
    """Pure formatter -> the dashboard string. All inputs are precomputed (testable)."""
    head = "=== %s (%s)%s ===" % (name, etype, "  STATUS: SOLVED" if solved else "")
    lines = [head]
    if summ:
        lines.append("hosts %d (owned %d) | creds %d | open paths %d"
                     % (summ["hosts"], summ["owned"], summ["creds"], summ["open_paths"]))
    if board:
        where, open_n, dead_n = board
        lines.append("board: %s | %d open | %d deadends" % (where, open_n, dead_n))
    ev = "evidence: %d poc shot(s), " % poc
    if cards:
        ev += "%d card(s), " % cards
    ev += "%d recon card(s)" % recon
    if died:
        ev += " (%d DIED - rerun or Deadends.md them)" % died
    lines.append(ev)
    if spend:
        lines.append(spend)
    if lanes:
        lines.append("open lanes:")
        lines += list(lanes)
    if deads:
        lines.append("recent deadends:")
        lines += ["  - " + x for x in deads]
    mt = moves_text
    if solved:                                   # a SOLVED box has nothing left to gap-fill
        mt = "\n".join(ln for ln in mt.splitlines() if "[gap]" not in ln)
    if mt.strip():
        lines.append(mt.strip())
    return "\n".join(lines)


def main():
    try:
        import _engagement
        d = _engagement.active_dir()
    except Exception:
        d = None
    if not d:
        print("No active engagement (targets/active.md).")
        return 0
    name = os.path.basename(d)
    etype = _engagement.engagement_type(d)
    if "--coverage" in sys.argv:   # full uncapped asset x class matrix (offensive.py coverage)
        print(render_coverage(*coverage_data(d, etype)))
        return 0
    solved = _engagement.is_solved(d)
    summ = _engagement.summary()
    board = board_phase(d)
    poc, cards, recon, died = evidence_counts(d)
    deads = deadend_lines(d)
    moves_text = ""
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "next_move.py")],
                           capture_output=True, text=True, timeout=25)
        moves_text = r.stdout or ""
    except Exception:
        pass
    print(render(name, etype, solved, summ, board, poc, cards, recon, deads, moves_text,
                 lane_lines(d), died=died, spend=spend_line(d)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
