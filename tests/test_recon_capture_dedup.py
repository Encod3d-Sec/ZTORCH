"""W2-1: two axis-tracking blocks (.recon-tools / .web-cap) appended `axis + "\\n"` on EVERY
matching command all engagement long, with no "already recorded" check, when only set-membership
was ever read back. W2-2: _wiki_index() did a full os.walk("wiki/") with no memoization, so it
could run twice within one hook invocation."""
import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "recon_capture", os.path.join(VAULT, "skills", "hooks", "recon-capture.py"))
recon_capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recon_capture)


def test_record_axis_once_dedupes(tmp_path):
    p = tmp_path / ".recon-tools"
    recon_capture._record_axis_once(str(p), "content")
    recon_capture._record_axis_once(str(p), "content")
    recon_capture._record_axis_once(str(p), "nuclei")
    lines = p.read_text().splitlines()
    assert lines.count("content") == 1
    assert lines.count("nuclei") == 1


def test_wiki_index_memoized_within_process(tmp_path, monkeypatch):
    calls = {"n": 0}
    real_walk = os.walk

    def counting_walk(path, *a, **kw):
        calls["n"] += 1
        return real_walk(path, *a, **kw)

    monkeypatch.setattr(recon_capture.os, "walk", counting_walk)
    recon_capture._WIKI_IDX_CACHE = None  # force a fresh state for this test
    recon_capture._wiki_index()
    recon_capture._wiki_index()
    assert calls["n"] == 1, "the second call must reuse the cached index, not re-walk wiki/"
