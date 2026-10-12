---
title: "Port proposals: aux tasks, evals, skills_guard, write guards"
type: docs
tags: [docs, port-spec, hermes, plan]
date_created: "2026-10-12"
sources: [raw/git/hermes-agent]
---

# Port proposals: auxiliary tasks, evals, skills_guard, write guards

Second-pass mining of raw/git/hermes-agent for the areas the first port plan skipped: the `auxiliary.*` LLM catalog, `evals/`, `tools/skills_guard.py`, `tools/file_tools_write_guards.py`. Ranked, max 8. Every claim carries file:line against the clone. Do not implement from this page without re-reading the cited lines.

## Ranked proposals

### 1. write-guard hook: binary-doc refusal + internal-display-text refusal (S, PORT)

- Evidence: `tools/file_tools_write_guards.py:481-545` `_check_binary_document_write` (opaque document ext always refused; SQLite sidecar always; PDF/binary only when overwriting an existing file, fail-closed when existence unknown at :536-544); `:613-644` `_is_internal_file_status_text` + `_looks_like_read_file_line_numbered_content` (>=60% consecutive `N|content` lines) + `_is_internal_file_tool_content`; extension sets `tools/binary_extensions.py:7-30`, sidecar logic `:37-74`; applied at `tools/file_tools.py:784,873-877`.
- ZTORCH gap: PreToolUse(Write|Edit) runs only session-guard (leak) + eng-ckpt (`.zcode/config.json` events). Nothing refuses a text Write into a `.docx`/`.xlsx`/`.db-wal` or a Write whose content is Claude Code Read display text (`N<tab>content` or `N|content`), which silently corrupts vault pages and loot files.
- Design: new `skills/hooks/write-guard.py` on the Write|Edit matcher (register in `setup/install-hooks.sh` + `scripts/check-hooks.py` canonical set + `.zcode/config.json`). Pure stdlib checks, port the two frozensets verbatim from binary_extensions.py: binary/opaque/sidecar ext = deny (deterministic data-loss class, same tier as scope-guard); line-numbered-content = deny with "that is Read display text, not file bytes". Test `tests/test_write_guard.py` over both corruption classes.
- Verdict: PORT. Smallest code, prevents silent data loss in the operator-owned vault.

### 2. skills_guard pattern battery as advisory scanner (M, PORT)

