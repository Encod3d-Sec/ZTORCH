---
title: "Port spec: hermes agent-loop internals"
type: docs
tags: [docs, port-spec, hermes, agent-loop]
date_created: "2026-10-12"
sources: [raw/git/hermes-agent]
---

# Agent-loop internals: ranked port proposals

Deep read of the hermes turn loop (`agent/conversation_loop.py`, `agent/turn_*.py`,
`agent/iteration_budget.py`, `tools/budget_config.py`, `tools/tool_result_storage.py`,
`tools/hook_output_spill.py`, `agent/interrupt_control.py`, `agent/retry_utils.py`,
`agent/turn_api_error.py`, `agent/turn_recovery_autorecover.py`). Ranked by behavior change
for an autonomous hackbot: budgets, spill, and retry first; cosmetics excluded. ZTORCH baseline
per the port plan: lanes (markdown briefs + Scope/Result/Key-files/Issues envelopes), hook layer
in `skills/hooks/` + `.zcode/config.json`, `output_econ.py` truncation on the VM bridge only,
PreCompact injection. No iteration budget, no tool-result size budget outside the bridge, no
spillover for local results.

## 1. Tool-result size budget + spillover (per-result, per-turn, MCP): PORT, M

**Hermes.** Three layers. Layer 1 per-tool caps: 50K bytes terminal output / 2K lines /
2K line length (`tools/tool_output_limits.py:13-15`), one head/tail algorithm, 40% head
(errors surface early) / 60% tail around a single marker shape (`tools/tool_output_truncate.py:12,25-32`).
Layer 2 per-result persistence: over the tool's threshold the FULL result is written to
`$HERMES_HOME/cache/spillover/{id}.txt` (size-verified write, discards on mismatch,
`tools/tool_result_storage.py:110-121`) and replaced inline by a `<persisted-output>` block:
original size, saved path, "page through with read_file offset/limit ... do NOT re-request the
same data" anti-loop recovery line, plus a 1.5K preview (`tool_result_storage.py:264-279,293-334`).
Threshold resolution: pinned (`read_file` pinned to infinity specifically to prevent a
persist-then-read-then-persist loop, `tools/budget_config.py:10`) > config overrides > tighter
MCP default 50K (`mcp_` prefix, `budget_config.py:19-22,69-70`) > per-tool registry > default
100K, all capped at the default (`budget_config.py:56-75`). Layer 3 per-turn aggregate 200K:
`enforce_turn_budget` spills the largest non-spilled results first until the turn total fits
(`tool_result_storage.py:359-391`). Window scaling: one result may take 15% of the context
window, one turn's tool output 30%, floored 8K/16K, clamped at the fixed defaults so large
models are byte-identical (`budget_config.py:85-89,92-114`). Spill files pruned at 24h
(`tool_result_storage.py:45-61`).

**ZTORCH gap.** `scripts/output_econ.py` (30K threshold, full output to
`targets/<eng>/ingest/`, stub with preview + path) covers ONLY the VM bridge pipe
(`vm-ssh.sh`). Local Bash output (a local `grep -r` over `raw/git/`, a `cat` of a dump), MCP
tool results (qmd `get`, zvec-grep bursts), and lane envelope payloads are unbudgeted;
`big-read.py` advises on Read over 200KB but nothing bounds what a Bash call returns, and no
per-turn aggregate exists.

**Native design.**
- Generalize `scripts/output_econ.py` into `scripts/spill-run.sh <cmd...>` (same persist/stub
  logic, engagement-relative ingest dir, works for local commands, honors `OUTPUT_ECON=0`).
- New PreToolUse(Bash) hook `skills/hooks/spill-guard.py`: ADVISE (never deny, fail-open)
  when the command matches unbounded-dump shapes (`cat`/`head -n9999` on files over ~200KB,
  un-piped `nmap`/`feroxbuster`/`linpeas`/`sqlmap --batch` output expected locally) and the
  advisory names `spill-run.sh` as the replacement. Dedupe per shape 15 min, pattern copied
  from `big-read.py`.
- Per-turn aggregate: extend `skills/hooks/tool-telemetry.py` (already PostToolUse) to
  accumulate result chars per session in `session/.turn-chars` and emit a one-line advisory
  when the running total crosses ~200K: "spill or summarize before more big reads".
- Register both in `.zcode/config.json`, add to the canonical set in `scripts/check-hooks.py`,
  one row in `docs/auto-triggers.md`.

