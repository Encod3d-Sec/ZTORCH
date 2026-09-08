"""eng-close.py: the close-out marker's last manual step was "edit state.md by hand" -- a step
skipped on every engagement to date. The cheap-path fix: ONE command appends the ## STATUS
marker (the thing the eval-metrics write, walkthrough build and learn harvest all key on)."""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "eng-close.py"


def _mk_vault(tmp_path, state="# State\n| target | service |\n|---|---|\n| box | http |"):
    t = tmp_path / "targets" / "engx"
    t.mkdir(parents=True, exist_ok=True)
    (t / "state.md").write_text(state, encoding="utf-8")
    (tmp_path / "targets" / "active.md").write_text("engx\n", encoding="utf-8")
    return tmp_path


def _run(vault, *args):
    env = dict(os.environ, ZTORCH_VAULT=str(vault))
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, timeout=30, env=env)


def test_appends_status_marker_to_active_engagement(tmp_path):
    v = _mk_vault(tmp_path)
    r = _run(v, "SOLVED")
    assert r.returncode == 0, (r.stdout + r.stderr)
    assert "## STATUS: SOLVED" in (v / "targets" / "engx" / "state.md").read_text()


def test_accepts_suspend_and_owned_forms(tmp_path):
    for st in ("SUSPEND", "OWNED", "ROOTED", "COMPLETE"):
        v = _mk_vault(tmp_path)
        r = _run(v, st)
        assert r.returncode == 0, st
        assert ("## STATUS: %s" % st) in (v / "targets" / "engx" / "state.md").read_text()


def test_refuses_unknown_status(tmp_path):
    v = _mk_vault(tmp_path)
    r = _run(v, "DONE-FOREVER")
    assert r.returncode != 0
    assert "STATUS" not in (v / "targets" / "engx" / "state.md").read_text()


def test_idempotent_once_any_status_exists(tmp_path):
    v = _mk_vault(tmp_path, state="# State\n\n## STATUS: SOLVED\n")
    r = _run(v, "SUSPEND")
    assert r.returncode != 0
    txt = (v / "targets" / "engx" / "state.md").read_text()
    assert txt.count("## STATUS") == 1 and "SOLVED" in txt


def test_named_engagement_overrides_active(tmp_path):
    t = tmp_path / "targets" / "other"
    t.mkdir(parents=True)
    (t / "state.md").write_text("# other\n", encoding="utf-8")
    v = _mk_vault(tmp_path)
    r = _run(v, "SUSPEND", "other")
    assert r.returncode == 0, (r.stdout + r.stderr)
    assert "## STATUS: SUSPEND" in (t / "state.md").read_text()
    assert "STATUS" not in (v / "targets" / "engx" / "state.md").read_text()


def test_closeout_nudge_carries_the_command():
    src = (ROOT / "skills" / "hooks" / "close-out.py").read_text(encoding="utf-8")
    assert "eng-close.py" in src, "the unmarked-close nudge must name the one-liner, not hand-editing"
