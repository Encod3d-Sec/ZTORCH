"""Close-out Stop hook must auto-chain walkthrough THEN learn as a MANDATORY directive
(not an optional nudge) when a box is SOLVED, so delta-extraction to wiki always fires."""
import pathlib, re

HOOK = pathlib.Path(__file__).resolve().parent.parent / "skills/hooks/close-out.py"


def test_closeout_emits_mandatory_walkthrough_then_learn():
    src = HOOK.read_text()
    # STEP 1/2: walkthrough directive, mandatory, points at learn next
    assert "STEP 1/2" in src and "Skill(walkthrough)" in src
    # STEP 2/2: learn directive, mandatory, names the delta-extraction to wiki
    assert "STEP 2/2" in src and "Skill(learn)" in src
    assert "EXTRACT DELTAS" in src.upper()
    # both steps assert non-optionality
    assert src.count("mandatory") >= 2 or src.upper().count("NOT OPTIONAL") >= 1
    # order: the walkthrough (step 1) branch precedes the learn (step 2) branch in the source
    assert src.index("STEP 1/2") < src.index("STEP 2/2")
    # the old purely-advisory phrasing is gone
    assert "learn harvest still due. Run Skill(learn)" not in src


def test_closeout_chain_gated_on_walkthrough_first():
    """The learn branch is an `elif` of walkthrough_stale -> walkthrough must complete first."""
    src = HOOK.read_text()
    # pass 13: both gates are computed once up front (before the slow subprocesses);
    # the branch stays walkthrough-then-learn via if/elif.
    assert src.index("_stale = _engagement.walkthrough_stale(d)") < \
        src.index("_pend = _engagement.learn_pending(d)")
    s1 = src.index("STEP 1/2")
    assert s1 < src.index("STEP 2/2")
    assert "elif _pend" in src[s1:]                       # learn only after walkthrough


def test_closeout_nudges_print_before_the_slow_subprocesses():
    """pass 13 reorder: the STEP prints are the chain's only voice and used to run
    AFTER two 15s subprocesses, so a slow one blew the hook's 10s budget and killed
    the chain silently. Source order must keep them first."""
    src = HOOK.read_text()
    assert src.index("STEP 1/2") < src.index("--write")
    assert "judgement_filled" in src      # .learn-done alone no longer clears learn


def test_closeout_lane_overclaim_sweep(tmp_path):
    """pass 13: a CLOSED lane whose SUCCESS criterion is absent from its capture is an
    over-claim that already poisoned loot/Killchain; the Stop hook must surface it
    (deduped on the bad-count marker so it re-fires only on a NEW bad lane)."""
    import json, os, subprocess, sys
    vault = tmp_path / "vault"
    eng = vault / "targets" / "eng1"
    (eng / "poc" / "b").mkdir(parents=True)
    (eng / "poc" / "b" / "out.txt").write_text("nothing here\n", encoding="utf-8")
    (eng / "log.md").write_text(
        "- lane b (10.0.0.9) in flight: SUCCESS = THM{zzz} | tmux win w1 | "
        "capture poc/b -> claim: rooted\n", encoding="utf-8")
    (vault / "targets" / "active.md").write_text("eng1\n", encoding="utf-8")
    env = dict(os.environ, ZTORCH_VAULT=str(vault),
               ENFORCE_OFF_MARKER=str(vault / ".no-enforce-off"))
    run = lambda: subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(
            {"session_id": "t", "transcript_path": "/nonexistent.jsonl"}),
        capture_output=True, text=True, timeout=60, env=env).stdout
    out1 = run()
    assert "lane NOT VERIFIED (over-claim): b" in out1
    # marker deduped: identical bad-count on the next Stop stays silent
    out2 = run()
    assert "lane NOT VERIFIED" not in out2
    # a SECOND bad lane raises the bad-count -> re-fires
    with open(eng / "log.md", "a", encoding="utf-8") as fh:
        fh.write("- lane z (10.0.0.9) in flight: SUCCESS = THM{qqq} | tmux win w2 | "
                 "capture poc/z -> claim: rooted\n")
    (eng / "poc" / "z").mkdir()
    (eng / "poc" / "z" / "out.txt").write_text("nope\n", encoding="utf-8")
    out3 = run()
    assert "lane NOT VERIFIED" in out3 and "b" in out3.split("over-claim")[1][:60]


def test_closeout_vault_spelled_capture_not_flagged(tmp_path):
    """comms review defect 1 (the 27/27 false-flag): close-out joined the capture
    cell its own way, without lane_validate._cap_dir's vault-prefix strip, so an
    honest lane whose capture dir is vault-spelled (`capture targets/<eng>/poc/x`,
    criterion verifiably on disk) was flagged NOT VERIFIED. Resolution must be the
    shared _cap_dir."""
    import json, os, subprocess, sys
    vault = tmp_path / "vault"
    eng = vault / "targets" / "eng1"
    (eng / "poc" / "x").mkdir(parents=True)
    (eng / "poc" / "x" / "out.txt").write_text("flag THM{zzz} captured\n", encoding="utf-8")
    (eng / "log.md").write_text(
        "- lane x (10.0.0.9) in flight: SUCCESS = THM{zzz} | tmux win w1 | "
        "capture targets/eng1/poc/x -> claim: rooted\n", encoding="utf-8")
    (vault / "targets" / "active.md").write_text("eng1\n", encoding="utf-8")
    env = dict(os.environ, ZTORCH_VAULT=str(vault),
               ENFORCE_OFF_MARKER=str(vault / ".no-enforce-off"))
    r = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(
            {"session_id": "t", "transcript_path": "/nonexistent.jsonl"}),
        capture_output=True, text=True, timeout=60, env=env)
    assert "NOT VERIFIED" not in r.stdout      # honest lane, criterion on disk
    assert not (eng / ".lane-verify-nudged").exists()   # and no poisoned dedup counter
