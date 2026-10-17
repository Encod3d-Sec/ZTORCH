---
name: ponytail-review
description: >
  Diff-scoped over-engineering review: "/ponytail-review", before committing
  framework changes, or when the close-out hook nudges it. One-line findings
  over the uncommitted diff, applies nothing - the operator decides.
metadata:
  hermes:
    tags: [ponytail, review, diff-quality]
    related_skills: [ponytail, ponytail-debt]
---

# ponytail-review

Review the uncommitted framework diff (scripts/, skills/, setup/)
against the ponytail ladder (Skill(ponytail)). From the Torchv2 root:

```
git diff --stat
git diff -- scripts/ skills/ setup/
```

For every hunk, one-line findings only:

- `UNNEEDED <file>:<line>` - the rung-1/2 finding: built at all / already
  exists in-repo (name the existing helper).
- `ABSTRACTION <file>:<line>` - an abstraction nobody asked for.
- `DEPENDENCY <file>:<line>` - new dependency the stdlib covers.
- `BIGGER-DIFF-THAN-NEEDED <file>:<line>` - a one-guard-shared-function fix
  exists with a smaller diff.
- `MISSING-MARKER <file>:<line>` - a deliberate corner cut with no
  `ponytail:` comment naming the ceiling.
- `MISSING-CHECK <file>:<line>` - non-trivial logic with no runnable check.

Applies NOTHING. Report, stop. The operator (or a follow-up request) applies.

For repo-wide (not diff-scoped): run `/ponytail-audit` shape instead - rank
every finding biggest-cut-first across the whole repo.
