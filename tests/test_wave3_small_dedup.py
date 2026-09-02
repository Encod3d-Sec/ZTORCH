"""W2-5: close-out.py re-checked engagement_type(d)=="ctf" before calling paths_write_gap(),
which already returns 0 for ctf internally -- a no-op ternary. W2-6: _telemetry.stamp() (the
overwrite variant) has zero callers anywhere in the repo. W2-11: offensive.py's seed_4b()
re-implemented _next_board_id()'s max-id-scan loop inline with a hardcoded "4b:" pattern instead
of parameterizing the existing helper."""
import importlib.util
import os
import subprocess
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(VAULT, "scripts"))
import offensive  # noqa: E402


def test_next_board_id_takes_prefix_param():
    rows = [{"id": "4a:3"}, {"id": "4b:7"}, {"id": "4a:1"}]
    assert offensive._next_board_id(rows, prefix="4a") == 3
    assert offensive._next_board_id(rows, prefix="4b") == 7
    assert offensive._next_board_id(rows) == 3  # default stays "4a", unchanged call sites work


def test_next_board_id_no_matches():
    assert offensive._next_board_id([], prefix="4b") == 0


def test_closeout_hook_no_redundant_ctf_ternary():
    src = (VAULT + "/skills/hooks/close-out.py")
    text = open(src).read()
    assert 'None if _engagement.engagement_type(d) == "ctf" else' not in text


def test_telemetry_dead_stamp_removed():
    src = (VAULT + "/skills/hooks/_telemetry.py")
    text = open(src).read()
    assert "\ndef stamp(" not in text, "dead stamp() (zero callers) should be deleted"
    assert "\ndef stamp_once(" in text, "stamp_once (the used variant) must remain"
