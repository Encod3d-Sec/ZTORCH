---
title: "Port spec: hermes subsystem triage"
type: docs
tags: [docs, port-spec, hermes, triage]
date_created: "2026-10-12"
sources: [raw/git/hermes-agent]
---

# Subsystem triage verdicts (from hermes-agent source audit)

PORT: checkpoints + repair-ledger discipline (shadow-git snapshots before destructive writes via GIT_DIR+GIT_WORK_TREE so no git state leaks; bounded-retry persistent attempt ledger with fingerprint refusal after 3 fails; forensic backups deduped + capped + disk-headroom gate). Doctor Finding pattern (ordered checks tuple, Finding accumulator, numbered manual-fix summary, --fix, --ack persistent suppression, nonzero exit on issues; check list maps to hook registration, scope files, qmd index, VM SSH, wiki lint). Hooks consent ledger + hooks test payload mode (approval keyed (event,command) with script-mtime drift warning). Engagement watcher (60s tick, flock single-ticker, heartbeat-with-error-reason sidecar, claim-once delivery queue where death-after-claim = unknown, never retried; tails engagement log.md/OOB state, pushes Telegram digests). Watch-pattern process monitor (rolling 200KB tail, per-process regex watch list emitting events, processes.json crash-recovery checkpoint, parent-first SIGTERM teardown). Subagent steer semantics (steer queues text merged at the NEXT tool-result boundary never mid-call; undeliverable = missed_steer on completion; list/steer/stop scoped to own spawn tree; bounded FIFO 200 recent children). Context manifest + injection scan (which vault files actually load, token cost, injection-pattern flags). PreCompact must-survive block (board + active lanes injected as a marked block; markers non-prose so the model cannot imitate them).

SKIP (with why): context compression core (harness owns it), kanban (board = markdown + offensive.py next; steal heartbeat/stale/orphan-reconcile semantics into lane_validate instead), todo tool (Claude Code TodoWrite; one rule transfers: re-inject only ACTIVE items after context loss), ACP adapter (ZTORCH is a client, not a server), gateway daemon + platform adapters (watcher port covers the need), skins (no persona surface), FTS5 machinery (qmd owns keyword indexing; keep the pre-open handler split idea: repair tools must never require the thing they repair), Honcho dialectic (external API, single-operator vault).

## Ranked PORT-FIRST designs

1. Shadow-git checkpoint manager: shared store (GIT_DIR+GIT_INDEX_FILE outside the vault), snapshot targets/<eng>/ before write-heavy driver phases, list/restore/prune by retention+size.
2. Steer/missed_steer lane contract: lane briefs gain steer (queued text merged at next file-write boundary, never mid-command), completions report missed_steer; brain gets list/steer/stop verbs over a live+recent lane registry file.
3. Doctor rework: Finding accumulator + numbered summary + --fix + --ack ledger; checks = hooks registered+approval-drift, scope/state files, qmd index fresh, VM SSH alive, wiki lint.
4. Engagement watcher tick: stdlib 60s loop, flock, heartbeat/error sidecar, claim-once Telegram digests of log.md/OOB deltas.
5. Watch-pattern process monitor for VM/background runs: registry + rolling tail + regex watch events into log.md and the watcher.
