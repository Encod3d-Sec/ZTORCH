"""playbook.json duplicate-fingerprint hard-fail (pass 10). json.loads keeps
the LAST duplicate key, so a duped fingerprint silently lobotomizes the
routing table (the author meant two routings; one vanished). next_move dies
loud instead - and the broad `except Exception` disabler must not swallow
that verdict (the `except SystemExit: raise` before it).

Exec'd against the REAL source with a synthetic __file__ (a reload would
rebind VAULT/_PB_PATH from __file__ and ignore any patch): the module derives
VAULT from __file__, so pointing __file__ at tmp_path/scripts/ reruns the
actual module-level load against the crafted playbook."""
import os
import sys

import pytest

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(VAULT, "scripts"))
import next_move  # noqa: E402


def test_duplicate_fingerprint_exits_loud(tmp_path, capsys):
    # RAW text, not json.dumps: a Python dict literal cannot carry a dup key.
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "playbook.json").write_text(
        '{"fingerprints": {"jenkins": {"tests": ["x"], "skills": []}, '
        '"jenkins": {"tests": ["y"], "skills": []}}}', encoding="utf-8")
    src = open(os.path.join(VAULT, "scripts", "next_move.py"), encoding="utf-8").read()
    ns = {"__file__": str(tmp_path / "scripts" / "next_move.py"), "__name__": "nm_under_test"}
    with pytest.raises(SystemExit) as ex:
        exec(compile(src, "next_move.py", "exec"), ns)
    assert ex.value.code == 2
    assert "DUPLICATE fingerprint 'jenkins'" in capsys.readouterr().err


def test_no_dup_keys_passes_pairs_through():
    out = next_move._no_dup_keys([("a", 1), ("b", 2)])
    assert out == {"a": 1, "b": 2}


def test_real_playbook_still_loads():
    """The vault's actual playbook.json parses clean (no dup fingerprints)."""
    assert next_move.PLAYBOOK, "expected a populated fingerprint table"