**Why PORT.** Context flooding from tool output is the recurring autonomous-run killer; hermes
solved it as budget layers with an explicit anti-re-request contract, and only the bridge half
exists here.

## 2. Iteration budget with refund + exit-reason taxonomy + grace wrap-up: PORT, M

**Hermes.** Thread-safe `IterationBudget` counter, consume/refund/remaining
(`agent/iteration_budget.py:25-56`); parent cap 500, each subagent 50 (`iteration_budget.py:3-5`).
Loop gate: `api_call_count < max_iterations AND iteration_budget.remaining > 0 OR _budget_grace_call`
(`agent/conversation_loop.py:1648-1650`). Consumption at iteration entry; exhaustion keeps ONE
toolless grace call whose flag is consumed so the loop exits after it regardless
(`agent/turn_iteration_prep.py:402-417`). Refunds: a redirect/compression/fallback restart that
produced no assistant item refunds count+budget, bounded by `restart_count` (resets to 0 once
any response arrives) so a runaway correction loop cannot refund forever
(`turn_iteration_prep.py:467-490,496-523,525-546`); an `execute_code`-only tool round is
refunded because cheap RPC-style calls should not eat the budget
(`agent/turn_tool_round.py:197-200`). Pre-exhaustion warning: at a configurable ratio
(default 0.9 for workers) a one-shot "checkpoint durable progress now, then continue; do not
stop solely because of this warning" notice is appended to the newest tool result, cache-safe,
never on persisted rows (`turn_iteration_prep.py:41-99`). At exhaustion with no answer the
finalizer makes one extra toolless summary request ("asking model to summarise",
`agent/turn_finalizer.py:124-171`) or preserves an already-withheld pending answer. Exit-reason
taxonomy stamped on every result and logged on every exit with budget used
(`turn_finalizer.py:331-384`): `budget_exhausted`, `max_iterations_reached(N/M)`,
`interrupted_by_user`, `interrupted_by_system(<issuer>)`, `review_input_budget_exhausted`,
`all_retries_exhausted_no_response`, `redirect_restart_limit_exceeded`,
`rebuilt_restart_limit_exceeded`, `compaction_handoff_not_actionable`,
`context_compression_exhausted`, `session_persistence_failed`, `guardrail_halt`,
`pending_tool_result`.

**ZTORCH gap.** No iteration budget anywhere. Stop conditions are prose rules (OOB sink 30-40
payloads, spray matrix once) with no mechanical counter; `drift-guard.py` counts repeated
commands (identical 3x, >= 6 exploit-shaped calls) but nothing bounds a lane's total tool
activity or forces a wrap-up. Lane completions carry no exit reason, so close-out audits cannot
distinguish "vector exhausted" from "lane gave up" from "budget hit".

**Native design.**
- Lane budget: `skills/workflow/exec/delegate/SKILL.md` brief schema gains a `budget: <N>`
  line (tool calls); `scripts/lane-run.sh` writes a per-lane counter file the lane's own
  PostToolUse telemetry increments (reuse `tool-telemetry.py` keyed on the lane session), and
  `scripts/lane_validate.py --brief` warns when an envelope reports more activity than budget.
- Exit-reason grammar: extend `docs/log-grammar.md` with an `exit` event,
  ``<TS> | lane | exit | reason=<token> | n_calls | detail``, and require the envelope's
  Issues line to carry one token from a fixed vocabulary (exhausted, budget_hit, blocked,
  interrupted, bridge_down, done). `scripts/offensive.py next` then ranks `budget_hit` rows as
  switch-vector instead of retry.
- Grace wrap-up: the checkpoint-warning shape (continue, do not stop) plus the exhaustion
  summary call map to `offensive.py next` banner text at 80% of lane budget: "checkpoint
  durable progress into state/Killchain now, then continue"; at 100% the driver refuses to
  re-rank that vector and demands the wrap-up line.

**Why PORT.** Mechanical budgets and exit reasons are what make a long autonomous run
auditable and terminable; today both live only in prose discipline.

## 3. Over-claim guard: file-mutation verifier + pending-result detection: PORT, S/M

**Hermes.** At turn end, every failed `write_file`/`patch` call never superseded by a
successful write to the same path gets a footer appended to the final response, so the model
structurally cannot summarize "all files edited" over a half-failed batch
(`agent/turn_finalizer.py:387-406`). A turn that fell out of the loop with a tool result as
the durable tail and no assistant text is detected as `pending_tool_result`, failed, and
closed with a visible notice instead of a silent stop (`turn_finalizer.py:553-575`); every
delivered final response is guaranteed a closing assistant row so the next turn does not
re-answer "unanswered" messages (`turn_finalizer.py:240-276`).

