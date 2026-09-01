"""Task 14: the 7 skills replaced by /offensive are retired, with no live references left.

Retired: bb-workflow, ctf-workflow, pt-workflow (-> Skill(offensive)/offensive.py),
arsenal (-> wiki-arsenal), next-move (-> offensive.py ranking), coverage (-> offensive.py
coverage), campaign-health (-> offensive-doctor).

The "no live refs" grep is deliberately narrow: it matches only unambiguous skill-invocation
FORMS, so it does not false-fire on the English word "coverage", the driver subcommand
`offensive.py coverage`, the `next_move.py` script, or `wiki-arsenal`.
"""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

RETIRED_DIRS = [
    "skills/workflow/bb-workflow",
    "skills/workflow/ctf-workflow",
    "skills/workflow/pt-workflow",
    "skills/workflow/arsenal",
    "skills/workflow/next-move",
    "skills/workflow/coverage",
    "skills/workflow/campaign-health",
]

# Scan roots (dispatch scope): skills/ + these three docs. docs/superpowers/ is a
# historical record and is never scanned (it is not under any root below).
SCAN_ROOTS = ["skills", "AGENTS.md", "docs/auto-triggers.md", "docs/skill-map.md"]

# Unambiguous invocation forms only. For coverage we check ONLY Skill(coverage) and a dead
# workflow/coverage path -- bare "coverage", "/coverage" (capture/coverage), and the backticked
# `coverage` driver subcommand are all legitimate. For arsenal the literal `arsenal` / /arsenal /
# Skill(arsenal) never occur inside wiki-arsenal (the preceding char there is '-'/backtick-then-w).
FORBIDDEN = [
    r"Skill\(bb-workflow\)", r"Skill\(ctf-workflow\)", r"Skill\(pt-workflow\)",
    r"Skill\(campaign-health\)", r"Skill\(arsenal\)", r"Skill\(next-move\)", r"Skill\(coverage\)",
    r"`bb-workflow`", r"`ctf-workflow`", r"`pt-workflow`", r"`campaign-health`",
    r"`next-move`", r"`arsenal`",
    # NB: no bare "/arsenal" -- it false-matches the /opt/arsenal tooling path and the
    # "wiki/arsenal-first" gate name; Skill(arsenal) and `arsenal` cover the real refs.
    r"/bb-workflow", r"/ctf-workflow", r"/pt-workflow", r"/campaign-health",
    r"workflow/bb-workflow", r"workflow/ctf-workflow", r"workflow/pt-workflow",
    r"workflow/campaign-health", r"workflow/arsenal", r"workflow/next-move", r"workflow/coverage",
]


def _iter_files():
    for root in SCAN_ROOTS:
        p = REPO / root
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and "superpowers" not in f.parts:
                    yield f


def test_retired_skills_absent():
    present = [d for d in RETIRED_DIRS if (REPO / d).exists()]
    assert not present, f"retired skill dirs still present: {present}"


def test_no_live_refs_to_retired():
    pats = [re.compile(p) for p in FORBIDDEN]
    hits = []
    for f in _iter_files():
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for pat in pats:
                if pat.search(line):
                    hits.append(f"{f.relative_to(REPO)}:{i}: {line.strip()[:100]}")
    assert not hits, "live references to retired skills:\n" + "\n".join(hits)
