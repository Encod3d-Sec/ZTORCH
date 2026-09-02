"""Task 15: the LIVE doc/prose set points at the /offensive driver, not the retired one.

Task 14 retired the per-type workflow SKILLS and their dirs; its grep (test_workflow_cleanup)
scanned skills/ + three docs but NOT setup/templates. Task 15 reconciles the remaining prose
refs across the full live doc set - the surviving SKILL.md files, the engagement scaffold
templates, AGENTS.md, and the two live docs - so nothing still tells the reader to run the
retired driver.

Scope is DOC/PROSE only: .py files (the executable harness) and docs/superpowers/ (historical
records) are never scanned.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Live doc set: surviving process skills, the scaffold templates, AGENTS.md, the two live docs.
SKILL_GLOBS = ["skills/**/SKILL.md"]
TEMPLATE_GLOBS = ["setup/templates/*.md", "setup/templates/*/*.md"]
DOC_FILES = ["AGENTS.md", "README.md", "docs/auto-triggers.md", "docs/skill-map.md"]

# Unambiguous retired-driver forms. Deliberately NOT matched: `wiki-arsenal`, the driver
# subcommand `offensive.py coverage`, the `[[crypto-ctf-workflow]]` wikilink, and bare table
# column names like `next-move` (a Killchain.md header, not a skill ref).
FORBIDDEN = [
    r"Skill\(arsenal\)",
    r"Skill\(coverage\)",
    r"Skill\((?:bb|ctf|pt)-workflow\)",
    r"/(?:bb|ctf|pt)-workflow\b",    # the slash-command form (README's own Quickstart used this)
    r"\bcampaign-health\b",         # retired doctor skill, as a Skill/health-check ref
    r"campaign\.py",                # prose invocations of the retired driver
    r"campaign\s*\(autonomous workflow driver\)",   # the Layout-table phrasing, stale as of Wave 2
]


def _iter_files():
    seen = set()
    for pat in SKILL_GLOBS + TEMPLATE_GLOBS:
        for f in REPO.glob(pat):
            if f.is_file() and "superpowers" not in f.parts and f not in seen:
                seen.add(f)
                yield f
    for rel in DOC_FILES:
        f = REPO / rel
        if f.is_file() and f not in seen:
            seen.add(f)
            yield f


def test_no_prose_refs_to_retired_driver():
    pats = [re.compile(p) for p in FORBIDDEN]
    hits = []
    for f in _iter_files():
        text = f.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            for pat in pats:
                if pat.search(line):
                    hits.append(f"{f.relative_to(REPO)}:{i}: {line.strip()[:100]}")
    assert not hits, "retired-driver refs in the live doc set:\n" + "\n".join(hits)
