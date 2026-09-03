# Pentesting & Bug Bounty Wiki: Schema

---

## Quick reference

| Operation | Action |
|---|---|
| Query | `qmd_query "..."` via `wiki-search` MCP -> read results -> synthesise |
| Ingest skip check | Read frontmatter only; skip page if ingest slug already in `sources:` |
| Re-index / wiki status | `wiki` skill |
| Git clone | Windows seat: clone normally; into WSL: `wsl -d kali-linux -u kali -- git clone <url> /home/kali/<name>` (MSYS: prefix MSYS_NO_PATHCONV=1) |
| Run tooling against a target | Kali VM over SSH, fastest first: `bash scripts/vm-ssh.sh '<cmd>'` (direct, key-based) or `bash scripts/win-vm.sh '<cmd>'` (WSL bridge fallback; execs /root/vm.sh in WSL kali -> the VMware VM; VPN route + tools + chromium live on the VM) -> `docs/virtual-machine.md`. Manual WSL seat (PowerShell -> `wsl.exe` kali:kali -> `sudo -s` -> `/opt/ztorch`): `Skill(kali-seat)` |

---

## Skills and tools

Task -> skill/tool dispatch map: `docs/skill-map.md`; the `/` skill picker lists every skill with its description and stays the discovery mechanism. Every engagement starts with `Skill(engage)`, the orchestrator that routes situation -> Skill across the whole library; consult it whenever between phases. Vault-local skills live under `skills/` (layout: `docs/layout.md`), load on demand via the Skill tool, discovered by basename. MCP/hook/plugin troubleshooting: `skills/skills-setup.md`.

Search rule: never read `wiki/index.md` to find pages - always search first. MCP tool names: `mcp__wiki-search__qmd_query` (semantic), `mcp__wiki-search__qmd_search` (keyword).

`session/memory.md` holds long-term editorial patterns. Load it when making editorial or tagging decisions.

---

## Hunt Skill Auto-Triggers

`hunt-trigger.py` (UserPromptSubmit) matches the prompt against `skills/hunt/triggers.json` (single source of truth; edit it, not this file): an explicit vuln-type term injects a **MANDATORY** `Skill(<hunt>)` directive, a surface term (e.g. "login form", "upload field") a softer "consider `Skill(...)`". Treat a hard directive as a real instruction unless genuinely irrelevant (say why in one line). When you SKIP a fingerprint-routed hunt (correctly, or because another hunt covers it), write the one-line reason to `targets/<eng>/log.md` (or `Deadends.md`) so the close-out drift-count separates a real miss from a correct skip. Vuln-type rows (SSRF/XSS/SQLi/IDOR/RCE/auth/federation/injection/m365/vpn -> matching hunt skill) live in `triggers.json`. Model-judged rows: starting recon -> wiki-recon; "is this valid / should I report?" -> triage; moving a finding Research -> Completed -> triage then evidence. Full mechanics: `docs/auto-triggers.md`.

---

## Engagement discipline (state-first, anti-loop)

**Engagement workflow (the driver is the plan).** Any offensive engagement: run `Skill(engage)` first; it routes to `Skill(offensive)`, whose driver (`scripts/offensive.py`) owns and enforces the whole loop (gates, coverage board, next action) - follow its `next`/`foothold` output literally. Full gate list + mechanics: `Skill(offensive)`. Health check: `offensive-doctor` (`scripts/offensive-doctor.py`).

