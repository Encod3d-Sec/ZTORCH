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


def _mk(tmp_path, last_move=None, ingest_files=0):
    t = tmp_path / "targets" / "engc"
    t.mkdir(parents=True, exist_ok=True)
    (t / "Approach.md").write_text(
        "| step | class | tool | status | notes |\n|---|---|---|---|---|\n" + ROW + "\n",
        encoding="utf-8")
    st = {"type": "pentest", "pass": 6, "asset_cursor": "web1", "last_move": last_move}
    (t / ".offensive.json").write_text(json.dumps(st), encoding="utf-8")
    if ingest_files:
        (t / "ingest").mkdir(exist_ok=True)
        for i in range(ingest_files):
            (t / "ingest" / ("raw%d.txt" % i)).write_text("x", encoding="utf-8")
    (tmp_path / "targets" / "active.md").write_text("engc\n", encoding="utf-8")
    return tmp_path


def _run(vault, source):
    env = dict(os.environ, ZTORCH_VAULT=str(vault))
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"source": source}),
                          capture_output=True, text=True, timeout=120, env=env)


def test_compact_reinjects_open_rows_verbatim(tmp_path):
    r = _run(_mk(tmp_path), "compact")
    assert ROW in r.stdout


def test_compact_reinjects_last_move(tmp_path):
    lm = {"ts": "2026-09-09T10:00:00+00:00", "asset": "web1", "row": "4a:2",
          "class": "ssrf", "skill": "hunt-ssrf", "tool": "nuclei"}
    r = _run(_mk(tmp_path, last_move=lm), "compact")
    assert "driver last move (2026-09-09T10:00:00+00:00)" in r.stdout
    assert "row 4a:2 ssrf -> Skill(hunt-ssrf) / nuclei" in r.stdout


def test_startup_does_not_reinject_board(tmp_path):
    r = _run(_mk(tmp_path), "startup")
    assert "restored post-compact" not in r.stdout


def test_pending_ingest_surfaced(tmp_path):
    """A mid-ingest compaction/restart used to lose the fact an ingest was in flight;
    SessionStart now counts non-archived files under ingest/ (re-runs are idempotent)."""
    r = _run(_mk(tmp_path, ingest_files=2), "startup")
    assert "ingest pending: 2 file(s)" in r.stdout


def test_no_ingest_line_when_clean(tmp_path):
    r = _run(_mk(tmp_path, ingest_files=0), "startup")
    assert "ingest pending" not in r.stdout
