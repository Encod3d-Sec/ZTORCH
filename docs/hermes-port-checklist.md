# hermes-agent read checklist (exhaustive, per file)

Scope: every implementation file of the subsystems the port touches: memory,
skills + curator, background review, compression/context/token control,
auxiliary (cheap-model) routing, delegation, session search, and the turn-loop
files that own token-relevant decisions. Source: `raw/git/hermes-agent` @
41cd7b64 (2026-10-12).

Status semantics:
- `[x]` read IN FULL + digested (line refs held)
- `[x] ip` integration-pass: the call sites that matter for the port were read
- `[ ]` pending, wave number noted
- `OUT` read + ruled out of the port with the reason in the digest

Out of the inventory entirely (different subsystems, nothing to port):
`gateway/` (20-platform chat adapters), `ui-tui/ tui_gateway/ web/ apps/`
(UIs), `cron/ kanban` (scheduler), `pm/ hermes_platform/` (env management),
`tools/browser_* bot_* approval_*` (browser/bot/approval plumbing),
`hermes_state_*.py` (session DB; FTS subset included below), i18n, providers
adapters, evals/tests (behavior contracts for hermes CI, not port surface).

## Memory

| Status | File | Lines | Read by | Digest / port verdict |
|---|---|---|---|---|
| [x] | agent/memory_manager.py | 985 | lane-mem | Orchestrator over provider plugins; per-turn prefetch, fenced `memory-context` injection appended to user msg (never system prompt); egress scrub `_redact_for_provider`; spill ceiling max(10x,100k). PORT: sidecar-injection + scrub rule. |
| [x] | agent/memory_provider.py | 206 | lane-mem | Provider ABC + `spawn_context_thread` (contextvars copy) + trivial-prompt regex gate (skip recall on greetings/acks/slash). PORT: trivial-gate idea. |
| [x] | plugins/memory/__init__.py | 591 | lane-mem | Plugin discovery, bundled-first, one external provider max. OUT: plugin loader for a single-store vault. |
| [x] | plugins/memory/config_schema.py | 133 | lane-mem | Config schema for memory plugins. OUT: no plugin config layer in ZTORCH. |
| [x] | plugins/memory/query_rewrite.py | 117 | lane-mem | Aux-model query rewrite: 1 English question, max_tokens 96, input cap 4000, must start with question word, else fall back to raw. PORT: candidate for wiki/qmd queries. |
| [x] | plugins/memory/retaindb/__init__.py | 492 | lane-mem | Cloud retaindb + SQLite write-behind queue replayed on startup; server-side top_k=8. OUT: cloud store; write-behind durability pattern noted. |
| [x] | plugins/memory/byterover/__init__.py | 282 | lane-mem (skim) | Shells to `brv` CLI, curates turns/query tree. OUT: external CLI store. |
| [x] | tools/memory_tool.py | 457 | lane-mem | Model-facing memory tool; unattended fork may ADD but never replace/remove (destructive staged for human approval). PORT: already the ZTORCH add-only reviewer rule. |
| [x] | tools/memory_tool_store.py | 606 | lane-mem | Two bounded stores (2200/1375 chars), `ENTRY_DELIMITER`, dedupe on add + load, budget on FINAL batch state, batch may not empty store, consolidation failure cap 3/turn then terminal stop. PORT: already ported; failure-cap + current-entries echo still missing. |

## Background review (the Stop-hook reviewer hermes runs)

| Status | File | Lines | Read by | Digest / port verdict |
|---|---|---|---|---|
| [x] | agent/background_review.py | 1340 | lane-mem | Forked AIAgent on warm prefix cache (~26% cost cut); digest replay tail 24 msgs (USER 300/ASSISTANT 200 chars); 16-iter cap; input budget 75% of window, cap 600k; tool whitelist dispatch-side; prompt trio (routing/do-not-capture/lesson). PORT: prompt trio + whitelist discipline into memory-review.py. |
| [x] | agent/review_engine.py | 195 | lane-mem | NOT memory: the `/review` code-reviewer subagent (10-msg snapshot, 12k/msg cap). OUT: different feature; shape noted for verifier lanes. |
| [x] | agent/review_idle_queue.py | 211 | lane-mem | One pending review per session, newest snapshot wins, 15s idle dispatch, 30min age-out, 3 requeues. PORT: coalescing rule for our detached reviewer. |

## Skills + curator

