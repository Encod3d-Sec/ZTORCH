"""Tests for the offensive.py `index` compile step and its markdown parsers.

Runs against the minimal fixture vault at tests/fixtures/offensive/ so the
parse contract is pinned independently of the (evolving) real vault content.
"""
import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive  # noqa: E402

VAULT = ROOT / "tests" / "fixtures" / "offensive"
ENG = VAULT / "targets" / "demo"


def test_parse_routing_table():
    rt = offensive.parse_routing_table(VAULT)
    assert set(rt) == {"ssrf", "idor", "sqli", "login-form"}
    assert rt["ssrf"] == {
        "class": "ssrf", "skill": "hunt-ssrf",
        "wiki": "ssrf", "arsenal": "payloads/ssrf",
    }
    # many-fingerprints-one-class: login-form routes to the sqli hunt
    assert rt["login-form"]["skill"] == "hunt-sqli"
    assert rt["login-form"]["class"] == "sqli"


def test_parse_tool_index():
    ti = offensive.parse_tool_index(VAULT)
    assert set(ti) == {"nuclei", "sqlmap"}
    assert ti["nuclei"]["phase"] == "recon"
    # invocation is the first RUNNABLE line (comments skipped)
    assert ti["nuclei"]["invocation"].startswith("nuclei -u https://target.example")
    assert ti["nuclei"]["page"] == "wiki/tools/nuclei.md"
    assert ti["sqlmap"]["phase"] == "exploit"
    assert ti["sqlmap"]["invocation"].startswith("sqlmap -u")


def test_parse_hunt_method():
    m = offensive.parse_hunt_method(VAULT / "skills" / "hunt" / "hunt-ssrf")
    assert "enumerate 127.0.0.1 ports" in m["approach"]
    assert "NOT confirmation" in m["avoid"]
    assert "wiki/payloads/ssrf" in m["refs"]
    assert "dns-rebinding" in m["refs"]


def test_build_index_from_fixture(tmp_path):
    # copy the demo engagement into a scratch dir so the cache write is isolated
    eng = tmp_path / "demo"
    eng.mkdir()
    (eng / "state.md").write_text((ENG / "state.md").read_text())
    (eng / "scope.md").write_text((ENG / "scope.md").read_text())

    idx = offensive.build_index(eng, VAULT)

    # fingerprint -> skill map
    routing = idx["routing"]
    assert routing["ssrf"]["skill"] == "hunt-ssrf"
    assert routing["login-form"]["skill"] == "hunt-sqli"

    # tool invocations
    assert idx["tools"]["nuclei"]["invocation"].startswith("nuclei -u")
    assert idx["tools"]["sqlmap"]["phase"] == "exploit"

    # method blocks, keyed by hunt-skill name
    assert "enumerate 127.0.0.1 ports" in idx["methods"]["hunt-ssrf"]["approach"]
    assert "wiki/payloads/idor" in idx["methods"]["hunt-idor"]["refs"]

    # cache written to the engagement dir
    cache = eng / ".offensive-index.json"
    assert cache.exists()
    on_disk = json.loads(cache.read_text())
    assert on_disk["routing"]["ssrf"]["skill"] == "hunt-ssrf"

    # load_index round-trips
    loaded = offensive.load_index(eng)
    assert loaded == idx

    # fresh cache is not stale
    assert offensive.index_stale(eng, VAULT) is False


# --------------------------------------------------------------------------- gates (Task 4)

def _write_hunt_core(vault, table_body):
    core = vault / "skills" / "hunt" / "hunt-core"
    core.mkdir(parents=True)
    (core / "SKILL.md").write_text(
        "---\nname: hunt-core\n---\n\n## Routing table (machine-readable)\n\n%s\n" % table_body
    )


def test_malformed_routing_row_exits_nonzero(tmp_path, capsys):
    vault = tmp_path / "vault"
    # third data row is missing a cell (4 columns, not 5)
    _write_hunt_core(vault, "\n".join([
        "| fingerprint | class | hunt-skill | primary wiki | arsenal slug |",
        "|---|---|---|---|---|",
        "| ssrf | ssrf | hunt-ssrf | ssrf | payloads/ssrf |",
        "| idor | idor | hunt-idor | access-control |",
    ]))

    with pytest.raises(SystemExit) as exc:
        offensive.build_index(tmp_path / "eng", vault)
    assert exc.value.code != 0

    err = capsys.readouterr().err
    assert "skills/hunt/hunt-core/SKILL.md" in err
    assert "expected 5" in err


