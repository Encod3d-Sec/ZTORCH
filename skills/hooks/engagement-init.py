#!/usr/bin/env python3
"""SessionStart hook: self-heal engagement state + inject summary + board + gap report.

- Creates any missing files from the active engagement's per-type core set (state/loot/
  Approach/...; Killchain only for pentest/bugbounty) from templates (self-heal; never
  overwrites).
- Injects the active-engagement summary, scope, OOB HITs, and the kill-chain board
  status (current phase + open/deadend counts) so you re-orient to the board.
- Collapses the per-item maintenance nags (wordlist / wiki-candidate / hook-drift /
  skill-drift / wiki-freshness / md-tables) into one compact `harness:` line, silent at zero.
- Keeps wiki/index.md fresh (scripts/gen_index.py, idempotent) only when the wiki
  actually changed since last session.
- Surfaces the active research project's loop state (scripts/research_status.py).

Plain stdout is added to context, alongside the other SessionStart hooks
(hot.md). Non-fatal: any error exits 0 silent.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _run_script(name, *args, timeout=40):
    """Run scripts/<name> from the vault; return CompletedProcess or None."""
    try:
        import _engagement
        script = os.path.join(_engagement.VAULT, "scripts", name)
        return subprocess.run(
            ["python3", script, *args],
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception:
        return None


def _board_empty(d):
    """True iff Approach.md exists but carries no board content -- no checklist item AND no
    populated 4a table row. Same criteria recon-capture.py's _board_never_built uses."""
    p = os.path.join(d, "Approach.md")
    if not os.path.isfile(p):
        return False
    try:
        txt = open(p, encoding="utf-8", errors="ignore").read()
    except OSError:
        return False
    if re.search(r"^\s*-\s*\[[ x~!\-]\]", txt, re.I | re.M):
        return False
    try:
        import _engagement
        if _engagement._parse_table(p):
            return False
    except Exception:
        pass
    return True


def self_heal_board():
    """Auto-run `offensive.py board` when Approach.md exists but was never populated (init ran,
    board never did). Removes the "is this box worth boarding" judgment call entirely (W7-2: a
    box judged 'too obvious to board' otherwise loses ALL foothold/privesc tracking). Only runs
    once .offensive.json exists (init already happened) -- a driver-less engagement is a
    deliberate choice this must not override. Returns True iff it ran the heal."""
    try:
        import _engagement
        d = _engagement.active_dir()
        if not d:
            return False
        if not os.path.isfile(os.path.join(d, ".offensive.json")):
            return False
        if not _board_empty(d):
            return False
        r = _run_script("offensive.py", "board", "--eng", d, timeout=15)
        return bool(r and r.returncode == 0)
    except Exception:
        return False


def self_heal_facts(d=None):
    """Append the ## Facts header to the active engagement's state.md when
    missing (cyberstrikeai L3): existing engagements predate the section.
    d defaults to the active engagement dir; tests pass an explicit path."""
    if not d:
        try:
            import _engagement
            d = _engagement.active_dir()
        except Exception:
            return
    if not d:
        return
    p = os.path.join(d, "state.md")
    if not os.path.isfile(p):
        return
    text = open(p, encoding="utf-8", errors="ignore").read()
    if "## Facts" in text:
        return
    block = ("\n## Facts\n\n"
             "One line per fact: key | confidence | summary. Negative results are facts.\n\n"
             "| key | conf | summary |\n|---|---|---|\n")
    if text and not text.endswith("\n"):
        text += "\n"
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(block)


def regen_index():
    """Keep wiki/index.md current (writes only when stale; no churn when fresh)."""
    _run_script("gen_index.py", timeout=30)


def board_status():
    """One-line kill-chain board summary for the active engagement, or None.
    Names the highest-numbered phase that still has an open ([ ] / [~]) item and
    counts total open items + deadends ([!]). Best-effort; None when no board or
    nothing is open/dead (so it stays silent on a fresh or finished board)."""
    try:
        import _engagement
        d = _engagement.active_dir()
        if not d:
            return None
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
        if open_n == 0 and dead_n == 0:
            return None
        where = _engagement.phase_explicit(d) or (("Phase %d %s" % cur) if cur else "complete")
        return "Board: %s, %d open, %d deadends" % (where, open_n, dead_n)
    except Exception:
        return None


