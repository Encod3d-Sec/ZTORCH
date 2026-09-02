"""W2-9: every place that triggers a post-edit wiki reindex must run BOTH `qmd update` (text
index) and `qmd embed` (semantic vectors) -- omitting embed leaves new/edited pages invisible to
qmd_query (semantic search), the framework's own documented primary search tool."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_wiki_reindex_hook_runs_embed():
    src = (ROOT / "skills/hooks/wiki-reindex.py").read_text()
    assert "qmd update" in src and "qmd embed" in src, (
        "wiki-reindex.py must run both qmd update AND qmd embed")


def test_engagement_init_nudge_mentions_embed():
    src = (ROOT / "skills/hooks/engagement-init.py").read_text()
    # the SessionStart nudge text itself (not just any mention elsewhere in the file)
    assert "qmd update && qmd embed" in src or "qmd update` and `qmd embed" in src, (
        "engagement-init.py's wiki-changed nudge must tell the operator to run embed too")


def test_wiki_promote_reindex_runs_embed():
    src = (ROOT / "scripts/wiki-promote.py").read_text()
    assert 'subprocess.run(["qmd", "update"' in src
    assert 'subprocess.run(["qmd", "embed"' in src or '"qmd", "update", "&&", "qmd", "embed"' in src, (
        "wiki-promote.py's reindex() must also run qmd embed after a successful promotion")
