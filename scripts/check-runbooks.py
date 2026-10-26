#!/usr/bin/env python3
"""check-runbooks.py - lint workflow.md + checklist.md pairs.

Rules: every paired skill (list mirrors tests/test_runbooks.py) has both
files; every checklist `- [ ]` line declaring ` @ ` carries a `[rule:...]`
from the closed vocabulary; every workflow.md has a `## N/A escapes` section
when its checklist can tick `[-]`. Exit 1 on violation.
"""
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRED = [
    "skills/workflow/js-extractor", "skills/workflow/workflow-brain",
    "skills/workflow/active-workflow", "skills/workflow/osint-workflow",
    "skills/orchestrate/engage", "skills/orchestrate/offensive",
    "skills/orchestrate/kali-seat", "skills/platform/wiki",
    "skills/platform/graphify", "skills/research/searchsploit",
    "skills/research/nday", "skills/research/research",
    "skills/research/wiki-arsenal", "skills/research/wiki-recon",
    "skills/surface/caido", "skills/surface/interceptor",
    "skills/surface/js-discover", "skills/surface/fuzz",
]

VOCAB = {"sha256_pass", "table_min_rows", "no_cell_contains", "md_table_headers",
         "md_table_or_explicit_empty", "dir_count_matches", "all_exist",
         "contains_lane_id"}

_RULE = re.compile(r"\[rule:\s*([^\]=]+(?:=[^\]]*)?)\]")


def main():
    bad = []
    for rel in PAIRED:
        d = os.path.join(VAULT, rel)
        wf, ckl = os.path.join(d, "workflow.md"), os.path.join(d, "checklist.md")
        for f in (wf, ckl):
            if not os.path.isfile(f):
                bad.append("%s: missing %s" % (rel, os.path.basename(f)))
        if not (os.path.isfile(wf) and os.path.isfile(ckl)):
            continue
        ctext = open(ckl, encoding="utf-8", errors="replace").read()
        wtext = open(wf, encoding="utf-8", errors="replace").read()
        for line in ctext.splitlines():
            s = line.strip()
            if not s.startswith("- ["):
                continue
            if " @ " not in s:
                continue
            rules = [m.group(1).split("=")[0].strip() for m in _RULE.finditer(s)]
            if not rules:
                bad.append("%s: '@' line without [rule:...]: %s" % (rel, s[:60]))
            for r in rules:
                if r not in VOCAB:
                    bad.append("%s: rule '%s' outside closed vocabulary" % (rel, r))
        if "- [-]" in ctext and "## N/A escapes" not in wtext:
            bad.append("%s: N/A ticks but workflow.md has no '## N/A escapes'" % rel)
    if bad:
        for b in bad:
            print("RUNBOOK FAIL: %s" % b)
        sys.exit(1)
    print("runbooks OK (%d paired skills)" % len(PAIRED))


if __name__ == "__main__":
    main()
