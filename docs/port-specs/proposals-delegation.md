---
title: "Hermes delegation internals: port proposals"
type: docs
tags: [docs, port-spec, hermes, delegation, proposal]
date_created: "2026-10-12"
sources: [raw/git/hermes-agent]
---

# Proposals: delegation/subagent internals (post wave-3a)

Already ported (wave 3a, see `docs/port-specs/README.md`): steer/missed-steer, usage telemetry,
concurrency caps. This pass mines what remains: output_schema, role/depth semantics, summary
budgets, background re-entry, worktree isolation, ephemeral child prompts. All evidence is
`file:line` into `raw/git/hermes-agent` (read-only reference). Nothing here is implemented yet.

## Evidence base (hermes mechanics)

### 1. output_schema: structured child results

- Request: per-task `output_schema` (JSON Schema) on `delegate_task`
  (`tools/delegate_tool.py:718-724`); a malformed schema fails the whole call before any child
  spawns (`tools/delegate_tool_tasks.py:107-122`, `tools/delegation_output_schema.py:19-42`).
- Told up front: `append_output_contract` appends an OUTPUT CONTRACT block to the child's
  context (final response must be ONLY the JSON value, no prose, no fence;
  `tools/delegation_output_schema.py:45-57`); schema rides on the child as
  `_delegate_output_schema` (`tools/delegate_tool.py:424-437`).
- Parsed: `extract_json_candidate` strips fences/prose to the outermost `{...}` / `[...]` span
  (`tools/delegation_output_schema.py:60-84`); `validate_output` runs jsonschema, renders max 10
  errors as JSON-pointer paths (`:87-106`).
- Retry: exactly ONE correction turn carrying the validation errors verbatim, schema never
  re-pasted (`tools/delegate_tool_child_run.py:478-518`; `build_retry_message`
  `tools/delegation_output_schema.py:109-115`); skipped when interrupted or empty.
- Failure handling: a miss after the retry does NOT fail the run. Status stays `completed`, the
  summary keeps the child's raw text, and the entry gains `schema_valid: false` +
  `schema_errors` + `schema_retries` + `schema_note` (raw UNVALIDATED text, extract what you
  need yourself rather than re-running; `tools/delegate_tool_child_run.py:580-585,626-640`).
  Rationale in-code: 68-minute audits were once written off as failed over a stray code fence.

### 2. Role/depth semantics

- Roles are `leaf` / `orchestrator` (`tools/delegate_tool.py:60`); the `role` kwarg is legacy
  and IGNORED. Capability is depth-derived: a child is orchestrator iff the kill switch is on
  and `child_depth < max_spawn_depth`, else leaf (`tools/delegate_tool.py:226-229`).
- Default is FLAT: `MAX_DEPTH = 1` (`tools/delegate_tool_config.py:21`); spawning at
  `depth >= max_spawn_depth` is refused with a raise-the-knob error
  (`tools/delegate_tool.py:510-517`); `delegation.orchestrator_enabled` forces all-leaf
  (`tools/delegate_tool_config.py:165-173`).
- `DELEGATE_BLOCKED_TOOLS` for every child: `delegate_task`, `clarify`, `memory`,
  `send_message`, `cronjob_manage`, `start_chat` (`tools/delegate_tool_toolsets.py:14-23`);
  only orchestrator gets `delegate_task` back (`:68-76`); children never gain a tool the parent
  lacks; `kanban` always stripped (`:78-124`).
- The child prompt carries the role's when/when-not-to-delegate rules plus a depth note that is
  literal config truth (`tools/delegate_tool_progress.py:156-176,210-216`).

### 3. Child summary budgets

- Static ceiling `delegation.max_summary_chars` (default 24000, 0 disables); dynamic budget =
  50% of the parent's REMAINING context headroom, split across the batch at ~4 chars/token,
  floor 2000; effective cap = min of the two (`tools/delegate_tool_results.py:158-166,239-294`).
- Over-cap summaries become a 75% head / 25% tail window snapped to line boundaries; the full
  text spills to `cache/delegation/subagent-summary-*.txt` and a footer gives the exact
  `read_file` offset for the omitted middle (`:187-223`); entry gains `summary_truncated` +
  `summary_full_path`.
- Receipt: only the summary re-enters the parent; intermediate tool calls never do
  (`tools/delegate_tool.py:8-11`). Full fidelity = per-task live transcript files, returned as
  paths (`tools/delegate_tool_dispatch.py:215-217,341-344,365-367`).

