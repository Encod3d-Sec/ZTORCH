"""Tests for scripts/lane-run.sh + scripts/lane_manifest.py (docker lane runner).

Standalone: plain `python3 tests/test_lane_run.py` (no docker needed; plain
asserts, failures raise; also collects clean under pytest). One live test runs
only with ZT_LANE_LIVE=1 and a reachable docker daemon.
"""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import lane_manifest as lm  # noqa: E402

LANE_RUN = ROOT / "scripts" / "lane-run.sh"
HELPER = ROOT / "scripts" / "lane_manifest.py"


def _plan(tmp, body):
    """Validate `body` and build argv against real temp eng/wiki dirs."""
    eng = Path(tmp) / "eng"
    wiki = Path(tmp) / "wiki"
    eng.mkdir(exist_ok=True)
    wiki.mkdir(exist_ok=True)
    cfg = lm.validate(lm.parse(body))
    return cfg, lm.build_argv(cfg, str(eng), str(wiki))


def _pair(argv, flag, val):
    assert any(argv[i] == flag and argv[i + 1] == val
               for i in range(len(argv) - 1)), "missing pair %s %s" % (flag, val)


def _raises(body, fragment):
    try:
        lm.validate(lm.parse(body))
    except lm.ManifestError as e:
        assert fragment in str(e), str(e)
    else:
        raise AssertionError("manifest must be refused: %s" % body)


def test_missing_and_bad_manifest_refused():
    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "nope.json"
        try:
            lm.load(missing)
        except lm.ManifestError as e:
            assert "not found" in str(e)
        else:
            raise AssertionError("missing manifest must refuse")
        r = subprocess.run([sys.executable, str(HELPER), str(missing)],
                           capture_output=True, text=True)
        assert r.returncode == 2 and "not found" in r.stderr
        _raises("{oops", "not valid JSON")


def test_defaults_argv_battery():
    with tempfile.TemporaryDirectory() as tmp:
        cfg, argv = _plan(tmp, "{}")
        assert cfg["network"] is False and cfg["timeout_s"] == 600
        for flag, val in [
            ("--cap-drop", "ALL"), ("--cap-add", "DAC_OVERRIDE"),
            ("--cap-add", "CHOWN"), ("--cap-add", "FOWNER"),
            ("--security-opt", "no-new-privileges"), ("--pids-limit", "512"),
            ("--cpus", "2"), ("--memory", "4g"), ("--shm-size", "1g"),
            ("--network", "none"),
            ("--tmpfs", "/tmp:rw,nosuid,size=512m"),
            ("--tmpfs", "/var/tmp:rw,nosuid,noexec,size=512m"),
            ("--tmpfs", "/run:rw,nosuid,noexec,size=64m"),
            ("-v", "%s:/ztorch/wiki:ro" % (Path(tmp) / "wiki")),
            ("-v", "%s:/eng" % (Path(tmp) / "eng")), ("-w", "/eng"),
        ]:
            _pair(argv, flag, val)
        for flag in ("--init", "--rm", "-i"):
            assert flag in argv
        assert argv[-1] == "kalilinux/kali-rolling"  # default image


def test_network_toggle_and_type():
    with tempfile.TemporaryDirectory() as tmp:
        _, argv = _plan(tmp, '{"network": true}')
        assert "--network" not in argv          # opts into docker default bridge
        _raises('{"network": "true"}', "network must be a boolean")


def test_network_extra_args_fail_closed():
    for key in ("extra_args", "docker_args", "network_extra", "docker_network"):
        _raises('{"network": true, "%s": []}' % key, "fail closed")


def test_blocklisted_env_refused():
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GITHUB_TOKEN", "GH_TOKEN",
                 "SLACK_BOT_TOKEN", "VERCEL_TOKEN", "MODAL_TOKEN",
                 "AUXILIARY_FOO_API_KEY", "openai_api_key"):
        _raises('{"env": ["%s"]}' % name, "blocklisted")


def test_env_ok_names_pass_as_e_pairs():
    with tempfile.TemporaryDirectory() as tmp:
        _, argv = _plan(tmp, '{"env": ["FOO", "HTTP_PROXY", "SHODAN_API_KEY"]}')
        for name in ("FOO", "HTTP_PROXY", "SHODAN_API_KEY"):
            _pair(argv, "-e", name)
        _raises('{"env": ["1BAD"]}', "bad env name")
        _raises('{"env": ["A-B"]}', "bad env name")


def test_unknown_keys_warn_not_fail():
    with tempfile.TemporaryDirectory() as tmp:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            cfg, argv = _plan(tmp, '{"tools": ["nmap"], "writes": ["/eng/**"],'
                                   ' "banana": 1}')
        assert cfg["timeout_s"] == 600 and argv[-1] == "kalilinux/kali-rolling"
        for key in ("tools", "writes", "banana"):
            assert "warning: unknown manifest key '%s'" % key in err.getvalue()
        # window_m/budget are KNOWN advisory cells (P4): parsed, never warned
        assert "unknown manifest key 'window_m'" not in err.getvalue()
        assert "unknown manifest key 'budget'" not in err.getvalue()


