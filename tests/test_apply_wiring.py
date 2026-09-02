"""W2-15/W2-16: apply-wiring.py's write_triggers() KeyError'd on the real triggers.json schema
(no "_comment" key exists); wiki_path() picked an arbitrary first match on a basename collision
(20 duplicate-basename pairs exist in wiki/ today) instead of warning."""
import importlib.util
import json
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "apply_wiring", os.path.join(VAULT, "scripts", "apply-wiring.py"))
apply_wiring = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(apply_wiring)


def test_write_triggers_survives_missing_comment_key(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_wiring, "TRIGGERS", str(tmp_path / "triggers.json"))
    # the real schema: no "_comment" key at all
    d = {"triggers": {"foo": "hunt-x"}, "surface_triggers": {}}
    apply_wiring.write_triggers(d)  # must not raise KeyError
    written = json.loads((tmp_path / "triggers.json").read_text())
    assert written["triggers"] == {"foo": "hunt-x"}


def test_wiki_path_warns_on_basename_collision(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_wiring, "ROOT", str(tmp_path))
    a = tmp_path / "wiki" / "payloads"
    b = tmp_path / "wiki" / "techniques" / "web"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "ssrf.md").write_text("payload twin")
    (b / "ssrf.md").write_text("technique twin")
    apply_wiring.warn.clear()
    apply_wiring.wiki_path("ssrf")
    assert apply_wiring.warn, "a basename collision must produce a warning, not a silent pick"


def test_wiki_path_single_match_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_wiring, "ROOT", str(tmp_path))
    d = tmp_path / "wiki" / "techniques"
    d.mkdir(parents=True)
    (d / "xxe.md").write_text("x")
    apply_wiring.warn.clear()
    hit = apply_wiring.wiki_path("xxe")
    assert hit and hit.endswith("xxe.md")
    assert not apply_wiring.warn