### 4. background=true re-entry + dedup

- Top-level delegations ALWAYS run in the background (the model does not choose;
  `tools/delegate_tool.py:772-778`); depth > 0 is synchronous so orchestrators join workers.
- Dispatch returns a handle (`status: dispatched`, ids, live transcript paths, control hint;
  `tools/delegate_tool_dispatch.py:347-368`); children are detached from parent interrupt
  fan-out (`:446-447`).
- Completion: a `type="async_delegation"` event is pushed onto the shared completion queue and
  surfaces as a NEW turn, only between turns (`tools/async_delegation.py:6-8,924-971`); the
  model is told to finish independent work, end its turn, and never poll transcripts
  (`tools/delegate_tool_dispatch.py:324-334`).
- Dedup/durability: a SQLite ledger row per delegation with delivery_state
  pending/delivered/dropped; atomic cross-process claim, 8 delivery attempts, 300s claim lease,
  48h replay age (`tools/async_delegation.py:40-51,438-513`); restart replay stamps
  `restored=True` so only a proven owner consumes (`:310-359`); an orphan sweep runs every 30s
  (`:362-404`); interim per-task failure notices are exempt from claim/dedup (`:454-458`).
- Sync fallbacks with an explanatory note when the session cannot receive detached results or
  the pool is at capacity (`tools/delegate_tool_dispatch.py:222-241`).

### 5. Worktree isolation (`delegation.worktree_isolation`)

- Opt-in, default off; git-only and local-terminal-backend-only, silently ignored otherwise
  (`tools/delegate_tool_config.py:115-119`; `tools/delegate_tool_child_run.py:384-403`).
- One worktree per child at `<repo>/.worktrees/subagent-<id>`, branch `hermes-subagent/<id>`
  off parent HEAD; `.worktrees/` auto-gitignored;
  hardened non-interactive git env (GHSA-7x36-8jrh-v4pw); any failure degrades silently to the
  shared workspace (`tools/subagent_worktree.py:62-103`).
- Child cwd is seeded to the worktree and the goal gains the isolation contract: work only
  there, commit to your branch, the parent reviews and merges; zero commits + clean tree means
  the worktree is discarded automatically (`tools/delegate_tool_child_run.py:747-769`;
  `tools/subagent_worktree.py:196-206`).
- Finalize prunes ONLY on proof: commits == 0 AND clean AND both git probes succeeded; any
  probe failure keeps the worktree and flags `inspection_failed` (commits/dirty UNKNOWN, not
  proven zero) (`tools/subagent_worktree.py:137-193`); the result entry carries a `worktree`
  payload `{path, branch, commits, dirty, pruned}` (`tools/delegate_tool_child_run.py:732-745`).
- Cost: a full working-tree checkout per child (shared object store) plus merge burden on the
  parent; that is why it is off by default.

### 6. Ephemeral child prompt: what leaks, what is excluded

- Fresh conversation by construction: `ephemeral_system_prompt`, `platform="subagent"`,
  `skip_context_files=True, skip_memory=True, clarify_callback=None`
  (`tools/delegate_tool.py:274-287`). Excluded on purpose: parent history, MEMORY.md, clarify
  prompts, SOUL.md identity.
- What DOES flow: goal as the first user turn (kept out of the system prompt;
  `tools/delegate_tool_progress.py:185-187`), the per-task `context` string only (each child
  sees only its own context; repeat shared background per task,
  `tools/delegate_tool.py:713-717`), credentials/model/runtime inheritance, the parent's
  `prefill_messages` and `request_overrides` (`tools/delegate_tool.py:269,275`), and exactly one
  deliberate re-inclusion: repo conventions (AGENTS.md / CLAUDE.md) via
  `build_context_files_prompt(cwd=workspace, skip_soul=True)` so a child is not blind to the
  repo's rules (`tools/delegate_tool_progress.py:197-208`).
- Workspace hint only ever a concrete absolute directory (`:219-232`). Schema text states the
  rule: children know nothing of this conversation, pass everything via context
  (`tools/delegate_tool.py:634-636`).

## Ranked ports (5 PORT, 3 SKIP)

### P1. Schema-validated lane envelope + one re-prompt. VERDICT: PORT

- Evidence: `delegation_output_schema.py:45-57,87-115`; `delegate_tool_child_run.py:478-518`
  (exactly one retry); `:626-640` (never discard the raw result).