| Status | File | Lines | Read by | Digest / port verdict |
|---|---|---|---|---|
| [x] | tools/skills_tool.py | 726 | lane-skl | 3-tier progressive disclosure (list = name+desc; view = SKILL.md + linked-file manifest by fixed glob table; view file = one support file); 30s TTL catalog cache; usage sidecar bumps; deps auto-install. PORT: glob manifest + dedup stub. |
| [x] | tools/skills_tool_dedup.py | 90 | lane-skl | Repeat-view stub keyed (task,name,file) with stat fingerprint; cleared on compaction; cap 200 FIFO. PORT: cheap, worth it. |
| [x] | tools/skill_manager_tool.py | 925 | lane-skl | create/patch/edit/delete lifecycle; validation ladder (name regex+64, frontmatter, desc<=60 AT CREATE, body non-empty, 100k cap); guarded atomic write with rollback; per-skill lock; ledger + cache clear. PORT: validation ladder into skill_manage.py. |
| [x] | tools/skill_manager_guards.py | 252 | lane-skl | Delete defense (no symlinks, never root, pinned/essential exempt), background-fork delete needs `created_by:agent` + read-before-write + `absorbed_into`. PORT: pin + archive-not-delete already in ZTORCH curator; read-before-write for auto-edits. |
| [x] | agent/skill_utils.py | 866 | lane-skl | Roots precedence, excluded dirs, collision policy (tier, realpath/sha256 identical dedupe, refuse genuine ties), desc limits (60 create / 1024 hard / 57+ellipsis index). PORT: collision policy for vault skills. |
| [x] | agent/skill_commands.py | 900 | lane-skl | `/skill` expands FULL body into a USER message (cache-safe), scaffold markers, config values resolved; stacked loads <=5. PORT: injection-shape rule already matches ZTORCH Skill tool. |
| [x] | agent/skill_preprocessing.py | 156 | lane-skl | `${HERMES_SKILL_DIR}` expansion; inline shell off by default, 4k cap. OUT mostly; path-expansion idea noted. |
| [x] | agent/skill_bundles.py | 206 | lane-skl | YAML bundles loading N skills under one command. OUT for now (ZTORCH has engage as router). |
| [x] | agent/skills_index_delta.py | 136 | lane-skl | Per-turn diff of prompt index vs catalog; added/removed skills delivered as one-shot user note, never a mid-conversation rebuild. PORT: the cache-sacred rule, already ZTORCH policy. |
| [x] | agent/curator.py | 1212 | lane-skl | 7d interval, stale 14d, archive 30d, LLM consolidation OFF by default; deterministic transitions; use_count==0 never archived young; cron-referenced = pinned; fork has skills-toolset only (no terminal), structured yaml verdict reconciled against tool-call audit. PORT: thresholds already ZTORCH; audit-reconcile is the upgrade. |
| [x] | agent/curator_backup.py | 492 | lane-skl | Pre-run tar.gz (keep 2, excludes .git/venv), rollback safety-snapshot first. PORT: cheap backup before curator runs. |
| [x] | agent/prompt_builder.py | 1883 | lane-skl | Skills index block (category rows, desc 57+ellipsis), LRU + disk snapshot cache keyed on file-signature manifest. PORT: manifest-keyed invalidation for skill index. |
| [x] | agent/system_prompt.py | 879 | lane-skl | Byte-stable system prompt; skills block omitted when tools absent; memory snapshot frozen in. PORT: principle only (harness owns this). |
| [x] | tools/skill_manager_batch.py | 308 | w2b | Atomic multi-op batches: shape-validate every op pre-effect, per-skill snapshot, rollback all on failure, delete must be sole op, cap 20 ops. PORT. |
| [x] | tools/skill_ledger.py | 633 | w2b | Append-only JSONL ledger + sha256 blob store, delta-dedup drops unchanged paths, cap 5MB trim to 0.8 low-water, fail-closed rollback with safety entry. PORT. |
| [x] | tools/skill_linter.py | 215 | w2b | Advisory lint: body budget 24000 chars, references sprawl over 60 files, incident-log shape rules, dangling refs, POSIX primitives need `platforms:`. PORT. |
| [x] | tools/skill_provenance.py | 44 | w2b | Two ContextVars: write-origin (foreground vs background_review sentinel) + review-attended flag. PORT: lane-vs-operator write separation. |
| [x] | tools/skills_guard.py | 958 | w2b | ~100-pattern regex security scanner (v10), exfil/injection/persistence tiers, community blocks on caution, `--force` never overrides dangerous, caps 50 files/256KB/5MB. PORT. |
| [x] | tools/skills_ast_audit.py | 92 | w2b | AST scan flagging dynamic import/importlib shapes; hints not verdicts. PORT: cheap pre-ingest check. |
| [x] | tools/skills_tool_plugin.py | 173 | w2b | `plugin:skill` names, disabled gates, traversal-checked serving, injection patterns logged. PART: no plugin namespaces. |
| [x] | tools/skills_tool_setup.py | 150 | w2b | Merges required env vars + collect_secrets + legacy prerequisites into validated entries; interactive-only prompts. PART: readiness concept. |
| [x] | tools/skill_usage.py | 748 | w2b | Sidecar `.usage.json` keyed by name (never frontmatter): use/view/patch counters, patch_generation, created_by, first_seen clock anchor, state+pinned, flock. PORT. |
| [x] | tools/skills_sync.py | 494 | w2b | Manifest `name:hash`: update only when bundled changed AND user copy hash-matches origin; deleted never re-added; rename recovery hash-identical only. PORT. |
| [x] | tools/skills_sync_optional.py | 235 | w2b | Backfills hub-lock provenance for byte-identical copies; restore moves to timestamped backups. PART: ZTORCH sync is git-side. |
| [x] | tools/skills_sync_bundled_ops.py | 260 | w2b | reset/diff/list-modified/opt-out/remove-pristine (hash-identical only, dry_run). PORT. |
| [x] | tools/skills_hub.py | 418 | w2c | Hub facade: PEP 562 dynamic paths, SSRF+policy-guarded HTTP (5 redirect hops max), index cache TTL 3600s. OUT: marketplace plumbing. |
| [x] | tools/skills_hub_search.py | 271 | w2c | Source router + parallel fan-out: overall_timeout 30s, 8 daemon workers, index-miss budget 8s, trust-ranked dedupe. OUT: orchestration only. |
| [x] | tools/skills_hub_clawhub.py | 578 | w2c | ClawHub adapter: catalog walk 12s, ZIP cap 25MiB, per-file 500KB skip. OUT. |
| [x] | tools/skills_hub_github.py | 619 | w2c | GitHub adapter: auth cascade, tree-SHA pinning kills fetch TOCTOU, retry wait cap 60s. OUT. |
| [x] | tools/skills_hub_install.py | 326 | w2c | Quarantine staging, symlink/escape/root-equal refusals, hash symmetric with scan. PART: destructive-boundary checks. |
| [x] | tools/skills_hub_models.py | 341 | w2c | TRUST_RANK builtin 2 / trusted 1 / community 0, dedupe-by-trust, PurePosix validators rejecting `..`. PART. |
| [x] | tools/skills_hub_official.py | 401 | w2c | Optional-skills + centralized index source, upstream stubs refetched. OUT. |
| [x] | tools/skills_hub_skillssh.py | 383 | w2c | skills.sh sitemap-walk adapter, gzip-only headers, badge scrape. OUT. |
| [x] | tools/skills_hub_sources.py | 431 | w2c | well-known/URL/LobeHub adapters: same-origin support files only, name regex. OUT. |

