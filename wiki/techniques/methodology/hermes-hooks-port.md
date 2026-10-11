---
title: "Hermes Hooks Port"
type: technique
tags: [methodology, agents, automation, harness, hooks]
phase: exploitation
date_created: 2026-10-11
date_updated: 2026-10-11
sources: ["HermesTORCH docs/hooks-port-design.md"]
---

# Torchv2 hooks port: landing ZCode hooks on Hermes native shell hooks (2026-10-11)

Technique page. What was actually done when porting the ZTorch hook surface onto
Hermes Agent's native shell-hooks system, what broke, and the two non-obvious
lessons. Canonical design: HermesTORCH `docs/hooks-port-design.md`; adapter:
HermesTORCH `hermes/agent-hooks/torch-hook-adapter.py`.

## The pattern that worked

- ONE adapter script registered N times in config.yaml; the registered command
  string's trailing `--hook <name>` selects the canonical child script. Child
  scripts stay byte-identical to the source harness; only the adapter translates.
- Dialect translation, both directions: tool names (`terminal`->Bash,
  `write_file`->Write, `patch`->Edit, `read_file`->Read), arg keys
  (`path`->`file_path`), decision dialects
  (`permissionDecision: deny`->`{"action":"block"}`,
  `ask`->`{"action":"approve","rule_key":...}`), and the advisory channel.
- The advisory `additionalContext` has NO consumer at pre/post_tool_call on
  Hermes. Relay it through a sidecar file (`$HERMES_HOME/torch-hooks/advisories/<session>.md`),
  appended at pre/post tool time, atomically renamed away (drained) by the one
  real channel: a `pre_llm_call` hook that emits `{"context": ...}`. Advisories
  land at the next turn boundary - acceptable for advisory doctrine, never for
  enforcement.
- Failure doctrine mirrors ONE-deny: the scope-guard chain alone fails CLOSED
  (adapter exit 2 + `fail_closed: true` on the config entry - two belts); every
  other hook fails open to `{}`, exit 0.
- Consent: pre-seed `<HERMES_HOME>/shell-hooks-allowlist.json` with the exact
  command strings (byte-identical to config.yaml) so non-TTY runs (gateway,
  cron, delegate children) register hooks without prompts.

## Lesson 1: test-harness payload dialect != production wire dialect

`hermes hooks test --payload-file X` merges X into SYNTHETIC KWARGS, not into
the wire payload. The wire's `tool_input` is built from kwargs key `args`
(`_payload_fields`: `tool_input := kwargs["args"]`), and `cwd` is ALWAYS
`Path.cwd()` of the CLI process - a `cwd` key in the payload file is silently
demoted to `extra` and ignored. A payload file written in the production dialect
(`tool_input`, `cwd`) therefore tests nothing: the child receives
`tool_input: null` and no-ops, and the test passes vacuously.

Fix: payload files for `hooks test` use `{"args": {...}}` and must be run from a
cwd inside the vault scope. Production firing is unaffected (the runtime builds
`tool_input` correctly). Generalized rule: **verify the test harness's input
dialect separately from the production wire format; a test that feeds the wrong
dialect and sees "no output" proves nothing.**

## Lesson 2: fixture state must match the parser, not the YAML eye

`_engagement.scope()` parses `## In scope` / `## Out of scope` markdown HEADERS
(`_SCOPE_SECTIONS` maps header text -> key); bare YAML keys (`out_of_scope:`)
are invisible to it, so a YAML-style fixture yields empty scope lists and a
scope-guard that "doesn't fire". Fixture files must be shaped like the real
artifacts the parser expects. Generalized rule: **when a hook "does nothing",
first feed the child the payload by hand (`echo json | python3 child.py`) -
if the child alone works and the chain doesn't, it's the adapter; if neither
works, it's the fixture/state.**

## Latency reality (Windows, 6 adapter spawns per terminal call)

Measured ~1.4s added per terminal call (worst case incl. CLI startup; raw
adapter chain ~1.9s). The planned chain-consolidation optimization (6 pre-hooks
-> 1 entry, threads inside) was NOT needed against the 1.5s gate - measure
before optimizing. Doctor timing: each hook spawns in 0.2-0.5s.

## pre_verify loop guard (R10/T6)

`pre_verify` re-fires on EVERY finish attempt; a close-out hook whose conditions
stay unmet (e.g. an infrastructure session with no engagement walkthrough to
run) would loop the turn forever. Mitigation shipped in the adapter: an
adapter-side once-per-15-min stamp (`$HERMES_HOME/torch-hooks/stamps/close-out.last`)
checked BEFORE spawning the child; fail-open if the stamp machinery breaks. The
stamp's first live creation happened within minutes of registration - the loop
risk is real, not theoretical.

## Scope gate (ZCode project-scoping has no Hermes equivalent)

Hermes hook config is profile-global; ZCode's was project-dir-scoped. The
adapter re-creates the scope: scope-guard runs ALWAYS (an active engagement
must be guarded wherever the terminal points; the script itself no-ops with no
active engagement), every other hook runs only when the payload cwd is under a
vault root OR an engagement is active (cheap `targets/active.md` probe).

## Verification battery (reusable)

T1 deny (out-of-scope IP -> block), T2 RoE (bruteforce under no_bruteforce ->
approve + rule_key), T3 context inject (first-turn engagement state + hunt
router), T4 sidecar write + atomic drain, T5 post-tool observer (state.md
auto-population + sidecar, "parsed: none" is CORRECT for observer hooks), T8
config round-trip (lists not strings), T9 latency. Fixture: `ZTORCH_VAULT` env
override to a scratch vault with `targets/active.md` + header-shaped scope.md.

Related: [[agentic-harness-patterns]], [[multi-agent-campaign-orchestration]]