def _driver_behind(vault):
    """Commits the framework repo's HEAD is behind its tracked upstream (0 on no-upstream / not-a-repo
    / any error). No fetch - measured against the last fetch, so it fail-opens rather than dialing out."""
    try:
        import subprocess
        r = subprocess.run(["git", "rev-list", "--count", "HEAD..@{u}"],
                           cwd=vault, capture_output=True, text=True, timeout=5)
        return int((r.stdout or "0").strip() or "0") if r.returncode == 0 else 0
    except Exception:
        return 0


def harness_maintenance():
    """Compact list of pending harness-maintenance tags -- replaces the old stack of
    per-item SessionStart nags (wordlist / wiki-candidate / hook-drift / skill-drift).
    Each is best-effort + silent-at-zero; returns [] when nothing pends."""
    tags = []
    try:
        wc = wordlist_candidates()
        if wc and (wc[0] + wc[1]) > 0:
            tags.append("wordlist %d+%d (wl-add.sh)" % wc)
    except Exception:
        pass
    try:
        wcc = wiki_candidate_count()
        if wcc:
            tags.append("wiki-candidates:%d (wiki-promote.py --list)" % wcc)
    except Exception:
        pass
    try:
        import importlib.util
        import _engagement
        _ch_path = os.path.join(_engagement.VAULT, "scripts", "check-hooks.py")
        _spec = importlib.util.spec_from_file_location("check_hooks", _ch_path)
        _ch = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_ch)
        miss = _ch.missing_hooks()
        if miss:
            tags.append("hook-drift: " + ",".join(miss) + " (install-hooks.sh)")
        stale = _ch.stale_hooks()
        if stale:
            tags.append("stale-hook: " + ",".join(stale) + " (install-hooks.sh)")
        if _ch.missing_skills():
            # name them: a vault-valid skill can still be Unknown on THIS seat
            # (symlink not installed); the name is what routes the fix
            tags.append("skill-drift: " + ",".join(_ch.missing_skills())
                        + " (install-skills.sh)")
    except Exception:
        pass
    # T4.1 driver-staleness: warn when the framework repo is meaningfully behind its upstream, so a
    # stale driver/hook set is surfaced like hook-drift (road ran a driver 26 commits behind main
    # and it cascaded). No fetch (SessionStart time budget) - measured against the last fetch; fail-open.
    try:
        import _engagement
        behind = _driver_behind(_engagement.VAULT)
        if behind >= 5:
            tags.append("driver-stale: %d commits behind upstream (git pull to refresh "
                        "offensive.py/hooks)" % behind)
    except Exception:
        pass
    try:
        import importlib.util
        import _engagement
        _lmt_path = os.path.join(_engagement.VAULT, "scripts", "lint-md-tables.py")
        _spec = importlib.util.spec_from_file_location("lint_md_tables", _lmt_path)
        _lmt = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_lmt)
        d = _engagement.active_dir()
        if d:
            broken = _lmt.lint_paths([d])
            if broken:
                tags.append("md-tables:%d broken (lint-md-tables.py %s)"
                            % (len(broken), os.path.basename(d.rstrip("/"))))
    except Exception:
        pass
    return tags


def wordlist_candidates():
    """(paths, params) count of NEW generic wordlist tokens minable from targets/, or None."""
    r = _run_script("wordlist-suggest.py", "--count", timeout=20)
    if r is None:
        return None
    try:
        p, q = r.stdout.split()
        return (int(p), int(q))
    except Exception:
        return None


def wiki_candidate_count():
    """Pending candidates in the active engagement's wiki-candidates/ inbox, or 0.
    Silent-at-zero surfacer, same shape as the wordlist nag. Best-effort.

    Detects pending by PARSING frontmatter via _engagement._frontmatter (the same
    tolerant parser wiki-promote.py's pending-detection uses), not a raw
    "status: pending" substring - a raw substring misses e.g. 'status:  pending'
    (extra spacing), silently undercounting a candidate that IS promotable."""
    try:
        import _engagement
        d = _engagement.active_dir()
        if not d:
            return 0
        inbox = os.path.join(d, "wiki-candidates")
        if not os.path.isdir(inbox):
            return 0
        n = 0
        for f in os.listdir(inbox):
            if not f.endswith(".md") or f.startswith("_"):
                continue
            text = open(os.path.join(inbox, f), encoding="utf-8", errors="ignore").read()
            fm = _engagement._frontmatter(text)
            if fm.get("status", "").strip().lower() == "pending":
                n += 1
        return n
    except Exception:
        return 0


def research_status_text():
    """Full status block for the active research project, or None if none set."""
    r = _run_script("research_status.py", timeout=15)
    if r is None:
        return None
    out = r.stdout.strip()
    return out if out and "No active research project" not in out else None