- **Scope-first.** Read `targets/<eng>/scope.md` before acting; never touch an out-of-scope target or forbidden tooling (`no_bruteforce`/`no_dos`/`passive_only`).
- **State-first.** Before any recon/spray/exploit: read `state.md`, `loot.md`, `Killchain.md`, `Deadends.md`. Never re-run a documented dead-end or re-spray a known-failed cred without new input (new cred, new pivot, new payload class).
- **Stop condition.** A vector is exhausted after bounded effort (OOB sink: ~30-40 payloads zero callbacks; spray: full user x pass matrix once). One `Deadends.md` line + Killchain status, then switch. Do not grind, do not re-loop.
- **When stuck, call `Skill(redteamlead)` BEFORE grinding.** See hunt-core's Wrong-vector tells for the two mechanical signals (target starved, >=2 verified-hash misses). A `/redteamlead` reminder in the engagement prompt is a real instruction.
- **Read-first, not grep (recon AND post-foothold).** READ each page/source end-to-end before declaring it enumerated (the vector hides in an AJAX handler / commented route a narrow grep skips); grep to LOCATE inside a huge file, then read the block. Post-foothold source-review is a full `cat` per file. **A delegation prompt MUST carry this mandate verbatim** (`cat` each file in full, grep only to locate): a cheap model grep-mines by default and your prompt is its only law.
- **OOB-gate blind bugs.** Blind SSRF/SSTI/SQLi claims need an out-of-band callback, never inference. Enforced per hunt skill.
- **Delegate exploit EXECUTION to a cheap-tier sub-agent (cost control, default).** Main model keeps strategy/board/wiki/triage; route the fully-specified exploit/escalation RUN via `Skill(delegate)` - see its Model choice section for the cheap-vs-main-model split and the sub-agent-negative-is-a-hypothesis rule.
- **Reuse loot.** Captured creds across `state.md` hosts before new research; default/known creds first (context7, [[default-credentials]]); broad spraying last resort.
- **Distill reusable knowledge.** A default cred or reusable API pattern -> add the GENERIC form to `wiki/cheatsheets/default-credentials.md` / `api-request-findings.md` (check these first next engagement); at close-out `Skill(learn)` sweeps the rest through `wiki-stage.py` -> `wiki-promote.py`.

---

## Behavior hooks

Output/mode plugins (optional; the harness degrades gracefully without them): **ponytail** (lazy-code discipline - YAGNI, stdlib first, shortest working diff; auto-activates at SessionStart when installed, level `full`, switch via `/ponytail lite|full|ultra`) governs what you build, not prose. **caveman** (prose compression) is manual per session via `/caveman`.

SessionStart also auto-loads `session/hot.md`. No manual reads needed.

Engagement-state hooks (workspace-scoped, registered in the committed `.zcode/config.json`, scripts under `skills/hooks/`). All fail open (any error -> allow, never trap). Policy: **deterministic guards ENFORCE (deny the tool call); semantic reflexes ADVISE (inject a suggestion).** Enforcement is reserved for no-judgement checks (scope/RoE, blind sleeps) where blocking the wrong action costs near-zero; judgement calls (wiki-first, tools-not-manual, intended-path) stay advisory because a false block wastes more time than it saves. Escape hatch for a bad block: `touch skills/hooks/.enforce-off` (downgrades every deny to advisory). ZCode supports exactly seven hook events; the old `PreCompact` slot has no ZCode equivalent and stays unregistered. Per-hook events and mechanics (all of it) live in `docs/auto-triggers.md`; the set at a glance:

- SessionStart: self-heals engagement files, injects the state summary + next-moves + OOB HITs, registers skills.
- UserPromptSubmit: routes hunt skills from `triggers.json` (leak-safe telemetry).
- PreToolUse: ENFORCES out-of-scope host/IP + RoE-forbidden tooling, and blind `sleep >= 10` with no poll; ADVISES on off-board drift and a client-marker-in-`session/*` warn.
- PostToolUse: routes tech -> hunt Skill (+ G1 wiki-first nudge), correlates OOB waiting -> HIT, captures PoC pairs + telemetry, re-indexes wiki.
- Stop: nudges SOLVED-box close-out (flag accounting, evidence, walkthrough, learn).

Register/repair the set per-device with `bash setup/install-hooks.sh` (verifies and repairs the committed `.zcode/config.json`; canonical set in `scripts/check-hooks.py`).