**ZTORCH gap.** "No claim without fresh capture" is prose-only; `find-lint.py` checks finding
cards and `lane_validate.py` checks brief shape, but nothing mechanically cross-checks a lane
envelope's claimed file writes (wiki edits, state.md updates) against what actually changed,
and nothing flags an envelope returned while a background unit (OOB listener, tmux window,
watched process) is still pending.

**Native design.**
- Envelope `Key files` entries become verifiable: `scripts/lane_validate.py` gains a check
  that each claimed-touched vault file has an mtime inside the lane's start/end window
  (timestamps already in `scripts/lane_manifest.py`); a claim with no matching mtime or git
  diff is reported as `unverified_write` in the validation output.
- Pending-result flag: lane teardown in `scripts/lane-run.sh` checks the manifest for live
  background registrations (existing process/tmux conventions) and appends
  `pending_result: <name>` to the envelope Issues line; `offensive.py next` surfaces it as a
  board row instead of letting the main session assume completion.

**Why PORT.** Over-claiming is THE hackbot failure mode hermes engineered around at the loop
boundary; ZTORCH's equivalent boundary is the lane envelope, which is currently trust-based.

## 4. Wall-clock run budget with 80% wrap-up notice: PORT, S

**Hermes.** Optional `run_budget_seconds` per turn; at 80% elapsed a ONE-TIME system notice is
appended to the newest (unpersisted) tool result: "Run time budget nearly exhausted. Stop new
discovery/verification work now. Produce the required final deliverable from the state you
already have, completing only mandatory writes" (`agent/conversation_loop.py:75-80,124-156`;
armed per-iteration at `turn_iteration_prep.py:184-186`; config at
`agent/agent_init.py:703-707,1394-1396`). Latched so it fires once; skipped when the interrupt
flag is set (never urges more work into a cancelling turn).

**ZTORCH gap.** The spend cap (`ZT_MAX_ENG_USD`) denies spend but never steers toward the
deliverable; a deep-mode engagement can burn its whole box on discovery and end with no
walkthrough, evidence gallery, or FIND promotion because nothing forced the pivot to close-out.

**Native design.** `scripts/offensive.py next` reads `time_budget_h` from `targets/<eng>/scope.md`
(default off), computes elapsed from the engagement's first `log.md` timestamp, and once past
80% (one latch file under `targets/<eng>/`) changes its banner to the wrap-up directive and
re-ranks close-out moves (walkthrough, evidence, FIND promotion) above every open vector.
Zero hooks, one file touched plus a log line.

**Why PORT.** Smallest possible diff that changes what an unattended run does at its end:
pivot to the deliverable instead of discovering until the box dies.

## 5. Retry ladder with jittered backoff + Retry-After for the VM bridge and MCP: PORT, S

**Hermes.** Provider retry policy is a pipeline: classify into a `FailoverReason` taxonomy
where context overflow means compress-not-failover and client errors are terminal
(`agent/error_classifier.py:34-66`); Retry-After honored from header, body field, and
free-text "resets in 2h 5m" grammars, capped 600s (`agent/retry_utils.py:30-64,69-101,185-195`);
jittered exponential backoff 2-60s (`retry_utils.py:121-134`); default 3 retries
(`agent/agent_init.py:1436-1439`); at exhaustion, one primary-transport rebuild, then the
fallback chain, then a bounded auto-recovery ladder parking the turn with a visible countdown
(5 cycles, jittered 15/30/60s, provider Retry-After up to 120s, only transient classes:
overloaded/server_error/timeout; `agent/turn_api_error.py:363-404`;
`agent/turn_recovery_autorecover.py:26-31,49-56`).

