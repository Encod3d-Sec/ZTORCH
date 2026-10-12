# Port proposals: hermes-agent operating rules + security posture

Source: `raw/git/hermes-agent` deep-read (root AGENTS.md, SECURITY.md, CONTRIBUTING.md, skills/tools/hermes_cli/agent/gateway AGENTS.md, guard + updater modules). Ranked by incident-class prevention for ZTORCH: credential bleed into lanes > injection via ingested target content > self-inflicted config corruption > process cosmetics.

## 1. Lane env is allowlist-only with a credential blocklist — PORT (S)

- Hermes evidence: `tools/environments/local_env_policy.py:15` (`_STATIC_PROVIDER_ENV_BLOCKLIST`: every provider/gateway/dashboard key, force-prefix escape hatch); `tools/env_passthrough.py:46-70` (GHSA-rhgp-j443-p4rf: a skill registering `OPENAI_API_KEY` as a "needed env var" re-admitted it into the `execute_code` child; fix = blocklist names can NEVER be re-allowed by declaration, fail-closed when the blocklist import fails, case-folded for Windows getenv); `agent/secret_scope.py:1-11` (profile A's keys never unioned where profile B runs); SECURITY.md §2.3 (scrubbing "reduces casual exfiltration", declared vars pass through).
- ZTORCH gap: `scripts/lane-run.sh:44,53` injects manifest `envs=` into lanes and inherits the rest of the parent env wholesale. Lanes read attacker-influenced target content; a socially-engineered lane command can `env`-dump `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, Burp/MCP tokens to an OOB endpoint. No blocklist exists anywhere in `scripts/`.
- Design: new `scripts/lane-env.py` (pure data: blocklist regexes `*_API_KEY`, `*_TOKEN`, `GATEWAY_*`, `Hermes-free` force prefix) + builder `lane_env(manifest)` returning allowlisted env; `lane-run.sh` sources it instead of passing parent env; `skills/hooks/lane-guard.py` denies any lane spawn whose manifest names a blocklisted var. AGENTS.md row: "Lane env = manifest allowlist minus credential blocklist; harness creds never cross into a lane."

## 2. Protected-instruction-file write gate — PORT (S)

- Hermes evidence: `tools/file_tools_write_guards.py:185-258`: `_PROTECTED_INSTRUCTION_BASENAMES = {agents.md, claude.md, soul.md, .cursorrules}` (+ `<repo>/.hermes/config.yaml`); writes ALWAYS escalate to ask, never silent; config-read failure keeps the gate ON (fail-safe); matches BOTH normalized path and realpath so a symlink in either direction cannot escape (#41351); rationale: "an AGENTS.md anywhere the agent might later run from is a live target".
- ZTORCH gap: nothing stops a lane or main session from editing `AGENTS.md`, `docs/auto-triggers.md`, `.zcode/config.json`, `skills/hunt/triggers.json`, or `~/.claude/CLAUDE.md` mid-engagement. ZTORCH's rules live in exactly these files; injected target content (fetched page, `research-ingest` blob, tool output) that talks the agent into "fixing" a hook is a silent guardrail rewrite. Obsidian page-breaker rule shows these files are also operator GUI.
- Design: extend `skills/hooks/lane-guard.py` + PreToolUse branch in `scripts/session-guard.py` (new `scripts/policy-guard.py` if cleaner): write/edit/move targeting that basename set under `$ZTORCH` or `~/.claude/` = deny with reason, bypass only via operator marker `.policy-edit-ok` in vault root (same pattern as `.roe-ok`). Fail-safe on unreadable path resolution.

## 3. Scope-guard fails CLOSED on unreadable/corrupt scope.md — PORT (S)

- Hermes evidence: `tools/file_tools_write_guards.py:193-204` (config parse failure → gate stays on); `agent/secret_scope.py` (scoped miss RAISES, never falls back to `os.environ`); gateway/AGENTS.md:139-154 ("Multiplex profile-scoped env reads MUST fail closed — never borrow from os.environ", #72348/#86905: a fallback-after-miss silently skipped allowlists). Root AGENTS.md keeps fail-open ONLY for advisory hooks; the boundary check is exempt.
- ZTORCH gap: ZTORCH doctrine says all hooks "fail open (any error -> allow)". For advisory guards that is right; but scope-guard parsing a truncated/corrupt `targets/<eng>/scope.md` (crash mid-write is plausible, see #4) yields "no scope known" → likely allow-all on the ONE hook whose deny is load-bearing. Silent scope loss during an autonomous deep engagement is the worst-case incident class.
- Design: `skills/hooks/scope-guard.py`: distinguish "parsed, host out of scope" (deny) from "unreadable/unparseable" (deny with `scope file unreadable — repair before acting`, still deny); keep every other hook fail-open. One `__main__` assert pair for both branches.

## 4. Atomic single-writer seam for engagement/harness config — PORT (S)

- Hermes evidence: `hermes_cli/AGENTS.md:90-98`: every config.yaml write goes through `atomic_config_write` (refuses deletion-by-omit) / `atomic_config_replace`; "Never call yaml.dump on a config path — `scripts/check_config_yaml_writers.py` (CI lint) rejects it" (#92554); fail-closed unreadable-file guard runs FIRST. Root invariant class: "never mutate X with raw Y" (AGENTS.md:134-136, pip/uv on PM envs).
- ZTORCH gap: `scope.md`, `state.md`, `targets/active.md`, `.zcode/config.json` are read-modify-written concurrently by driver, hooks, and 2-3 lanes with bare `open(..., 'w')`. A crashed interleaved write corrupts scope (feeding #3) or knocks hooks offline; no lint forbids direct writes to these paths.
- Design: `scripts/_atomic.py` (tmp in same dir + `os.replace` + fsync; refuse empty-overwrite of non-empty target); adopt in `scope-guard.py` writes, `engagement-init.py`, `offensive.py` (rebase/autonomy), `check-hooks.py` repair path; a check in `scripts/check-hooks.py` greps for bare writes to the guarded paths. AGENTS.md one line under Behavior hooks.

## 5. Write-time secret redaction (regex battery + exact-value registry) — PORT (S)

- Hermes evidence: `agent/redact.py:1-45`: regex redaction for logs/tool output (short tokens fully masked, long keep 6+4); vault-value registry — exact secret bytes registered BEFORE use, every later tool result scrubbed, keyed per home so B's output is never checked against A's passwords; `hermes_logging.py:365,684` per-profile redaction at the logging boundary, not share-time.
- ZTORCH gap: `targets/<eng>/log.md`, `session/hot.md`, cmdlog summaries record raw command lines; a captured session cookie in a `curl -H "Cookie: ..."` lands verbatim in the vault. `scripts/check-leaks.sh` has no KEY/TOKEN/SECRET patterns (client markers only) and runs only before sharing. Redaction at share time misses everything already written.
- Design: `scripts/_redact.py` (port of the regex set + `register(value)` exact-value registry fed from `loot.md` cred lines at SessionStart); call from `skills/hooks/session-guard.py` PostToolUse on any write under `session/` or `targets/*/log.md`|`loot.md`; `check-leaks.sh` reuses the same battery as sweep. Output rule row in AGENTS.md: tokens appear as `REDACTED-xxxx`.

## 6. Trust-model doc: name the boundary, demote the heuristics — PORT (S)

- Hermes evidence: SECURITY.md §2.2 "The only security boundary against an adversarial LLM is the operating system... any in-process component that screens LLM output is a heuristic operating on an attacker-influenced string"; §2.4 (approval gate / redaction / skills guard = accident prevention); §3.1-vs-§3.2 split (what is a vuln vs ordinary hardening). This document is the scope authority referenced from AGENTS.md:52-54.
- ZTORCH gap: ZTORCH AGENTS.md describes hook gates but never states which are boundaries vs heuristics; the VM seat split IS the real OS boundary (attacker-influenced execution confined to kali VM) yet no rule says so. Model and operator over-trust lane-guard/drift-guard; scope discussions (e.g. hook bypass debates) have no authority to cite.
- Design: `docs/trust-model.md` (~40 lines): VM/seat = the boundary; all ZTORCH hooks = heuristics/advisors except scope-guard deny; anything parsing attacker-influenced strings (tells, lane output) is named as such; the `.enforce-off`/`.roe-ok` markers framed as break-glass operator decisions. Linked from AGENTS.md engagement-discipline. No code.

## 7. Self-repo guard: refuse git mutations of the live vault checkout — PORT (M)

- Hermes evidence: `tools/self_repo_guard.py:12-16` (`_WORKTREE_MUTATIONS = {checkout, switch, rebase, merge, pull, restore, clean, cherry-pick, revert, bisect}` + `reset --hard/--merge/--keep`, stash unsafe forms, worktree move/remove); unwraps sudo/env/setsid/nice wrappers; purpose: "bisect drives repeated checkouts of the running root — the exact skew hazard guarded here".
- ZTORCH gap: the running agent or a lane executing `git reset --hard`/`clean -fd`/`checkout` inside `~/tools/ZTORCH` mid-session destroys live hook scripts, uncommitted skill edits, and `targets/` adjacency state while hooks still reference them (fail-open everywhere = silent degradation). Nothing guards the repo the harness itself runs from; ZTORCH's default state is a dirty tree.
- Design: `scripts/self-repo-guard.py` (v1: mutation-verb scan over the command with the existing `_cmdnorm.py`/shell-word helpers; deny when cwd resolves inside the vault and no `.repo-edit-ok` marker); wired into `skills/hooks/lane-guard.py` + PreToolUse for the main session; log-grammar line on deny.
- SKIP candidate note: full wrapper/alias resolution from hermes is unnecessary at v1; a lane calling `sudo git reset` is already outside lane contract.

## 8. Harness-edit receipts: snapshot before mutating the harness itself — PORT (M)

- Hermes evidence: `hermes_cli/AGENTS.md:129-145` update pipeline "plan -> snapshot -> apply -> restart-per-kind -> verify -> report; every stage guards a real field failure (#91277)"; snapshots are file-loss recovery; post-commit failures are owed follow-ups with receipts in `logs/update_receipts/`; `update_abort_recovery.py:1-9` + `update_restart_recovery.py:14-38` (fresh-process recovery with conservative outcome vocabulary `verified/relaunch_attempted/failed`; process identity = `(pid, create_time)` incarnation, never PID alone).
- ZTORCH gap: harness self-modification (hook edits, skill changes, trigger.json rows) is live uncommitted edits with no snapshot or receipt; `offensive-doctor`/`check-hooks.py` verify wiring only on demand, not after edits. A half-applied hook edit leaves `.zcode/config.json` pointing at broken code and every guard silently fail-opens. Engagements have `checkpoint.py`; the harness has nothing.
- Design: `scripts/checkpoint.py` gains `--harness` mode (pre-edit `git stash create` + receipt line `ckpt harness <sha>` into `session/log.md`); `scripts/check-hooks.py` parse-verifies every registered hook script after any receipt; AGENTS.md rule: no edit under `skills/hooks/` or `.zcode/` without a preceding harness receipt.
- Skip: hermes's fleet/restart machinery (multiplex units, ZIP fallback, serve recovery) — single-seat vault does not need it.

## Considered, SKIP

- Skills Guard regex scanner (`tools/skills_guard.py`, trust-tier install policy): ZTORCH skills are self-authored; external knowledge enters via `research-ingest` with `sources:` dedup. Revisit only if ZTORCH ever installs third-party skills.
- Multiplex profile secret-scope machinery (contextvar scopes, per-profile slots): single-operator vault; item 1's blocklist covers the bleed class without the multi-profile complexity.
- Contribution rubric, code-health ratchets, facade+siblings layout, prompt-caching invariants, Windows cross-platform rules, dependency `<next_major` pinning: multi-contributor / API-loop / Windows concerns ZTORCH does not have.
- Forged-history state hydration (`run_agent.py:1023`, GHSA-5g4g-6jrg-mw3g: replay only provenance-verified tool responses): no analog consumer in ZTORCH today; note for any future state-replay feature.