Active engagement set by `targets/active.md`; create with `bash setup/new-engagement.sh <name> <pentest|bugbounty|ctf>` (full per-type file schema: `docs/page-types.md`, self-healed by `engagement-init`). ctf engagements lack `Killchain.md`/`log.md` (the live chain lives in `state.md`'s `## Chain`/`## Status` instead); `walkthrough.md` is the full copy-pasteable repro, distinct from `log.md`'s terse audit/continuity-cache role - client narrative always goes to `targets/<eng>/log.md`, never generic `session/hot.md`. Missing wiki pages: `scripts/wiki-gaps.py`.

Framework subsystems (each a script + on-demand skill; mechanics in `docs/auto-triggers.md`): **Ingest** (`ingest` skill: raw output -> `targets/<eng>/ingest/`, synthesized into state/loot/Killchain, archived). **Move ranking** (`offensive.py next`: the driver ranks the next move from the board; update tables after acting so it re-ranks). **Fingerprints** (`scripts/playbook.json`: tech -> targeted tests + hunt skill + payload arsenal; extend as you learn). **Chaining** (`scripts/chains.json`: `finding -> pivot` edges; add edges, no code; `gate:oob` edges wait for an operator callback). **Coverage** (`Approach.md` 4a table + `offensive.py coverage`: a tested class gets `[x]` + a `poc/` image or the gap recurs). **Finding quality** (`scripts/find-lint.py` before /evidence and before a report; findings scaffold from `setup/templates/_find.md`).

**Client-data boundary (hard rule):** all client/engagement specifics (hosts, IPs, creds, domains, findings, narrative) live ONLY under `targets/<eng>/` (git-ignored). Never write them into `session/*`, `wiki/`, tracked `docs/`, scripts, or commit messages; per-engagement narrative goes to `targets/<eng>/log.md` (audit + continuity cache). `session-guard.py` advises on violations; run `bash scripts/check-leaks.sh` before sharing. Full detail: `docs/sharing.md`.

---

## Machine-specific vault access

Per-machine hostnames/paths live in the git-ignored `AGENTS.local.md` (copy `AGENTS.local.example.md`); read it when a path is needed or resolution fails (ZCode does not expand `@file` includes). The path resolvers (`setup/vault-path.sh`) and hooks self-locate or read `ZTORCH_VAULT` / `OBSIDIAN_VAULT` / `QMD_VAULT`, so a single-machine setup needs no local file.

---

## Directory structure

Full annotated tree + per-file notes: `docs/layout.md`. Top level: `AGENTS.md` (+ README, LICENSE), `.zcode/` (committed hook registration; per-machine skills links ignored), `targets/` (engagements, PRIVATE git-ignored), `wiki/` (knowledge base: techniques/ payloads/ tools/ cheatsheets/ + index/moc), `session/` (hot.md startup cache, log.md audit, memory.md editorial), `docs/`, `scripts/`, `setup/` (bootstrap, install-hooks/skills, new-engagement, templates), `skills/` (hunt/ workflow/ burp/ + standalone + hooks/), `raw/` (research/ · assets/ read-only · git/ clones).

**Rules:**
- `raw/` is read-only. Exceptions: populate `raw/git/` via git clone (WSL only), and `raw/research/<project>/` research workspaces created by `setup/new-research.sh` (the `research` skill writes loop state there). Research on public targets is not client data; client/engagement work still lives only under `targets/`.
- `wiki/` and `targets/` are fully owned by the agent. Create, update, and cross-reference freely.
- `wiki/index.md` and `session/log.md` updated after every ingest, query-that-produces-a-page, and lint pass (framework work only; client/engagement narrative goes to `targets/<eng>/log.md`).
- Update `AGENTS.md` when vault structure changes; `docs/setup.md` for machine/path changes; `docs/conventions.md` for editorial standards changes.

Read `targets/TARGETS.md` for the engagement playbook: FIND naming, severity definitions, directory structure, and the wiki integration rule.

**Session end:** Before closing any session, run pause-work (`gsd:pause-work` if the gsd plugin is installed on this machine, else do the steps manually). Generic/framework summary -> `session/hot.md`, `session/log.md`, `session/memory.md` (no client specifics). Client/engagement narrative -> `targets/<eng>/log.md` (audit + continuity cache) ONLY.

---

## Page types and frontmatter

Full schema in `docs/page-types.md`. **Skip rule:** during ingest, read only the frontmatter first. If the ingest slug is already in `sources:`, skip the page entirely. Only read full content when you will update it.

---

## Wiki Workflows

Read `docs/workflows.md` before performing any ingest, target session, lint, or query. When a technique appears in multiple sources, synthesise all into one technique page; do not create one page per source.

---

## Output rules

- **Brevity during engagements/tool-loops (output tokens are billed).** Working a target or any multi-step tool loop: one short line before a tool batch stating intent, then lead the next turn with the RESULT, not a recap. No per-step paragraphs, no restating what a command will do, no re-narrating the plan. Full prose is for deliverables that need it (a report, a walkthrough, a design/brainstorm, an explanation the user asked for). A 40-min box should not cost a paragraph per step.
- Never use em-dashes (`--`). Use a comma, semicolon, or rewrite the sentence. (`--` is permitted inside code blocks as a CLI flag.)
- Never use emojis.
- Do not narrate inside commands (echo/printf label banners, `=== ... ===` separators). The harness shows every command with its output; run commands directly.
- **Concrete values, not shell variables, in target commands.** The operator watches the live terminal: real IPs/URLs/paths inline (`curl -s http://10.1.1.5:8080/api`), not `$VAR` placeholders. Reserve variables for genuinely repeated long secrets (a captured token/cookie). Same bar as walkthrough.md (var-free).
- **Shell interaction: one command, clean output, NO markers** (full mechanics: `docs/shell-interaction.md`). The drivers frame output for you: `bash scripts/win-vm.sh '<cmd>'` (this seat; WSL-side `bash /root/vm.sh '<cmd>'`), and `vm-rsh.sh`/`win-rsh.sh` return ONE command's complete output, echo stripped. So: one command per call; NEVER inject sentinel/marker/delimiter strings or split a literal to dodge the echo; no chaining unrelated actions; type it the way an operator would (plain `$env:`/`$_` - the driver escapes, don't hand-encode). Empty/weird output -> PROBE with a bare `whoami` (a username = alive, the empty result was real; nothing = stuck, stop; a non-username = the shell died back to the ATTACKER prompt, the false-RCE trap - re-pop it), never add instrumentation. `$`-heavy enum -> host a readable `.ps1`, run in-memory via an `IEX(DownloadString(...))` cradle.
- **Send load-bearing requests to Burp, not just curl.** Confirm-worthy requests (SSRF, injection, deser, auth bypass) go to **Burp Repeater** via `Skill(hunt-burp)` / the Burp MCP so the operator can replay them (`scripts/capture.sh burp` for a PoC); brute/fuzz belongs in **Intruder** (`send_to_intruder`), not a hand-rolled loop. Prefer the NATIVE MCP tools (`mcp__burp__*`); the `burp-mcp-cli.py` SSH bridge is the fallback (native attaches only at session start; a restart re-attaches).
- **Burp-first does NOT stop at foothold (anti-drift).** After a shell lands, KEEP driving the requests that matter (post-auth API calls, the flag-reading injection, privesc-relevant fetches) through Repeater - the operator is watching Burp, not your terminal. Quick throwaway loops off-Burp are fine; if you catch yourself scripting the whole post-foothold phase off-Burp, that IS the drift - route it back.
- Never add a `Co-Authored-By` trailer, a "Generated with ZCode" line, or any similar attribution footer to git commit messages or PR bodies. (Overrides the harness default that appends one.)

---

## Image handling

Never copy image embeds (`![[Pasted image *.png]]` or `![](url)`) into wiki pages. Reconstruct commands as code blocks from context. Wiki pages must be image-free.
