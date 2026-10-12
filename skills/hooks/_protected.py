"""Shared protected-file lists (dedup across hooks + scripts).

PROTECTED_CONFIG: harness routing/config files whose writes need operator
consent (session-guard protected-instruction gate).
referenced(vault): {relpath: text} of the files that route skills; a skill
named in them is protected from archive/delete (curator, skill_manage).
Callers apply their own membership test (token set vs substring) so each
keeps its original strictness.
"""
import os

PROTECTED_CONFIG = ("/AGENTS.md", "/.zcode/config.json", "scripts/triggers.json",
                    "scripts/routing.json", "setup/install-hooks.sh", "scripts/check-hooks.py")

REF_SOURCES = ("scripts/triggers.json", "scripts/routing.json",
               "skills/workflow/engage/SKILL.md")


def referenced(vault):
    """{relpath: text} for each existing routing file under vault."""
    out = {}
    for f in REF_SOURCES:
        p = os.path.join(vault, f)
        if os.path.exists(p):
            out[f] = open(p, encoding="utf-8", errors="ignore").read()
    return out