def _stamp_path():
    import _engagement
    return os.path.join(_engagement.VAULT, ".wiki-stamp")


def wiki_fingerprint():
    """Cheap max-mtime over wiki/ + triggers.json + playbook.json (stat only, no reads).
    Detects any page add/remove/edit so the heavy walks run only when needed."""
    import _engagement
    mx = 0.0
    stack = [os.path.join(_engagement.VAULT, "wiki")]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                    else:
                        m = e.stat(follow_symlinks=False).st_mtime
                        if m > mx:
                            mx = m
        except OSError:
            pass
    for f in ("skills/exploit/hunt/triggers.json", "scripts/playbook.json"):
        try:
            m = os.stat(os.path.join(_engagement.VAULT, f)).st_mtime
            if m > mx:
                mx = m
        except OSError:
            pass
    return f"{mx:.3f}"


def wiki_changed():
    """(changed, fingerprint). True if wiki/triggers/playbook changed since last stamp."""
    fp = wiki_fingerprint()
    try:
        old = open(_stamp_path(), encoding="utf-8").read().strip()
    except OSError:
        old = ""
    return (fp != old, fp)


def write_stamp(fp):
    try:
        open(_stamp_path(), "w", encoding="utf-8").write(fp)
    except OSError:
        pass


def _compact_restore():
    """SessionStart(source=='compact') addition: after compaction the context holds the
    summary plus capped attachments, and this hook's normal output re-injects counts and
    next-moves -- but not the board itself. The board is the one artifact the next
    context must hold EXACTLY (the driver re-ranks from it; a paraphrased row loses the
    tool/asset/status cells), so re-inject the open rows VERBATIM (capped)."""
    try:
        import _engagement
        d = _engagement.active_dir()
        if not d:
            return None
        lines = open(os.path.join(d, "Approach.md"), encoding="utf-8",
                     errors="ignore").read().splitlines()
        rows = [ln.rstrip() for ln in lines if "[ ]" in ln or "[~]" in ln][:40]
        # the driver's served move, persisted by cmd_next (pass 4): the printed plan
        # is otherwise context-only and a mid-loop compaction loses it.
        lm = ""
        try:
            st = json.load(open(os.path.join(d, ".offensive.json"), encoding="utf-8"))
            m = st.get("last_move")
            if m:
                lm = ("\ndriver last move (%s): asset %s row %s %s -> Skill(%s) / %s"
                      % (m.get("ts", "?"), m.get("asset", "?"), m.get("row", "?"),
                         m.get("class", ""), m.get("skill", ""), m.get("tool", "")))
        except Exception:
            try:   # corrupt driver state silently drops the post-compact move restore
                if os.path.isfile(os.path.join(d, ".offensive.json")):
                    import _telemetry
                    _telemetry.log_event("hook", d=d, hook="engagement-init",
                                         error=".offensive.json unparseable - post-compact driver-move restore skipped")
            except Exception:
                pass
        # open (in-flight) delegate lanes from log.md: a lane's continuation handle lives
        # only in the dispatch message, which compaction ate. The log line IS the state
        # (no new state file) - re-inject them aged so they get resumed or closed instead
        # of the driver silently re-serving the same work.
        try:
            # lane_validate is stateless (parses log.md text), so anchor to the vault the
            # HOOK ships in (HERE/../..), not _engagement.VAULT: a ZTORCH_VAULT override
            # pointing at a bare test tree would silently kill the import.
            sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "scripts")))
            import lane_validate
            lanes = lane_validate.lane_lines(d)
        except Exception:
            lanes = []
        # OOB sinks ride the re-inject verbatim (pentagi short_execution_context: callback
        # values are the one thing a compaction must not paraphrase away). waiting/HIT rows
        # only; actioned/expired already landed in findings.
        try:
            oob_lines = []
            ot = os.path.join(d, "oob.md")
            if os.path.isfile(ot):
                for ln in open(ot, encoding="utf-8", errors="ignore").read().splitlines():
                    cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                    if len(cells) >= 5 and cells[0] and cells[0] != "token" \
                            and cells[4].lower() in ("waiting", "hit"):
                        oob_lines.append("OOB sink (verbatim): %s -> %s [%s]"
                                         % (cells[0], cells[1], cells[4]))
            if oob_lines:
                oob_lines.insert(0, "OOB sinks (do NOT paraphrase tokens or sink hosts):")
        except Exception:
            oob_lines = []
        if not rows and not lm and not lanes and not oob_lines:
            return None
        head = ("restored post-compact (Approach.md open rows, verbatim; re-run "
                "`offensive.py next` before acting):\n")
        body = head + "\n".join(rows) + lm
        if lanes:
            body += "\nopen delegate lanes (log.md 'in flight'; resume via handle or "
            body += "close the line):\n" + "\n".join(lanes)
        if oob_lines:
            body += "\n" + "\n".join(oob_lines)
        return body
    except Exception:
        return None