**ZTORCH gap.** The recovery ladder for harness-owned transports is prose ("retry once, fix
args, heed advisory, then fall back" in AGENTS.md) with no backoff math; a dead SSH bridge or
a downed zvec-grep server inside a lane produces either an immediate second identical failure
or a dead lane, and `zg server on` remediation is manual.

**Native design.** Add a `retry_run()` helper to `scripts/vm-ssh.sh` and `scripts/win-vm.sh`:
up to 3 attempts, jittered waits (2s, 4s, 8s + 0-50% jitter; pure bash `$RANDOM` math), distinct
exit codes for transport-dead vs command-failed, and a stderr one-liner per retry so the lane
log records `tool vm-ssh retry 1/3 ok`. Exit code propagates to the lane envelope as
`bridge_down` (proposal 2's vocabulary). Optionally the same helper answers "qmd MCP errored"
by suggesting `zg server on` once, matching the documented fallback. No hook changes.

**Why PORT.** Transient transport failures are routine in long runs; hermes' whole
classify-then-backoff discipline reduces to ~20 lines of shell here and removes the most
common cause of a lane dying on attempt one.

## 6. Cap every recurring hook injection (hook-output spill): PORT, S

**Hermes.** Hook `{"context": ...}` output rides EVERY subsequent API call, so one oversized
blob inflates every turn and breaks the prompt-cache prefix. Above 10K chars the text is
written to `<home>/hook_outputs/<session>/<uuid>.txt` (private 0600, exclusive
symlink-refusing create, `tools/spill_safety.py:22-66`) and replaced by a header with total
size + saved path + 500-char head and tail previews; never raises, disk failure still returns
a preview (`tools/hook_output_spill.py:24-113`). Applied to `pre_llm_call` plugin context
(`agent/turn_context.py:819-841`) and memory-manager injections (`agent/memory_manager.py:562`).

**ZTORCH gap.** `session-start.sh` caps `hot.md` itself (200 lines / 25KB) but the other
recurring injections are uncapped: SessionStart engagement state summary, `hunt-trigger.py`
directive text, PreCompact board+lane block, `offensive.py next` banners. Any of these growing
(a many-engagement vault, a fat scope file quoted in an advisory) silently taxes every prompt
of every session.

**Native design.** One shared function `spill_if_oversized(text, cap, dest_dir)` in a new
`skills/hooks/_spill.py` (head/tail preview + path header, 20-line stdlib implementation);
call it at the tail of `session-start.sh` (on the assembled state summary, spill dir
`session/spill/`), `hunt-trigger.py` (on the directive block), and `pre-compact.sh` (on the
must-survive block). Cap default 10K, env override `ZT_INJECT_CAP`. Files over cap land in
`session/spill/<ts>-<src>.txt` which compaction can re-read selectively.

**Why PORT.** Cheap insurance on the one cost axis (per-prompt bytes) that recurs forever;
half the mechanism already exists for `hot.md`, this generalizes it to every injection point.

## 7. Loop-level interrupt vs queued steer plumbing: SKIP, S

**Hermes.** Three tiers: `interrupt()` hard stop fanning out to tool worker threads and child
agents with issuer attribution (`agent/interrupt_control.py:128-230`); `steer()` queues text
delivered as a standalone user row after the current tool batch, never mid-call
(`interrupt_control.py:267-278`, drained pre-API at `turn_iteration_prep.py:179-181,284-295`,
leftover handed back as `result["pending_steer"]` at `turn_finalizer.py:747-749`); `redirect()`
cancels only the in-flight model request and rebuilds the turn around the correction
(`interrupt_control.py:280-341`).

**Why SKIP.** The harness owns main-session interrupts natively and the wave-3a lane
steer/missed-steer contract already ported the queue-at-boundary semantics; what remains
(provider request cancellation) has no ZTORCH-owned equivalent to cancel.

## 8. Per-turn background reviews + memory sync forks: SKIP, S

**Hermes.** After delivery: skill-nudge counter check, external memory sync, and a background
memory/skill review fork (~30K tokens per event, suppressed for cron) run so review never
competes with the user's task (`agent/turn_finalizer.py:762-807`).

**Why SKIP.** Wave 1 already ported memory/curator and wave 3 the doctor; a per-turn aux-LLM
fork is exactly the token-burn class ZTORCH's output-economy rules exist to prevent, and
close-out `learn` covers the same harvest at 1/Nth the cost.

## Not proposed (one line each)

- Continuation nudges (truncated response, dropped tool call, empty-after-tools;
  `conversation_loop.py:914-983`): harness-owned streaming, nothing to nudge.
- Post-turn micro-compaction (`turn_finalizer.py:287-328`): compaction is the harness's; the
  PreCompact must-survive block (wave 3a) is the ZTORCH-relevant half and is done.
- Outer-loop error cap of 8 (`conversation_loop.py:237`): subsumed by proposal 2's budget.
- Tool-retry outcome stamping on the durable row (`hermes_state_tool_retries.py`): neat
  pattern, but ZTORCH has no durable tool-row store to stamp; the envelope `Issues` line
  carries it.