- Evidence: `tools/skills_guard.py:150-530` THREAT_PATTERNS (134 entries, counted via ast), categories exfiltration/injection/destructive/persistence/network/obfuscation/execution/traversal/mining/supply_chain/privilege_escalation/credential_exposure; `:599-606` invisible-unicode table; `:848-890` structure checks (symlink escape, binary payload, oversized, exec bit, file count); `:949-952` verdict mapping critical to dangerous, high to caution; invoked for project skills at `agent/skill_utils.py:604-629`, hub installs at `tools/skills_hub_install.py:17`. The fine-grained FP control is the porting lesson: docstring-level guards at `:64-148` (modify-verb vs bare mention, prose vs shell write, negation/delegation guards on context exfil).
- ZTORCH gap: no native skills security scanner. `scripts/skill-scan.sh` wraps SkillSpector, which is not installed on this machine (dead script); ingested research and any third-party skill tree land unscanned in an agent-read vault.
- Design: new `scripts/skill-guard.py` (stdlib `re` only). Curate the subset that fits an OFFENSIVE vault: injection (`prompt_injection_ignore`, `html_comment_injection` `:266-274`, `hidden_div`, `context_exfil` `:524-527`, invisible-unicode), credential_exposure (`hardcoded_secret` `:485-488` with the SHOUTY_SNAKE env-name exemption, provider token shapes `:493-503`), agent-config persistence tiers (`_prose_modify_re`/`_shell_write_re` `:77-97` retargeted from `AGENTS.md|CLAUDE.md|.cursorrules` `:71` plus session/*), destructive root/home rm `:286-293`, supply chain (`curl_pipe_shell` `:409-412`, unpinned installs `:416-419`). DROP the classes the vault legitimately contains (reverse shells, `nc`, tunnels, hardcoded IP:port, env access) or every hunt page is "dangerous". Targets: `skills/`, lane briefs under `targets/<eng>/`, wiki pages touched by research-ingest; `--root <dir>` one-shot for third-party trees (replaces skill-scan.sh's missing dep). Wire as an offensive-doctor advisory check (Finding.advice row, never gates; operator-owned vault). Keep hermes' markdown fence-aware scanning (`:661-691`) so code blocks are scanned verbatim and prose link destinations are masked.
- Verdict: PORT. Real threat surface (ingested external text an agent trusts), but advisory-only per the 2026-10-05 operator directive.

### 3. Engagement postmortem forensics eval (M, PORT)

- Evidence: `evals/postmortem/run.py:29-83` probe table + gating (pass = `rc == 0` and marker in stdout, exit 1 on any FAIL, offline by default); `evals/postmortem/README.md:27-64` forensics = offline recompute over state.db + rotated logs into observed cost buckets, cache behavior, delegation timeouts, tool friction, rework inventory, with explicit OBSERVED vs MODELED labels (`:16-17`). Entirely outside CI (not in `.github/workflows`, justfile, or scripts/check; pytest collects only `tests/`).
- ZTORCH gap: `targets/<eng>/log.md` is recorded in a fixed ASCII grammar (docs/log-grammar.md) but nothing replays it into decision-quality figures; the close-out drift-count (learn) is manual eyeballing.
- Design: new `scripts/eng-postmortem.py`: parse `log.md` audit lines into tool ok/fail/blocked counts, dead-end repeats, re-spray of known-failed creds, lane drift events, time-per-vector, OOB callback latency; emit a close-out block that `Skill(learn)` consumes and offensive-doctor renders as an advisory. Deterministic, no LLM, no live target. Test over a fixture log in `tests/test_eng_postmortem.py`. This is the agent-behavior eval ZTORCH can actually run: it measures the harness's own decisions from data it already records.
- Verdict: PORT. Highest-value eval shape; everything else in evals/ needs a spawnable agent.

### 4. Stale-overwrite refusal via read-baseline tracking (M, PORT, phase 2 of #1)

- Evidence: `tools/file_tools_write_guards.py:555-592` `_stale_overwrite_blocker` (refuses whole-file overwrite of content the task never fully read; mtime-drift check `:571-574`; blind-patch notice `:583-586`; kill switch honored `:566-568`); support `tools/file_tools_read_tracking.py:278-299` baseline mark/query, `:227-245` mtime refresh after own write, `:47` 1000-entry cap.
- ZTORCH gap: Claude Code's Edit needs a prior Read, but Write can whole-file overwrite a page the agent last saw before an ingest or another lane changed it; a stale conversation copy then clobbers current vault content.
- Design: extend `skills/hooks/write-guard.py`: PostToolUse(Read) recorder into `session/.read-baselines.json` (resolved path to mtime_ns, 1000-cap, drop on own write); PreToolUse(Write) denies when the target exists and (mtime drifted since last Read) or (never read this session), with hermes' message shape (re-read, merge, retry; prefer Edit). New PostToolUse(Read) hook registration alongside big-read.py. Memory store (`scripts/memory.py`) is unrelated (entry consolidation, not file bytes), so no overlap.
- Verdict: PORT. Real clobber vector once lanes and the main session touch the same pages; M only because of the recorder state.

### 5. Sentinel tripwire + byte-parity composition checks (S, PORT)

- Evidence: `evals/compaction/test_region_scoping.py:62-90` (plant HEAD/MID/TAIL sentinels, capture the summarizer prompt, assert head/tail never leak into the summarized region and the tail survives); `evals/prompt_footprint/property_guidance.py:27-56` (system prompt built before/after a pinned diff, byte-parity asserted outside the change, token footprint both sides).
- ZTORCH gap: ZTORCH composes agent-fed text with truncation caps (hot.md snapshot, lane briefs, the pre-compact must-survive block) and nothing asserts a protected region survives composition or that an AGENTS.md edit changes only its own block.
- Design: one test file `tests/test_context_assembly.py`: fixture engagement with sentinels at region boundaries, run engagement-init's compact-reinject branch and pre-compact.sh, assert the board/lane marked block survives and sentinels do not leak into the steer text; a byte-parity assert for a pinned AGENTS.md edit. No LLM, no runtime.
- Verdict: PORT. Cheap insurance on the composition paths ZTORCH already ships.

### 6. Auxiliary LLM task catalog: SKIP (needs a provider runtime ZTORCH does not have)

- Evidence: catalog `hermes_cli/config_defaults.py:738-816` (19 live tasks; `web_extract`/`session_search` retired at `:760`, #27590), block shape `_aux()` `:21-29`; per-task resolution + plugin layering `agent/auxiliary_task_config.py:16-79`; fallback ladder `agent/auxiliary_client.py:4396-4444` (configured chain, transient retries first per `config_defaults.py:742`); compression escalates to a deterministic fallback summary `agent/conversation_compression.py:917-952,1049`.
- Per-task honesty: `title_generation` (two-stage instant-derived then cheap-tier upgrade, provenance `derived < llm < user`, 12-word answer-shape guard; `agent/title_generator.py:1-6,56-58`) — engagement naming is operator-owned, no surface. Session summarization — retired in hermes itself. `compression` — Claude Code owns compaction; pre-compact.sh already steers it (wave 3). `curator` — deterministic lifecycle already ported (waves 1/3c); hermes' LLM consolidation fork is opt-in (`agent/curator.py:28-29` DEFAULT_CONSOLIDATE=False) and ZTORCH's learn covers it. `background_review` (`agent/background_review.py:1-7`, post-turn forked AIAgent) — would mean shelling out to a second agent every turn: cost plus nag, and the main session already owns improve-at-close-out. `approval`/`monitor`/`goal_judge`/`moa_*`/kanban tasks — no ZTORCH analog surface. The one portable idea (deterministic-first, LLM-upgrade-optional) is already ZTORCH's fail-open hook doctrine.
- Verdict: SKIP, all tasks. Revisit only if ZTORCH ever gains a sanctioned side-LLM lane.

### 7. INSTALL_POLICY trust tiers as a gate: SKIP (fold vocabulary into #2)

- Evidence: `tools/skills_guard.py:26-33` (builtin/trusted/community/agent-created x safe/caution/dangerous), `should_allow_install` `:818-831` (force cannot override dangerous on community).
- ZTORCH gap: none. The vault is operator-owned and there is no install flow to gate; per the operator directive a scanner here advises, it must not block. Keep the three-word verdict vocabulary (dangerous/caution/safe, `:949-952`) as the report format inside #2 and drop the trust-tier table.
- Verdict: SKIP as a standalone; verdict vocabulary ports with #2.

### 8. Live A/B and LLM-judge eval harnesses: SKIP (spawnable-agent + provider dependency)

- Evidence: `evals/toolperf_abeval/ab_eval.py:192-204` (arms differ only by PYTHONPATH, subprocesses a live agent CLI, scores NeMo Relay traces `:224-257`); `evals/readtool/runner.py:44-71,113` (real AIAgent, per-fixture graders, hermetic env); `evals/compaction/runner.py:215-226,383,401` (LLM question generation + 2/1/0 judge, FTS5 recovery arm `:91-153`). Noise discipline (n=3 minimum, same-denominator rule, infra errors never scored) is worth copying into #3's report header if it ever gains comparisons.
- ZTORCH gap is structural, not missing code: ZTORCH's agent is the operator's Claude session; a `claude -p` harness would measure Claude Code, not ZTORCH, at real cost per arm. The offline shapes that survive that filter are already entries 3 and 5.
- Verdict: SKIP. Gateway/wire/provider/desktop probes in evals/ are hermes-runtime plumbing, out of scope entirely.

## Summary table

| # | Port | Effort | Verdict |
|---|---|---|---|
| 1 | write-guard hook (binary-doc + display-text) | S | PORT |
| 2 | skills_guard curated battery, advisory | M | PORT |
| 3 | eng postmortem forensics from log grammar | M | PORT |
| 4 | stale-overwrite read-baseline refusal | M | PORT |
| 5 | sentinel tripwire + byte-parity tests | S | PORT |
| 6 | auxiliary LLM task catalog | - | SKIP |
| 7 | INSTALL_POLICY trust tiers | - | SKIP |
| 8 | live A/B + LLM-judge evals | - | SKIP |