def main():
    try:
        import _engagement
    except Exception:
        return

    # Post-compact SessionStart fires with stdin {"source": "compact"}: beyond the normal
    # state summary, re-inject the open board rows verbatim (see _compact_restore). The
    # isatty guard keeps manual/terminal runs non-blocking (no piped stdin to read).
    payload = {}
    if not sys.stdin.isatty():
        try:
            payload = json.loads(sys.stdin.read()) or {}
        except Exception:
            payload = {}
        if payload.get("source") == "compact":
            cr = _compact_restore()
            if cr:
                print(cr)
                print()

    # Session lineage: the host passes session_id on every SessionStart fire; one line
    # per FRESH session in log.md is the evidence timeline (which sessions touched this
    # engagement, grep-able). Same-session re-fires (resume, source=compact) never
    # duplicate; no active engagement or no id -> silent.
    try:
        sid = str(payload.get("session_id") or "")
        if sid and payload.get("source") != "compact":
            _d = _engagement.active_dir()
            lp = os.path.join(_d, "log.md") if _d else None
            if lp:
                old = open(lp, encoding="utf-8", errors="ignore").read() if \
                    os.path.isfile(lp) else ""
                if sid[:8] not in old:
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                    with open(lp, "a", encoding="utf-8") as fh:
                        fh.write("\n## %s - session %s start\n" % (ts, sid[:8]))
    except Exception:
        pass

    out = []
    created = _engagement.ensure_state_files()
    if created:
        out.append("Self-heal: created " + ", ".join(created) + " from template.")

    try:
        if self_heal_board():
            out.append("Self-heal: Approach.md board was empty - ran `offensive.py board` to "
                       "populate it.")
    except Exception:
        pass

    try:
        self_heal_facts()
    except Exception:
        pass

    # telemetry: back-fill the box start time on first sight (new-engagement.sh stamps the precise
    # start; this covers pre-existing boxes) and record the session-start hook fire.
    try:
        import _telemetry
        _d = _engagement.active_dir()
        if _d:
            _telemetry.stamp_once("started_at", _telemetry.now_iso(), d=_d)
            _telemetry.hook("engagement-init", d=_d, action="session-start")
    except Exception:
        pass

    summ = _engagement.summary_text()
    if summ:
        out.append(summ)
        # Output-economy caps ride with the summary: summary_text() is truthy only when
        # an engagement is active (active_dir() resolved), so a bare vault never sees this.
        out.append("Output caps (engagement turns): intent line before a tool batch <=25 "
                   "words; whole turn <=100 words; emit text only for operator decisions, "
                   "milestones, or blockers that change the plan.")

    sc = _engagement.scope_text()
    if sc:
        out.append(sc)

    # tunnel_safe is an affirmation, not a forbidden flag, so scope_text (RoE-forbidden
    # list) omits it. Surface it explicitly so the model knows curl+nc is the intended
    # tool here (scanners exhaust the pivot's conntrack). Silent when unset.
    try:
        if _engagement.scope().get("tunnel_safe"):
            out.append("tunnel_safe: curl+nc only (scanners kill the pivot)")
    except Exception:
        pass

    # OOB callback HITs land the highest: a confirmed blind-bug callback should be
    # turned into a FIND immediately. Surfaced above next-moves.
    try:
        hits = _engagement.oob_hits()
        if hits:
            sinks = "; ".join((h.get("sink") or h.get("token") or "?") for h in hits[:4])
            out.append(f"OOB HIT: {len(hits)} callback(s) landed ({sinks}) -> scaffold + "
                       "validate the FIND(s), then mark the oob.md row 'actioned'.")
    except Exception:
        pass

    # Pending ingest is invisible after compaction/restart: SessionStart never looked at
    # ingest/ before this. Safe to surface every time -- the archive-at-end design makes
    # an ingest re-run idempotent (already-processed files are under _processed/).
    try:
        _d = _engagement.active_dir()
        ing = os.path.join(_d, "ingest") if _d else None
        if ing and os.path.isdir(ing):
            pend = [f for f in os.listdir(ing)
                    if not f.startswith(("_", "."))
                    and os.path.isfile(os.path.join(ing, f))]
            if pend:
                out.append(f"ingest pending: {len(pend)} file(s) in targets/"
                           f"{os.path.basename(_d)}/ingest/ - re-run Skill(ingest) "
                           "(re-runs are idempotent: processed files archive to _processed/)")
    except Exception:
        pass

    # kill-chain board: current phase + open/deadend counts, so you re-orient to the
    # board rather than re-running the last thing. Silent when no board / nothing open.
    try:
        bs = board_status()
        if bs:
            out.append(bs)
    except Exception:
        pass

    # evidence captured (observability): a multi-finding box with few deliberate shots is a
    # capture gap the operator should see at a glance. Silent at zero. Full view: scripts/status.py.
    try:
        import glob as _glob
        import re as _re
        _d = _engagement.active_dir()
        if _d:
            _poc = len(_glob.glob(os.path.join(_d, "poc", "**", "*.png"), recursive=True))
            _rec = _glob.glob(os.path.join(_d, "recon", "*.png"))
            if _poc or _rec:
                _line = "evidence: %d poc shot(s), %d recon card(s)" % (_poc, len(_rec))
                _died = sum(1 for _p in _rec if _re.search(r"-x\d+", os.path.basename(_p)))
                if _died:
                    _line += " (%d DIED)" % _died
                out.append(_line + " (scripts/status.py = full status)")
    except Exception:
        pass

    # VM tabs in flight (pass 11 L6): windows autocard has SEEN but never carded - its
    # .open-tabs ledger, maintained every Stop hook, so this needs no SSH round-trip here.
    # A tab stuck on this list across sessions is a wedged scan or an un-carded listener.
    try:
        _d = _engagement.active_dir()
        _p = os.path.join(_d, ".open-tabs") if _d else ""
        if _p and os.path.isfile(_p):
            _tabs = [l.strip().split("=", 1)[0] for l in
                     open(_p, encoding="utf-8", errors="ignore") if l.strip()]
            if _tabs:
                _extra = " +%d more" % (len(_tabs) - 5) if len(_tabs) > 5 else ""
                out.append("vm tabs in flight: %d un-carded (%s%s) - card them "
                           "(capture.sh recon) or expect the close-out sweep"
                           % (len(_tabs), ", ".join(_tabs[:5]), _extra))
    except Exception:
        pass

    # ranked next-moves from the analyzer (top 3)
    try:
        sys.path.insert(0, os.path.join(_engagement.VAULT, "scripts"))
        import next_move
        for m in next_move.suggest(limit=3):
            out.append("  next: " + m)
    except Exception:
        pass

    # One compact harness-maintenance line replaces the old stack of per-item nags
    # (wordlist / wiki-candidate / hook-drift / skill-drift). Silent at zero.
    try:
        maint = harness_maintenance()
        if maint:
            out.append("harness: " + "; ".join(maint))
    except Exception:
        pass

    # Wiki upkeep runs ONLY when wiki/triggers/playbook actually changed since the
    # last session (a cheap stat-only fingerprint vs a stamp) - the main SessionStart
    # speedup on the slow Windows mount. Refresh index.md silently, fold a freshness
    # count into one note, and nudge a qmd reindex. The gaps/lint checks are on-demand
    # scripts now (scripts/wiki-gaps.py, scripts/lint-wiki.py), not SessionStart nags.
    changed, _ = wiki_changed()
    if changed:
        regen_index()  # keep index.md fresh (idempotent)
        note = "Wiki changed since last session -> run `qmd update && qmd embed` to refresh the search index (embed keeps new pages semantically findable)."
        try:
            import freshness
            fr = freshness.stale()
            if fr:
                note += "  [%d reuse page(s) stale -> scripts/freshness.py]" % len(fr)
        except Exception:
            pass
        out.append(note)
        write_stamp(wiki_fingerprint())   # recompute AFTER regen_index bumped index.md, else next session re-fires

    if out:
        print("=== Engagement state ===")
        print("\n".join(out))

    # client narrative loads from the private per-engagement log.md, NOT session/
    # (session/hot.md stays generic/framework-only). log.md = the per-engagement audit;
    # its newest block is the continuity cache surfaced here.
    try:
        rl = _engagement.recent_log()
        if rl:
            print("=== Recent engagement log ===")
            print(rl)
    except Exception:
        pass

    # active research project (raw/research/active.md) surfaces its loop state
    rs = research_status_text()
    if rs:
        print(rs)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
