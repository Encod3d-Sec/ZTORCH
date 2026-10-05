---
name: brain
description: Brain mode - the main chat keeps strategy/driver/triage while 2-3 concurrent subagents execute. DEFAULT posture once the board has 2+ open assets. Use for "/brain", "brain mode", "run offensive via brain", "dispatch this via brain".
---

# brain

Main chat = brain. Subagents = hands. The brain never executes a fully-specified
run itself (except a safeguard-refused step, see Failure handling), and never
lets a subagent make a strategy call. The brain is also the
only one allowed to stop the loop: dispatches return results, the brain decides.

## Role split

The BRAIN keeps (never dispatched):

- Driver commands: `offensive.py next/note/done/foothold/closeout`. The driver is
  still the plan; the brain never hand-picks moves.
- All `targets/<eng>` writes (state.md, loot.md, Killchain.md, Deadends.md,
  decisions.md, log.md).
- Vector selection, triage, scope/RoE judgement, wiki + arsenal selection (which
  card, which hunt skill).
- Firing `Skill(hunt-*)` in the MAIN session: loads the doctrine into brain
  context AND satisfies G2 telemetry (the PostToolUse hook records main-session
  fires to `.events.jsonl`; a subagent's internal skill fire is not guaranteed to
  land there).
- Authoring every checklist, dispatching, integrating results, verifying them.

The brain DISPATCHES, fully-specified execution chunks only:

- Scanner invocations, exploit compile+run, pspy/tcpdump watch windows, evidence
  capture, read-a-source-file-end-to-end passes, payload delivery.

## Tier routing (Agent tool aliases)

| Alias | Actual model | Use for |
|---|---|---|
| haiku | glm-5.3-flash | DEFAULT. Mechanical fully-specified runs: one-tool runs, compile+run a known PoC, watch windows, scripted evidence capture, read-and-summarize passes. |
| sonnet | glm-5.3 | Multi-step runs whose next step depends on reading live responses: hunt-skill execution against a live surface, JS-heavy analysis, a decision-bearing exploit chain. |

Fresh agents only: `subagent_type` general-purpose, never `fork` (a fork inherits
the main model and ignores the alias, silently voiding this table).

NEVER dispatched at either tier: discovery (route/endpoint/token enumeration),
"is this surface empty or am I querying it wrong", anything not fully specified.
A guess wearing a checklist stays on the brain (see `Skill(delegate)`).

## Dispatch archetypes (roster tiers)

Named lane archetypes with a FIXED tier; the table above still governs
unnamed execution lanes.

- Verifier lane: glm-5.3, always. Independent re-derivation of an
  escalation-candidate finding from the recorded evidence, never trusting the
  discovering lane's verdict. A flash verifier hardening a wrong negative is
  the delegate cheap-tier trap.
- Research lane: glm-5.3-flash. CVE/PoC lookup across NVD, MITRE, CISA KEV,
  GHSA/GitHub search, Exploit-DB, vendor advisories, Packet Storm, Vulners,
  returning a credibility read plus publication/last-updated dates. Output is
  intelligence only; the go/no-go on testing it stays on the brain.
- Scribe lane: glm-5.3-flash. Draft and merge finding entries from returned
  envelopes, dedupe, timestamp. Drafts return to the brain; the brain remains
  the only APPLIER of shared-file edits (lanes hand back paste-blocks per
  slot (f); a lane's own capture dir under `poc/<lane>/` is its output, not a
  shared-file write). Dedupe judge criteria: two entries are the SAME finding
  only when root cause AND component AND fix all match (same tainted param on
  the same endpoint version twice = duplicate; same param on two hosts or two
  sinks = two findings); anything uncertain keeps BOTH entries flagged for the
  brain, never a silent merge.
- Console / Lead Strategist: brain duties (routing, judgement, sign-off),
  never subagent roles; the main chat is glm-5.3 by definition.
- Step-up rule: a flash lane that hits a judgement fork (vector choice,
  ambiguous analysis, "is this real or am I querying it wrong") stops and
  returns to the brain for re-tier instead of guessing.

## The dispatch (delegate is the contract)

Fire `Skill(delegate)` in the MAIN session BEFORE the first dispatch of a phase
(same reasoning as hunt skills: doctrine lands in brain context, G2 records the
fire). Delegate's eight-slot checklist IS the prompt skeleton - slots a-h,
anti-give-up/no-guess, the read-first mandate verbatim, the false-root
guardrail, the log.md lane line and its close-on-return, `lane_validate.py`,
and delegate's returned-lane processing order (verdict above the claim, pending
is status not guess, partial recovery, resume-with-context, 3-fail switch).
This skill restates NONE of it; when the two files disagree, delegate wins -
EXCEPT where this file explicitly supersedes it (concurrency: up to 3 disjoint
lanes replaces delegate's serial one-at-a-time WAIT rule; nothing else
overrides). Fallback if the delegate fire was skipped or a compaction ate it:
every dispatch prompt still carries, verbatim, the false-root guardrail
(`hostname` alongside any `id` output), the read-first mandate (cat each file
in full, grep only to locate), and anti-give-up/no-guess (run the full
window, report raw output, never invent a result).

