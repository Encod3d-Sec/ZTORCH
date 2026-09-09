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


def _promote(tmp, target_rel, page_text, body):
    """Run promote_one on a staged technique candidate; returns (status, stdout)."""
    import io
    import contextlib
    wiki = os.path.join(tmp, "wiki")
    inbox = os.path.join(tmp, "inbox")
    os.makedirs(os.path.join(wiki, os.path.dirname(target_rel)), exist_ok=True)
    os.makedirs(inbox, exist_ok=True)
    target = os.path.join(wiki, target_rel)
    open(target, "w").write(page_text)
    cand = os.path.join(inbox, "slug-t.md")
    open(cand, "w").write(
        "---\nslug: slug-t\nkind: technique\ntarget_page: %s\n---\n\n%s"
        % (target_rel, body))
    # leak_check runs check-leaks against the real vault; stub it fail-open
    wiki_promote.leak_check = lambda *a, **k: (True, "")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        st = wiki_promote.promote_one(cand, {"slug": "slug-t", "kind": "technique",
                                             "target_page": target_rel},
                                      body, inbox, tmp)
    return st, buf.getvalue()


def test_tools_page_without_usage_fence_refused(tmp_path):
    st, out = _promote(str(tmp_path), "tools/fenceless.md",
                       "---\ntitle: x\n---\n\n## What it is\n\nno fence\n",
                       "## Gotchas\n\nbody only\n")
    assert st == "refused" and "Core usage" in out


def test_tools_page_fence_in_body_passes(tmp_path):
    st, _ = _promote(str(tmp_path), "tools/newtool.md",
                     "---\ntitle: x\n---\n\n## What it is\n\npage\n",
                     "## Core usage\n\n```sh\nnewtool --scan T\n```\n")
    assert st == "promoted"


def test_nontools_target_unaffected(tmp_path):
    st, _ = _promote(str(tmp_path), "techniques/web/page.md",
                     "---\ntitle: x\n---\n\n## What it is\n\nno fence\n",
                     "## Gotchas\n\nbody\n")
    assert st == "promoted"
