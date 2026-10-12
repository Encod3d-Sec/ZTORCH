"""Tests for the P1/P4/P5 delegation ports (docs/port-specs/proposals-delegation.md):
lane envelope schema (scripts/lane_envelope.py + lane_validate.py --envelope),
manifest window_m/budget cells (scripts/lane_manifest.py), worktree isolation
(scripts/lane_worktree.py).

Standalone: plain `python3 tests/test_lane_envelope.py` (no docker needed;
plain asserts, failures raise; also collects under pytest). Worktree tests
skip when git is unavailable.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import lane_envelope as le   # noqa: E402
import lane_manifest as lm   # noqa: E402
import lane_validate as lv   # noqa: E402
import lane_worktree as lw   # noqa: E402

ENVELOPE_PY = ROOT / "scripts" / "lane_envelope.py"
GOOD = {
    "scope": "sqli confirm on param id",
    "result": {"verdict": "success: union-based sqli confirmed",
               "success_observable_raw": "uid=33(www-data)"},
    "key_files": ["poc/lane-x/sqli.txt"],
    "issues": [],
}
GOOD_NEG = {
    "scope": "sqli probe",
    "result": {"verdict": "failed: no sql error oracle",
               "success_observable_raw": "no output captured",
               "failure_class": "environmental"},
    "key_files": [],
    "issues": ["VM flaked mid-run"],
}


def _errs(e):
    return "; ".join(le.validate(e))


def test_envelope_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        cap = Path(tmp) / "poc" / "lane-x"
        r = subprocess.run([sys.executable, str(ENVELOPE_PY), "init", str(cap),
                            "--lane", "lane-x"], capture_output=True, text=True)
        assert r.returncode == 0 and "lane-x" in r.stdout
        env = cap / "envelope.json"
        assert env.exists()
        template = json.loads(env.read_text())
        assert template == le.TEMPLATE
        # the unfilled template must NOT pass: empty scope/verdict/observable
        assert _errs(template) != ""
        assert "result.verdict: empty" in _errs(template)
        r = subprocess.run([sys.executable, str(ENVELOPE_PY), "validate", str(cap)],
                           capture_output=True, text=True)
        assert r.returncode == 1 and r.stdout.startswith("INVALID")
        # filled envelope validates, both via file and via dir path
        env.write_text(json.dumps(GOOD))
        r = subprocess.run([sys.executable, str(ENVELOPE_PY), "validate", str(cap)],
                           capture_output=True, text=True)
        assert r.returncode == 0 and r.stdout.strip() == "VALID", r.stdout
        r = subprocess.run([sys.executable, str(ENVELOPE_PY), "validate", str(env)],
                           capture_output=True, text=True)
        assert r.returncode == 0 and r.stdout.strip() == "VALID"
        # init never clobbers a filled envelope
        r = subprocess.run([sys.executable, str(ENVELOPE_PY), "init", str(cap),
                            "--lane", "lane-x"], capture_output=True, text=True)
        assert r.returncode == 1 and "not overwritten" in r.stdout


def test_envelope_invalid_cases():
    assert le.validate(GOOD) == []
    assert le.validate(GOOD_NEG) == []
    assert le.validate(dict(GOOD, pending_write=["+ new line"])) == []
    assert le.validate(dict(GOOD, extra_key=1)) == []          # extras ignored

    def bad(mut, frag):
        e = json.loads(json.dumps(GOOD))
        mut(e)
        assert frag in _errs(e), "%s missing from %r" % (frag, _errs(e))

    bad(lambda e: e.pop("result"), "result: missing")
    bad(lambda e: e.pop("key_files"), "key_files: missing")
    bad(lambda e: e.pop("issues"), "issues: missing")
    bad(lambda e: e.update(scope=5), "scope: must be str")
    bad(lambda e: e.update(key_files="poc/x"), "key_files: must be a list of strings")
    bad(lambda e: e.update(key_files=[1]), "key_files: must be a list of strings")
    bad(lambda e: e["result"].pop("verdict"), "result.verdict: missing")
    bad(lambda e: e["result"].pop("success_observable_raw"),
        "result.success_observable_raw: missing")
    bad(lambda e: e["result"].update(success_observable_raw=""),
        "success_observable_raw: empty")
    # negative verdict REQUIRES failure_class, and it must be a known class
    bad(lambda e: e["result"].update(verdict="failed: blocked by WAF"),
        "failure_class: missing on negative verdict")
    bad(lambda e: e["result"].update(verdict="failed: x", failure_class="meh"),
        "failure_class: 'meh' not one of")
    e = json.loads(json.dumps(GOOD))            # positive verdict MAY carry one
    e["result"]["failure_class"] = "technical"
    assert le.validate(e) == []
    assert le.validate(["not", "an", "object"]) == ["envelope: must be a JSON object"]
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "broken.json"
        p.write_text("{oops")
        r = subprocess.run([sys.executable, str(ENVELOPE_PY), "validate", str(p)],
                           capture_output=True, text=True)
        assert r.returncode == 1 and "unreadable" in r.stdout
        r = subprocess.run([sys.executable, str(ENVELOPE_PY), "validate",
                            str(Path(tmp) / "none")], capture_output=True, text=True)
        assert r.returncode == 1 and "no envelope.json" in r.stdout


def test_lane_validate_envelope_mode():
    with tempfile.TemporaryDirectory() as tmp:
        eng = Path(tmp)
        for lane, env in (("lane-ok", GOOD), ("lane-bad", None),
                          ("lane-ugly", {"scope": "x"}), ("lane-none", "skip")):
            cap = eng / "poc" / lane
            cap.mkdir(parents=True)
            (cap / "raw.txt").write_text("uid=33(www-data) probe output\n")
            if env == "skip":
                continue                      # no envelope.json at all
            if env is not None:
                (cap / "envelope.json").write_text(json.dumps(env))
            else:
                (cap / "envelope.json").write_text("{oops")   # unparsable
        log = eng / "log.md"
        log.write_text(
            "# log\n"
            "- lane lane-ok in flight @10:00: SUCCESS = `uid=33(www-data)` | "
            "tmux win 1 | capture poc/lane-ok -> returned\n"
            "- lane lane-bad in flight @10:00: SUCCESS = `uid=33(www-data)` | "
            "tmux win 1 | capture poc/lane-bad -> returned\n"
            "- lane lane-ugly in flight @10:00: SUCCESS = `uid=33(www-data)` | "
            "tmux win 1 | capture poc/lane-ugly -> returned\n"
            "- lane lane-none in flight @10:00: SUCCESS = `uid=33(www-data)` | "
            "tmux win 1 | capture poc/lane-none -> returned\n"
            "- lane lane-nodir in flight @10:00: SUCCESS = `uid=33(www-data)` | "
            "tmux win 1 | capture poc/lane-nodir -> returned\n"
            "- lane lane-open in flight @10:00: SUCCESS = `uid=33(www-data)` | "
            "tmux win 1 | capture poc/lane-open | handle a1b2c3\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = lv.main(["--envelope", str(eng)])
        text = out.getvalue()
        assert rc == 0
        assert "lane lane-ok: ENVELOPE VALID" in text
        assert "lane lane-bad: ENVELOPE-INVALID" in text and \
            "re-prompt due" in text
        assert "lane lane-ugly: ENVELOPE-INVALID" in text and \
            "result: missing" in text
        assert "lane lane-none: ENVELOPE-MISSING" in text and \
            "re-prompt due" in text
        assert "lane lane-nodir: no capture dir" in text and \
            "envelope check n/a" in text
        assert "lane-open" not in text                     # open lane: skipped
        # the hermes rule: a schema miss NEVER flips the log verdict - log.md
        # is not rewritten by the validator
        assert "in flight @10:00" in log.read_text()
        # existing normal mode still governs the verdict side, unchanged shape
        out2 = io.StringIO()
        with contextlib.redirect_stdout(out2):
            lv.main([str(eng)])
        assert "lane lane-ok: VERIFIED" in out2.getvalue()
        assert "lane lane-nodir: NOT VERIFIED - no capture dir" in out2.getvalue()
        # advisory cross-check: a VALID envelope whose raw observable is absent
        (eng / "poc" / "lane-ok" / "envelope.json").write_text(json.dumps(
            dict(GOOD, result=dict(GOOD["result"],
                                   success_observable_raw="`THM{not_there}`"))))
        out3 = io.StringIO()
        with contextlib.redirect_stdout(out3):
            lv.main(["--envelope", str(eng)])
        assert "advisory: success_observable_raw tokens not found" in out3.getvalue()
        # usage / missing log: exit 0, like every lane_validate mode
        out4 = io.StringIO()
        with contextlib.redirect_stdout(out4):
            assert lv.main(["--envelope"]) == 0
            assert lv.main(["--envelope", str(eng / "nope")]) == 0
        assert "usage" in out4.getvalue() and "no log at" in out4.getvalue()


def _git_repo(path):
    path.mkdir(parents=True)
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    for args in (["init", "-q"], ["config", "user.email", "t@t"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git"] + args, cwd=str(path), env=env,
                       capture_output=True, check=True)
    (path / "f.txt").write_text("one\n")
    subprocess.run(["git", "add", "-A"], cwd=str(path), env=env,
                   capture_output=True, check=True)
    subprocess.run(["git", "commit", "-qm", "c1"], cwd=str(path), env=env,
                   capture_output=True, check=True)
    return path


def test_worktree_create_prune():
    if shutil.which("git") is None:
        print("skip: worktree tests (git missing)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        src = _git_repo(Path(tmp) / "src")
        eng = Path(tmp) / "eng"
        eng.mkdir()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert lw.create("lane-x", str(src), base=str(eng)) == 0
        wt = eng / "worktrees" / "lane-x"
        assert wt.is_dir() and (wt / "f.txt").exists()
        assert "ztorch-lane/lane-x" in out.getvalue()
        # duplicate lane / existing worktree refused
        with contextlib.redirect_stdout(io.StringIO()):
            assert lw.create("lane-x", str(src), base=str(eng)) == 2
        # dirty source refused
        (src / "dirty.txt").write_text("x")
        with contextlib.redirect_stdout(io.StringIO()) as o2:
            assert lw.create("lane-z", str(src), base=str(eng)) == 2
        assert "dirty" in o2.getvalue()
        (src / "dirty.txt").unlink()
        # raw/git source refused (vault rule: raw/ clones are read-only)
        rawgit = _git_repo(Path(tmp) / "raw" / "git" / "clone1")
        with contextlib.redirect_stdout(io.StringIO()) as o3:
            assert lw.create("lane-r", str(rawgit), base=str(eng)) == 2
        assert "read-only" in o3.getvalue()
        # raw/research source is the allowed non-vault source
        res = _git_repo(Path(tmp) / "raw" / "research" / "proj")
        with contextlib.redirect_stdout(io.StringIO()):
            assert lw.create("lane-res", str(res), base=str(eng)) == 0
        # bad lane name refused (it becomes a path + branch name)
        with contextlib.redirect_stdout(io.StringIO()):
            assert lw.create("a/b", str(src), base=str(eng)) == 2

        # prune refuses on commits beyond source HEAD
        (wt / "f.txt").write_text("two\n")
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        subprocess.run(["git", "add", "-A"], cwd=str(wt), env=env, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "lane work"], cwd=str(wt), env=env,
                       capture_output=True)
        with contextlib.redirect_stdout(io.StringIO()) as o4:
            assert lw.prune("lane-x", base=str(eng)) == 1
        assert "commit(s) on the lane branch" in o4.getvalue() and wt.is_dir()
        # merge the lane into src -> now provable; but tree must also be clean
        subprocess.run(["git", "merge", "-q", "ztorch-lane/lane-x"], cwd=str(src),
                       env=env, capture_output=True, check=True)
        (wt / "untracked.txt").write_text("x")
        with contextlib.redirect_stdout(io.StringIO()) as o5:
            assert lw.prune("lane-x", base=str(eng)) == 1
        assert "untracked files" in o5.getvalue() and wt.is_dir()
        (wt / "untracked.txt").unlink()
        (wt / "f.txt").write_text("dirty\n")            # tracked, modified
        with contextlib.redirect_stdout(io.StringIO()) as o6:
            assert lw.prune("lane-x", base=str(eng)) == 1
        assert "dirty tree" in o6.getvalue() and wt.is_dir()
        subprocess.run(["git", "checkout", "--", "f.txt"], cwd=str(wt), env=env,
                       capture_output=True, check=True)
        # clean + merged: prune succeeds, branch deleted
        with contextlib.redirect_stdout(io.StringIO()) as o7:
            assert lw.prune("lane-x", base=str(eng)) == 0
        assert not wt.exists() and "proven" in o7.getvalue()
        br = subprocess.run(["git", "rev-parse", "--verify", "ztorch-lane/lane-x"],
                            cwd=str(src), env=env, capture_output=True)
        assert br.returncode != 0                       # branch gone
        # zero-commit clean worktree prunes without any merge
        with contextlib.redirect_stdout(io.StringIO()):
            assert lw.create("lane-e", str(src), base=str(eng)) == 0
            assert lw.prune("lane-e", base=str(eng)) == 0
        assert not (eng / "worktrees" / "lane-e").exists()
        # list reports lanes (and empty base is not an error)
        with contextlib.redirect_stdout(io.StringIO()) as o8:
            assert lw.list_wts(base=str(eng)) == 0
        assert "lane-res" in o8.getvalue() and "clean" in o8.getvalue()
        with contextlib.redirect_stdout(io.StringIO()) as o9:
            assert lw.list_wts(base=str(Path(tmp) / "empty")) == 0
        assert "no worktrees" in o9.getvalue()
        # unknown lane prune is rc 2, not a crash
        with contextlib.redirect_stdout(io.StringIO()):
            assert lw.prune("ghost", base=str(eng)) == 2


def test_manifest_window_and_budget():
    cfg = lm.validate(lm.parse("{}"))
    assert cfg["window_m"] == 45 and cfg["budget"] == {"max_iters": 250, "child_max": 2}
    cfg = lm.validate(lm.parse('{"window_m": 10, "budget": '
                               '{"max_iters": 5, "child_max": 1}}'))
    assert cfg["window_m"] == 10 and cfg["budget"] == {"max_iters": 5, "child_max": 1}
    # bad types WARN (stderr) and fall back to defaults; never a hard refusal
    for bad in ('{"window_m": "45"}', '{"window_m": true}',
                '{"budget": 5}', '{"budget": {"max_iters": "x", "child_max": false}}'):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            cfg = lm.validate(lm.parse(bad))
        assert cfg["window_m"] == 45, bad
        assert cfg["budget"] == {"max_iters": 250, "child_max": 2}, bad
        assert "warning" in err.getvalue(), bad
    # known keys: no unknown-key warning for window_m/budget anymore
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        lm.validate(lm.parse('{"window_m": 5}'))
    assert "unknown manifest key" not in err.getvalue()
    # plan lines: timeout, envs, then the advisory cells, then docker argv
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "lane.json"
        p.write_text('{"image": "img:1", "timeout_s": 45, "window_m": 9, '
                     '"budget": {"max_iters": 7, "child_max": 1}}\n')
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "lane_manifest.py"),
                            str(p)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        lines = r.stdout.splitlines()
        assert lines[0] == "timeout=45" and lines[1] == "envs="
        assert lines[2] == "window_m=9" and lines[3] == "budget=7,1"
        assert lines[4] == "--cap-drop" and lines[-1] == "img:1"


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    for name, fn in fns:
        fn()
        print("ok: %s" % name)
    print("all %d lane_envelope tests passed" % len(fns))
