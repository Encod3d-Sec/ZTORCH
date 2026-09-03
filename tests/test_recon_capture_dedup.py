"""W2-1: two axis-tracking blocks (.recon-tools / .web-cap) appended `axis + "\\n"` on EVERY
matching command all engagement long, with no "already recorded" check, when only set-membership
was ever read back. W2-2: _wiki_index() did a full os.walk("wiki/") with no memoization, so it
could run twice within one hook invocation."""
import importlib.util
import json
import os
import sys
import time

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
    # isolated vault (no pre-existing .wiki-slug-index.json) so the first call is
    # guaranteed to walk, regardless of the persisted-cache fix below.
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "xss.md").write_text("# XSS\n")
    import _engagement  # noqa: E402
    monkeypatch.setattr(_engagement, "VAULT", str(tmp_path))

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


def test_wiki_index_persists_across_process_invocations(tmp_path, monkeypatch):
    """Regression: each hook firing is a FRESH process, so the module-level
    _WIKI_IDX_CACHE alone (the pre-fix state) never actually saved anything across
    invocations despite its docstring's claim -- only the file-persisted cache does."""
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "xss.md").write_text("# XSS\n")

    import _engagement  # noqa: E402 -- same module object recon_capture imports internally
    monkeypatch.setattr(_engagement, "VAULT", str(tmp_path))

    calls = {"n": 0}
    real_walk = os.walk

    def counting_walk(path, *a, **kw):
        calls["n"] += 1
        return real_walk(path, *a, **kw)

    monkeypatch.setattr(recon_capture.os, "walk", counting_walk)

    recon_capture._WIKI_IDX_CACHE = None
    idx1 = recon_capture._wiki_index()
    assert "xss" in idx1
    assert calls["n"] == 1
    assert (tmp_path / ".wiki-slug-index.json").is_file()

    # simulate a FRESH process: reset the in-memory cache, same as a new hook invocation
    recon_capture._WIKI_IDX_CACHE = None
    idx2 = recon_capture._wiki_index()
    assert idx2 == idx1
    assert calls["n"] == 1, "a fresh 'process' must reuse the persisted file cache, not re-walk"


def test_wiki_index_rebuilds_after_reindex_stamp(tmp_path, monkeypatch):
    """The persisted cache is invalidated once .wiki-reindex-stamp (touched on a real
    wiki edit) is newer than it -- a stale cache from before an edit must not linger."""
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "xss.md").write_text("# XSS\n")

    import _engagement  # noqa: E402
    monkeypatch.setattr(_engagement, "VAULT", str(tmp_path))

    recon_capture._WIKI_IDX_CACHE = None
    recon_capture._wiki_index()
    cache_path = tmp_path / ".wiki-slug-index.json"
    assert cache_path.is_file()

    # a new page lands, and the reindex hook stamps the edit -- AFTER the cache
    (tmp_path / "wiki" / "idor.md").write_text("# IDOR\n")
    time.sleep(0.01)
    (tmp_path / ".wiki-reindex-stamp").write_text("")

    recon_capture._WIKI_IDX_CACHE = None
    idx = recon_capture._wiki_index()
    assert "idor" in idx, "cache must rebuild once the reindex stamp postdates it"
