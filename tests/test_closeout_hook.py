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
    w = src.index("walkthrough_stale(d)")
    l = src.index("learn_pending(d)")
    assert w < l  # walkthrough gate evaluated before learn gate
    # learn is under elif (only after walkthrough assembled)
    seg = src[w:l]
    assert "elif" in src[src.index("STEP 1/2"):l]
