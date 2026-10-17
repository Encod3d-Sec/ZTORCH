---
name: ponytail
description: >
  Lazy senior dev discipline for ALL code written in this repo (scripts/,
  skills/, setup/): YAGNI ladder before every diff, ponytail: marker
  for known ceilings, deletion over addition. Use when writing, reviewing, or
  editing any Torchv2 framework code, and when /ponytail-debt or
  /ponytail-review fire.
metadata:
  hermes:
    tags: [ponytail, lean, doctrine]
    related_skills: [ponytail-debt, ponytail-review]
---

# ponytail

Lazy means efficient, not careless. The best code is the code never written.

Before writing any code in this repo, stop at the first rung that holds:

1. Does this need to be built at all? (YAGNI)
2. Does it already exist in this codebase? Reuse the helper, util, or pattern
   that is already here, do not re-write it.
3. Does the standard library already do this? Use it.
4. Does a native platform feature cover it? Use it.
5. Does an already-installed dependency solve it? Use it.
6. Can this be one line? Make it one line.
7. Only then: write the minimum code that works.

The ladder runs AFTER you understand the problem, not instead of it: read the
task and the code it touches, trace the real flow end to end, then climb.
A small diff you do not understand is laziness dressed up as efficiency.

Bug fix = root cause, not symptom: grep every caller of the function you touch
and fix the shared function once. One guard there is a smaller diff than one
per caller, and patching only the path the report names leaves a sibling
caller still broken.

## Rules

- No abstractions that were not explicitly requested.
- No new dependency if it can be avoided.
- No boilerplate nobody asked for.
- Deletion over addition. Boring over clever. Fewest files possible.
- Shortest working diff wins, but only once you understand the problem.
- Question complex requests: "Do you actually need X, or does Y cover it?"
- Pick the edge-case-correct option when two stdlib approaches are the same
  size; lazy means less code, not the flimsier algorithm.

## The ponytail: marker

Mark deliberate simplifications that cut a real corner with a known ceiling
(global lock, O(n^2) scan, naive heuristic) with a `ponytail:` comment naming
the ceiling and the upgrade path. These are DEBT, tracked by the sweep:
`python3 scripts/ponytail-debt.py` lists every marker; the close-out hook
nudges the sweep when framework files changed since the last stamp.

## Not lazy about

Understanding the problem, input validation at trust boundaries, error
handling that prevents data loss, security, anything explicitly requested.
Non-trivial logic leaves ONE runnable check behind: the smallest thing that
fails if the logic breaks (assert-based self-check or one small test; no
frameworks, no fixtures). Trivial one-liners need no test.

## Companion commands

- `/ponytail-debt` - run `python3 scripts/ponytail-debt.py` (marker ledger
  sweep; refresh the stamp with `--stamp` once swept).
- `/ponytail-review` - diff-scoped over-engineering review of uncommitted
  framework changes: one-line findings, applies nothing.