def test_mounts_parsed_and_unsafe_refused():
    with tempfile.TemporaryDirectory() as tmp:
        _, argv = _plan(tmp, '{"mounts": ["raw:/raw:ro", "/abs:/out"]}')
        _pair(argv, "-v", "%s/raw:/raw:ro" % (Path(tmp) / "eng"))  # rel src resolved
        _pair(argv, "-v", "/abs:/out")
        _raises('{"mounts": ["/onlysrc"]}', "bad mount")
        _raises('{"mounts": ["a:relative"]}', "absolute")
        _raises('{"mounts": ["/h:/etc"]}', "refusing unsafe mount")
        _raises('{"mounts": ["/h:/var/run/docker.sock"]}', "refusing unsafe mount")
        _raises('{"mounts": ["/h:/d:rw2"]}', "bad mount mode")


def test_timeout_validation():
    with tempfile.TemporaryDirectory() as tmp:
        cfg, _ = _plan(tmp, '{"timeout_s": 30}')
        assert cfg["timeout_s"] == 30
        for bad in ('"30"', "0", "-5", "true", "1.5"):
            _raises('{"timeout_s": %s}' % bad, "timeout_s must be a positive integer")


def test_missing_wiki_warns_and_skips_mount():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = lm.validate(lm.parse("{}"))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            argv = lm.build_argv(cfg, str(Path(tmp) / "eng"), "/nonexistent/wiki")
        assert not any(a == "/ztorch/wiki:ro" for a in argv)
        assert "wiki dir" in err.getvalue()


def test_cli_plan_format():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "lane.json"
        p.write_text('{"image": "img:1", "timeout_s": 45, "env": ["FOO"]}\n')
        r = subprocess.run([sys.executable, str(HELPER), str(p)],
                           capture_output=True, text=True)
        assert r.returncode == 0
        lines = r.stdout.splitlines()
        assert lines[0] == "timeout=45" and lines[1] == "envs=FOO"
        assert lines[2] == "window_m=45" and lines[3] == "budget=250,2"
        assert lines[4] == "--cap-drop" and lines[-1] == "img:1"


def test_plan_advisory_cells_never_reach_docker_argv():
    """P4: window_m/budget plan lines are brain-side advice; the runner parser
    must swallow them (a stray line landing in ARGS would reach `docker run`)."""
    with tempfile.TemporaryDirectory() as tmp:
        eng = Path(tmp)
        stub = eng / "docker-stub.sh"
        argsfile = eng / "stub-args.txt"
        stub.write_text("#!/usr/bin/env bash\n"
                        '[ "$1" = "info" ] && exit 0\n'
                        'printf "%%s\\n" "$@" > "%s"\n'
                        "exit 0\n" % argsfile)
        stub.chmod(0o755)
        m = eng / "lane.json"
        m.write_text('{"timeout_s": 60, "window_m": 9, '
                     '"budget": {"max_iters": 7, "child_max": 1}}\n')
        r = subprocess.run(["bash", str(LANE_RUN), str(m), "id"], cwd=eng,
                           capture_output=True, text=True,
                           env=dict(os.environ, DOCKER_BIN=str(stub)))
        assert r.returncode == 0, r.stderr
        got = argsfile.read_text().splitlines()
        assert got[0] == "run"
        assert "window_m=9" not in got and "budget=7,1" not in got
        assert got[-1] == "id" and "kalilinux/kali-rolling" in got


def test_usage_no_args():
    r = subprocess.run(["bash", str(LANE_RUN)], capture_output=True, text=True)
    assert r.returncode != 0
    assert "usage" in (r.stdout + r.stderr).lower()


def test_missing_manifest_via_runner_rc2():
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(["bash", str(LANE_RUN), str(Path(tmp) / "nope.json"), "id"],
                           capture_output=True, text=True)
        assert r.returncode == 2 and "not found" in r.stderr


def test_docker_missing_rc2():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "lane.json"
        p.write_text("{}\n")
        env = dict(os.environ, DOCKER_BIN="/nonexistent/docker")
        r = subprocess.run(["bash", str(LANE_RUN), str(p), "id"],
                           capture_output=True, text=True, env=env)
        assert r.returncode == 2 and "docker binary not found" in r.stderr
        assert "brain" in r.stderr  # fallback is an explicit decision, never silent


def _docker_up():
    return bool(shutil.which("docker")) and subprocess.run(
        ["docker", "info"], capture_output=True).returncode == 0


def test_live_default_image_id_and_no_network():
    if os.environ.get("ZT_LANE_LIVE") != "1" or not _docker_up():
        print("skip: live lane test (needs ZT_LANE_LIVE=1 and a running docker daemon)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        eng = Path(tmp)
        (eng / "ingest").mkdir()
        m = eng / "lane.json"
        m.write_text('{"timeout_s": 300}\n')
        probe = ("id; getent hosts example.com >/dev/null 2>&1 "
                 "&& echo NET_UP || echo NET_DOWN")
        r = subprocess.run(["bash", str(LANE_RUN), str(m), "sh", "-c", probe],
                           cwd=eng, capture_output=True, text=True, timeout=600)
        assert "uid=" in r.stdout and r.returncode == 0
        assert "NET_DOWN" in r.stdout and "NET_UP" not in r.stdout  # network=none
        outs = list((eng / "ingest").glob("lane-*.out"))            # tee landed
        assert outs and "uid=" in outs[0].read_text()
        r2 = subprocess.run(["bash", str(LANE_RUN), str(m), "sh", "-c", "exit 7"],
                            cwd=eng, capture_output=True, text=True, timeout=600)
        assert r2.returncode == 7                                   # rc passthrough


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    for name, fn in fns:
        fn()
        print("ok: %s" % name)
    print("all %d lane_run tests passed" % len(fns))