## Compression + context (token fighting)

| Status | File | Lines | Read by | Digest / port verdict |
|---|---|---|---|---|
| [x] | agent/context_compressor.py | 5852 | lane-tok | Phased compress: LLM-free tool-result pruning first (md5 dedupe, per-tool stubs with `FAILED:` suffix, 200-char floor, keep-newest windows, never stub the pending round), structured single-aux-call summary, verbatim head/tail protection, anti-thrash breaker judged on REAL prompt tokens (2 strikes = 300s block + 1 probe), lean mode verbatim-quote + regex-anchor sections. PORT: pruning rules + breaker + lean sections. |
| [x] | agent/context_compressor_prellm.py | 92 | lane-tok | Skip the summary LLM when middle < 10% of threshold or 2 fallbacks benched the model 300s. PORT: skip-LLM gate. |
| [x] | agent/context_compressor_summary.py | 103 | lane-tok | Summary text assembly helpers. PORT: with compressor. |
| [x] | agent/context_compressor_telemetry.py | 139 | lane-tok | Compaction telemetry events. OUT: no bus in ZTORCH. |
| [x] | agent/micro_compaction.py | 521 | lane-tok | OFF by default (breaks cache every turn); absorbs ONE exchange/turn into rolling summary, aux call 1500 tokens, defrag at 2000, 3-fail skip. OUT (cache-hostile by design). |
| [x] | agent/native_compaction.py | 421 | lane-tok | OpenAI server-side compaction; NOT portable (provider-owned). OUT. |
| [x] | agent/relay_compaction.py | 93 | lane-tok | Relay provider compaction shim. OUT. |
| [x] | agent/turn_context_compaction.py | 507 | lane-tok | Turn-start orchestration: preflight threshold check (raw-char gate 4 chars/token), max 3 attempts, <5% progress blocks, API-count refund. PORT: attempt/progress gates for any local trim. |
| [x] | agent/context_engine.py | 250 | lane-tok | Context-engine plugin ABC; provider context capped 6000 chars before summarizer. PORT: cap constant. |
| [x] | agent/context_breakdown.py | 347 | lane-tok | 8-category token accounting, usage-anchored occupancy; per-skill and per-toolset tables. PORT: extend token-audit.py. |
| [x] | agent/context_pin.py | 73 | lane-tok | Explicit context-length pin beats metadata, one-time warning. OUT (harness knows window). |
| [x] | agent/context_references.py | 699 | lane-tok | `@file` expansion bounded: max 16 refs, 25% soft/50% hard window refuse, oversized becomes pointer block, 4MB pipe drain + SIGKILL. PORT: pointer-block + subprocess caps. |
| [x] | agent/context_file_sources.py | 125 | lane-tok | Per-file manifest (loaded/truncated/shadowed) with est_tokens. PORT: audit surface. |
| [x] | agent/bounded_response.py | 79 | lane-tok | 64KB/10s bounded error-body reads, daemon drain, keep partial. PORT: capture tools. |
| [x] | agent/command_token_source.py | 149 | lane-tok | Token accounting for shell commands. PORT: with breakdown. |
| [x] | agent/image_token_cost.py | 149 | lane-tok | Per-image token price LEARNED from usage residual, EMA 0.5, band 64-32768, default 1500. PORT: screenshot-heavy evidence accounting. |
| [x] | agent/conversation_compression.py | 4564 | w1b | Compress facade: commit fence, durable lease TTL 300s, stall ladder (idle 120s / ceiling 600s / pool 4), split-failure cooldown 60s, in-place + rotation commits. PART: fence/cooldown/timeout patterns port; lease/commit is loop-owned. |
| [x] | agent/compression_facade.py | 328 | w1b | Per-attempt fence stack, progress-timeout over deep-snapshot worker (never the live list), persisted-marker mirror. PART: snapshot-worker pattern. |
| [x] | agent/compression_marker.py | 86 | w1b | Non-imitable elision marker (per-instance omitted/total counts, never-reproduce wording) + `elide`/`elide_middle`. PORT: dependency-free, fits ZTORCH tool-output truncation. |
| [x] | agent/conversation_compression_manual.py | 163 | w1b | One `/compress` core for all surfaces: `here [N]`/focus/`--preview` parse, force bypasses cooldown, MIN_MESSAGES=4, verbatim-tail rejoin. PART: parser/preview portable. |
| [x] | agent/conversation_compression_reply_anchor.py | 251 | w1b | Reinserts a just-delivered reply the engine folded away; break-even math guards re-adding. OUT: assumes list assembly we do not own. |
| [x] | agent/conversation_compression_codex.py | 136 | w1c | Delegates compaction to Codex app-server thread; non-forced skips on shared failure cooldown; failed delegate arms cooldown to stop per-turn retry. OUT: Codex-thread-specific. Cooldown-after-no-op rule noted. |
| [x] | agent/conversation_compression_archive.py | 136 | w1c | Held-row coverage for in-place archive vs watermark cap; markers `_absorbed_row_ids`; watermark fallback when newest held row inactive. OUT: SessionDB row bookkeeping. |
| [x] | agent/compaction_display.py | 54 | w1c | Strips 8 internal fields (tool_calls, reasoning, codex items ~115K tokens/27% of a 214-turn payload) from display carriers. PART: display/model projection split is generic. |
| [x] | agent/compaction_events.py | 307 | w1c | Content-free 41-field telemetry, closed outcome sets, abort-vs-fail split (`would_grow`/`no_progress`/`commit_fence_cancelled`), publish never raises, first failure WARN then DEBUG. PORT: greppable hook vocabulary. |
| [x] | agent/manual_compression_feedback.py | 96 | w1c | User-facing compress summaries; lock-holder vs failed-acquire wording; force-redacts failure reasons at UI boundary (provider text can embed creds). PORT: redact-at-boundary. |

