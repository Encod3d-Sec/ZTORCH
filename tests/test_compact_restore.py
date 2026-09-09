"""Pass 1 (host-internals): SessionStart(compact) re-injection. Post-compact the context
holds the summary plus capped attachments; engagement-init's source=="compact" branch
additionally re-injects the open Approach.md rows VERBATIM -- the board is the one
artifact the next context must hold exactly, because offensive.py re-ranks from it. A
plain startup fire must NOT carry the duplicate."""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "skills" / "hooks" / "engagement-init.py"
ROW = "- [ ] rustscan + nmap -sCV all hosts        -> [[wiki/tools/rustscan]]"


def _mk(tmp_path):
    t = tmp_path / "targets" / "engc"
    t.mkdir(parents=True, exist_ok=True)
    (t / "Approach.md").write_text(
        "| step | class | tool | status | notes |\n|---|---|---|---|---|\n" + ROW + "\n",
        encoding="utf-8")
    (tmp_path / "targets" / "active.md").write_text("engc\n", encoding="utf-8")
    return tmp_path


def _run(vault, source):
    env = dict(os.environ, ZTORCH_VAULT=str(vault))
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"source": source}),
                          capture_output=True, text=True, timeout=120, env=env)


def test_compact_reinjects_open_rows_verbatim(tmp_path):
    r = _run(_mk(tmp_path), "compact")
    assert ROW in r.stdout


def test_startup_does_not_reinject_board(tmp_path):
    r = _run(_mk(tmp_path), "startup")
    assert "restored post-compact" not in r.stdout
