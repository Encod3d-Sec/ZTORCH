---
name: engagement-retro
description: "Use when an engagement, campaign, or framework push closes: extract drifts + fixes into routed actions (skill patches, memory entries, wiki staging, scripts). Turns repeated mistakes into standing fixes."
metadata:
  hermes:
    tags: [retrospective, closeout, drift-analysis, self-learning, torchv2]
    related_skills: [evidence, triage, walkthrough, wiki, ponytail-review]
---

# Engagement Retrospective

The close-out retro: after a completed engagement (or campaign, or
framework push), record where execution drifted from prescribed
discipline and what harness or skill change each drift produced.
The retro is the mechanism that turns repeated mistakes into standing
fixes; without it the same drift recurs on the next engagement.

Fires as the final link of the closeout chain
(`CLOSEOUT_CHAINS` in scripts/offensive.py: triage -> evidence ->
walkthrough -> THIS SKILL).

## Wiki

Hub: [[methodology-moc]] - Primary page: [[multi-agent-campaign-orchestration]]
Anchors: [[bug-hunting-methodology]], [[vulnerability-reports]]
**REFS:** [[multi-agent-campaign-orchestration]]

## Paths (binding - define once at the top of the run notes)

    # seat side (WSL via /mnt/c; ported 2026-10-17) - engagement tree is
    # DOUBLE-NESTED in VMshare:
    ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>
    # repo tree (admin/ledgers):
    REPO=/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch
    # the retro log itself (generic, codenamed, never client-named):
    session/retro-log.md (append; harness-side, shared across engagements)

Retro outputs NEVER land under targets/<eng>/ (client tree) - the retro
is harness knowledge, written generic.

## When to Use

- An engagement, campaign, or multi-session task just completed
  (success or failure)
- The user asks "what went wrong", "do a retro", "why did that take so
  long"
- A recurring mistake was noticed mid-work and should be captured
  before it is forgotten

Don't use for: single bugs with a clear root cause (systematic
debugging); code review of changes (ponytail-review).

## Where the outputs land (one layer per output)

Route each output to the layer that will actually re-surface it:

| Output | Land it in | Why |
|---|---|---|
| A discipline fix for a recurring situation | the SKILL itself via `skill_manage` (patch the skill whose mandate was missed) | the fix loads exactly when the situation recurs |
| A cross-session fact (env quirk, seat config, model behavior) | `memory` tool (Hermes GUI seat; wsl claude cli: project memory/CLAUDE.md) - one declarative entry | auto-injected every session, no rereading needed |
| "Have we hit this before" questions | `session_search` (Hermes GUI seat; wsl claude cli: transcript/session recall) | transcript recall beats archaeology |
| A reusable offensive technique (generic, leak-checked) | wiki via `scripts/wiki-stage.py` -> `scripts/wiki-promote.py` | the only sanctioned path into the wiki |
| The human-readable audit trail | session/retro-log.md (append, generic wording only) | history stays greppable |
| A new mechanical check | a script in scripts/ (falsifiable, exit 0 on pass, tested) | code beats prose for mechanical gates |

## Procedure

1. **Collect the evidence first.** Read the session transcript, tool
   call logs, state files, and any drift/telemetry markers BEFORE
   writing anything. Do not reconstruct from memory. Completion
   criterion: you can cite concrete tool calls or file states for
   every claim.
2. **List each drift with a root cause, not a symptom.** For each:
   what was supposed to happen (which skill or rule), what actually
   happened, and WHY the discipline failed (missing rule, rule ignored
   under momentum, tooling gap, or environment failure). Name the
   failure's owner honestly: agent drift, harness gap, or environment.
3. **Route each drift to exactly one action:**
   - Skill fix: the rule existed but was under-specified or in the
     wrong place.
   - New mechanism (hook/script/checklist item): the failure is
     mechanically detectable - only if deterministic; judgement calls
     stay as skill prose.
   - Log-only negative knowledge: a rabbit hole worth recording so it
     is never re-entered (Deadends.md pattern).
   - No change: the reflex fired and was ignored; note it as operator
     discipline.
4. **Also record what went right.** Validated disciplines need
   confirmation too, or a later cleanup pass deletes them as unused -
   a past de-bloat deleted two capture reflexes a prior retro had
   proven necessary, and the drifts recurred.
5. **Mark each fix DONE / PROPOSED / DEFERRED.** Small fixes land this
   session with tests or a skill edit; larger mechanisms go to the
   operator as a proposal with a one-line rationale.
6. **Write generic, never client-specific.** Codename the engagement;
   no hosts, IPs, creds, or client-identifying detail, so the retro
   file is safe to keep and share. check-leaks before any push.
7. **Prefer the smallest fix that closes the class.** A tightened
   skill line beats a new hook; a new hook beats a new subsystem.
   Complex failures get a root-cause pass before a fix: one retro
   found the "root cause" was a regression from an earlier cleanup,
   not missing prose.

## Recurring patterns worth checking for

- Abandoned the prescribed driver/plan once manual work started
  flowing (the meta-drift; the most expensive one in the source data)
- Grep-as-read on results that needed a full read (the load-bearing
  line is what grep skips)
- Serial work that should have been a parallel fan-out
- Advisory nudges ignored under momentum; capture deferred to close-out
- Silent tooling failure read as a negative result (tool never ran vs
  ran and found nothing)
- Re-deriving from memory what a reference page or skill already
  documents
- Validator matched its own scaffold: a fill-detector regex whose `\S`
  can cross a newline matches the template's next section (an HTML
  comment marker) and passes on a blank form. Anchor same-line checks
  with `[ \t]+\S`, never `\s*\S`
- Evidence detector written against fixture shapes only: galleries use
  named alt text (`![label](path)`), captures live in per-lane
  subdirs - test detectors against a REAL completed artifact, not only
  synthetic fixtures shaped like the detector expects

## Verification

- Every drift in the retro names a root cause and an action with a
  status.
- Every DONE fix has a concrete artifact: a skill edit, a test, or a
  file change.
- No client-identifying data anywhere in the retro file.
- Close-out ordering: stamp the completion marker AFTER the last write
  to the engagement's state/walkthrough files. Those gates re-arm when
  the marker is older than state.md (staleness rule), so
  marker-then-document ordering re-arms the nag even though the work
  is done - if a hook nags about an already-done step, check the
  detector's freshness rule and re-stamp instead of redoing work.
- Retro applies to framework-improvement sessions too, not only field
  engagements: harness edits, gate fixes, and doctrine ports get a
  retro-log entry with their test evidence, and any nag that misfired
  gets its detector root-caused (a nag that is wrong about a completed
  task is a detector bug, not operator drift).

## Exit artifact

Appended session/retro-log.md entry (codename, drifts + root causes +
routed actions + statuses), plus whatever the routing table landed
(skill patches committed, memory entries saved, wiki candidates
staged). The closeout chain is DONE when the retro entry exists and
every PROPOSED item is parked with its owner.

## Stop conditions

Retro entry appended, every PROPOSED item parked with an owner, no
unchecked boxes above REVIEW, nothing written into skill dirs
(skills/workflow/closeout/engagement-retro/ stays untouched). hunt-core
stop conditions fire unchanged for any field-engagement content the
retro touches.