| [x] | plugins/context_engine/__init__.py | 126 | w1c | Context-engine plugin discovery: bundled wins, user plugins gated by 8192-char text heuristic; engine named by config, default compressor. PART. |
| [x] | agent/conversation_compression_telemetry.py | 208 | w3c | Content-free per-attempt JSON log; attempt-seed ownership; effect fields dropped unless committed. PART: relay metrics wiring. |
| [x] | agent/redact.py | 1360 | w3c | Pattern-table secret scrubber; under 18 chars fully masked, else 6+4 kept; nonreusable redaction sentinel prevents writing back a dead credential. PORT. |
| [x] | hermes_cli/observability/shared_metrics_contract.py | 1900 | w3c | Closed-enum telemetry contract v4/v5 with legacy field sets. OUT: Relay subscriber schema. |
| [x] | hermes_cli/partial_compress.py | 188 | w3c | `/compress here [N]` parse (keep-last default 2, clamp 100); splits on user-message boundaries preserving alternation. PORT. |
| [x] | agent/error_classifier.py | 1504 | w3c | FailoverReason enum + ordered substring tables into ClassifiedError (retry/rotate/fallback/compress); stage order plugin, profile, special, status, code, message, transport. PORT. |
| [x] | agent/credential_pool.py | 3139 | w3c | ok/exhausted/dead rotation; cooldowns 401=300s, 429/default=3600s, sole-credential=60s; flock-serialized refresh; fail-closed quarantine. PART. |
| [x] | agent/backend_identity.py | 133 | w3c | BackendIdentity + FailureScope MODEL/CREDENTIAL/ENDPOINT; one `should_skip_candidate` predicate. PORT. |
| [x] | agent/relay_llm.py | 964 | w3c | NeMo Relay adapters, encoded-chunk pairing, 10s aclose. OUT: Relay-only. |
| [x] | agent/conversation_loop.py | 1859 | w3d | Turn driver: `_LoopState` + phase dispatch; pre-API pressure with real-usage floor, billing/overflow/deferred-result contracts, failed-turn durable close. PORT. |
| [x] | agent/usage_anchor.py | 203 | w3d | Provider usage anchor: prompt+completion + rough delta of ONLY appended messages; sha256 prefix fingerprints fail closed; persisted, restored on resume. PORT. |
| [x] | agent/model_metadata.py | 2670 | w3d | 9-step context-length resolver + estimators: CJK-aware bytes/4, wire shadow (strips images/encrypted), pinned-id memo, tools estimate. PART: estimator core portable. |
| [x] | agent/message_sanitization.py | 1006 | w3d | Surrogate sweeps, tool-call JSON repair ladder, deterministic call ids, `serialized_messages_bytes` 413 yardstick. PART. |
| [x] | agent/retry_utils.py | 195 | w3d | Jittered exponential backoff (time_ns XOR seed), Retry-After parse capped 600s, Z.AI overload long-wait schedule. PORT. |
| [x] | agent/empty_response_guard.py | 243 | w3d | Two usage-proven zero-output attempts on same (model, provider, finish_reason) skip retries straight to fallback; over-$0.25 attempt cuts budget 3 to 1; mixed evidence fails open. PORT. |
| [x] | agent/aux_accounting.py | 91 | w3c | ContextVar republished by background threads so aux usage bills the owning session; moa excluded. PORT. |
| [x] | tools/async_delegation.py | 1238 | w3c | Durable sqlite ledger; capacity rejects never queue (default 3); progress-based stall monitor 450s idle / 1200s in-tool + 120s grace; delivery 300s lease, 8 attempts, 48h replay. PORT. |
| [x] | tools/daemon_pool.py | 70 | w3c | Daemon ThreadPoolExecutor skipping `_threads_queues` so a wedged worker never blocks interpreter exit. PORT. |
| [x] | tools/delegation_output_schema.py | 115 | w3c | jsonschema contract; exactly ONE bounded retry (10 errors max) without re-pasting schema; a miss keeps the summary with `schema_valid: false`, never discards. PORT. |
| [x] | tools/subagent_worktree.py | 206 | w3c | Per-child worktree + branch; prunes only on proof (zero commits AND clean), else kept with note. PART: git-worktree lanes only. |
| [x] | tools/file_state.py | 261 | w3c | Read-stamp registry blocks cross-subagent clobbered writes; severity sibling-writer then mtime/partial; 4096-path caps. PORT. |

