"""Tests for offensive.py `init` (engagement scaffold)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive  # noqa: E402

TEMPLATE_FILES = ("state.md", "scope.md", "Deadends.md", "loot.md",
                   "Killchain.md", "oob.md", "decisions.md")


def test_init_scaffolds_files_and_state(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    rc = offensive.main(["--vault", str(vault), "init", "demo", "--type", "pentest"])
    assert rc == 0

    eng = vault / "targets" / "demo"
    for name in TEMPLATE_FILES:
        assert (eng / name).exists(), name

    state = json.loads((eng / ".offensive.json").read_text())
    assert state["type"] == "pentest"
    assert state["pass"] == 0
    assert state["asset_cursor"] is None
    assert state["dry_streak"] == 0
    assert state["cmd_ledger"] == {}
    assert state["req_count"] == 0
    assert state["foothold"] is False
    assert "started_at" in state and state["started_at"]
