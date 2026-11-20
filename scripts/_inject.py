#!/usr/bin/env python3
"""_inject.py - shared injection screen (P3 WS1).

Screens markdown prose for instruction-shaped text addressed to the agent
(indirect prompt injection) at the two trust boundaries: finding cards
(find-lint, advisory) and memory writes (wiki-stage, quarantine). Fenced
code blocks are exempt - payloads are the product.

Pattern battery: scripts/inject-patterns.json (operator-editable, one
rationale per row). Fail-open: a missing/corrupt file or a bad regex row
disables the screen with one stderr note, never an error.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
PATTERNS_PATH = os.path.join(HERE, "inject-patterns.json")

_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING_RE = re.compile(r"^#+\s")


def load_patterns(path=None):
    """(patterns, off_note): compiled [(regex, rationale)] rows, and "" when
    the battery loaded. Any failure disables the screen (fail-open)."""
    if path is None:
        path = PATTERNS_PATH
    try:
        data = json.loads(open(path, encoding="utf-8").read())
    except (OSError, ValueError):
        return [], "inject-patterns.json missing/corrupt - screen off (fail-open)"
    rows = data.get("patterns") if isinstance(data, dict) else None
    if not isinstance(rows, list):   # wrong-shape battery = corrupt -> fail open
        rows = []
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        try:
            out.append((re.compile(str(row.get("re", ""))),
                        str(row.get("rationale", ""))))
        except re.error:
            print("inject-patterns.json: bad regex in pattern %d - skipped" % i,
                  file=sys.stderr)
    return out, ("" if out else "inject-patterns.json loaded no patterns - screen off")


def screen(text, patterns=None):
    """[(line_no, section, line_text, rationale)] for prose hits only.
    Fenced blocks and their content are exempt; section is the nearest
    preceding heading text, or 'frontmatter' before the first heading."""
    if patterns is None:
        patterns, _ = load_patterns()
        if not patterns:
            return []
    hits, in_fence, mark, section = [], False, "", "frontmatter"
    for n, ln in enumerate(text.splitlines(), 1):
        m = _FENCE_RE.match(ln)
        if m:
            if not in_fence:
                in_fence, mark = True, m.group(1)[0] * 3
            elif ln.lstrip().startswith(mark):
                in_fence = False
            continue
        if in_fence:
            continue
        for rx, why in patterns:
            if rx.search(ln):
                hits.append((n, section, ln.strip(), why))
                break
        if _HEADING_RE.match(ln):   # heading is scanned, then opens the next section
            section = ln.lstrip("#").strip() or section
    return hits
