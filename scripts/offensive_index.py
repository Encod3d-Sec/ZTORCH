#!/usr/bin/env python3
"""offensive_index.py - vault-markdown index compiler for offensive.py.

Reads vault markdown (the hunt-core routing table, tool-page frontmatter +
usage fences, hunt-skill method blocks) into a per-engagement JSON cache
`targets/<eng>/.offensive-index.json`. offensive.py's board/next/gates build
on this cache via build_index/load_index/index_stale.

Python 3 stdlib only.
"""
import json
import re
import sys
from pathlib import Path

CACHE_NAME = ".offensive-index.json"


# --------------------------------------------------------------------------- helpers

def _read(p):
    return Path(p).read_text(encoding="utf-8", errors="ignore")


def _die(msg, code=2):
    """Hard-refusal exit (mirrors campaign.py's _die): print to stderr, exit
    non-zero. Used by the G1/G2/G3/G9 gates - never a silent drop."""
    print("offensive: %s" % msg, file=sys.stderr)
    sys.exit(code)


def _rel(p, vault_root):
    try:
        return str(Path(p).relative_to(vault_root))
    except ValueError:
        return str(p)


def _frontmatter(text):
    """key->value dict from a leading --- YAML block, or {}. Scalars only
    (all this task needs: phase, engagement_type, RoE flags)."""
    m = re.match(r"\s*---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        km = re.match(r"([A-Za-z][\w-]*):\s*(.*)$", line)
        if km:
            fm[km.group(1).lower()] = km.group(2).strip().strip('"').strip("'")
    return fm


def _section(text, heading_lower):
    """Body of the `## <heading>` section (case-insensitive), up to the next
    `## ` heading. Returns '' if the section is absent."""
    lines = text.splitlines()
    out, grab = [], False
    for ln in lines:
        if ln.startswith("## "):
            if grab:
                break
            grab = ln[3:].strip().lower().startswith(heading_lower)
            continue
        if grab:
            out.append(ln)
    return "\n".join(out).strip()


def _first_section(text, *headings_lower):
    for h in headings_lower:
        s = _section(text, h)
        if s:
            return s
    return ""


# --------------------------------------------------------------------------- parsers

def parse_routing_table(vault_root):
    """{fingerprint: {class, skill, wiki, arsenal}} from the hunt-core
    `## Routing table (machine-readable)` markdown table."""
    text = _read(Path(vault_root) / "skills" / "hunt" / "hunt-core" / "SKILL.md")
    section = _section(text, "routing table")
    rows = {}
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
        if len(cells) != 5:
            continue
        fp, cls, skill, wiki, arsenal = cells
        if fp in ("fingerprint", "") or set(fp) <= set("-: "):  # header / separator
            continue
        rows[fp] = {"class": cls, "skill": skill, "wiki": wiki, "arsenal": arsenal}
    return rows


def _first_usage_command(text):
    """First runnable line inside the fenced block under `## Core usage`
    (blanks and `#` comments skipped), or '' if absent. Matches the contract
    tests/test_tool_pages.py enforces on every real tool page."""
    body = _first_section(text, "core usage", "usage", "syntax", "commands")
    fence = re.search(r"```[^\n]*\n(.*?)```", body, re.S)
    if not fence:
        return ""
    for raw in fence.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        return line
    return ""


def parse_tool_index(vault_root):
    """{slug: {phase, invocation, page}} from wiki/tools/*.md frontmatter
    (`phase:`) + the first `## Core usage` command."""
    tdir = Path(vault_root) / "wiki" / "tools"
    idx = {}
    for md in sorted(tdir.glob("*.md")) if tdir.is_dir() else []:
        text = _read(md)
        slug = md.stem
        idx[slug] = {
            "phase": (_frontmatter(text).get("phase") or "").strip(),
            "invocation": _first_usage_command(text),
            "page": "wiki/tools/%s.md" % slug,
        }
    return idx


def parse_hunt_method(hunt_skill_dir):
    """{approach, avoid, refs} for one hunt-<x> dir. approach/avoid come from
    the `**APPROACH:**` / `**AVOID:**` labeled lines in the attack-surface
    block; refs is the space-joined `[[wikilink]]` targets from the `## Wiki`
    block. Absent fields are ''."""
    text = _read(Path(hunt_skill_dir) / "SKILL.md")

    surface = _first_section(text, "attack surface")
    approach = avoid = ""
    for label, key in (("APPROACH", "approach"), ("AVOID", "avoid")):
        m = re.search(r"\*\*%s:?\*\*[:\s]*(.+)" % label, surface)
        val = m.group(1).strip() if m else ""
        if key == "approach":
            approach = val
        else:
            avoid = val

    wiki = _section(text, "wiki")
    refs = " ".join(re.findall(r"\[\[([^\]]+)\]\]", wiki))
    return {"approach": approach, "avoid": avoid, "refs": refs}


# --------------------------------------------------------------------------- lint gate (G1)
#
# The parsers above are deliberately tolerant (a malformed row/section is just
# skipped) so they stay simple. build_index is the trust boundary: before it
# ever writes a cache, these checks re-walk the same inputs and DIE LOUD,
# naming the offending file, instead of letting a bad row silently vanish
# from the routing table.

def _lint_routing_table(vault_root):
    """Every `| ... |` line inside the hunt-core routing-table section must
    have exactly 5 columns (header/separator included) - catches a wrong
    column count, a missing cell, or a pipe embedded in a cell."""
    path = Path(vault_root) / "skills" / "hunt" / "hunt-core" / "SKILL.md"
    if not path.exists():
        return
    section = _section(_read(path), "routing table")
    rel = _rel(path, vault_root)
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = line.strip("|").split("|")
        if len(cells) != 5:
            _die("%s: routing row has %d columns, expected 5" % (rel, len(cells)))


def _lint_hunt_methods(vault_root, routing):
    """Every hunt-skill dir referenced by the routing table must carry a
    non-empty `## Wiki` section (the routing/method contract next/board rely
    on)."""
    for row in routing.values():
        skill = row.get("skill")
        if not skill:
            continue
        skill_md = Path(vault_root) / "skills" / "hunt" / skill / "SKILL.md"
        if not skill_md.exists():
            continue
        if not _section(_read(skill_md), "wiki"):
            _die("%s: missing required '## Wiki' section" % _rel(skill_md, vault_root))


def _lint_tool_index(vault_root):
    """Every wiki/tools/*.md page must carry a runnable `## Core usage`
    (or usage/syntax/commands) fenced command."""
    tdir = Path(vault_root) / "wiki" / "tools"
    if not tdir.is_dir():
        return
    for md in sorted(tdir.glob("*.md")):
        if not _first_usage_command(_read(md)):
            _die("%s: missing required '## Core usage' usage command" % _rel(md, vault_root))


# --------------------------------------------------------------------------- index

def _index_sources(vault_root):
    """Every markdown file build_index reads - used for the staleness check."""
    vault_root = Path(vault_root)
    srcs = [vault_root / "skills" / "hunt" / "hunt-core" / "SKILL.md"]
    tdir = vault_root / "wiki" / "tools"
    srcs += sorted(tdir.glob("*.md")) if tdir.is_dir() else []
    hdir = vault_root / "skills" / "hunt"
    if hdir.is_dir():
        for d in sorted(hdir.iterdir()):
            if d.is_dir() and d.name.startswith("hunt-"):
                srcs.append(d / "SKILL.md")
    return [p for p in srcs if p.exists()]


def build_index(eng_dir, vault_root):
    """Compile the routing table, tool index, and per-skill method blocks into
    a dict and write it to eng_dir/.offensive-index.json. Returns the dict."""
    eng_dir, vault_root = Path(eng_dir), Path(vault_root)
    _lint_routing_table(vault_root)
    routing = parse_routing_table(vault_root)
    _lint_hunt_methods(vault_root, routing)
    _lint_tool_index(vault_root)

    # method block per hunt-skill referenced by the routing table (dedup)
    methods = {}
    for row in routing.values():
        skill = row["skill"]
        if skill and skill not in methods:
            sdir = vault_root / "skills" / "hunt" / skill
            if (sdir / "SKILL.md").exists():
                methods[skill] = parse_hunt_method(sdir)

    idx = {
        "vault": str(vault_root),
        "routing": routing,
        "tools": parse_tool_index(vault_root),
        "methods": methods,
    }
    (eng_dir / CACHE_NAME).write_text(json.dumps(idx, indent=2, sort_keys=True))
    return idx


def load_index(eng_dir):
    """Read the cached index. Raises FileNotFoundError if never built."""
    return json.loads((Path(eng_dir) / CACHE_NAME).read_text())


def index_stale(eng_dir, vault_root):
    """True if any source markdown is newer than the cache (or no cache).
    Predicate only - Task 4 wires the enforcement."""
    cache = Path(eng_dir) / CACHE_NAME
    if not cache.exists():
        return True
    cache_mtime = cache.stat().st_mtime
    return any(p.stat().st_mtime > cache_mtime for p in _index_sources(vault_root))
