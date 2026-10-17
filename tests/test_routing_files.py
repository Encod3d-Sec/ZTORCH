"""check-routing.py: routing data files are valid (insurance + catch test)."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_routing", ROOT / "scripts" / "check-routing.py")
check_routing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_routing)


def test_current_routing_files_clean():
    """The committed playbook/chains/tells/triggers/coverage pass every check."""
    assert check_routing.violations() == []


def test_catches_chain_drift(tmp_path):
    """A bad chains edge (unknown to_class, non-scalar skill) is reported."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "skills" / "exploit" / "hunt").mkdir(parents=True)
    (tmp_path / "wiki").mkdir()
    (tmp_path / "scripts" / "playbook.json").write_text('{"fingerprints": {}}')
    (tmp_path / "scripts" / "coverage-classes.json").write_text(
        '{"_comment": "", "ctf": ["rce"]}')
    (tmp_path / "scripts" / "tells.json").write_text('{"_doc": "", "tells": []}')
    (tmp_path / "skills" / "exploit" / "hunt" / "triggers.json").write_text(
        '{"triggers": {}, "surface_triggers": {}}')
    (tmp_path / "scripts" / "chains.json").write_text(json.dumps({"edges": {
        "ssrf": {"then": [{"move": "x", "to_class": "not-a-class",
                           "skill": ["hunt-ssrf"], "gain": 1, "likelihood": 0.5}]}}}))
    msgs = [m for _, m in check_routing.violations(str(tmp_path))]
    assert any("to_class" in m for m in msgs)
    assert any("SCALAR" in m for m in msgs)
