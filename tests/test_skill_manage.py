#!/usr/bin/env python3
"""Tests for scripts/skill_manage.py (guarded skill authoring port)."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "zt_skm", os.path.join(HERE, "..", "scripts", "skill_manage.py"))
skm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skm)


def reroot(tmp):
    """Point the module at a synthetic vault."""
    os.makedirs(os.path.join(tmp, "skills", "workflow"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "scripts"), exist_ok=True)
    open(os.path.join(tmp, "scripts", "routing.json"), "w").write("{}")
    skm.VAULT = tmp
    skm.SKILLS = os.path.join(tmp, "skills")
    skm.ARCHIVE = os.path.join(skm.SKILLS, ".archive")
    skm.LEDGER = os.path.join(skm.SKILLS, ".skill-ledger.jsonl")


def test_create_guards():
    with tempfile.TemporaryDirectory() as tmp:
        reroot(tmp)
        assert not skm.NAME_RE.match("Bad Name")
        # desc > 60 refused, name rules refused, duplicate refused
        # exercise through arg parsing (main() returns an int; it does not raise)
        sys.argv = ["skill_manage.py", "create", "--name", "zz-test", "--desc", "x" * 61]
        assert skm.main() != 0
        sys.argv = ["skill_manage.py", "create", "--name", "ZZ bad", "--desc", "ok desc"]
        assert skm.main() != 0
        sys.argv = ["skill_manage.py", "create", "--name", "zz-test", "--desc", "test skill desc"]
        try:
            skm.main()
        except SystemExit as e:
            assert e.code == 0
        assert os.path.exists(os.path.join(tmp, "skills", "zz-test", "SKILL.md"))
        fm = open(os.path.join(tmp, "skills", "zz-test", "SKILL.md")).read()
        assert "state: active" in fm and "created_by: agent" in fm
        # duplicate refused
        sys.argv = ["skill_manage.py", "create", "--name", "zz-test", "--desc", "test skill desc"]
        assert skm.main() != 0


def test_patch_read_before_write():
    with tempfile.TemporaryDirectory() as tmp:
        reroot(tmp)
        sys.argv = ["skill_manage.py", "create", "--name", "zz-p", "--desc", "patch test"]
        assert skm.main() == 0
        path = os.path.join(tmp, "skills", "zz-p", "SKILL.md")
        good = skm.sha(path)
        # stale sha refused
        sys.argv = ["skill_manage.py", "patch", "zz-p", "--old", "patch test",
                    "--new", "patched", "--from-read", "0" * 64]
        assert skm.main() != 0
        # good sha applies; sha printed changes
        sys.argv = ["skill_manage.py", "patch", "zz-p", "--old", "# zz-p",
                    "--new", "# zz-p patched", "--from-read", good]
        assert skm.main() == 0
        assert "zz-p patched" in open(path).read()
        # ledger has create + patch
        lines = open(os.path.join(tmp, "skills", ".skill-ledger.jsonl")).read().strip().splitlines()
        assert any('"op": "create"' in l for l in lines) and any('"op": "patch"' in l for l in lines)


def test_write_file_and_delete():
    with tempfile.TemporaryDirectory() as tmp:
        reroot(tmp)
        sys.argv = ["skill_manage.py", "create", "--name", "zz-w", "--desc", "write file test"]
        assert skm.main() == 0
        # traversal refused
        sys.argv = ["skill_manage.py", "write-file", "zz-w", "--path", "../evil.md"]
        assert skm.main() != 0
        # allowed subdir works (stdin body)
        import io
        stdin = sys.stdin
        sys.stdin = io.StringIO("ref body")
        sys.argv = ["skill_manage.py", "write-file", "zz-w", "--path", "references/a.md"]
        assert skm.main() == 0
        sys.stdin = stdin
        assert os.path.exists(os.path.join(tmp, "skills", "zz-w", "references", "a.md"))
        # delete needs existing umbrella
        sys.argv = ["skill_manage.py", "delete", "zz-w", "--absorbed-into", "nope"]
        assert skm.main() != 0
        # create umbrella then archive
        sys.argv = ["skill_manage.py", "create", "--name", "zz-umb", "--desc", "umbrella"]
        assert skm.main() == 0
        sys.argv = ["skill_manage.py", "delete", "zz-w", "--absorbed-into", "zz-umb"]
        assert skm.main() == 0
        assert not os.path.exists(os.path.join(tmp, "skills", "zz-w"))
        assert os.path.isdir(os.path.join(tmp, "skills", ".archive"))


def test_referenced_skill_protected():
    with tempfile.TemporaryDirectory() as tmp:
        reroot(tmp)
        open(os.path.join(tmp, "scripts", "routing.json"), "w").write('{"x": {"skill": "zz-routed"}}')
        open(os.path.join(tmp, "skills", "zz-routed", "SKILL.md").__class__ and
             os.path.join(*[tmp, "skills", "zz-routed"]) + "/SKILL.md", "w") if os.makedirs(
            os.path.join(tmp, "skills", "zz-routed"), exist_ok=True) is None else None
        assert skm.referenced("zz-routed") == ["scripts/routing.json"]
        assert skm.referenced("zz-other") == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok {fn.__name__}")
    print(f"{len(fns)} passed")
