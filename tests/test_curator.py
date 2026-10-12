#!/usr/bin/env python3
"""Tests for scripts/curator.py (lifecycle port)."""
import importlib.util
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "zt_cur", os.path.join(HERE, "..", "scripts", "curator.py"))
cur = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cur)


def fixture(tmp, days_old, use_ts="", state="active", pinned=False):
    cur.VAULT = tmp
    cur.SKILLS = os.path.join(tmp, "skills")
    cur.STATE = os.path.join(cur.SKILLS, ".curator-state.json")
    cur.LEDGER = os.path.join(cur.SKILLS, ".skill-ledger.jsonl")
    os.makedirs(os.path.join(cur.SKILLS, "zz-demo"), exist_ok=True)
    created = time.strftime("%Y-%m-%d", time.localtime(time.time() - days_old * 86400))
    fm = (f"---\nname: zz-demo\ndescription: demo\nstate: {state}\ncreated: {created}\n"
          f"created_by: operator\npinned: {'true' if pinned else 'false'}\nlast_used: {use_ts[:10]}\n---\n")
    open(os.path.join(cur.SKILLS, "zz-demo", "SKILL.md"), "w").write(fm + "# demo\n")
    # no referenced names (empty wiring files)
    os.makedirs(os.path.join(tmp, "scripts"), exist_ok=True)
    open(os.path.join(tmp, "scripts", "routing.json"), "w").write("{}")
    open(os.path.join(tmp, "skills", "workflow", "engage", "SKILL.md") if os.makedirs(
        os.path.join(tmp, "skills", "workflow", "engage"), exist_ok=True) is None else "/dev/null", "w").write("x")
    return os.path.join(cur.SKILLS, "zz-demo", "SKILL.md")


def run():
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cur.main()
    return rc, buf.getvalue()


def test_seed_first_sight():
    with tempfile.TemporaryDirectory() as tmp:
        cur.VAULT = tmp; cur.SKILLS = os.path.join(tmp, "skills")
        cur.STATE = os.path.join(cur.SKILLS, ".curator-state.json")
        cur.LEDGER = os.path.join(cur.SKILLS, ".skill-ledger.jsonl")
        os.makedirs(os.path.join(cur.SKILLS, "zz-new"), exist_ok=True)
        open(os.path.join(cur.SKILLS, "zz-new", "SKILL.md"), "w").write("---\nname: zz-new\ndescription: d\n---\n# x\n")
        sys.argv = ["cur", "--force"]
        rc, out = run()
        assert rc == 0 and "seeded zz-new" in out
        assert "state: active" in open(os.path.join(cur.SKILLS, "zz-new", "SKILL.md")).read()


def test_stale_transition():
    with tempfile.TemporaryDirectory() as tmp:
        p = fixture(tmp, days_old=20, use_ts=time.strftime("%Y-%m-%d", time.localtime(time.time() - 20 * 86400)))
        sys.argv = ["cur", "--force"]
        rc, out = run()
        assert rc == 0 and "active -> stale" in out
        assert "state: stale" in open(p).read()


def test_archive_and_protection():
    with tempfile.TemporaryDirectory() as tmp:
        p = fixture(tmp, days_old=40, use_ts=time.strftime("%Y-%m-%d", time.localtime(time.time() - 40 * 86400)))
        os.makedirs(os.path.join(tmp, "targets", "e1"), exist_ok=True)
        with open(os.path.join(tmp, "targets", "e1", ".events.jsonl"), "w") as f:
            f.write(json.dumps({"ts": "2026-09-01T00:00:00", "tool": "Skill", "skill": "zz-demo"}) + "\n")
        sys.argv = ["cur", "--force"]
        rc, out = run()
        assert rc == 0 and "archived zz-demo" in out
        assert not os.path.exists(p)
        assert os.path.isdir(os.path.join(cur.SKILLS, ".archive"))
    with tempfile.TemporaryDirectory() as tmp:
        p = fixture(tmp, days_old=40, use_ts="", pinned=True)
        sys.argv = ["cur", "--force"]
        rc, out = run()
        assert "archived" not in out and os.path.exists(p)  # pinned protected
    with tempfile.TemporaryDirectory() as tmp:
        # never-used skill: absence of use is not evidence -> no archive
        p = fixture(tmp, days_old=40, use_ts="")
        sys.argv = ["cur", "--force"]
        rc, out = run()
        assert "archived" not in out and os.path.exists(p)


def test_reactivate_and_gate():
    with tempfile.TemporaryDirectory() as tmp:
        p = fixture(tmp, days_old=20, use_ts=time.strftime("%Y-%m-%d"), state="stale")
        sys.argv = ["cur", "--force"]
        rc, out = run()
        assert "stale -> active" in out
    with tempfile.TemporaryDirectory() as tmp:
        fixture(tmp, days_old=1, use_ts="")
        os.makedirs(os.path.join(tmp, "skills"), exist_ok=True)
        json.dump({"last_run": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(cur.STATE, "w"))
        sys.argv = ["cur"]
        rc, out = run()
        assert rc == 0 and out == ""  # not due: silent


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok {fn.__name__}")
    print(f"{len(fns)} passed")