def test_hunt_dir_without_wiki_exits_nonzero(tmp_path, capsys):
    vault = tmp_path / "vault"
    _write_hunt_core(vault, "\n".join([
        "| fingerprint | class | hunt-skill | primary wiki | arsenal slug |",
        "|---|---|---|---|---|",
        "| ssrf | ssrf | hunt-ssrf | ssrf | payloads/ssrf |",
    ]))
    ssrf_dir = vault / "skills" / "hunt" / "hunt-ssrf"
    ssrf_dir.mkdir(parents=True)
    # no '## Wiki' section here
    (ssrf_dir / "SKILL.md").write_text("---\nname: hunt-ssrf\n---\n\n## Attack surface\n\nno wiki block.\n")

    with pytest.raises(SystemExit) as exc:
        offensive.build_index(tmp_path / "eng", vault)
    assert exc.value.code != 0

    err = capsys.readouterr().err
    assert "skills/hunt/hunt-ssrf/SKILL.md" in err
    assert "Wiki" in err


def test_tool_without_usage_exits_nonzero(tmp_path, capsys):
    vault = tmp_path / "vault"
    _write_hunt_core(vault, "\n".join([
        "| fingerprint | class | hunt-skill | primary wiki | arsenal slug |",
        "|---|---|---|---|---|",
        "| ssrf | ssrf | hunt-ssrf | ssrf | payloads/ssrf |",
    ]))
    tdir = vault / "wiki" / "tools"
    tdir.mkdir(parents=True)
    # no '## Core usage' fence
    (tdir / "broken.md").write_text("---\ntitle: broken\nphase: recon\n---\n\n## Purpose\n\nno usage block.\n")

    with pytest.raises(SystemExit) as exc:
        offensive.build_index(tmp_path / "eng", vault)
    assert exc.value.code != 0

    err = capsys.readouterr().err
    assert "wiki/tools/broken.md" in err
    assert "Core usage" in err


def test_index_stale_true_after_source_touch(tmp_path, monkeypatch):
    # index_stale() caches a confirmed-fresh result for a few seconds (perf fix: it's
    # called every driver loop turn) -- disable that window so this test's two
    # back-to-back calls each do a real scan, same as the production default did
    # before that fix.
    monkeypatch.setenv("OFFENSIVE_STALE_INTERVAL", "0")
    eng = tmp_path / "demo"
    eng.mkdir()
    offensive.build_index(eng, VAULT)
    assert offensive.index_stale(eng, VAULT) is False

    # bump a real source file's mtime past the cache's
    cache_mtime = (eng / ".offensive-index.json").stat().st_mtime
    future = cache_mtime + 10
    src = VAULT / "skills" / "hunt" / "hunt-core" / "SKILL.md"
    os.utime(src, (future, future))
    try:
        assert offensive.index_stale(eng, VAULT) is True
    finally:
        # restore mtime so repeat test runs / other tests aren't affected
        now = time.time()
        os.utime(src, (now, now))


def test_index_stale_check_is_cached_within_interval(tmp_path, monkeypatch):
    """Perf fix: index_stale() is called every driver loop turn and a full scan over
    ~100 source files costs real wall-clock on a slow filesystem. A confirmed-fresh
    result is cached for OFFENSIVE_STALE_INTERVAL seconds; a source touched WITHIN
    that window is not detected until it elapses -- the accepted trade for a check
    that runs hundreds of times per engagement."""
    monkeypatch.setenv("OFFENSIVE_STALE_INTERVAL", "60")
    eng = tmp_path / "demo"
    eng.mkdir()
    offensive.build_index(eng, VAULT)
    assert offensive.index_stale(eng, VAULT) is False   # stamps the cache

    cache_mtime = (eng / ".offensive-index.json").stat().st_mtime
    future = cache_mtime + 10
    src = VAULT / "skills" / "hunt" / "hunt-core" / "SKILL.md"
    os.utime(src, (future, future))
    try:
        # within the interval -> still reports fresh (cached), even though a real
        # source is now newer than the cache
        assert offensive.index_stale(eng, VAULT) is False
    finally:
        now = time.time()
        os.utime(src, (now, now))
