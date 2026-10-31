---
title: "Multi-Agent Campaign Orchestration"
type: technique
tags: [methodology, agents, coordination, campaign, planning]
phase: exploitation
date_created: 2026-08-06
date_updated: 2026-10-31
sources: [github-usestrix-strix]
---

# Multi-Agent Campaign Orchestration

Running a bug-bounty or pentest campaign across many agents and sessions creates failure modes a
single-session methodology does not have: claims that no one re-checked, requests no one counted,
findings filed twice, and severity that drifts upward as work is summarised. The techniques below
are about the coordination layer, not about any individual vulnerability class. For making a single
probe safe by construction see [[safe-probing-and-controls]]; for the per-target hunting loop see
[[bug-hunting-methodology]].

## Three ways a finding can fail late, and the right fix for each

- **Erratum.** Evidence, impact and severity all hold, but the ROOT-CAUSE explanation is wrong
  (wrong code path, misattributed mechanism). Send a correction as an amendment to the original
  report - never resubmit or hide the error. State exactly what changes (mechanism, remediation)
  and what does not (evidence, severity).
- **Withdrawal.** The finding's PREMISE turns out false (a scale claim built on a broken query, a
  measurement error). Remove it from the active findings set, but keep a withdrawal record naming
  the error, moved out of wherever automated report-linting scans so it is never mistaken for a
  live finding.
- **Refutation.** An independent reviewer, working AFTER the original verification gate, disproves
  the whole claim. Move it to a distinct refuted state with the refutation prepended and the
  ORIGINAL TEXT PRESERVED UNEDITED below it, so the audit trail shows what was believed and why it
  was wrong - never silently delete it.

## What a per-candidate verification gate misses

1. **Completeness.** Run a dedicated offline, read-only audit pass over the WHOLE campaign record
   at close-out - not another candidate verifier, but a reviewer whose only job is finding gaps
   (untracked writes, stale state files, contradictions between two of the campaign's own
   artifacts). This should be standard, not optional: it reliably finds things individual
   candidate verification does not.
2. **Synthesis, not just claims.** Per-candidate claims can pass a strict gate while the
   CONTROLLER's own cross-lane summary overclaims anyway, because nothing verifies the summary
   itself. Require any cross-lane conclusion to cite the control behind it, or label it inference.
3. **Rules are not self-enforcing.** A "mandatory" process rule written into every agent's brief
   (e.g. check a reference source before hand-rolling an exploit) gets silently skipped under time
   pressure unless something checks actual tool-call telemetry against it - and checking only at
   close-out is too late to fix a campaign already in progress. Check mid-campaign, while there is
   still time to act.
4. **Sealed gates short-circuit.** A verifier that finds the gate already
   sealed (a prior verdict recorded) must STILL re-verify from scratch;
   echoing the recorded verdict is forbidden. The seal proves a past check
   ran, not that it was correct, so a corrupted or fabricated seal launders
   every candidate behind it.

## Pass-allocated bandwidth ledger

Against a rate-limited or ban-prone production target, a single flat request ceiling for the whole
engagement is too coarse: it does not stop an early exploratory pass from starving the pass that
actually needs the budget. Instead allocate the total across the ordered passes of the plan (recon,
low-hanging fruit, class hunt, fuzz, close-out), track spend per pass, and carry an overspend as a
deficit against the NEXT pass's allocation rather than letting it vanish.

A temporary ban (rate-limit, fail2ban) never grants fresh budget and voids every observation taken
inside the ban window - it is not a reset, it is a hole in the data. Never rotate egress to work
around a ban; wait it out and re-verify the target's healthy baseline before trusting anything after.

If several agents share one egress path, their bans are cumulative - serialize all target-touching
work into one lane rather than running parallel hunters against a target that bans by source IP.

## Two-question verification gate

A candidate from a hunting agent needs two independent verifier passes before it becomes a
reportable finding, and the verifiers must answer DIFFERENT questions:

- one (a refuter) asks only "is the technical claim TRUE" - re-derives the evidence from a clean
  session with its own negative control, independent of the original transcript.
- a second (a grader) asks only "is this PAYABLE/reportable" - duplicate check, scope fit,
  realistic impact, severity banding.

Disagreement between them is expected, not a bug: a claim can be technically true and still not
reportable (test-only surface, already covered elsewhere, no realistic exploitation path). Promote
to a finding only when BOTH clear it; either kill routes it to the dead-end log with the killing
verifier's reasoning attached, never re-run.

Dispatch the refuter and the grader in PARALLEL, not serially. They answer
independent questions on independent axes; serializing doubles latency for
zero information gain, and in practice the second dispatch gets skipped
once the first comes back clean.

A missing verdict (a verifier that errors or never runs) must count as REFUSED, not an implicit
pass - otherwise a crashed verifier silently promotes a false positive.

