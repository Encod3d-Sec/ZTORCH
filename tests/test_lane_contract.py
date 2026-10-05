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


if __name__ == "__main__":
    test_brain_fleet_rules()
    test_brain_return_envelope()
    test_delegate_envelope_and_read_first()
    test_dispatch_hygiene_tokens()
    test_verifier_contract_tokens()
    print("test_lane_contract: OK")
