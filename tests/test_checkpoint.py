"""checkpoint.py (hermes port design 1): shadow-git snapshots of an engagement dir.
Covers snapshot->modify->restore roundtrip, list output, prune-by-count,
restore-conflict refusal, the 3-consecutive-failure repair-ledger refusal, and
the vault git-status-clean invariant (the store must never leak into it).
Fixtures are synthetic tempdir vaults; no live engagement data."""
import importlib.util
import json
import os
import re
import shutil
import subprocess

import pytest

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "checkpoint", os.path.join(VAULT, "scripts", "checkpoint.py"))
cp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cp)

requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not installed")


def _mk_vault(tmp_path, monkeypatch):
    """A VAULT-shaped synthetic fixture: git repo + ignored targets/test-eng/."""
    v = tmp_path / "vault"
    eng = v / "targets" / "test-eng"
    eng.mkdir(parents=True)
    (v / ".gitignore").write_text("targets/*\n", encoding="utf-8")
    (eng / "state.md").write_text("state v1\n", encoding="utf-8")
    (eng / "loot.md").write_text("loot v1\n", encoding="utf-8")
    ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(v)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(v)] + ident + ["add", ".gitignore"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(v)] + ident + ["commit", "-q", "-m", "fixture"],
                   check=True, capture_output=True)
    monkeypatch.setattr(cp, "VAULT", str(v))
    return v, eng


def _ids(v):
    return cp._snap_ids(os.path.join(str(v), cp.STORE_NAME), "test-eng")


def _ledger(v):
    return os.path.join(str(v), cp.STORE_NAME, cp.LEDGER)


@requires_git
def test_snapshot_modify_restore_roundtrip(tmp_path, monkeypatch):
    v, eng = _mk_vault(tmp_path, monkeypatch)
    assert cp.main(["snapshot", "test-eng", "pre-nuke"]) == 0
    (eng / "state.md").write_text("state v2 CLOBBERED\n", encoding="utf-8")
    (eng / "loot.md").unlink()
    assert cp.main(["restore", "test-eng", _ids(v)[0], "--force"]) == 0
    assert (eng / "state.md").read_text(encoding="utf-8") == "state v1\n"
    assert (eng / "loot.md").read_text(encoding="utf-8") == "loot v1\n"


@requires_git
def test_list_shows_ids_labels_and_delta(tmp_path, monkeypatch, capsys):
    v, eng = _mk_vault(tmp_path, monkeypatch)
    cp.main(["snapshot", "test-eng", "pre"])
    (eng / "notes.md").write_text("new\n", encoding="utf-8")
    cp.main(["snapshot", "test-eng", "post"])
    assert cp.main(["list", "test-eng"]) == 0
    out = capsys.readouterr().out
    assert "-pre" in out and "-post" in out
    assert re.search(r"2 files$", out, re.MULTILINE)          # root snapshot
    assert "1 files changed since previous" in out            # post adds notes.md


@requires_git
def test_prune_keeps_last_n(tmp_path, monkeypatch):
    v, eng = _mk_vault(tmp_path, monkeypatch)
    for i in range(7):
        (eng / ("f%d.md" % i)).write_text("x\n", encoding="utf-8")
        assert cp.main(["snapshot", "test-eng", "s%d" % i]) == 0
    assert len(_ids(v)) == 7
    assert cp.main(["prune", "test-eng", "--keep", "3"]) == 0
    ids = _ids(v)
    assert len(ids) == 3
    assert ids[0].endswith("-s4") and ids[-1].endswith("-s6")  # newest survive


@requires_git
def test_restore_refuses_on_conflict_without_force(tmp_path, monkeypatch, capsys):
    v, eng = _mk_vault(tmp_path, monkeypatch)
    cp.main(["snapshot", "test-eng", "pre"])
    (eng / "state.md").write_text("dirty\n", encoding="utf-8")
    capsys.readouterr()
    assert cp.main(["restore", "test-eng", _ids(v)[0]]) == 1
    out = capsys.readouterr().out
    assert "state.md" in out and "--force" in out
    assert (eng / "state.md").read_text(encoding="utf-8") == "dirty\n"  # not clobbered


@requires_git
def test_ledger_refuses_after_three_consecutive_failures(tmp_path, monkeypatch, capsys):
    v, eng = _mk_vault(tmp_path, monkeypatch)
    cp.main(["snapshot", "test-eng", "pre"])
    sid = _ids(v)[0]
    with open(_ledger(v), "w", encoding="utf-8") as f:
        for i in range(3):
            f.write(json.dumps({"eng": "test-eng", "id": sid, "ok": False,
                                "fingerprint": "f%d" % i}) + "\n")
    capsys.readouterr()
    assert cp.main(["restore", "test-eng", sid, "--force"]) == 1
    assert "refusing" in capsys.readouterr().out
    # a success resets the streak: 2 fails, 1 ok, 2 fails -> still allowed
    with open(_ledger(v), "w", encoding="utf-8") as f:
        for ok in (False, False, True, False, False):
            f.write(json.dumps({"eng": "test-eng", "id": sid, "ok": ok,
                                "fingerprint": "f"}) + "\n")
    assert cp.main(["restore", "test-eng", sid, "--force"]) == 0


@requires_git
def test_failed_restore_appends_fingerprint(tmp_path, monkeypatch):
    v, eng = _mk_vault(tmp_path, monkeypatch)
    cp.main(["snapshot", "test-eng", "pre"])
    sid = _ids(v)[0]
    real = cp._git

    def failing(store, work, index, *args):
        if "checkout-index" in args:
            class R:
                returncode, stdout, stderr = 1, "", "synthetic checkout failure"
            return R()
        return real(store, work, index, *args)

    monkeypatch.setattr(cp, "_git", failing)
    assert cp.main(["restore", "test-eng", sid, "--force"]) == 1
    d = json.loads(open(_ledger(v), encoding="utf-8").read().splitlines()[-1])
    assert d["ok"] is False and d["id"] == sid and d["fingerprint"]


@requires_git
def test_vault_git_status_stays_clean(tmp_path, monkeypatch):
    v, eng = _mk_vault(tmp_path, monkeypatch)
    assert cp.main(["snapshot", "test-eng", "pre"]) == 0
    (eng / "state.md").write_text("v2\n", encoding="utf-8")
    assert cp.main(["restore", "test-eng", _ids(v)[0], "--force"]) == 0
    assert cp.main(["prune", "test-eng", "--keep", "1"]) == 0
    assert os.path.isdir(os.path.join(str(v), cp.STORE_NAME))    # store really used
    r = subprocess.run(["git", "-C", str(v), "status", "--porcelain"],
                       capture_output=True, text=True)
    assert r.stdout.strip() == ""     # no leak: neither store nor targets show up
