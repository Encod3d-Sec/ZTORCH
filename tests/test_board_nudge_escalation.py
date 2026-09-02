"""Wave 7 W7-2 (defense in depth): the BOARD NOT BUILT nudge used to fire exactly once per
engagement (a marker file); a box that ignored it under momentum got zero further tracking.
Escalate to the same capped-counter shape recon-completeness/web-evidence already use in this
file (fire up to _BOARD_NUDGE_CAP times, not once)."""
import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "recon_capture", os.path.join(VAULT, "skills", "hooks", "recon-capture.py"))
recon_capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recon_capture)


def _stub_approach(d):
    (d / "Approach.md").write_text("# Approach\n\n### 4a. Coverage matrix\n\n"
                                    "| id | asset |\n|---|---|\n")


def test_board_nudge_fires_up_to_cap_then_stops(tmp_path):
    _stub_approach(tmp_path)
    d = str(tmp_path)
    fires = [recon_capture._board_nudge(d) for _ in range(recon_capture._BOARD_NUDGE_CAP + 2)]
    non_none = [f for f in fires if f is not None]
    assert len(non_none) == recon_capture._BOARD_NUDGE_CAP


def test_board_nudge_none_when_board_populated(tmp_path):
    (tmp_path / "Approach.md").write_text("# Approach\n\n- [ ] 1. Recon\n")
    assert recon_capture._board_nudge(str(tmp_path)) is None