## Auxiliary (cheap-model side calls)

| Status | File | Lines | Read by | Digest / port verdict |
|---|---|---|---|---|
| [x] | agent/auxiliary_client.py | 8416 | w1a | Facade: auto route, client cache 64, recovery ladder (param strips -> creds -> provider fallback), transient retry 2/backoff cap 8s, no-progress 60s, unhealthy TTL 600s, per-task semaphores. PORT: ladder + per-task pinning. |
| [x] | agent/auxiliary_client_registry.py | 134 | w1a | auth_type dispatch arms; absent creds `(None,None)`. OUT: no provider zoo. |
| [x] | agent/auxiliary_wire.py | 24 | w1a | OpenAI-SDK-only message hygiene. OUT. |
| [x] | agent/auxiliary_task_config.py | 79 | w1a | Read-time `auxiliary.<task>` block, cycle-guarded `inherit_from`, 8 route keys as one unit. PORT: per-task tier table. |
| [x] | agent/auxiliary_hooks.py | 252 | w1a | per-attempt observer events, fail-open, error text capped 2000, tokens ~ chars/4. PORT: telemetry pattern. |
| [x] | agent/auxiliary_fallback_recovery.py | 50 | w1a | param-strip rungs only, each field once. OUT: harness fixes params. |
| [x] | agent/auxiliary_health.py | 73 | w1a | host-scoped quarantine: 60s transient vs 600s default hold. PORT: lane quarantine TTLs. |
| [x] | agent/auxiliary_call_outcome.py | 60 | w1a | cancel-vs-fail split, HTTP-200 embedded errors reshaped. PART: telemetry split. |
| [x] | agent/auxiliary_async_rebuild.py | 42 | w1a | carries api_key callable across rebuilds. OUT. |
| [x] | agent/auxiliary_codex_response.py | 55 | w1a | Responses normalization; partials rejected. OUT. |
| [x] | agent/auxiliary_key_rotation.py | 23 | w1a | in-place key swap in runtime dict. OUT. |
| [x] | agent/auxiliary_local_runtime.py | 35 | w1a | bare llamacpp alias -> managed local server. OUT. |
| [x] | agent/auxiliary_plugin_oauth.py | 45 | w1a | OAuth pool select + rotate. OUT. |
| [x] | agent/auxiliary_reasoning_floor.py | 126 | w1a | steps effort UP to low when off refused. OUT: no reasoning control. |
| [x] | agent/auxiliary_stream_watchdog.py | 180 | w1a | first-token vs inter-chunk windows (60s), substantive chunks re-arm, FD-safe shutdown. PART: stall-kill policy. |
| [x] | agent/auxiliary_structured_output.py | 111 | w1a | drops response_format when unsupported, 400s never memoized. OUT. |
| [x] | agent/auxiliary_unavailable.py | 275 | w1a | typed raise classes, pool cooldown, warn-once failure memory. PART: typed lane errors. |

## Delegation (subagents for cost)

