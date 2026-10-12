---
title: "Hermes -> ZTORCH port plan"
type: docs
tags: [docs, port-spec, hermes, plan]
date_created: "2026-10-12"
sources: [raw/git/hermes-agent]
---

# Hermes -> ZTORCH native port plan

Goal: incorporate every hermes capability that improves this harness, as NATIVE ZTORCH machinery (markdown vault + stdlib python scripts + shell hooks). Hermes is reference material only (raw/git/hermes-agent, read-only); ZTORCH never invokes it.

| Hermes capability | ZTORCH gap | Native port | Wave |
|---|---|---|---|
| Agent-curated memory (2 stores, budgets, frozen snapshot, nudge) | session/memory.md referenced but absent; no store semantics, no injection | scripts/memory.py + session/memory.md two sections + SessionStart snapshot injection + Stop-hook nudge | 1 |
| Session search (4 shapes, demote automation, lineage dedup) | engagement history unsearchable | scripts/session_search.py over targets/*/log.md + session/log.md | 1 |
| Self-generated skills mid-run + guardrails | learn is close-out only | scripts/skill_manage.py + skill_use/patch telemetry + nudge | 1 |
| Curator lifecycle (stale/archive, exemptions) | skills never age | scripts/curator.py (frontmatter states, git-mv archive, 14d/30d) | 1 |
| Docker lane sandbox + manifests + creds scrub | lanes run raw | scripts/lane-run.sh + lane manifest format | 2 |
| Command-safety tiers (hardline/dangerous) | only scope-guard + sleep/drift | hardline deny + dangerous advisory patterns in a lane-guard hook | 2 |
| Usage/cost telemetry per dispatch | spend cap exists, no per-lane capture | Agent-tool PostToolUse cost capture into .metrics.json | 2 |
| Checkpoints (shadow-git) + repair ledger | none (git history only) | scripts/checkpoint.py | 3 |
| Steer/missed_steer lane contract | SendMessage exists, no contract | lane brief steer semantics + lane registry file | 3 |
| Doctor Finding pattern + --fix/--ack | offensive-doctor is flat | rework scripts/offensive-doctor.py | 3 |
| Engagement watcher (async operator digests) | none | scripts/watcher.py (60s tick, claim-once, default off) | 3 |
| Watch-pattern process monitor | tmux manual | process registry + regex watch events | 3 |
| Context manifest + injection scan | partial (skill-lint) | context manifest report in doctor | 3 |
| PreCompact must-survive block | pre-compact.sh exists | extend with board+lane marked block | 3 |

Skipped with rationale: subsystems-triage.md. Specs: memory.md, self-improvement.md, sandbox-tooling.md.

Each wave: implement, assert-based tests (tests/test_*.py), wiring (AGENTS.md/engage/skill-map/layout as needed), commit. Iterate until test-green.

## Status (2026-10-12)

| Port | State | Tests |
|---|---|---|
| memory.py + SessionStart injection + Stop nudge | DONE (wave 1) | 7 |
| session_search.py | DONE (wave 1) | 3 |
| skill_manage.py + ledger | DONE (wave 1) | 4 |
| curator.py lifecycle | DONE (wave 1) | 4 |
| lane-run.sh + lane_manifest.py (docker sandbox) | DONE (wave 2a, live-verified once) | 15 |
| lane-guard.py hardline/dangerous hook (registered x4) | DONE (wave 2b, head-position rule) | 12 |
| delegate steer/missed-steer + usage telemetry | DONE (wave 3a, doctrine) | - |
| PreCompact must-survive data block | DONE (wave 3a) | - |
| checkpoint.py shadow-git manager | DONE (wave 3b) | 7 (+9 eng-ckpt coexist) |
| offensive-doctor Finding rework | DONE (wave 3c; live 37 checks green) | suite |
| watcher.py + pmonitor.py | DONE (wave 3d; default-off, env-gated Telegram, dry-mode safe) | 7 |

Final full-suite sweep: 89 test files, 0 failures. All ported capabilities are DONE; skipped-with-rationale list lives in subsystems-triage.md.