- Gap: the ZTORCH lane return is prose (15-line Scope/Result/Key-files/Issues);
  `scripts/lane_validate.py` regex-matches the log line, not a machine-readable return, so a
  narrative verdict with the observable buried or absent is caught only by brain discipline.
- Design: slot (f) contract gains: the lane's LAST write into its capture dir is
  `envelope.json` with keys `scope, result, verdict, failure_class, key_files, issues`
  (terminal-status-first, before post-processing); the prose return stays 15 lines and points
  at it. `scripts/lane_validate.py` gains envelope mode: for each closed lane line, parse
  `envelope.json`, check required keys (and `failure_class` on negatives), cross-check
  `verdict`/`key_files` against the lane line's SUCCESS criterion via existing `criterion_met`
  (`scripts/lane_validate.py:200-213`). Malformed or missing: the brain re-prompts the SAME
  agent handle exactly once with the validation errors verbatim (hermes `build_retry_message`
  shape); a second miss files the lane NOT VERIFIED, raw capture kept.
- Files: `scripts/lane_validate.py`; `skills/workflow/exec/delegate/SKILL.md` slot (f);
  `skills/workflow/brain/SKILL.md` dispatch hygiene.
- Effort: M (about 60 validator lines + skill text + one assert test).

### P2. Brief pre-dispatch quality gate. VERDICT: PORT

- Evidence: `delegate_tool_tasks.py:14-65`: placeholder goals (`todo`, `task N`), unexpanded
  template markers (snake-case `<feature_name>` / `{file path}` shapes), and sub-10-char goals
  in multi-task fan-outs are rejected with actionable errors BEFORE any child spawns;
  duplicate goals deliberately allowed (best-of-N is legitimate).
- Gap: slot (a)'s 4-field gate is doctrine only; a guess-wearing-a-checklist dispatch burns
  tokens before anyone notices.
- Design: extend `lane_validate.py --brief` (already warns on capture-less SUCCESS criteria,
  `scripts/lane_validate.py:220-232`): also flag placeholder/template-marker goal text, a
  SUCCESS criterion with zero checkable tokens (reuse `has_checkable`), and a missing 4-field
  element. Brain rule: any WARN means fix the brief before dispatch.
- Files: `scripts/lane_validate.py`; `skills/workflow/brain/SKILL.md`.
- Effort: S (about 30 lines + test).

### P3. Explicit context contract in the shared lane preamble. VERDICT: PORT

- Evidence: `delegate_tool.py:274-287` (skip flags, fresh conversation), `:634-636` (children
  know nothing of this conversation), `:713-717` (repeat shared background per task); the one
  deliberate re-inclusion of repo conventions `delegate_tool_progress.py:197-208`.
- Gap: ZTORCH briefs share a byte-identical preamble for slots a/c/d/e/g but state no context
  boundary; briefs sometimes paste board/state summaries in (bloat, staleness) or assume the
  lane knows the engagement.
- Design: add a CONTEXT RULES block to the shared preamble: the lane receives ONLY this brief,
  the files it names by path, and nothing else; no board, no other lanes' returns, no wiki
  curation rights, no prior-turn memory; shared background is repeated in each brief that
  needs it. Mirror hermes's single deliberate inclusion: when a lane edits vault files, the
  binding AGENTS.md rules travel in the brief.
- Files: `skills/workflow/brain/SKILL.md` (shared section); `skills/workflow/exec/delegate/SKILL.md`
  slot (a).
- Effort: S (doc-only).

### P4. Per-lane expected window: aging + 80% wrap-up nudge. VERDICT: PORT

- Evidence: hermes differentiates staleness (idle 450s vs in-tool 1200s,
  `delegate_tool.py:106-116`), restarts the budget on any progress
  (`delegate_tool_child_run.py:789-825`), and fires a one-time 80% warning through the steer
  channel telling the child to wrap up and return (`:228-245`).
- Gap: ZTORCH ages every open lane at a flat 45 minutes (`scripts/lane_validate.py:70`,
  consumed by status.py) although slot (g) already promises a specified window; a 5-minute
  watch lane and a 3-hour watch lane get the same false STALE clock.
- Design: lane line gains an optional `window Nm` cell (extend `_LANE_RE`,
  `scripts/lane_validate.py:31-33`); `lane_lines`/`fresh_lane_open` age against the declared
  window (default unchanged at 45); brain rule: at roughly 80% of the window send one
  STOP-REASON-shaped wrap-up steer to the lane handle (composes with the ported steer).
