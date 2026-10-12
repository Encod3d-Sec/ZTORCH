#!/usr/bin/env python3
"""Hermes seat tests: static config/wrapper checks (no API spend) + opt-in live smoke.

Static:  python3 tests/test_hermes_seat.py
Live:    ZT_HERMES_LIVE=1 python3 tests/test_hermes_seat.py
         (one tiny `hermes -z` call on the real seat; costs ~1 haiku-tier request)
"""
import os
import subprocess
import tempfile

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT = os.path.join(VAULT, "setup", "hermes-seat-init.sh")
WRAP = os.path.join(VAULT, "scripts", "hermes.sh")


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _seat_env(home):
    env = dict(os.environ)
    env["ZTORCH_HERMES_HOME"] = home
    env["ZTORCH_HERMES_BASE_URL"] = "https://gw.example/api/anthropic"
    env["ZTORCH_HERMES_KEY"] = "test-key-123"
    return env


def test_init_writes_config():
    with tempfile.TemporaryDirectory() as home:
        r = _run(["bash", INIT], env=_seat_env(home))
        assert r.returncode == 0, r.stderr
        cfg = open(os.path.join(home, "config.yaml")).read()
        for needle in [
            "provider: ztorch-gw",
            "api_mode: anthropic_messages",
            'base_url: "https://gw.example/api/anthropic"',
            "glm-5.3-flash", "glm-5.3", "glm-5.3-max",
            "external_dirs:", f'- "{VAULT}/skills"',
            "command: qmd", "QMD_VAULT:",
            "curator:", "enabled: false",
            "backend: local",
        ]:
            assert needle in cfg, f"config missing: {needle}"
        dotenv = open(os.path.join(home, ".env")).read()
        assert "ZTORCH_HERMES_KEY=test-key-123" in dotenv
        assert oct(os.stat(os.path.join(home, ".env")).st_mode)[-3:] == "600"


def test_init_idempotent_and_force():
    with tempfile.TemporaryDirectory() as home:
        env = _seat_env(home)
        _run(["bash", INIT], env=env)
        cfg1 = open(os.path.join(home, "config.yaml")).read()
        dotenv1 = open(os.path.join(home, ".env")).read()
        # key never overwritten by a different env key on rerun
        env["ZTORCH_HERMES_KEY"] = "other-key-999"
        r = _run(["bash", INIT], env=env)
        assert "unchanged" in r.stdout
        assert open(os.path.join(home, ".env")).read() == dotenv1
        r = _run(["bash", INIT, "--force"], env=env)
        assert "wrote" in r.stdout
        assert open(os.path.join(home, "config.yaml")).read() == cfg1
        assert open(os.path.join(home, ".env")).read() == dotenv1  # key still not clobbered


def test_init_needs_base_url():
    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ)
        env["ZTORCH_HERMES_HOME"] = home
        env.pop("ZTORCH_HERMES_BASE_URL", None)
        env.pop("ANTHROPIC_BASE_URL", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        r = _run(["bash", INIT], env=env)
        assert r.returncode != 0
        assert "base URL" in r.stderr


def test_wrapper_validation():
    env = dict(os.environ)
    env["ZTORCH_HERMES_HOME"] = "/nonexistent-hermes-home"
    r = _run(["bash", WRAP], env=env)
    assert r.returncode == 2 and "prompt" in r.stderr
    r = _run(["bash", WRAP, "hi", "--tier", "gpt"], env=env)
    assert r.returncode == 2 and "tier" in r.stderr
    r = _run(["bash", WRAP, "hi", "--dir", "/no/such/dir"], env=env)
    assert r.returncode == 2 and "dir" in r.stderr
    r = _run(["bash", WRAP, "check"], env=env)
    assert r.returncode == 2 and "seat config" in r.stderr


def test_wrapper_check_passes_on_seeded_seat():
    with tempfile.TemporaryDirectory() as home:
        env = _seat_env(home)
        _run(["bash", INIT], env=env)
        r = _run(["bash", WRAP, "check"], env=env)
        assert r.returncode == 0, r.stderr
        assert "OK:" in r.stdout


def test_live_smoke():
    if os.environ.get("ZT_HERMES_LIVE") != "1":
        print("skip live (set ZT_HERMES_LIVE=1)")
        return
    with tempfile.TemporaryDirectory() as cap:
        r = _run(["bash", WRAP, "Reply with the single word OK and nothing else.",
                  "--capture", cap], cwd=VAULT)
        assert r.returncode == 0, r.stderr[-500:]
        assert "OK" in r.stdout
        assert os.path.exists(os.path.join(cap, "response.md"))
        usage = os.path.join(cap, "usage.json")
        assert os.path.exists(usage)
        import json
        u = json.load(open(usage))
        assert u.get("completed") is True and u.get("session_id")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok {fn.__name__}")
    print(f"{len(fns)} passed")