Brain adds two fleet rules on top:

- Frozen shared prefix: author the shared contract body ONCE per phase - slots
  a, c, d, e, g plus delegate's cross-lane mandates, byte-identical in every
  lane prompt; only the trailing LANE DIRECTIVE (slot b commands, slot f
  SUCCESS criterion, target/paths) differs per lane. No dynamic content in the
  shared section; any per-lane fact lives in the directive.
- Fixed return envelope: every lane returns Scope (what was attempted) /
  Result (verdict + the raw SUCCESS observable) / Key files (capture-dir
  paths) / Issues (blockers + what was ruled out). Slot h's
  no-one-line-verdict rule applies inside Result, and delegate's slot (f)
  rides whole within it (paste-able diff block for any shared-file change,
  REVERT of state the run changed); the envelope is the return shape, not a
  narrower contract.

## Concurrency

- Up to 3 concurrent subagents, disjoint targets or vectors only; never two
  agents on the same asset+class. This supersedes delegate's one-at-a-time
  serial rule; delegate's no-parallel-duplicate rule still applies.
- One scanner at a time on the Kali VM; parallel lanes must be genuinely
  independent (a watch window + a read-only source pass + drafting).
- While agents run, the brain keeps driving the board, wiki, and next-row prep.
- Few long lanes beat many short forks: prefer a lane that owns a whole vector
  over a fresh subagent per step (every fresh dispatch re-pays the prompt
  prefix); re-dispatch only on stall/refusal, per Failure handling.
- Lane completions arrive as notifications; never poll a running lane. Integrate
  in return order; persist to `state.md`/`loot.md` before the next dependent
  move.
- Drift-guard interplay: an OPEN, FRESH lane line (`in flight @<HH:MM>`) in
  log.md counts as driver contact, so lane-flight calls never feed the
  off-board deny - only while the line is open AND younger than the 45-min
  stale window (a forgotten line stops exempting; `status.py` flags it
  resume-or-close). Windowless lanes (offline/research/read passes) still
  write the line with `tmux win -` so it parses. Close every lane line on
  return; after several brain-side exploit-shaped calls with no lane open, run
  driver `note` before the next wave so the streak resets through the front
  door.
- Name the join strategy at every fan-in point in a lane plan (cyberstrikeai L4):
  `merge: all_merge` (apply every lane's writes) | `first_non_empty` (first lane returning
  the observable wins) | `fail_fast` (one lane's failure kills the merge). Defaults when
  unstated: all_merge for board writes, first_non_empty for verifications.

## Offensive integration (brain mode over the driver)

1. `python3 scripts/offensive.py --eng <name> next` in the main chat.
2. Fire the mapped `Skill(hunt-*)` in the MAIN session (G2 telemetry + doctrine).
3. Distill the action plus the loaded skill's mandates into a checklist; dispatch
   at the tier from the table above.
4. The lane returns the envelope (Scope / Result / Key files / Issues): raw
   output and evidence path land in Result, `hostname`+`id` where
   shell-shaped.
5. The brain verifies the result (re-verify any negative before it becomes a
   Deadend), records `note`/`done`/`foothold` on the driver, re-runs `next`.

The closeout chain (triage, evidence, walkthrough, learn) stays on the brain.
Below 2 open assets, plain single-agent `Skill(offensive)` execution applies:
main model executes directly.

## Failure handling

- Subagent stalls or dies: stop it, ONE re-dispatch with a tightened checklist,
  then the brain takes the step over.
- Lane VANISHED (no return, no completion notification): BEFORE any
  re-dispatch, sweep the lane's capture dir, its tmux window, and the open lane
  lines (`python3 scripts/status.py` ages them) - a vanished lane often
  finished its work on disk while the agent died (delegate's partial-recovery
  rule); re-dispatching redoes completed work.
- Safeguard refusal on a dispatched run: the brain executes that step itself
  rather than churning re-dispatches.
- An escalation-candidate finding dispatches to a Verifier lane (glm-5.3) for
  independent reproduction before it is recorded as foothold/fact.
- A negative from a subagent is re-verified on the brain before it reaches
  Deadends.md.

## Known ceilings

Deliberate simplifications, named so they read as intent. A late or duplicate
envelope (the original agent returning after sweep, re-dispatch, and takeover)
is resolved by the brain's verdict line, no merge protocol. Cron/scheduled
lanes run outside the lane-line contract: open a line for them if their calls
should count as driver contact. An operator-mandated fleet larger than 3
supersedes the cap by explicit order (disjointness and the applier rule still
bind). The scanner-cap advisory is per-engagement, so disjoint-target scanner
lanes may trade spurious serialize warnings. The shared prefix and lane
directives live only in prompts: stage a copy in the lane's capture dir if a
compaction landing in the spawn window loses one.

## Client-data boundary

Worked examples in this file use placeholders only; never put a real target IP,
hostname, or credential into this skill file.
