---
name: brain
description: Brain mode - main chat keeps strategy/driver/triage, 2-3 concurrent subagents execute. DEFAULT posture once the board has 2+ open assets. Use for "/brain", "brain mode", "run offensive via brain", "dispatch this via brain".
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
  decisions.md).
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
  the only writer of `targets/<eng>` files.
- Console / Lead Strategist: brain duties (routing, judgement, sign-off),
  never subagent roles; the main chat is glm-5.3 by definition.
- Step-up rule: a flash lane that hits a judgement fork (vector choice,
  ambiguous analysis, "is this real or am I querying it wrong") stops and
  returns to the brain for re-tier instead of guessing.

## The dispatch (checklist contract)

Reuse `Skill(delegate)`'s eight-slot checklist as the prompt skeleton: confirmed
primitive + assumption set, exact copy-paste commands with real IPs/paths inline
(no `$VAR`), egress/port constraints, false-root/hostname guardrail, fragile-box
discipline, SUCCESS criterion, report contract. Every dispatch prompt
additionally carries:

- anti-give-up/no-guess: run the FULL specified window; if blocked, report RAW
  output/errors and STOP; never guess or substitute a value, never invent a
  result.
- the read-first mandate, verbatim: cat each file in full, grep only to locate.
- report `hostname` + `id` alongside any shell/id output.
- the boundary: subagents never run driver commands and never write
  `targets/<eng>` files; they return raw output and evidence paths only.
- the assumption set (delegate slot a), verbatim: the lane prompt spells out
  what must hold true for the run to make sense (access still valid, file
  still at path, version match); a mismatch is reported, not silently absorbed.
- the SUCCESS criterion (delegate slot f), verbatim: the brain writes
  `SUCCESS = <exact observable>` (e.g. `hostname` = target AND `id` =
  expected uid, plus log path) into the lane prompt before dispatch; the lane
  returns that observable raw; on return the brain verifies the capture
  against the criterion; a claimed success whose observable is absent from
  the capture is a failed lane. Append the lane line to
  `targets/<eng>/log.md` before dispatch (format per Skill(delegate)) and
  CLOSE it on return by appending the verdict to that same line; the log
  line is the lane's only durable state across compaction.
- the output-landing mandate (delegate slot h), verbatim: per-lane capture dir with
  full request/response captures, named tmux window for evidence-worthy runs, raw
  pairs returned for Repeater; no one-line-verdict-only returns.

Two fleet rules (prompt-cache + uniform returns):

- Frozen shared prefix: author the shared contract body ONCE per phase - slots
  a, c, d, e, g plus the mandates above, byte-identical in every lane prompt;
  only the trailing LANE DIRECTIVE (slot b commands, slot f SUCCESS criterion,
  target/paths) differs per lane. No dynamic content in the shared section;
  any per-lane fact lives in the directive. Concurrent lanes then share one
  cached prefix instead of each re-paying a fresh one.
- Fixed return envelope: every lane returns Scope (what was attempted) /
  Result (verdict + the raw SUCCESS observable) / Key files (capture-dir
  paths) / Issues (blockers + what was ruled out). Slot h's
  no-one-line-verdict rule applies inside Result.

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
- Safeguard refusal on a dispatched run: the brain executes that step itself
  rather than churning re-dispatches.
- An escalation-candidate finding dispatches to a Verifier lane (glm-5.3) for
  independent reproduction before it is recorded as foothold/fact.
- A negative from a subagent is re-verified on the brain before it reaches
  Deadends.md.

## Client-data boundary

Worked examples in this file use placeholders only; never put a real target IP,
hostname, or credential into this skill file.
