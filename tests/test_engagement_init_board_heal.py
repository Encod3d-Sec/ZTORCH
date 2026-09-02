"""Wave 7 W7-2: a box judged 'too obvious to board' skips offensive.py board entirely and loses
ALL foothold/privesc tracking. engagement-init.py's SessionStart self-heal now auto-runs the board
generator when Approach.md exists but carries zero rows AND .offensive.json shows init already ran
- removing the judgment call instead of relying only on a runtime nudge."""
import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "engagement_init", os.path.join(VAULT, "skills", "hooks", "engagement-init.py"))
engagement_init = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(engagement_init)


def test_board_empty_true_for_stub_approach(tmp_path):
    (tmp_path / "Approach.md").write_text("# Approach\n\n### 4a. Coverage matrix\n\n"
                                           "| id | asset |\n|---|---|\n")
    assert engagement_init._board_empty(str(tmp_path)) is True


def test_board_empty_false_when_checklist_item_present(tmp_path):
    (tmp_path / "Approach.md").write_text("# Approach\n\n- [ ] 1. Recon\n")
    assert engagement_init._board_empty(str(tmp_path)) is False


def test_board_empty_false_when_no_approach_file(tmp_path):
    assert engagement_init._board_empty(str(tmp_path)) is False


def test_self_heal_board_skips_without_offensive_json(tmp_path, monkeypatch):
    import _engagement
    monkeypatch.setattr(_engagement, "active_dir", lambda: str(tmp_path))
    (tmp_path / "Approach.md").write_text("# Approach\n\n### 4a. Coverage matrix\n\n"
                                           "| id | asset |\n|---|---|\n")
    assert engagement_init.self_heal_board() is False


def test_self_heal_board_runs_offensive_board_when_empty(tmp_path, monkeypatch):
    import _engagement
    monkeypatch.setattr(_engagement, "active_dir", lambda: str(tmp_path))
    (tmp_path / ".offensive.json").write_text("{}")
    (tmp_path / "Approach.md").write_text("# Approach\n\n### 4a. Coverage matrix\n\n"
                                           "| id | asset |\n|---|---|\n")
    calls = {}

    def fake_run_script(name, *args, timeout=40):
        calls["name"] = name
        calls["args"] = args
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(engagement_init, "_run_script", fake_run_script)
    assert engagement_init.self_heal_board() is True
    assert calls["name"] == "offensive.py"
    assert calls["args"] == ("board", "--eng", str(tmp_path))


def test_self_heal_board_noop_when_already_populated(tmp_path, monkeypatch):
    import _engagement
    monkeypatch.setattr(_engagement, "active_dir", lambda: str(tmp_path))
    (tmp_path / ".offensive.json").write_text("{}")
    (tmp_path / "Approach.md").write_text("# Approach\n\n- [ ] 1. Recon\n")
    assert engagement_init.self_heal_board() is False