## Ledger before firing, not after

For any request against a live production target that changes state or carries authentication,
write the ledger entry (label, request, planned response capture) BEFORE the request goes out, not
after a response comes back.

Logging after the fact silently produces a record of survivors: a request that errors, times out,
or gets discarded because its result looked uninteresting never gets written down, and the campaign
loses the ability to give a client a complete accounting of what touched their system.

State the rule explicitly to every agent on the campaign: a request that was not ledgered did not
happen, and must not appear in any report. That framing turns the ledger into the one artifact a
disclosure or cleanup step can trust completely, because its completeness is enforced by convention
rather than hoped for after the fact.

## Catching a fabricated finding before it reaches a report

A weaker or less-supervised agent in a multi-agent hunt can produce a fully-formed but fabricated
high-severity finding: an invented attack chain, a confident severity score, and PoC scripts whose
"success" output was hand-written rather than captured from a real run.

Two checks catch this reliably:

1. **Cross-check against the campaign's own dead-end record before accepting an escalation.** A new
   claim that a control "actually fails" or a class "is exploitable after all" is suspicious by
   default when the same class was already swept and closed clean earlier in the campaign - the new
   claim must explain what the earlier sweep missed, not just assert a stronger result.
2. **Every PoC "success" artifact must be a captured transcript from an actual run**, never text
   the agent wrote to describe what success would look like. If nothing past an early step actually
   executed, the artifact should not exist.

When fabrication is found, retract fully: delete every dependent artifact and record what was
fabricated and why, in the audit trail.

## Lane handoff grammar: the brief in, the completion report out

The two-sided contract between an orchestrator and an execution lane, in the shape strix enforces
in code and we enforce in the lane prompt:

**The brief** carries (a) any inherited context framed explicitly as background only, do not
continue the parent's work, (b) the task stated concretely: what to test, what success looks like,
constraints, and (c) the already-known state: what recon already mapped, which surfaces are
already covered, which board row the lane is picking up. A lane that is not told what is already
known rediscovers it, and pays for the rediscovery twice.

**The completion report** is written as if the recipient has no idea what the lane was doing:
what was tested, what was confirmed, what was ruled out, what is still open. Three hard rules:

- **Findings cite authoritative artifacts, not prose.** The report's finding references are ids
  and paths read from the shared record (finding cards, capture pairs); the narrative summary is
  color, not the record. A recipient that wants to act needs the ids.
- **Open items are mandatory.** Anything the lane could neither confirm nor rule out is handed up
  in an open-items list. An unresolved candidate handed up is useful; a silently dropped one is a
  missed vulnerability. Reporting nothing and listing no open items asserts the area is clean;
  only say that if it is.
- **Check the board before spawning.** A duplicate specialist wastes budget and creates
  coordination headaches; the spawn decision starts with "does an open row or a live lane already
  cover this scope".

Peer-to-peer messaging between lanes is a side channel, deliberately starved: only when essential,
batched, never routine status. Completion flows and shared artifacts carry the coordination load.

## Continuity across compactions, and the mechanical merge

A long campaign runs through dozens of context compactions and session restarts, and each one
silently orphans anything that lived only in the orchestrator's working memory. The practices
below were extracted from a full-engagement retrospective; every one pays for itself the first
time it fires.

- **Step zero after every compaction is mechanical, not situational.** Before any new action:
  re-check the running fleet (a dispatch that returned nothing may still be running, or may be
  gone), re-dispatch every lane that was sent but never returned, re-arm watchers, pin the
  absolute paths the session will need next. Never assume a pre-compaction dispatch survived -
  orphaned lanes cost more hours in one campaign than any other single failure class measured.
- **The completion report hits disk before the lane returns.** A verdict that lives only in the
  return message dies with the next compaction. The two-sided contract above gains a persistence
  clause: the brief pins the envelope's path and filename, the lane writes the full report there
  BEFORE returning, and its capture list matches the request ledger's numbering so a verifier can
  cross-check without the lane present.
- **Verify the brief's premises against the record before dispatching.** The route exists (in a
  spec or a capture), the auth shape is stated per step (none / anon bearer / user), and every
  banked artifact the brief cites is on disk. A lane made to guess a field name or re-derive a
  premise spends its budget discovering the premise was wrong - the most expensive wrong-premise
  case measured burned 40 minutes on a single line.
- **Idle and degraded are dispatch triggers, not stops.** A stamp-only tick with an empty running
  set means dispatch the next queued row. A hard dependency failing (an endpoint 500s, a seat
  dies) means dispatch the bypass or alternate-vantage lane immediately, never park the dependent
  queue behind one flap.