| Status | File | Lines | Read by | Digest / port verdict |
|---|---|---|---|---|
| [x] ip | tools/delegate_tool.py | 803 | lane-tok | Children inherit parent model unless pinned via delegation.provider/model. PORT: already ZTORCH tier table. |
| [x] | tools/delegate_tool_child_run.py | 1090 | w2a | Child lifecycle: max_workers=1 daemon worker, heartbeat stale verdict, inactivity budget (5s poll, warn at 0.8), 1 schema retry, result entry. PORT: wait+envelope contract. |
| [x] | tools/delegate_tool_config.py | 602 | w2a | delegation.* knobs: max_concurrent_children 10, child_timeout = inactivity not wall-clock (floor 30s), deny-by-default approval. PART: knob semantics portable. |
| [x] | tools/delegate_tool_dispatch.py | 477 | w2a | Batch runner: 0.5s poll, interrupt abandons pending as interrupted, background units share one pool slot, capacity reject falls back sync. PORT: grouping + reject-not-queue. |
| [x] | tools/delegate_tool_progress.py | 436 | w2a | Child event relay, batch tags scoped per parent session `[set N - i/M]`, child prompt = goal as first user turn. PORT: attributable lane tags. |
| [x] | tools/delegate_tool_registry.py | 310 | w2a | Live registry + steer under registry lock, ownership 2-tier (weakref max 8 hops, else session lineage), recent cap 200. PORT: steer drain + ownership. |
| [x] | tools/delegate_tool_results.py | 410 | w2a | Summary budget min(24000, 50% headroom/N at 4 chars/token, floor 2000), 75/25 trim + spill file with read_file offset footer, URL cred stripping. PORT: budget/spill. |
| [x] | tools/delegate_tool_tasks.py | 162 | w2a | Input validation: template-marker goal regexes, min goal 10 chars for 2+ batches, images max 8/task. PORT: goal quality gate. |
| [x] | tools/delegate_tool_toolsets.py | 124 | w2a | `DELEGATE_BLOCKED_TOOLS` frozenset (delegate/clarify/memory/cron...); children never gain parent-lacking tools; dual strip. PORT: whole mechanism. |
| [x] | agent/delegation_context.py | 184 | lane-tok | Kanban identity fencing, NOT model selection. OUT for cost; env-scrub idea noted. |

## Session search + misc tools

| Status | File | Lines | Read by | Digest / port verdict |
|---|---|---|---|---|
| [x] | tools/session_search_tool.py | 797 | w2c | Four-shape FTS5 recall, ZERO LLM: discovery dedups by lineage root, demote-before-dedupe (cron), adaptive hydration (full only top hit), caps 1200/4000/2000, limit 10 / scan 300 / exclude 20. PORT: ranking + hydration ladder for scripts/session_search.py. |
| [x] | tools/todo_tool.py | 337 | w2c | Revisioned TodoStore: atomic write w/ restore-on-reject, bump only on diff, 4000 chars/item, 256 items, post-compression active-only tree. PORT: reference shape. |
| [x] | agent/title_generator.py | 800 | w3c | Two-stage titles: instant derived (48-char cap), LLM upgrade on daemon thread; 512 max_tokens, 12-word answer-shape reject, provenance ladder. PORT: background-aux spawn shape. |
| [x] | agent/inline_tool_executors.py | 321 | w3c | Inline dispatch table `fn(agent,args,ctx)` replacing drifted if/elif chains; lazy imports. PORT: registry-free tool table. |
| [x] | agent/tool_executor.py | 1941 | w3c | Sequential/concurrent/segmented dispatch; memory counter reset on explicit save (744-747), subdir hint append at commit; 8 workers, 420s batch, 1M-char trim flag. PORT. |
| [x] | agent/coding_context.py | 569 | w3c | Frozen RuntimeMode posture, workspace snapshot probed once then replayed byte-stable; 500-entry code scan, 2.5s git probes. PART. |
| [x] | agent/subdirectory_hints.py | 320 | w3c | First-visit AGENTS.md/CLAUDE.md appended to tool result, 32k head+tail cap with path marker, digest dedup, symlink containment. PORT. |

## Turn loop (token-relevant decisions)

