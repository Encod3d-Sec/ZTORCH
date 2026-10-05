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
import json
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
    """Delegates to lane_validate.lane_lines (the parse + aging now live beside
    _LANE_RE, so close-out.py imports it directly instead of exec-ing this
    module by path). Kept as a name for existing callers/tests."""
    sys.path.insert(0, HERE)
    import lane_validate
    return lane_validate.lane_lines(d, stale_min)


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
    transcripts here would be too heavy for a dashboard; the hook keeps the running total.
    With ZT_MAX_ENG_USD set, annotates the budget band (strix 70/85/95 + the 90% reserve):
    70 = plan the finish, 85 = wrap-up mode, 90 = reserve held for evidence + report,
    95 = stop testing. The hard deny at 100% lives in drift-guard; this is the early
    steering that makes reaching 100% a choice instead of a surprise."""
    import json
    try:
        m = json.load(open(os.path.join(d, ".metrics.json"), encoding="utf-8"))
        v = float(m.get("spend_usd", 0) or 0)
    except Exception:
        return None
    if v <= 0:
        return None
    try:
        cap = float(os.environ.get("ZT_MAX_ENG_USD", "") or 0)
    except ValueError:
        cap = 0
    if cap > 0:
        pct = v / cap * 100
        if pct >= 95:
            band = "; BAND 95: STOP testing, close out now (hard deny at cap)"
        elif pct >= 90:
            band = ("; RESERVE 10%%: hold the last tenth for evidence packaging + report; "
                    "open NO new lanes (%.0f%%)" % pct)
        elif pct >= 85:
            band = "; BAND 85: wrap-up mode - finish open rows only, no new surface"
        elif pct >= 70:
            band = ("; BAND 70: plan the finish - no new surface classes; list what "
                    "close-out needs")
        else:
            band = " (%.0f%% of cap)" % pct
        return "spend: $%.2f%s" % (v, band)
    return "spend: $%.2f" % v


def facts_line(d):
    """One 'facts: N (a confirmed, b tentative, c neg)' line from state.md's
    ## Facts table, or None when the section is absent/empty. Deprecated rows
    (struck keys) are counted in neither bucket."""
    rows = []
    p = os.path.join(d, "state.md")
    try:
        text = open(p, encoding="utf-8", errors="ignore").read()
    except OSError:
        return None
    if "## Facts" not in text:
        return None
    for line in text.split("## Facts", 1)[1].splitlines():
        s = line.strip()
        if not s.startswith("|") or set(s) <= {"|", "-", " ", ":"}:
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 3 or cells[0] in ("key", ""):
            continue
        rows.append(cells)
    if not rows:
        return None
    live = [c for c in rows if "deprecated" not in c[1].lower()]
    conf = sum(1 for c in live if c[1].lower().startswith("confirmed"))
    tent = sum(1 for c in live if c[1].lower().startswith("tentative"))
    neg = sum(1 for c in live if c[0].strip("`~").startswith("negative/"))
    return "facts: %d (%d confirmed, %d tentative, %d neg)" % (len(live), conf, tent, neg)


OPEN_STATUSES = ("RESEARCH", "DETECTED", "CONFIRMED", "EXPLOITED")
_NEUTRAL_STATUSES = ("FALSE_POSITIVE", "IGNORED")
_RISK_W = {"CRITICAL": 10.0, "HIGH": 5.0, "MEDIUM": 2.0, "LOW": 0.5}
_SEV_RE = re.compile(r"FIND-\d+-([A-Z]+)-", re.I)


def finding_rows(d):
    """[(severity, status)] from Vulns/**/FIND-*.md (severity from the filename
    per the FIND naming rule, status from frontmatter). Skipped*/False* dirs are
    excluded exactly like find-lint.find_files."""
    out = []
    for p in glob.glob(os.path.join(d, "Vulns", "**", "FIND-*.md"), recursive=True):
        low = os.path.basename(os.path.dirname(p)).lower()
        if low.startswith("skip") or low.startswith("false"):
            continue
        mm = _SEV_RE.search(os.path.basename(p))
        sev = mm.group(1).upper() if mm else "INFO"
        try:
            text = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        m = re.search(r"^status:\s*(\w+)", text, re.M)
        out.append((sev.upper(), (m.group(1).upper() if m else "")))
    return out


def risk_line(d):
    """Weighted OPEN risk (cyberstrikeai L2): crit*10+high*5+med*2+low*0.5 over
    open (non-neutral) findings; fix-rate = EXPLOITED share of actionable.
    ZTorch has no FIXED status; EXPLOITED is the terminal verified state."""
    rows = [r for r in finding_rows(d)
            if r[1] not in _NEUTRAL_STATUSES and r[0] in _RISK_W]
    if not rows:
        return None
    open_rows = [r for r in rows if r[1] in OPEN_STATUSES]
    score = sum(_RISK_W[s] for s, _ in open_rows)
    n = {s: sum(1 for r in open_rows if r[0] == s) for s in _RISK_W}
    band = ("SAFE" if score <= 3 else "LOW" if score <= 10 else
            "MEDIUM" if score <= 30 else "HIGH" if score <= 60 else "SEVERE")
    expl = sum(1 for _, st in rows if st == "EXPLOITED")
    return ("risk: %s (score %g, open: %dc/%dh/%dm/%dl) fix-rate: %d%% (%d/%d)"
            % (band, score, n["CRITICAL"], n["HIGH"], n["MEDIUM"], n["LOW"],
               round(100 * expl / len(rows)), expl, len(rows)))


def activity_line(d):
    """Activity KPI from the engagement telemetry (eval_metrics.read_events - the
    ONE loader, no second parser). Rate is executed/(executed+blocked): blocked
    calls never executed, so they sit in the denominator only. No per-call fail
    dimension exists in .events.jsonl; do not invent one."""
    sys.path.insert(0, HERE)
    import eval_metrics
    events = eval_metrics.read_events(d)
    if not events:
        return None
    executed = sum(1 for e in events if e.get("kind") == "tool")
    blocked = sum(1 for e in events if e.get("kind") == "hook"
                  and e.get("action") == "deny")
    try:
        sys.path.insert(0, HERE)
        from offensive import changelog_pending
        pend = changelog_pending(d)[0]
    except Exception:
        pend = 0
    total = executed + blocked
    rate = (100.0 * executed / total) if total else 100.0
    return ("calls %d blocked %d rate %.1f%% cleanup-pending %d"
            % (executed, blocked, rate, pend))


ACTIONABLE = ("oob", "cleanup")


def attention_rows(d):
    """[(key, priority, prefix, text)] for the ATTENTION block, sorted p0 first.
    Reason keys are language-independent `kind:count` (cyberstrikeai
    dismissal-fingerprint pattern). wedged has no live feed in status.py this
    pass - p1 is lane-only."""
    rows = []
    oob_waiting = 0
    p = os.path.join(d, "oob.md")
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8", errors="ignore"):
            s = line.strip()
            if s.startswith("|") and not set(s) <= {"|", "-", " ", ":"}:
                cells = [c.strip().lower() for c in s.strip("|").split("|")]
                if len(cells) >= 5 and cells[4] == "waiting":
                    oob_waiting += 1
    if oob_waiting:
        rows.append(("oob:%d" % oob_waiting, "p0", "ACTION REQUIRED ",
                     "OOB callbacks pending (see oob.md)"))
    try:
        sys.path.insert(0, HERE)
        from offensive import changelog_pending
        n, det = changelog_pending(d)
    except Exception:
        n, det = 0, []
    if n:
        rows.append(("cleanup:%d" % n, "p0", "ACTION REQUIRED ",
                     "changelog rows lack verified rollback"))
    crit = sum(1 for sev, st_ in finding_rows(d)
               if sev == "CRITICAL" and st_ in OPEN_STATUSES
               and st_ != "EXPLOITED")  # done findings do not pin ATTENTION
    if crit:
        rows.append(("crit:%d" % crit, "p0", "", "%d open critical finding(s)" % crit))
    stale = sum(1 for ln in lane_lines(d) if "STALE" in ln)
    if stale:
        rows.append(("lane:%d" % stale, "p1", "",
                     "%d lane line(s) stale (>45m) - resume or close" % stale))
    return rows


def _dismiss_path(d):
    return os.path.join(d, ".attention-dismissed")


def attention_store(d, keys):
    with open(_dismiss_path(d), "a", encoding="utf-8") as fh:
        fh.write(",".join(sorted(keys)) + "\n")


def attention_suppressed(d, keys):
    """Dismissal holds ONLY while the current dismissable key set equals a
    stored fingerprint. A new key, changed count, or resolved subset re-arms."""
    try:
        stored = open(_dismiss_path(d), encoding="utf-8", errors="ignore").read()
    except OSError:
        return False
    cur = ",".join(sorted(keys))
    return any(ln.strip() == cur for ln in stored.splitlines() if ln.strip())


def attention_reset(d):
    try:
        os.remove(_dismiss_path(d))
    except OSError:
        pass


def render_attention(rows, d):
    """== ATTENTION == block. Actionable rows (oob, cleanup) always render;
    dismissable rows render unless the current dismissable key set matches a
    stored fingerprint."""
    dismissable = [r for r in rows if r[0].split(":")[0] not in ACTIONABLE]
    if dismissable and attention_suppressed(d, [r[0] for r in dismissable]):
        rows = [r for r in rows if r[0].split(":")[0] in ACTIONABLE]
    if not rows:
        return ""
    out = ["== ATTENTION =="]
    for key, pri, prefix, text in rows:
        out.append("[%s] %s%s - %s" % (pri, prefix, key, text))
    out.append("(dismiss: python3 scripts/status.py --attention-dismiss; "
               "reset: --attention-reset)")
    return "\n".join(out)


def render(name, etype, solved, summ, board, poc, cards, recon, deads, moves_text, lanes=(),
           died=0, spend=None, facts=None, risk=None, kpi=None):
    """Pure formatter -> the dashboard string. All inputs are precomputed (testable)."""
    head = "=== %s (%s)%s ===" % (name, etype, "  STATUS: SOLVED" if solved else "")
    lines = [head]
    if summ:
        lines.append("hosts %d (owned %d) | creds %d | open paths %d"
                     % (summ["hosts"], summ["owned"], summ["creds"], summ["open_paths"]))
    if risk:
        lines.append(risk)
    if kpi:
        lines.append(kpi)
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
    fl_ = facts
    if fl_:
        lines.append(fl_)
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
    if "--attention-reset" in sys.argv:
        attention_reset(d)
        print("attention dismissals cleared.")
        return 0
    if "--attention-dismiss" in sys.argv:
        rows = attention_rows(d)
        attention_store(d, [r[0] for r in rows
                            if r[0].split(":")[0] not in ACTIONABLE])
        print("dismissed (actionable rows never dismiss).")
        return 0
    solved = _engagement.is_solved(d)
    summ = _engagement.summary()
    board = board_phase(d)
    if board:
        # D3 (pass 14): board_phase counts checkbox LINES (4a + 4b tables + any checklist
        # prose); the parsed 4a/4b ROWS are what the driver serves. On skew, name both so
        # "N open" is never misread as board rows. Fail-open: parse trouble -> no note.
        try:
            import offensive
            prows = offensive.read_board(d) + offensive.read_board_4b(d)
            popen = sum(1 for r in prows
                        if (r.get("status") or "").strip() in ("[ ]", "[~]"))
            if popen != board[1]:
                board = ("%s [line-count; board parses %d open]" % (board[0], popen),
                         board[1], board[2])
        except Exception:
            pass
    poc, cards, recon, died = evidence_counts(d)
    deads = deadend_lines(d)
    moves_text = ""
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "next_move.py")],
                           capture_output=True, text=True, timeout=25)
        moves_text = r.stdout or ""
    except Exception:
        pass
    lanes = lane_lines(d)
    spend = spend_line(d)
    facts = facts_line(d)
    risk = risk_line(d)
    kpi = activity_line(d)
    if "--json" in sys.argv:
        # machine-readable dashboard (brain lanes / steering; mirrors render()'s inputs).
        # moves_text stays raw prose - it is next_move.py's own output, already line-based.
        print(json.dumps({
            "eng": name, "type": etype, "solved": solved,
            "summary": summ, "board_phase": board,
            "evidence": {"poc": poc, "cards": cards, "recon": recon, "died": died},
            "deadends": deads, "lanes": [ln.strip() for ln in lanes],
            "moves": moves_text.splitlines(), "spend": spend,
            "risk": risk, "activity": kpi,
            "attention": [r[0] for r in attention_rows(d)],
        }, ensure_ascii=False))
        return 0
    att = render_attention(attention_rows(d), d)
    print((att + "\n" if att else "") + render(name, etype, solved, summ, board,
                                               poc, cards, recon, deads, moves_text,
                                               lanes, died=died, spend=spend,
                                               facts=facts, risk=risk, kpi=kpi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