- Files: `scripts/lane_validate.py`; `scripts/status.py`; `skills/workflow/brain/SKILL.md`.
- Effort: S.

### P5. Worktree isolation for code-editing lanes, opt-in. VERDICT: PORT (scoped)

- Evidence: `subagent_worktree.py:75-103` (create, silent degrade), `:137-193` (prune only on
  proof, `inspection_failed` payload), `delegate_tool_child_run.py:747-769` (cwd seed + goal
  contract note), default off `delegate_tool_config.py:115-119`.
- Gap: parallel ZTORCH lanes that edit code share one checkout (the vault repo during harness
  work; a `raw/research` project dir): two edit lanes collide and a failed lane leaves a dirty
  tree; `scripts/checkpoint.py` restores state but does not isolate concurrent writers.
- Design: new `scripts/lane_worktree.py` (create/finalize; worktrees under
  `targets/<eng>/worktrees/<lane>/` or vault `.worktrees/`, branch `ztorch-lane/<lane>`; prune
  only on commits == 0 AND clean; keep + `inspection_failed` otherwise). Lane manifest gains a
  known `worktree: true` key (`scripts/lane_manifest.py:32`); the brief's paths point into the
  worktree; the envelope carries the worktree payload and the brain reviews and merges. Scope:
  vault repo and `raw/research` workspaces only; `raw/git` clones stay read-only (a worktree
  add writes admin files into the clone's `.git`, violating the raw/ rule).
- Files: new `scripts/lane_worktree.py`; `scripts/lane_manifest.py`;
  `skills/workflow/brain/SKILL.md`.
- Effort: M-L (about 120 lines + tests + merge doctrine).

### P6. Mechanical summary budget in the envelope. VERDICT: SKIP

- Evidence: `delegate_tool_results.py:158-294` (ceiling, headroom fraction, head/tail trim,
  spill file + read offset footer).
- Rationale: ZTORCH already lands the full report as a FILE in the capture dir and caps the
  returned envelope at 15 lines (delegate slots (f)/(h); brain dispatch hygiene); the
  parent-context blowout hermes defends against cannot occur through a file-path report. The
  one port-worthy fragment, trim plus a pointer to the full file, is already the ZTORCH shape.
- Revisit only if envelopes start carrying bodies instead of paths.

### P7. Role-based toolsets / structural leaf enforcement. VERDICT: SKIP

- Evidence: `delegate_tool_toolsets.py:14-23,68-124` (blocked frozenset, orchestrator re-grant,
  parent-subset intersection).
- Rationale: "a worker never spawns its own subagent" is already prompt law in two skills, and
  ZTORCH has no toolset layer to strip: lanes get the harness's fixed surface; the brain cannot
  remove the Agent tool from a subagent. Depth is flat by construction, which is hermes's own
  default (`MAX_DEPTH = 1`, `delegate_tool_config.py:21`). If a lane role ever legitimately
  fans out, port the depth-derived role note (`delegate_tool.py:226-229`) as brief text then.

### P8. Durable background-result ledger (re-entry + dedup). VERDICT: SKIP

- Evidence: `async_delegation.py:40-51,310-404,438-513` (SQLite delivery ledger, atomic claims,
  8 attempts, 48h replay, orphan sweep, interim-notice exemption).
- Rationale: hermes needs durable re-entry because the parent PROCESS may exit before detached
  children finish. ZTORCH lanes are harness Agent-tool subagents in an operator-attended
  session: completion notifications, the log.md lane line with handle, and status.py aging
  already cover re-entry, one-line-per-handle dedup, and lost-lane surfacing; a second
  persistent queue would duplicate the log's job. The one doctrinal fragment hermes states
  (results arrive between turns, never poll) already exists verbatim as ZTORCH's "never poll a
  running lane" rule.

## Not proposed

Steer/missed-steer, usage telemetry, concurrency caps: DONE in wave 3a
(`docs/port-specs/README.md` status table). Per-task early failure notices
(`push_task_failure_notice`, `async_delegation.py:975-1007`) are inherent in ZTORCH's
per-agent completion notifications. Sibling-write reminders
(`delegate_tool_child_run.py:969-988`) are moot: ZTORCH lanes never edit shared files in place
(PENDING-WRITE rule, delegate slot (f)).