| Status | File | Lines | Read by | Digest / port verdict |
|---|---|---|---|---|
| [x] ip | agent/turn_context.py | 1344 | lane-mem | Review counters rehydrate; prefetch skip on trivial prompts; memory injection into `api_content` sidecar. |
| [x] ip | agent/turn_finalizer.py | 811 | lane-mem | Fires background review post-response iff final + not interrupted + interval met. |
| [x] | agent/turn_preflight.py | 396 | w3a | Pre-API compression gate: anchors on prompt_tokens only, refunds api_call_count when a pass never reaches provider, fails closed on forced overflow. PORT: refund accounting. |
| [x] | agent/turn_preflight_gate.py | 102 | w3a | Overflow re-arm (`pressure >= threshold`), insufficient-progress blocker compares assembled requests. PORT. |
| [x] | agent/turn_iteration_prep.py | 566 | w3a | Steer drained as standalone user row post-tool; iteration-budget warning at 0.9 ratio into newest tool result. PORT: in-flight lane budget warnings. |
| [x] | agent/turn_request_assembly.py | 285 | w3a | Cache plan LAST after canonicalization for byte-perfect prefixes; pressure anchored on real usage. PORT: principle. |
| [x] | agent/turn_api_request.py | 185 | w3a | Per-attempt kwargs: re-apply pad/cache for fallback, strip images for rejecting models. PART. |
| [x] | agent/turn_usage.py | 297 | w3a | Folds usage into compressor/anchor/counters; budget rearms when prompt under threshold post-compaction. PORT. |
| [x] | agent/turn_overflow.py | 511 | w3a | 413 scored in BYTES, context errors in tokens; shrink must beat 0.95x; unexplained rejection stays retryable. PORT: unit-matched progress scoring. |
| [x] | agent/turn_truncation.py | 770 | w3a | Continuation max 4 nudges, stop under 512 headroom; tool-call retry `base*2^n` cap 32768; 3-streak stall fallback. PORT: bounded-escalation ladder. |
| [x] | agent/turn_api_call.py | 288 | w3b | Streaming decision, middleware relay, redirect-vs-response race under lock; interrupt keeps partial text. OUT: CC owns inference. |
| [x] | agent/turn_api_error.py | 426 | w3b | Pre/post-classification recovery routing, non-retryable client-error exit. OUT. |
| [x] | agent/turn_recovery.py | 1938 | w3b | One-shot recovery chains per classified error, terminal result builders, interruptible backoff, Retry-After hints. PART: backoff + result-stamping. |
| [x] | agent/turn_recovery_autorecover.py | 116 | w3b | Post-exhaustion wait ladder: 5 cycles, jittered 15/30/60s, Retry-After wins capped 120s, pre-delivery only. PART. |
| [x] | agent/turn_recovery_codex.py | 76 | w3b | Stale encrypted-reasoning strip. OUT. |
| [x] | agent/turn_retry_state.py | 60 | w3b | Dataclass of one-shot recovery latches + restart signals. PART: latch-ledger for lane retries. |
| [x] | agent/turn_response_check.py | 352 | w3b | Shape validation, finish_reason derivation, content-filter routing. OUT. |
| [x] | agent/turn_response_intake.py | 197 | w3b | Normalize to assistant message, incomplete-scratchpad retries. OUT. |
| [x] | agent/turn_empty_response.py | 295 | w3b | Empty-response ladder: partial reuse, one nudge, prefill x2, deterministic-empty short-circuit. PART: ladder design. |
| [x] | agent/turn_tool_round.py | 308 | w3b | Validate, expand batches, persist-before-execute durability, post-tool compression. OUT. |
| [x] | agent/turn_tool_validation.py | 236 | w3b | Unknown tool auto-repair with 3-strike exit, malformed args, unclosed-brace detection. OUT. |
| [x] | agent/turn_stop_gates.py | 177 | w3b | Appends candidate answer as interim + synthetic nudge; candidate kept as budget-exhaustion fallback. PART: gate design. |
| [x] | agent/turn_liveness.py | 250 | w3b | Sampled-idle watchdog; abort revalidated under the activity lock as `(generation, timestamp)`; two-phase observational vs committed. PORT: watcher kill safety. |
| [x] | agent/turn_scripted_prelude.py | 59 | w3b | Scripted tool calls before first model call. OUT. |
| [x] | agent/turn_summary.py | 209 | w3b | CLI per-turn accounting line. OUT: token-audit covers it. |
| [x] | agent/turn_facade.py | 224 | w3b | Lease, relay scopes, balanced start/finish marks on every exit. OUT. |
| [x] | agent/turn_facade_lease.py | 486 | w3b | Durable SQLite turn lease: TTL refresh, authority-deadline math, holder-fenced release. PORT: cross-process lock pattern. |
| [x] | agent/turn_final_response.py | 376 | w3b | Reasoning sidecar, stall/degenerate guards, scaffolding pop, durable flush. OUT. |
| [x] | agent/turn_author.py | 103 | w3b | Turn authorship as env-carried JSON. OUT. |
| [x] | agent/turn_explainers.py | 275 | w3b | Failed file-mutation footer keyed by stat signature re-checked at turn end. PART: write-verify pattern. |
| [x] | agent/turn_failure_copy.py | 462 | w3b | Every terminal result carries `failure_reason` + `failure_retryable`. PART: verdict-stamp contract. |
| [x] | agent/turn_loop_errors.py | 171 | w3b | Interpreter-shutdown break, local-bug classification, per-turn escaped-error cap. OUT. |
| [x] | agent/voice_turn_route.py | 217 | w3b | Per-turn swap onto auxiliary voice model with snapshot capture/restore. OUT. |
| [x] | agent/kanban_turn_recovery.py | 379 | w3b | In-place worker-turn retry with claim re-proof after backoff (TOCTOU closure), fail closed. PART: retry-authority pattern. |

## Docs + config (spec layer)

