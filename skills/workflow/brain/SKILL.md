---
name: brain
description: Brain mode - the main chat (glm-5.3) stays the strategist brain while all execution runs in subagents: haiku (glm-5.3-flash) for fully-specified mechanical runs, sonnet (glm-5.3) when the run needs in-run judgement, up to 3 concurrent disjoint agents. Fully integrated with the offensive driver: invoked via /brain, the driver loop stays in the brain and each next-action's execution is dispatched. Use for "/brain", "brain mode", "run offensive via brain", "dispatch this via brain".
---

# brain

Main chat = brain. Subagents = hands. The brain never executes a fully-specified
run itself, and never lets a subagent make a strategy call. The brain is also the
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

## The dispatch (checklist contract)

Reuse `Skill(delegate)`'s six-slot checklist as the prompt skeleton: confirmed
primitive, exact copy-paste commands with real IPs/paths inline (no `$VAR`),
egress/port constraints, false-root/hostname guardrail, fragile-box discipline,
report contract. Every dispatch prompt additionally carries:

- anti-give-up/no-guess: run the FULL specified window; if blocked, report RAW
  output/errors and STOP; never guess or substitute a value, never invent a
  result.
- the read-first mandate, verbatim: cat each file in full, grep only to locate.
- report `hostname` + `id` alongside any shell/id output.
- the boundary: subagents never run driver commands and never write
  `targets/<eng>` files; they return raw output and evidence paths only.

## Concurrency

- Up to 3 concurrent subagents, disjoint targets or vectors only; never two
  agents on the same asset+class (delegate's no-parallel-duplicate rule).
- One scanner at a time on the Kali VM; parallel lanes must be genuinely
  independent (a watch window + a read-only source pass + drafting).
- While agents run, the brain keeps driving the board, wiki, and next-row prep.
- Integrate results in return order; persist to `state.md`/`loot.md` before the
  next dependent move.

## Offensive integration (brain mode over the driver)

1. `python3 scripts/offensive.py --eng <name> next` in the main chat.
2. Fire the mapped `Skill(hunt-*)` in the MAIN session (G2 telemetry + doctrine).
3. Distill the action plus the loaded skill's mandates into a checklist; dispatch
   at the tier from the table above.
4. The subagent returns raw output, evidence path, and `hostname`+`id` where
   shell-shaped.
5. The brain verifies the result (re-verify any negative before it becomes a
   Deadend), records `note`/`done`/`foothold` on the driver, re-runs `next`.

The closeout chain (triage, evidence, walkthrough, learn) stays on the brain.
Plain `Skill(offensive)` without /brain is unchanged: single agent, main model
executes directly.

## Failure handling

- Subagent stalls or dies: stop it, ONE re-dispatch with a tightened checklist,
  then the brain takes the step over.
- Safeguard refusal on a dispatched run: the brain executes that step itself
  rather than churning re-dispatches.
- A negative from a subagent is re-verified on the brain before it reaches
  Deadends.md.

## Client-data boundary

Worked examples in this file use placeholders only; never put a real target IP,
hostname, or credential into this skill file.