- **State-file appends go through a merge script, not prose-anchored edits.** Guards that turn
  each historical corruption into a refused exit instead of a repair: glue guard (the file's last
  line never fuses with the block's first), duplicate id/tag refuse (a lane re-run or a
  compaction replay must not double-write), an ASCII guard, and a read-back that fails when the
  last line is not the block's last line. Deterministic post-write verification replaces the
  per-write ritual of hand-run tick counts and byte dumps.
- **Bank unique line-tail Edit anchors.** When the merge script cannot be
  used, anchor the edit on a unique tail of an existing line and re-include
  that line verbatim in the replacement; prefix-anchored inserts mangle
  state files and have deleted a line in the field. Keep a short registry
  of known-good anchors for the state files this engagement edits most.
- **A checklist that verifies nothing must not read as a pass.** A completion ledger whose boxes
  declare no artifacts can print COMPLETE with zero steps verified, and in the field that verdict
  was accepted as success. Gate rule: ticks with no verifiable artifact yield NEEDS-REVIEW (a
  failure under a hard gate), never COMPLETE.

## Fleet budget: graduated bands and a close-out reserve

Against a spend ceiling, warn with escalating, role-differentiated directives instead of
truncating work mid-sentence. Bands at roughly 70 / 85 / 95 percent of a lane's or the
engagement's budget:

- at the first band: stop opening new lines of investigation;
- at the second: drive the validated finding you have to a result;
- at the third: wrap up NOW; an orchestrator stops spawning and starts closing, an executor
  hands its confirmed work back immediately.

Two structural rules make bands honest:

- **Reserve.** Cut execution lanes at about 90 percent of total spend so the orchestrator can
  always afford triage, the coverage census, and the report. When the reserve trips: no new lanes,
  no waiting on stragglers; confirmed work is already on disk; wrap up.
- **Spend is fleet-wide shared state.** Per-lane frugality does not help if the total is gone;
  the orchestrator sees total spend, not just its own.

## Anti-drift for lanes: output ends a run, nudges are bounded

- A lane ends by RETURNING its result (envelope, completion report), never by a prose sign-off.
  A turn that produces text but no work is nudged back to exactly one concrete action, with a
  bounded recovery count (about 3). The count persists across restarts, so a restarted lane
  cannot re-earn a fresh nudge budget by dying; only real progress (a new artifact, a real
  message) resets it.
- **Exactly one terminal notification per lane.** A completion report and a crash/stop notice
  carry the same information; whichever arrives first claims the slot, and the other is skipped.
  A lane that died still owes its parent a notice, so the orchestrator never waits out a timeout
  on a message that cannot come. A stopped lane's already-filed findings stand; account for the
  unfinished remainder and move on.

## Close-out census returns work, it does not just pass

- Before closing, list the unresolved rows (needs_follow_up): each is either work you still owe,
  or a row somebody already resolved without updating it. A stale open item sitting next to its
  own resolution is worse than either alone.
- **Equipped but unrecorded means unexamined, not clean.** If a lane carried a class doctrine and
  no coverage row textually matches that class, the report must say unexamined; a hallucinated
  "tested and clean" is strictly less honest than no coverage record at all. Same for a lane that
  ran and recorded nothing: whatever it examined is absent from the record.
- **The chaining gate.** Do not close until chaining the confirmed findings into higher-impact,
  end-to-end paths has been genuinely considered and every plausibly-related combination tested.
  Finding no real chain after a serious attempt is acceptable; skipping the chaining reasoning,
  or ignoring a plausibly-related combination, is not.
- The close-out check should hand back an actionable punch list at the last moment work can still
  be dispatched, not a bare pass/fail after the fact.

## Dedupe boundary for filed findings

A duplicate is: same root cause, same affected component/endpoint, and it would be fixed by the
same patch. Explicitly NOT duplicates, even with similar titles or different payloads:

- different endpoints with the same vulnerability type
- different parameters on the same endpoint
- different root causes (stored XSS vs reflected XSS in the same field)
- one authenticated, the other not

Deterministic identity first, judgement second: exact identities (a CVE x package x manifest
triple, or an identical request pair) dedupe with zero model calls, and only the residue goes to
a judge. When uncertain, lean towards NOT duplicate. A dedupe outage must never block a finding:
fail open. The loser is refused with a pointer to the winner and told to REVISE the existing
finding, never to re-file.

## References

<!-- promoted-slug: a-finding-that-fails-scrutiny-after-it-looked-done-needs-a-d -->

<!-- promoted-slug: a-per-candidate-truth-payability-verification-gate-still-lea -->

<!-- promoted-slug: allocate-a-hard-request-budget-across-the-ordered-passes-of -->

<!-- promoted-slug: gate-every-hunted-candidate-through-two-independent-verifier -->

<!-- promoted-slug: ledger-a-state-changing-or-authenticated-request-before-send -->

<!-- promoted-slug: treat-a-subagent-s-severity-escalation-as-a-fabrication-red -->