| Status | File | Read by | Digest |
|---|---|---|---|
| [x] | AGENTS.md (root) | main | invariants: prompt cache sacred; narrow-waist core; footprint ladder. |
| [x] | agent/AGENTS.md | main | loop shape; compression two-layer (85% hygiene / 50% compressor); aux task list. |
| [x] | skills/AGENTS.md | main | frontmatter; 60-char desc hardline; curator invariants (archive max, pinned exempt). |
| [x] | cli-config.yaml.example | lane-tok | all compaction/context defaults. |
| [x] | skills/software-development/hermes-agent-skill-authoring/SKILL.md | lane-skl | authoring standards. |
| [x] ip | run_agent.py | lane-mem | facade; review spawn + turn lease call sites. |
| [x] ip | agent/agent_init.py | lane-mem | memory budgets + nudge interval defaults. |
| [x] | website/docs/developer-guide/context-compression-and-caching.md | 796 | w3d | Canonical spec: 85% hygiene vs 50% compressor, anchor accounting, cooldown ladders with deterministic-fallback rungs, lean tail, in_place compaction. DOC (one stale anchor claim vs code). |
| [x] | website/docs/developer-guide/creating-skills.md | 440 | w3d | Authoring spec: frontmatter gating, env vs config vs credential files, `${HERMES_SKILL_DIR}`, opt-in inline shell with trust scoping, blueprints, scan trust tiers. DOC. |
| [x] | website/docs/developer-guide/agent-loop.md | 243 | w3d | Loop overview: phases, alternation, budgets. DOC but stale in 3 places (rotation, removed pressure warnings, missing 4th api mode). |
| [x] | website/docs/developer-guide/subagent-lifecycle-api.md | 61 | w3d | Plugin subagent API: 9 stable states, cooperative cancel, immutable 32k-capped terminal results, fail-closed narrowing, no restart survival. DOC. |

## Port plan (implementation checklist)

Derived from every PORT/PART verdict above. Already in place before this pass
(verified fixed today): Stop-hook reviewer wiring (`json` shadow + detached
spawn), memory `--text` alias, phantom `(empty)` bullet, curator dry-run guard.
Already faithful ports needing no change: skill_manage guard ladder,
spill-run elision marker (matches compression_marker.py shape: computed
counts, non-imitable wording), delegate tier table, two-store budgets
(2200/1375), lane envelopes.

| Status | Change | File | Hermes source |
|---|---|---|---|
| [x] | P1. Cadence reset: a successful memory write resets the 10-turn review counter to 0 (explicit save suppresses the nudge) | scripts/memory.py | tool_executor.py:744-747 |
| [x] | P2. Overflow error lists current entries so the consolidator can pick victims | scripts/memory.py | memory_tool_store.py:345-352 |
| [x] | P3. Single-flight reviewer: flock; skip spawn when one is already running (one pending review per session, newest coalesces) | scripts/memory-review.py | review_idle_queue.py |
| [x] | P4. Failure-streak cap: 3 consecutive gateway errors stands the reviewer down (log line), next counter cycle re-arms | scripts/memory-review.py | memory_tool_store.py:150,170-185 (consolidation cap) |
| [x] | P5. Post-patch re-validation: frontmatter parses, desc still <= 60 after the patch | scripts/skill_manage.py | skill_manager_tool.py:508-556 |
| [x] | P6. OVERSIZED advisory on create/patch: body > 24000 chars prints a distill warning (routing-signal hygiene) | scripts/skill_manage.py | curator.py distill target |
| [x] | P7. Pre-run curator backup: tar.gz of skills/ (keep 2, exclude .git/.archive/.locks) before any mutation pass | scripts/curator.py | curator_backup.py |
| [x] | P8. Explore steering: `--exclude` (cap 20) omits already-seen files/lines so follow-up queries explore | scripts/session_search.py | session_search_tool.py:179-198 |
| [x] | P9. Result limit clamp: `--n` max 10 | scripts/session_search.py | session_search_tool.py |
| [x] | P10. Verification battery on a fresh glm flash subagent: every changed path end to end | dispatch | delegate contract |

P10 result: 9/11 PASS first run; step 3 was a battery flaw (identical adds
dedupe - message verified with distinct entries), step 4 was a REAL pre-existing
bug (dry-run appended to `session/skill-ideas.md` and printed a false
"wrote N"); fixed (`out["skills"] and write and not dry_run` + dry-run-qualified
print) and re-verified write-free.

Deliberately NOT ported (read + rejected): micro/native/relay compaction
(cache-hostile or provider-owned), session-DB plumbing, hub marketplace,
auxiliary provider zoo, recovery ladders for providers we do not own,
prompt-cache hysteresis (harness owns the cache). The token-fighting posture
ZTORCH ends with: deterministic elision markers with counts (spill-run),
flash-tier side-LLM for review/search/compression-shaped work, per-skill
size budgets with OVERSIZED distillation, demoted-automation search ranking,
bounded hydration, lane summary budgets + spill, and cache-stable injection
rules (user-message/tool-result only).
