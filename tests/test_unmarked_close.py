"""Close-out root-cause fix: engagements finish but never get the ## STATUS marker, so the
whole auto-chain (eval metrics write, walkthrough build, learn harvest) never fires -- every
closed engagement so far has an empty eval.md. Tests: the unmarked-close detector, the Stop-hook
wiring, the SUSPEND close-out path, and the offensive.py init re-scaffold guard."""
import importlib.util
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "skills" / "hooks"))
_spec = importlib.util.spec_from_file_location(
    "_engagement", ROOT / "skills" / "hooks" / "_engagement.py")
_engagement = importlib.util.module_from_spec(_spec)
sys.modules["_engagement"] = _engagement
_spec.loader.exec_module(_engagement)


def _mk_eng(tmp_path, loot_rows=1, chain_rows=0, status=None, last_event_hours=None):
    d = tmp_path / "eng"
    d.mkdir(exist_ok=True)
    state = "# State\n"
    if chain_rows:
        state += "\n## Chain\n\n| what | how |\n|---|---|\n" + "| hop | x |\n" * chain_rows
    if status:
        state += "\n## STATUS: %s\n" % status
    (d / "state.md").write_text(state, encoding="utf-8")
    if loot_rows:
        (d / "loot.md").write_text(
            "| what | value |\n|---|---|\n" + "| cred | x |\n" * loot_rows, encoding="utf-8")
    if last_event_hours is not None:
        ts = (datetime.now(timezone.utc) - timedelta(hours=last_event_hours)).isoformat()
        (d / ".events.jsonl").write_text(
            json.dumps({"ts": ts, "kind": "tool"}) + "\n", encoding="utf-8")
    return str(d)


def test_gap_fires_on_idle_unmarked_substance(tmp_path):
    d = _mk_eng(tmp_path, loot_rows=2, last_event_hours=30)
    assert _engagement.unmarked_close_gap(d) >= 1


def test_gap_quiet_while_box_is_live(tmp_path):
    # recent telemetry (2h) -> mid-box, do not nag
    assert _engagement.unmarked_close_gap(_mk_eng(tmp_path, loot_rows=2, last_event_hours=2)) == 0


def test_gap_quiet_once_status_marked(tmp_path):
    # SOLVED or SUSPEND marker present -> handled by the solved/suspend chain, not this nudge
    assert _engagement.unmarked_close_gap(
        _mk_eng(tmp_path, loot_rows=2, status="SOLVED", last_event_hours=30)) == 0
    assert _engagement.unmarked_close_gap(
        _mk_eng(tmp_path, loot_rows=2, status="SUSPEND", last_event_hours=30)) == 0


def test_gap_quiet_without_substance(tmp_path):
    # fresh scaffold, nothing captured -> no nudge even if idle
    assert _engagement.unmarked_close_gap(_mk_eng(tmp_path, loot_rows=0, last_event_hours=30)) == 0


def test_gap_ctf_chain_counts_as_substance(tmp_path):
    # a ctf keeps its live chain in state.md ## Chain (no loot.md); chain rows are substance
    assert _engagement.unmarked_close_gap(
        _mk_eng(tmp_path, loot_rows=0, chain_rows=1, last_event_hours=30)) >= 1


def test_hook_wires_the_nudge_and_suspend():
    src = (ROOT / "skills" / "hooks" / "close-out.py").read_text(encoding="utf-8")
    # the unmarked-close nudge is wired in the not-solved branch and names the exact action
    assert "unmarked_close_gap" in src and "## STATUS" in src
    assert "SUSPEND" in src and "unmarked" in src.lower()
    # a SUSPEND close-out still writes the eval metrics block (measured even when parked)
    assert src.index("SUSPEND") < src.index("eval_metrics.py")


def test_offensive_init_refuses_live_dir_without_rebase(tmp_path):
    eng = tmp_path / "targets" / "livebox"
    eng.mkdir(parents=True)
    (eng / "state.md").write_text("# live state, do not clobber\n", encoding="utf-8")
    (eng / ".offensive.json").write_text('{"type": "ctf", "pass": 2}', encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "offensive.py"),
         "--vault", str(tmp_path), "init", "livebox", "--type", "ctf"],
        capture_output=True, text=True, timeout=60)
    assert r.returncode != 0, "init must refuse a dir holding live driver state"
    assert "rebase" in (r.stdout + r.stderr).lower()
    assert '"pass": 2' in (eng / ".offensive.json").read_text()
    # --rebase proceeds without touching the live state file, but repoints active.md
    r2 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "offensive.py"),
         "--vault", str(tmp_path), "init", "livebox", "--type", "ctf", "--rebase"],
        capture_output=True, text=True, timeout=60)
    assert r2.returncode == 0
    assert '"pass": 2' in (eng / ".offensive.json").read_text()
    assert (tmp_path / "targets" / "active.md").read_text().strip() == "livebox"


def test_offensive_init_allows_scaffolded_dir_adding_driver_state(tmp_path):
    # the new-engagement.sh flow: dir holds scaffolded .md files, no .offensive.json yet --
    # init ADDS driver state (fill-missing templates only), must stay allowed
    eng = tmp_path / "targets" / "fresh"
    eng.mkdir(parents=True)
    (eng / "state.md").write_text("# scaffolded\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "offensive.py"),
         "--vault", str(tmp_path), "init", "fresh", "--type", "ctf"],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (r.stdout + r.stderr)
    assert (eng / ".offensive.json").is_file()
    assert "# scaffolded" in (eng / "state.md").read_text()   # not clobbered
