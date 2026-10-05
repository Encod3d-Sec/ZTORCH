#!/usr/bin/env python3
"""Stop hook: close-out reflex. When the active engagement is marked SOLVED but its
web evidence is incomplete (a web box with no recon cards or no saved render+source) --
or the walkthrough is not assembled -- or the walkthrough is done but the learn harvest is
still due -- surface a one-line nudge to run the close-out steps. The web-evidence gate
fires FIRST: you cannot have a complete walkthrough without the evidence, and it is the
thing skipped under momentum (recon cards, site render+source).

This is the reflex the de-bloat left unwired: deleting loop-driver removed the Stop-gate,
and _engagement.is_solved / walkthrough_stale / learn_pending had no caller, so a SOLVED box
produced no reminder (observed live: a solved box whose walkthrough + learn were never
invoked). Advisory + fail-open: never blocks the Stop, prints nothing on any
error, and self-clears the moment the walkthrough is assembled and Skill(learn) writes
.learn-done.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def inflight_signals(d):
    """Work still in flight at Stop, as a list of short strings: open lanes (aged by
    status.lane_lines), the driver's last-served row never dispositioned, pending
    ingest files, waiting OOB sinks. Open lanes and the undisposed serve have NO
    other surface anywhere (lane state lives in log.md text; last_move is never
    re-checked); ingest/OOB do re-surface at SessionStart, this adds turn-end
    visibility for the operator watching the session end."""
    parts = []
    try:                                       # open lanes (age/STALE via lane_validate)
        import _engagement
        # anchor to the vault the HOOK ships in, not _engagement.VAULT: a
        # ZTORCH_VAULT override pointing at a bare test tree has no scripts/ and
        # the import (this whole lane surface) would silently vanish. Same fix
        # as engagement-init's post-compact restore.
        sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "scripts")))
        import lane_validate
        parts += [ln.strip() for ln in lane_validate.lane_lines(d)]
        # closed-lane verdict sweep (pass 13): a returned lane whose SUCCESS criterion is
        # absent from its capture is an over-claim that already poisoned loot/Killchain
        # (append_draft_chain_rows trusts loot lines). The verdict surface otherwise runs
        # ONLY when the main agent remembers the delegate-skill prose. Deduped on the
        # bad-count marker so it re-fires only when a NEW bad lane lands.
        try:
            _log = open(os.path.join(d, "log.md"), encoding="utf-8",
                        errors="ignore").read()
            _bad = []
            for _n, _obs, _cap in lane_validate.lanes_from_text(_log):
                _cd = _cap if os.path.isabs(_cap) else os.path.normpath(
                    os.path.join(d, _cap))
                if not lane_validate.criterion_met(_cd, _obs):
                    _bad.append(_n)
            if _bad:
                vm = os.path.join(d, ".lane-verify-nudged")
                last = 0
                try:
                    last = int((open(vm).read().strip() or "0"))
                except Exception:
                    last = 0
                if len(_bad) > last:
                    parts.append("lane NOT VERIFIED (over-claim): " + ", ".join(sorted(set(_bad)))
                                 + " - criterion absent from capture; treat the claim as a "
                                   "hypothesis, check or strike it")
                    open(vm, "w").write(str(len(_bad)))
        except Exception:
            pass
    except Exception:
        pass
    try:                                       # served move with no disposition
        import json
        lm = (json.loads(open(os.path.join(d, ".offensive.json"),
                              encoding="utf-8", errors="ignore").read())
              .get("last_move") or {})
        rid = (lm.get("row") or "").strip()
        if rid:
            for line in open(os.path.join(d, "Approach.md"),
                             encoding="utf-8", errors="ignore").read().splitlines():
                s = line.strip()
                if s.startswith("|") and rid in s:
                    if "[ ]" in s or "[~]" in s:
                        parts.append("served %s @%s not disposed (done/note the row)"
                                     % (rid, lm.get("ts", "?")))
                    break
    except Exception:
        try:    # corrupt driver state silently drops the served-move surface; record it
            if os.path.isfile(os.path.join(d, ".offensive.json")):
                import _telemetry
                _telemetry.log_event("hook", d=d, hook="close-out",
                                     error=".offensive.json unparseable - served-move surface skipped")
        except Exception:
            pass
    try:                                       # pending ingest (SessionStart repeats it)
        ing = os.path.join(d, "ingest")
        n = [f for f in os.listdir(ing) if not f.startswith(("_", "."))]
        if n:
            parts.append("%d ingest file(s) pending (ingest skill)" % len(n))
    except Exception:
        pass
    try:                                       # wedged VM scan tabs (autocard's ledger)
        wt = os.path.join(d, ".wedged-tabs")
        if os.path.isfile(wt):
            parts += [ln.strip() for ln in
                      open(wt, encoding="utf-8", errors="ignore").read().splitlines()
                      if ln.strip()]
    except Exception:
        pass
    try:                                       # planted OOB tokens still waiting
        oob = os.path.join(d, "oob.md")
        if os.path.isfile(oob):
            w = 0
            for line in open(oob, encoding="utf-8", errors="ignore").read().splitlines():
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 5 and cells[4].lower() == "waiting":
                    w += 1
            if w:
                parts.append("%d OOB sink(s) waiting (callback still owed)" % w)
    except Exception:
        pass
    return parts


def _approach_needs_review(d):
    """needs-review: true in Approach.md's provenance block blocks a CLEAN
    close until acknowledged with an 'approach reviewed' line in decisions.md."""
    try:
        t = open(os.path.join(d, "Approach.md"), encoding="utf-8", errors="ignore").read()
    except OSError:
        return False
    try:
        dec = open(os.path.join(d, "decisions.md"), encoding="utf-8", errors="ignore").read()
    except OSError:
        dec = ""    # decisions.md absent: still advise until acknowledged
    return "needs-review: true" in t and "approach reviewed" not in dec.lower()


def _open_class_census(d):
    """finish_scan census (strix): the classes the engagement actually carried, with
    unresolved 4a rows listed, plus a chaining-gate flag (closed vectors exist).
    Advisory only; fail-open (([], False))."""
    rows = []
    try:
        with open(os.path.join(d, "Approach.md"), encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                s = line.strip()
                if not s.startswith("| 4a:"):
                    continue
                cells = [c.strip() for c in s.strip("|").split("|")]
                if len(cells) >= 7:            # id|asset|class|arsenal|skill|tool|status...
                    rows.append(cells)
    except OSError:
        return [], 0
    by_class = {}
    closed = 0
    for c in rows:
        cls = (c[2] if c[2] else "-").lower()
        st = c[6]
        if st in ("[ ]", "[~]", "[?]"):
            by_class.setdefault(cls, []).append(c[0])
        elif st == "[x]":
            closed += 1
    census = ["%s: %d unresolved (%s)" % (k, len(v), ", ".join(v))
              for k, v in sorted(by_class.items())]
    return census, closed


def main():
    try:
        import _engagement
        d = _engagement.active_dir()
    except Exception:
        return
    if not d:
        return
    # Always-on live capture: card any scan tmux tab that FINISHED since last turn into recon/.
    # Run it SYNCHRONOUSLY but BOUNDED (autocard caps itself to AUTOCARD_MAX tabs/run + per-SSH
    # timeout, so a run finishes in a few seconds, inside the hook's 10s budget). A detached spawn
    # was unreliable over the WSL/remote-VM SSH bridge - the grandchild often never ran, so cards
    # only showed up in one late batch at close-out instead of trickling in live. In-hook + capped
    # trades a couple of seconds at turn-end for deterministic live cards. Hard-bounded by timeout
    # so a dead VM can never hang the hook.
    try:
        import subprocess
        sc = os.path.join(_engagement.VAULT, "scripts", "autocard.sh")
        if os.path.isfile(sc):
            env = dict(os.environ, AUTOCARD_MAX=os.environ.get("AUTOCARD_MAX", "2"))
            # total budget 8s (> autocard's 5s per-SSH cap, < the harness 10s hook timeout);
            # the fast nudge logic below needs only sub-second, so it is never starved.
            # stdout is CAPTURED (pass 11): autocard's "RUNNING >45m" lines are the
            # wedged-scan signal the inflight surface below should see, not /dev/null.
            r = subprocess.run(["bash", sc, os.path.basename(d)],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               stdin=subprocess.DEVNULL, env=env, timeout=8)
            # persist UNCONDITIONALLY (pass 11): a clean run empties the file, so a
            # tab that recovered stops surfacing; stale wedged lines never accumulate.
            wedged = [ln for ln in (r.stdout or "").splitlines() if "RUNNING >45m" in ln]
            try:
                open(os.path.join(d, ".wedged-tabs"), "w", encoding="utf-8").write(
                    "".join(ln + "\n" for ln in wedged))
            except OSError:
                pass
    except Exception:
        pass
    if _approach_needs_review(d):
        print("APPROACH NEEDS-REVIEW - provenance block says needs-review: true; "
              "acknowledge in decisions.md (one line: 'approach reviewed <date>')")
    solved = _engagement.is_solved(d)
    suspended = (not solved) and _engagement.is_suspended(d)
    if not solved and not suspended:
        # During the box: state-discipline reflex. Loot captured but Killchain.md has no chain
        # rows -> nudge to write the attack path now, not at close-out. Deduped on the loot
        # row-count (a marker) so it re-fires only when a NEW finding lands, never every Stop.
        # Killchain.md is pentest/bugbounty-only; a ctf's live chain lives in state.md (## Chain),
        # so skip the nudge entirely for ctf engagements.
        gap = _engagement.paths_write_gap(d)
        if gap:
            marker = os.path.join(d, ".paths-nudged")
            last = 0
            try:
                last = int((open(marker).read().strip() or "0"))
            except Exception:
                last = 0
            if gap > last:
                # cheap-path fix: the nudge alone fired-and-was-ignored on every engagement
                # to date, so the draft rows are WRITTEN here automatically and the nudge
                # becomes "polish the drafts", not "author from blank"
                drafted = _engagement.append_draft_chain_rows(d)
                if drafted:
                    print("State-discipline: %d draft chain row(s) AUTO-APPENDED to "
                          "Killchain.md from loot.md. Polish them NOW (fill stage + next-move "
                          "per hop) so the chain persists across sessions." % drafted)
                else:
                    print("State-discipline: loot.md has %d finding(s) but Killchain.md has no chain "
                          "rows. Write the attack path NOW (one row per hop: what -> stage -> "
                          "status) so the chain persists across sessions -- do not defer it to "
                          "close-out." % gap)
                try:
                    open(marker, "w").write(str(gap))
                    import _telemetry
                    _telemetry.drift("close-out", "loot captured but Killchain.md empty (state discipline)")
                    _telemetry.hook("close-out", action="paths-nudge")
                except Exception:
                    pass
        # Cred-reuse reflex: several credentials captured, box not rooted, and no spray/reuse
        # line in Deadends.md -> a captured password is sitting unused. Deduped on the cred
        # row-count so it re-fires only when a NEW credential lands.
        creds = _engagement.unsprayed_cred_gap(d)
        if creds:
            cmarker = os.path.join(d, ".cred-spray-nudged")
            clast = 0
            try:
                clast = int((open(cmarker).read().strip() or "0"))
            except Exception:
                clast = 0
            if creds > clast:
                print("Cred-reuse: loot.md holds %d credential(s) and the box is not rooted, but "
                      "Deadends.md records no spray/reuse attempt. Try EVERY captured secret "
                      "against EVERY auth surface (ssh, su, the DB, the web login) BEFORE hunting "
                      "a new privesc vector -- and crack any hash you already hold. Log the "
                      "result to Deadends.md either way." % creds)
                try:
                    open(cmarker, "w").write(str(creds))
                    import _telemetry
                    _telemetry.drift("close-out", "credentials captured but never sprayed")
                    _telemetry.hook("close-out", action="cred-spray-nudge")
                except Exception:
                    pass
        # Deadends quality reflex: rows whose 'why exhausted' cell is a placeholder (or that
        # duplicate an earlier asset x class pair, or that leave the fail-class cell empty)
        # pass the anti-loop gate on shape but carry no signal -- the same vector gets
        # re-tested later. Deduped on the bad-row count.
        bad_rows = (_engagement.deadends_placeholder_rows(d)
                    + _engagement.deadends_unclassed_rows(d)
                    + _engagement.deadends_uncontrolled_rows(d))
        if bad_rows:
            dmarker = os.path.join(d, ".deadends-nudged")
            dlast = 0
            try:
                dlast = int((open(dmarker).read().strip() or "0"))
            except Exception:
                dlast = 0
            if bad_rows > dlast:
                print("Deadends quality: %d row(s) carry a placeholder 'why exhausted' cell, "
                      "duplicate an earlier asset x class pair, leave the fail-class cell "
                      "empty (type it: technical | environmental | conceptual | external), "
                      "or claim safety without naming the control ('safe because "
                      "<control> at <location>'). "
                      "A dead-end without a concrete "
                      "WHY is machine-read as exhaustible-but-unknown and gets re-tested later; "
                      "fill each 'why exhausted' cell (one sentence: what ruled it out) and drop "
                      "duplicates NOW." % bad_rows)
                try:
                    open(dmarker, "w").write(str(bad_rows))
                    import _telemetry
                    _telemetry.drift("close-out", "placeholder/duplicate/unclassed Deadends rows")
                    _telemetry.hook("close-out", action="deadends-quality-nudge")
                except Exception:
                    pass
        # Activity auto-synthesis (webserver-lab shape): every state file blank but poc/cmdlog
        # holds the whole work record -> draft an ## Activity block so the box carries SOMETHING
        # forward. Idempotent (quiet on the second Stop), never fires once loot/chain exist.
        if _engagement.append_activity_draft(d):
            print("Activity auto-draft: state files were blank while poc/cmdlog held the work; "
                  "drafted an ## Activity block into state.md (tools, counts, hosts). Polish it "
                  "into real state rows, or close the box with scripts/eng-close.py.")
        # Unmarked-close reflex (the close-out root cause): substance captured, NO '## STATUS:'
        # heading at all, last activity > 12h ago (the first Stop of a session after the box
        # was left mid-close-out). The entire close-out chain -- eval-metrics write, walkthrough
        # build, learn harvest -- keys on that marker; without it the box closes UNMEASURED
        # (every closed engagement to date has an empty eval.md for exactly this reason).
        # Deduped on the substance row-count, so it re-fires only when NEW substance lands.
        unmarked = _engagement.unmarked_close_gap(d)
        if unmarked:
            umarker = os.path.join(d, ".closeout-nudged")
            ulast = 0
            try:
                ulast = int((open(umarker).read().strip() or "0"))
            except Exception:
                ulast = 0
            if unmarked > ulast:
                print("Close-out UNMARKED: %d captured row(s) but state.md carries no "
                      "'## STATUS:' heading. Run `python3 scripts/eng-close.py SOLVED` now "
                      "(or `python3 scripts/eng-close.py SUSPEND` to park it) -- the "
                      "eval-metrics write, walkthrough build and learn harvest all key on "
                      "it; an unmarked box closes unmeasured." % unmarked)
                try:
                    open(umarker, "w").write(str(unmarked))
                    import _telemetry
                    _telemetry.drift("close-out", "substance captured but no STATUS marker "
                                                 "(box closes unmeasured)")
                    _telemetry.hook("close-out", action="unmarked-close-nudge")
                except Exception:
                    pass
        # In-flight surface (turn-end): the signals whose only other visibility is the
        # next SessionStart -- or nothing at all, for open lanes and a served move that
        # was never dispositioned.
        parts = inflight_signals(d)
        if parts:
            print("In flight at Stop: " + " | ".join(parts))
            try:
                import _telemetry
                _telemetry.hook("close-out", action="inflight-surface")
            except Exception:
                pass
        return
    # box is SOLVED (or SUSPENDED): stamp the finish time once (the far end of the start->finish delta)
    try:
        import _telemetry
        _telemetry.stamp_once("finished_at", _telemetry.now_iso(), d=d)
    except Exception:
        pass
    # nudges FIRST (pass 13 reorder): the STEP prints are the close-out chain's only
    # voice; they used to print AFTER two 15s subprocesses (eval transcript scan +
    # build), so a slow scan blew the hook's 10s budget and killed the chain silently.
    _stale = _engagement.walkthrough_stale(d)
    _pend = _engagement.learn_pending(d)
    if not _pend:
        # .learn-done is gameable by a bare touch: the eval-judgement gate lived only in
        # skill prose -> enforce in code (fresh marker + blank judgement = still pending).
        try:
            _ep = os.path.join(d, "eval.md")
            sys.path.insert(0, os.path.join(_engagement.VAULT, "scripts"))
            import eval_metrics
            _pend = not eval_metrics.judgement_filled(
                open(_ep, encoding="utf-8", errors="ignore").read()
                if os.path.isfile(_ep) else "")
        except Exception:
            pass
    if _stale:
        print("CLOSE-OUT (mandatory, auto-chain) [STEP 1/2]: engagement is SOLVED. Run "
              "Skill(walkthrough) NOW to draft the narrative (scaffold + Evidence gallery "
              "auto-build each Stop), THEN Skill(learn). This chain is not optional - a "
              "SOLVED box always runs walkthrough then learn before you end the session.")
    elif _pend:
        print("CLOSE-OUT (mandatory, auto-chain) [STEP 2/2]: walkthrough assembled -> run "
              "Skill(learn) NOW to EXTRACT DELTAS to wiki/ (the qmd-dedup -> stage -> "
              "promote harvest) + the harness retrospective. Not optional; every SOLVED "
              "box harvests its deltas automatically.")
    # finish_scan census (strix): unresolved classes reflected back at close, and the
    # chaining gate. Unresolved means UNEXAMINED-or-incomplete, never clean.
    if _stale or _pend:
        try:
            census, closed = _open_class_census(d)
            if census:
                print("Close-out census: %s; unresolved = unexamined/incomplete, NOT "
                      "clean; say so explicitly in the walkthrough." % "; ".join(census))
            if closed:
                print("Chaining gate: %d closed vector row(s); run the escalate-and-chain "
                      "check before the walkthrough (can any two findings combine into one "
                      "bigger impact, or one escalate to critical?)" % closed)
        except Exception:
            pass
    # fire the auto eval-metrics block once at close-out (SOLVED or SUSPEND -- a parked box is
    # still measured; observed live: a formally-suspended engagement closed with a blank eval).
    # Previously ONLY Skill(learn) Phase 0d ran eval_metrics, so a light close-out that skipped
    # learn produced no eval (observed live). Bounded subprocess, fail-open, once per engagement
    # (.eval-written marker); learn still re-runs it later.
    try:
        import subprocess
        em_marker = os.path.join(d, ".eval-written")
        em = os.path.join(_engagement.VAULT, "scripts", "eval_metrics.py")
        if not os.path.exists(em_marker) and os.path.isfile(em):
            r = subprocess.run(["python3", em, os.path.basename(d), "--write"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               stdin=subprocess.DEVNULL, timeout=15)
            # only mark done on success: a crashed eval marked done is never re-run
            if r.returncode == 0:
                open(em_marker, "w").close()
    except Exception:
        pass
    if not solved:
        return          # SUSPEND: measured and parked; walkthrough/learn resume when reopened
    # Flag-accounting reflex (ctf only): SOLVED but fewer flags recorded than flags_expected,
    # or flags_expected unset -> nudge the full-FS flag sweep. Prints first but does NOT return,
    # so the evidence/walkthrough/learn chain below still surfaces. Fires each Stop while unsatisfied
    # (same as the walkthrough/learn nudges); resolves the moment the flags are recorded.
    fg = _engagement.flag_accounting_gap(d)
    if fg:
        print("Flag accounting: " + fg)
        try:
            import _telemetry
            _telemetry.drift("close-out", "flags under-counted / flags_expected unset at SOLVED")
            _telemetry.hook("close-out", action="flag-accounting-nudge")
        except Exception:
            pass
    gaps = _engagement.web_evidence_gaps(d)
    if gaps:
        print("Close-out INCOMPLETE (web box marked SOLVED but evidence missing): "
              + "; ".join(gaps) + ". Capture these NOW so the operator can see/verify what was "
              "found -- do not consider the box done until status.py shows recon-card + source "
              "evidence.")
        return
    # Auto-build the walkthrough scaffold + Evidence gallery (idempotent, no-clobber: only the
    # ## Evidence section is refreshed, narrative bytes preserved). Same bounded/fail-open pattern
    # as the eval_metrics call above. This does the mechanical assembly so a SOLVED box always has
    # a started walkthrough.md; the narrative stubs remain, so walkthrough_stale below stays True
    # and the "draft the narrative" nudge still fires. Runs each SOLVED Stop (build is idempotent).
    try:
        import subprocess
        bw = os.path.join(_engagement.VAULT, "scripts", "build-walkthrough.py")
        if os.path.isfile(bw):
            subprocess.run(["python3", bw, os.path.basename(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, timeout=15)
    except Exception:
        pass
    # chain observability (pass 13): triage/evidence (pentest/bb) had NO done-artifact
    # check anywhere - half the printed chain was phantom steps a SOLVED box could skip
    # with zero signal. Cheap existence-grade gates only (find-lint/redaction stay in the
    # skills): triage = a FIND in Vulns/Completed/; evidence = poc/ non-empty.
    try:
        import json
        _et = (json.load(open(os.path.join(d, ".offensive.json"),
                              encoding="utf-8")).get("type") or "")
        if _et in ("pentest", "bugbounty"):
            _vc = os.path.join(d, "Vulns", "Completed")
            _tri = os.path.isdir(_vc) and any(
                f.endswith(".md") for f in os.listdir(_vc))
            _pd = os.path.join(d, "poc")
            _ev = os.path.isdir(_pd) and bool(os.listdir(_pd))
            print("Close-out chain [%s]: triage [%s] | evidence [%s] | walkthrough [%s] "
                  "| learn [%s]  (triage gate: FIND in Vulns/Completed/; evidence gate: "
                  "poc/ non-empty)" % (_et, "x" if _tri else " ",
                                       "x" if _ev else " ", "x" if not _stale else " ",
                                       "x" if not _pend else " "))
    except Exception:
        try:    # corrupt driver state silently drops the chain status line; record it
            if os.path.isfile(os.path.join(d, ".offensive.json")):
                import _telemetry
                _telemetry.log_event("hook", d=d, hook="close-out",
                                     error=".offensive.json unparseable - close-out chain line skipped")
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
