"""Lane-contract pins: brain/delegate skill text must keep the fleet rules
(frozen shared prefix, return envelope, read-first mandate, few-long-lanes)."""
import pathlib

VT = pathlib.Path(__file__).resolve().parents[1]
BRAIN = VT / "skills" / "workflow" / "brain" / "SKILL.md"
DELEGATE = VT / "skills" / "workflow" / "exec" / "delegate" / "SKILL.md"


def test_brain_fleet_rules():
    t = BRAIN.read_text(encoding="utf-8")
    assert "Frozen shared prefix" in t
    assert "Few long lanes" in t
    assert "never poll a running lane" in t


def test_brain_return_envelope():
    t = BRAIN.read_text(encoding="utf-8")
    for label in ("Scope", "Result", "Key files", "Issues"):
        assert label in t, label


def test_delegate_envelope_and_read_first():
    t = DELEGATE.read_text(encoding="utf-8")
    for label in ("Scope", "Result", "Key files", "Issues"):
        assert label in t, label
    assert "cat each file in full, zg/grep only to locate" in t


def test_dispatch_hygiene_tokens():
    for path in (BRAIN, DELEGATE):
        t = path.read_text(encoding="utf-8")
        for token in (
            "15 lines or fewer",
            "never spawns its own subagent",
            "model:",
            "cost metric is turn count",
            "one brief enumerating every item",
            "a listed item with no capture is a Missing finding",
        ):
            assert token in t, (path.name, token)


def test_verifier_contract_tokens():
    t = DELEGATE.read_text(encoding="utf-8")
    for token in (
        "read ONLY the package file",
        "NOT CONFIRMED",
        "UNVERIFIABLE",
        "would this pass on a wrong result",
        "attempted is not addressed",
    ):
        assert token in t, token
    b = BRAIN.read_text(encoding="utf-8")
    assert "package file only" in b


def test_supervision_tokens():
    t = BRAIN.read_text(encoding="utf-8")
    assert "no rows is not a scan" in t
    assert "finished without reporting" in t
    assert "never poll" not in t.replace("never poll a running lane", "")


def test_browser_evidence_tokens():
    for path in (
        VT / "skills" / "workflow" / "env" / "chrome-devtools-browser" / "SKILL.md",
        VT / "skills" / "hunt" / "hunt-xss" / "SKILL.md",
    ):
        t = path.read_text(encoding="utf-8").lower()
        assert "console listener" in t or "console capture" in t, path
        assert "networkidle" in t, path


def test_review_focus_and_harness_stops():
    hc = (VT / "skills" / "hunt" / "hunt-core" / "SKILL.md").read_text(encoding="utf-8")
    assert "no board row exercises" in hc
    ag = (VT / "AGENTS.md").read_text(encoding="utf-8")
    assert "architecture stop" in ag
    assert "component boundaries" in ag


if __name__ == "__main__":
    test_brain_fleet_rules()
    test_brain_return_envelope()
    test_delegate_envelope_and_read_first()
    test_dispatch_hygiene_tokens()
    test_verifier_contract_tokens()
    test_supervision_tokens()
    test_browser_evidence_tokens()
    test_review_focus_and_harness_stops()
    print("test_lane_contract: OK")
