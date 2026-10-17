"""Relational-question nudge: hunt-trigger.py advisory tier for Skill(graphify).

The relational_triggers tier in skills/exploit/hunt/triggers.json is page-noun-gated:
engagement prose ("path between the two hosts") must NOT fire it, only
wiki-page relational phrasing may.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "skills" / "hooks" / "hunt-trigger.py"


def _fire(prompt):
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"prompt": prompt}), capture_output=True, text=True)
    return p.stdout


def test_relational_question_nudges_graphify():
    out = _fire("how do the pages for kerberos attacks and golden tickets connect")
    assert "Skill(graphify)" in out
    assert "qmd answers content" in out  # carries the which-lane rule


def test_hub_orphan_terms_nudge_graphify():
    out = _fire("which wiki pages are orphan pages nobody links to")
    assert "Skill(graphify)" in out


def test_engagement_path_prose_does_not_fire():
    out = _fire("find the path between the two hosts and pivot")
    assert "graphify" not in out


def test_plain_prompt_stays_quiet():
    out = _fire("continue with the ingest")
    assert "graphify" not in out
