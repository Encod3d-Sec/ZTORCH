import importlib.util
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "skills" / "hooks" / "close-out.py"


def load_hook():
    sys.path.insert(0, str(HOOK.parent))
    spec = importlib.util.spec_from_file_location("close_out_mod", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ponytail_nudge_fires_once_per_edit_burst(tmp_path, capsys):
    mod = load_hook()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "x.py").write_text("x = 1\n")
    mod._ponytail_debt_nudge(str(tmp_path))
    assert "ponytail-debt" in capsys.readouterr().out
    mod._ponytail_debt_nudge(str(tmp_path))
    assert "ponytail-debt" not in capsys.readouterr().out


def test_ponytail_nudge_no_framework_files_is_silent(tmp_path, capsys):
    mod = load_hook()
    mod._ponytail_debt_nudge(str(tmp_path))
    assert capsys.readouterr().out == ""
    assert not (tmp_path / ".ponytail-debt-stamp").exists()


def test_ponytail_nudge_new_edit_refires(tmp_path, capsys):
    import os
    mod = load_hook()
    f = tmp_path / "scripts" / "x.py"
    (tmp_path / "scripts").mkdir()
    f.write_text("x = 1\n")
    os.utime(f, (1_000_000, 1_000_000))
    mod._ponytail_debt_nudge(str(tmp_path))
    capsys.readouterr()
    os.utime(f, (2_000_000, 2_000_000))
    mod._ponytail_debt_nudge(str(tmp_path))
    assert "ponytail-debt" in capsys.readouterr().out
