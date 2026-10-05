"""Tests for scripts/wiki-graph.py (stdlib wikilink relation layer)."""
import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wiki-graph.py"
_spec = importlib.util.spec_from_file_location("wiki_graph", _SCRIPT)
wiki_graph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wiki_graph)
sys.modules["wiki_graph"] = wiki_graph


def _wiki(tmp_path, pages):
    for rel, body in pages.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def test_build_resolves_link_forms_and_skips_fences(tmp_path):
    _wiki(tmp_path, {
        "index.md": ("links: [[techniques/ssrf]], [[XSS|alias]], "
                     "[[kerberos#header]], [[nowhere-page]], [[RCE]]\n"
                     "fenced:\n```\n[[ghost-link]]\n```\n"),
        "techniques/ssrf.md": "see [[index]]",
        "techniques/xss.md": "body",
        "techniques/rce.md": "body",
    })
    g = wiki_graph.build(tmp_path)
    assert g["index"] == {"techniques/ssrf", "techniques/xss", "techniques/rce"}
    assert g["techniques/ssrf"] == {"index"}
    assert "ghost-link" not in g["index"]


def test_shortest_multi_hop_undirected(tmp_path):
    _wiki(tmp_path, {"a.md": "[[b]]", "b.md": "[[c]]", "c.md": "body"})
    g = wiki_graph.build(tmp_path)
    assert wiki_graph.shortest(g, "a", "c") == ["a", "b", "c"]
    assert wiki_graph.shortest(g, "c", "a") == ["c", "b", "a"]
    assert wiki_graph.shortest(g, "a", "zzz") is None


def test_in_degrees_and_orphans(tmp_path):
    _wiki(tmp_path, {
        "hub.md": "[[a]] [[b]]",
        "a.md": "[[hub]]",
        "b.md": "[[hub]]",
        "loner.md": "no links at all",
    })
    g = wiki_graph.build(tmp_path)
    ind = wiki_graph.in_degrees(g)
    assert ind["hub"] == 2 and ind["a"] == 1
    assert sorted(r for r in g if ind[r] == 0) == ["loner"]


def test_resolve_exact_basename_and_substring(tmp_path):
    _wiki(tmp_path, {"techniques/ssrf.md": "x", "a/rce.md": "x", "b/rce.md": "x"})
    g = wiki_graph.build(tmp_path)
    assert wiki_graph.resolve("techniques/ssrf", g) == "techniques/ssrf"
    assert wiki_graph.resolve("SSRF", g) == "techniques/ssrf"
    with pytest.raises(SystemExit):
        wiki_graph.resolve("rce", g)  # two basenames -> ambiguous


def test_cmd_path_prints_chain(capsys):
    g = {"a": {"b"}, "b": {"c"}, "c": set()}
    assert wiki_graph.cmd_path(g, "a", "c") == 0
    out = capsys.readouterr().out
    assert "a -> b -> c" in out and "(2 hops)" in out
    assert wiki_graph.cmd_path(g, "c", "zzz") == 1
    assert "no path" in capsys.readouterr().out
