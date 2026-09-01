"""Every hunt-* skill carries a canonical `## Wiki` block and a machine-readable
method block (APPROACH/AVOID/REFS) the offensive driver's `next` prints.

Runs against the REAL vault (repo root) so the 26 shipped skills stay normalized:
- a non-empty `## Wiki` section,
- every `[[wikilink]]` in that section resolves to a real wiki/**.md page,
- no ambiguous bare `[[xss]]` (must be pinned, e.g. [[techniques/web/xss]]),
- parse_hunt_method returns non-empty approach AND avoid AND refs (the driver
  reads approach/avoid from the `## Attack surface` section, refs from `## Wiki`).

hunt-core is the discipline hub (no vuln-class attack-surface / method block); it
is held only to the ## Wiki + link-resolution contract.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive  # noqa: E402

WIKI = ROOT / "wiki"
HUNT_DIRS = sorted(p for p in (ROOT / "skills" / "hunt").glob("hunt-*") if p.is_dir())
HUB = "hunt-core"


def _resolvable_targets():
    """Every string a `[[target]]` may take and still name a real wiki page:
    the basename, the wiki-relative path, and the wiki/-prefixed path."""
    s = set()
    for md in WIKI.rglob("*.md"):
        rel = md.relative_to(WIKI).with_suffix("")
        s.add(md.stem)              # [[ssrf]]
        s.add(str(rel))             # [[techniques/web/xss]]
        s.add("wiki/" + str(rel))   # [[wiki/payloads/ssrf]] (legacy form)
    return s


TARGETS = _resolvable_targets()


def _wiki_links(hunt_dir):
    text = offensive._read(hunt_dir / "SKILL.md")
    wiki = offensive._section(text, "wiki")
    return wiki, [m.split("|")[0].strip() for m in re.findall(r"\[\[([^\]]+)\]\]", wiki)]


@pytest.mark.parametrize("hunt_dir", HUNT_DIRS, ids=lambda p: p.name)
def test_every_hunt_has_canonical_wiki(hunt_dir):
    wiki, links = _wiki_links(hunt_dir)
    assert wiki, "%s: missing '## Wiki' section" % hunt_dir.name

    for link in links:
        assert link != "xss", (
            "%s: ambiguous bare [[xss]] - pin to [[techniques/web/xss]]" % hunt_dir.name
        )
        assert link in TARGETS, "%s: [[%s]] does not resolve to a wiki page" % (
            hunt_dir.name, link,
        )

    if hunt_dir.name == HUB:
        return  # discipline hub: no vuln-class method block

    m = offensive.parse_hunt_method(hunt_dir)
    assert m["approach"], "%s: empty APPROACH (attack-surface section)" % hunt_dir.name
    assert m["avoid"], "%s: empty AVOID (attack-surface section)" % hunt_dir.name
    assert m["refs"], "%s: empty REFS (no wikilinks in ## Wiki)" % hunt_dir.name
