"""F-GO1 (pass 14): the pre-edit checkpoint hook. A Write/Edit under targets/<eng>/
must shadow-commit the PRE-edit state via offensive._ckpt before the edit lands;
files outside targets/ and dirs without driver state must create nothing."""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "skills" / "hooks" / "eng-ckpt.py"


def _run(payload):
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30)


def test_write_under_engagement_checkpoints_prior_state(tmp_path):
    t = tmp_path / "targets" / "engA"
    t.mkdir(parents=True)
    (t / ".offensive.json").write_text('{"type": "pentest"}', encoding="utf-8")
    (t / "state.md").write_text("PRE-EDIT CONTENT", encoding="utf-8")
    r = _run({"tool_name": "Write",
              "tool_input": {"file_path": str(t / "state.md"), "content": "x"}})
    assert r.returncode == 0 and r.stdout == ""      # silent allow, always
    log = subprocess.run(["git", "-C", str(t), "log", "--oneline"],
                         capture_output=True, text=True).stdout
    assert "pre-edit state.md" in log
    blob = subprocess.run(["git", "-C", str(t), "show", "HEAD:state.md"],
                          capture_output=True, text=True).stdout
    assert blob == "PRE-EDIT CONTENT"                # the checkpoint is PRE-edit


def test_non_targets_and_non_engagement_paths_are_silent(tmp_path):
    outside = tmp_path / "wiki" / "page.md"
    outside.parent.mkdir()
    outside.write_text("x", encoding="utf-8")
    plain = tmp_path / "targets" / "notes"
    plain.mkdir(parents=True)
    plain_file = plain / "junk.md"
    plain_file.write_text("x", encoding="utf-8")
    for fp in (outside, plain_file):
        r = _run({"tool_name": "Edit",
                  "tool_input": {"file_path": str(fp), "old_string": "x",
                                 "new_string": "y"}})
        assert r.returncode == 0 and r.stdout == ""
        assert not (fp.parent / ".git").exists()     # no repo created
