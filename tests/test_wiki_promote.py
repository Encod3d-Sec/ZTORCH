import importlib.util
import os
import tempfile

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "wiki_promote", os.path.join(VAULT, "scripts", "wiki-promote.py"))
wiki_promote = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wiki_promote)


def test_strip_empty_sections_drops_stub_stack():
    scaffold = ("---\ntitle: x\n---\n\n## What it is\n\n## Rule 1\n\n"
                "## Rule 2\n\n## Rule 3\n\n## Rule 4\n\n")
    got = wiki_promote._strip_empty_sections(scaffold)
    assert got.rstrip() == "---\ntitle: x\n---"
    assert "##" not in got


def test_strip_empty_sections_keeps_real_sections():
    page = "## What it is\n\nreal body\n\n## Rule 1\n\nmore body\n"
    assert wiki_promote._strip_empty_sections(page) == page


def test_merge_section_dedups_scaffold_stubs():
    with tempfile.TemporaryDirectory() as d:
        target = os.path.join(d, "page.md")
        open(target, "w").write("---\ntitle: x\n---\n\n## What it is\n\n## Rule 1\n\n")
        wiki_promote.merge_section(target, "## What it is\n\nbody\n", "slug-x")
        out = open(target).read()
        assert out.count("## What it is") == 1
        assert "## Rule 1" not in out  # empty stub dropped, body did not carry it
        assert "body" in out and "<!-- promoted-slug: slug-x -->" in out
