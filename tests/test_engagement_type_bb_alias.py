"""W2-10: offensive.py writes .offensive.json's "type" as "bb" (its own CLI vocabulary), but
_engagement.TYPES only recognized the full word "bugbounty" -- so engagement_type() silently
mis-resolved every bug-bounty engagement to "pentest". This is the regression test for the fix."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "hooks"))

import _engagement  # noqa: E402


def test_offensive_json_bb_resolves_to_bugbounty(tmp_path):
    eng = tmp_path / "demo"
    eng.mkdir()
    (eng / ".offensive.json").write_text(json.dumps({"type": "bb"}))
    assert _engagement.engagement_type(eng) == "bugbounty"


def test_offensive_json_bugbounty_still_resolves(tmp_path):
    """The full word must keep working unchanged (no regression on the existing behavior)."""
    eng = tmp_path / "demo"
    eng.mkdir()
    (eng / ".offensive.json").write_text(json.dumps({"type": "bugbounty"}))
    assert _engagement.engagement_type(eng) == "bugbounty"


def test_offensive_json_pentest_and_ctf_unaffected(tmp_path):
    for t in ("pentest", "ctf"):
        eng = tmp_path / t
        eng.mkdir()
        (eng / ".offensive.json").write_text(json.dumps({"type": t}))
        assert _engagement.engagement_type(eng) == t
