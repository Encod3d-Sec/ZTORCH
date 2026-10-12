# Pentesting & Bug Bounty Wiki: Schema

---

## Quick reference

| Operation | Action |
|---|---|
| Query | `qmd_query "..."` via `wiki-search` MCP -> read results -> synthesise |
| Ingest skip check | Read frontmatter only; skip page if ingest slug already in `sources:` |
| Re-index / wiki status | `wiki` skill |
| Session memory / search history | `python3 scripts/memory.py view` (two stores, budgets); `python3 scripts/session_search.py query '<text>'` over engagement+session logs |
| Record a reusable procedure mid-engagement | `python3 scripts/skill_manage.py create/patch` (guarded; umbrella-first); lifecycle via `scripts/curator.py` |
| Git clone | Windows seat: clone normally; into WSL: `wsl -d kali-linux -u kali -- git clone <url> /home/kali/<name>` (MSYS: prefix MSYS_NO_PATHCONV=1) |
| Run tooling against a target | Kali VM over SSH, fastest first: `bash scripts/vm-ssh.sh '<cmd>'` (direct, key-based) or `bash scripts/win-vm.sh '<cmd>'` (WSL bridge fallback; execs /root/vm.sh in WSL kali -> the VMware VM; VPN route + tools + chromium live on the VM) -> `docs/virtual-machine.md`. Manual WSL seat (PowerShell -> `wsl.exe` kali:kali -> `sudo -s` -> `/opt/ztorch`): `Skill(kali-seat)` |

---

## Skills and tools

Task -> skill/tool dispatch map: `docs/skill-map.md`; the `/` skill picker lists every skill with its description and stays the discovery mechanism. Every engagement starts with `Skill(engage)`, the orchestrator that routes situation -> Skill across the whole library; consult it whenever between phases. Vault-local skills live under `skills/` (layout: `docs/layout.md`), load on demand via the Skill tool, discovered by basename. MCP/hook/plugin troubleshooting: `skills/skills-setup.md`.

Search rule: never read `wiki/index.md` to find pages - always search first. Wiki MCP tools: `mcp__wiki-search__qmd_query` (semantic), `mcp__wiki-search__qmd_search` (keyword). Workspace/text search over the vault, `targets/`, and `raw/git` clones: `zg` (zvec-grep) first - MCP tool `zvec_grep_search` on the `zvec-grep` server, or CLI `zg query --human "<q>" --limit N` (run `zg server on` if the MCP tool errors; deterministic fallback `bash scripts/wiki-query.sh`). Locate ACROSS files with zg; grep is fine inside a single file. qmd/wiki queries stay English even when the target's content is not (the wiki is indexed in English; a non-English query retrieves nothing). Translate entities into English search terms and keep original-language values in the finding, not the query. Wiki question routing by shape (measured): content ("which page is about X") -> qmd (BM25 ~0.5s, semantic via MCP); relations ("how do X and Y connect", hub or orphan detection) -> the `graphify` skill (`scripts/wiki-graph.py`, structural wikilink graph, ~1.5s, no LLM); multi-hop exploration -> graphify first for the chain, then qmd to read the pages it names.

`session/memory.md` holds long-term editorial patterns. Load it when making editorial or tagging decisions.

---

## Hunt Skill Auto-Triggers

`hunt-trigger.py` (UserPromptSubmit) matches the prompt against `skills/hunt/triggers.json` (single source of truth; edit it, not this file): an explicit vuln-type term injects a **MANDATORY** `Skill(<hunt>)` directive, a surface term (e.g. "login form", "upload field") a softer "consider `Skill(...)`", and a wiki-relation phrasing (how pages connect, hub or orphan pages) a `Skill(graphify)` advisory (the structural wikilink layer; page-noun-gated so engagement prose never fires it). Treat a hard directive as a real instruction unless genuinely irrelevant (say why in one line). When you SKIP a fingerprint-routed hunt (correctly, or because another hunt covers it), write the one-line reason to `targets/<eng>/log.md` (or `Deadends.md`) so the close-out drift-count separates a real miss from a correct skip. Vuln-type rows (SSRF/XSS/SQLi/IDOR/RCE/auth/federation/injection/m365/vpn -> matching hunt skill) live in `triggers.json`. Model-judged rows: starting recon -> wiki-recon; "is this valid / should I report?" -> triage; moving a finding Research -> Completed -> triage then evidence. Full mechanics: `docs/auto-triggers.md`.

---

## Engagement discipline (state-first, anti-loop)

**Engagement workflow (the driver is the plan).** Any offensive engagement: run `Skill(engage)` first; it routes to `Skill(offensive)`, whose driver (`scripts/offensive.py`) owns and enforces the whole loop (gates, coverage board, next action) - follow its `next`/`foothold` output literally. Full gate list + mechanics: `Skill(offensive)`. Health check: `offensive-doctor` (`scripts/offensive-doctor.py`).

- **Scope-first.** Read `targets/<eng>/scope.md` before acting. Out-of-scope hosts/IPs are the ONE hook-enforced deny (scope-guard). RoE-forbidden tooling (`no_bruteforce`/`no_dos`/`passive_only`) is an OPERATOR-decision gate (operator directive 2026-10-05): the hook asks; once the operator approves, run it via a `ZT_ROE_OK=1` command prefix, a `.roe-ok` marker in the engagement dir, or by flipping the flag in scope.md.
- **Deep is the DEFAULT.** Every new engagement opens at full depth (scope.md `mode: deep`, `autonomy: L3`; operator directive 2026-10-05) and runs LONG autonomous phases - a bb/pentest/engagement does not stop a few minutes after it begins. The loop stops on a documented stop condition or an operator decision, not elapsed time; `offensive.py next` carries the mode in its banner.
- **State-first.** Before any recon/spray/exploit: read `state.md`, `loot.md`, `Killchain.md`, `Deadends.md`. Never re-run a documented dead-end or re-spray a known-failed cred without new input (new cred, new pivot, new payload class).
- **Stop condition.** A vector is exhausted after bounded effort (OOB sink: ~30-40 payloads zero callbacks; spray: full user x pass matrix once). One `Deadends.md` line + Killchain status, then switch. Do not grind, do not re-loop.
- **Log grammar.** One-line events in `targets/<eng>/log.md` use the ASCII token
  vocabulary + audit-line convention in `docs/log-grammar.md` (`tool X ok|fail|blocked`,
  `[lane]` prefixes, `<TS> | category | action | result | detail`).
  **Obsidian-safe log lines (hard):** any angle-bracketed value a lane or the driver writes into a
  vault page (route shapes like `preliminaryCheck/<id>`, lane tags like `<laneX-name>`, payloads)
  sits inside inline backticks; a bare `<token>` renders as an HTML tag and silently swallows the
  rest of the block. Lane-authored log lines are the recurring failure vector - the main session
  backtick-sweeps lane output before it lands in a `.md`.
- **When stuck, call `Skill(redteamlead)` BEFORE grinding.** See hunt-core's Wrong-vector tells for the two mechanical signals (target starved, >=2 verified-hash misses). A `/redteamlead` reminder in the engagement prompt is a real instruction.
- **Harness bugs get the same stops as target vectors.** Instrument
  component boundaries (what enters and exits, config propagation) before proposing a fix to a
  harness issue; three failed fixes on one harness bug is an architecture stop,
  escalate instead of attempting a fourth.
- **Read-first, not grep (recon AND post-foothold).** READ each page/source end-to-end before declaring it enumerated (the vector hides in an AJAX handler / commented route a narrow grep skips); zg to LOCATE across files, grep inside one file, then read the block. Post-foothold source-review is a full `cat` per file. **A delegation prompt MUST carry this mandate verbatim** (`cat` each file in full, zg/grep only to locate): a cheap model grep-mines by default and your prompt is its only law. It MUST also carry the Obsidian-safe rule verbatim (any `<token>` you write into a `.md` is wrapped in inline backticks; bare angle brackets break the page).
- **OOB-gate blind bugs.** Blind SSRF/SSTI/SQLi claims need an out-of-band callback, never inference. Enforced per hunt skill.
- **Delegate exploit EXECUTION to a cheap-tier sub-agent (cost control, default).** Main model keeps strategy/board/wiki/triage; route the fully-specified exploit/escalation RUN via `Skill(delegate)` - see its Model choice section for the cheap-vs-main-model split and the sub-agent-negative-is-a-hypothesis rule.
- **No claim without fresh capture.** A lane or finding claim is claimable only if the proving command ran and its raw output was read this session; `scripts/find-lint.py` checks the finding-card side, `python3 scripts/lane_validate.py --brief <file>` warns on the lane-brief side.
- **Run 2-3 agents by default (brain posture).** Once the board has 2+ open assets/vectors, the engagement runs under `Skill(brain)`: main session keeps the driver/board/wiki/triage, execution goes to 2-3 concurrent disjoint-lane subagents (lane contract = delegate slots a-h). Serial single-agent execution is the fallback for < 2 disjoint rows, not the default; `offensive.py next` prints the `PARALLEL` line when the posture applies.
- **Reuse loot.** Captured creds across `state.md` hosts before new research; default/known creds first (context7, [[default-credentials]]); broad spraying last resort.
- **Memory + skills as you go (hermes port).** Durable facts (operator preferences, environment gotchas) -> `scripts/memory.py add --store operator|environment` (budgets enforced, SessionStart-injected); a repeated procedure -> `scripts/skill_manage.py create` (60-char desc rule, archive-only deletes, curator ages at 14d/30d); past-session recall -> `scripts/session_search.py query`.
- **Distill reusable knowledge.** A default cred or reusable API pattern -> add the GENERIC form to `wiki/cheatsheets/default-credentials.md` / `api-request-findings.md` (check these first next engagement); a new small indicator (a regex tell that would have caught the vector early) -> add a row to `scripts/tells.json` (the tracked tell battery; hunt-core runs it before big reads); at close-out `Skill(learn)` sweeps the rest through `wiki-stage.py` -> `wiki-promote.py`.

---

## Behavior hooks

Output/mode plugins (optional; the harness degrades gracefully without them): **ponytail** (lazy-code discipline - YAGNI, stdlib first, shortest working diff; auto-activates at SessionStart when installed, level `full`, switch via `/ponytail lite|full|ultra`) governs what you build, not prose. **caveman** (prose compression) is a vault skill (ultra level in-file: `/caveman ultra`), manual per session; it stays off in engagement turns, where the output caps above already govern.

SessionStart also auto-loads `session/hot.md`. No manual reads needed.

Engagement-state hooks (workspace-scoped, registered in the committed `.zcode/config.json`, scripts under `skills/hooks/`). All fail open (any error -> allow, never trap). Policy (operator directive 2026-10-05): **only scope-guard denies** - out-of-scope host/IP, a deterministic no-judgement check; RoE-forbidden tooling is an OPERATOR decision (the hook asks; pre-approvable), and every other guard (blind sleeps, drift) ADVISES - a false block wastes more time than it saves (the drift hard advisories and the operator-opt-in spend cap `ZT_MAX_ENG_USD` are the loud exceptions: the cap still denies). Escape hatch for a bad block: `touch skills/hooks/.enforce-off` (downgrades the scope deny and the RoE ask to advisory). Six hook events are registered here, including `PreCompact` (`pre-compact.sh`). Per-hook events and mechanics (all of it) live in `docs/auto-triggers.md`; the set at a glance:

- SessionStart: self-heals engagement files, injects the state summary + next-moves + OOB HITs, registers skills.
- UserPromptSubmit: routes hunt skills from `triggers.json` (leak-safe telemetry).
- PreToolUse: DENIES out-of-scope host/IP only (scope-guard, the one enforcement left); ASKS the operator on RoE-forbidden tooling (`ZT_ROE_OK=1` prefix / `.roe-ok` marker pre-approves); ADVISES (no longer denies) on blind `sleep >= 10` with no poll (sleep-guard), repeat off-board patterns (drift-guard: identical off-board command 3x, >= 6 exploit-shaped calls with zero driver contact pre-foothold -> hard advisories), one-off off-board drift, and a client-marker-in-`session/*` warn.
- PostToolUse: routes tech -> hunt Skill (+ G1 wiki-first nudge), correlates OOB waiting -> HIT, captures PoC pairs + telemetry, re-indexes wiki.
- Stop: nudges SOLVED-box close-out (flag accounting, evidence, walkthrough, learn).

Register/repair the set per-device with `bash setup/install-hooks.sh` (verifies and repairs the committed `.zcode/config.json`; canonical set in `scripts/check-hooks.py`).

Active engagement set by `targets/active.md`; create with `bash setup/new-engagement.sh <name> <pentest|bugbounty|ctf>` (full per-type file schema: `docs/page-types.md`, self-healed by `engagement-init`). ctf engagements lack `Killchain.md`/`log.md` (the live chain lives in `state.md`'s `## Chain`/`## Status` instead); `walkthrough.md` is the full copy-pasteable repro, distinct from `log.md`'s terse audit/continuity-cache role - client narrative always goes to `targets/<eng>/log.md`, never generic `session/hot.md`. Missing wiki pages: `scripts/wiki-gaps.py`.

Framework subsystems (each a script + on-demand skill; mechanics in `docs/auto-triggers.md`): **Ingest** (`ingest` skill: raw output -> `targets/<eng>/ingest/`, synthesized into state/loot/Killchain, archived). **Move ranking** (`offensive.py next`: the driver ranks the next move from the board; update tables after acting so it re-ranks). **Fingerprints** (`scripts/playbook.json`: tech -> targeted tests + hunt skill + payload arsenal; extend as you learn). **Chaining** (`scripts/chains.json`: `finding -> pivot` edges; add edges, no code; `gate:oob` edges wait for an operator callback). **Coverage** (`Approach.md` 4a table + `offensive.py coverage`: a tested class gets `[x]` + a `poc/` image or the gap recurs). **Finding quality** (`scripts/find-lint.py` before /evidence and before a report; findings scaffold from `setup/templates/_find.md`). **Driver aux commands** (`offensive.py plan`: dry-run top-N of `next`, writes nothing; `autonomy`: set the advisory L0-L3 envelope in scope.md; `rebase`: re-point a rotated asset value across the engagement).

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

- **Brevity during engagements/tool-loops (output tokens are billed).** Working a target or any multi-step tool loop: one short line before a tool batch stating intent (<=25 words); whole engagement-turn text <=100 words; then lead the next turn with the RESULT, not a recap. Emit text only for (a) decisions needing the operator, (b) milestone status, (c) errors/blockers that change the plan. No per-step paragraphs, no restating what a command will do, no re-narrating the plan. Full prose is for deliverables that need it (a report, a walkthrough, a design/brainstorm, an explanation the user asked for). A 40-min box should not cost a paragraph per step.
- Never use em-dashes (`--`). Use a comma, semicolon, or rewrite the sentence. (`--` is permitted inside code blocks as a CLI flag.)
- Never use emojis.
- **Obsidian-safe angle brackets (vault pages are the operator GUI).** Obsidian parses any bare angle-bracket token (`<marker>`, `<value>`, `<host>`) as an HTML tag, and one unclosed token silently swallows the rest of the page's rendering. Never write an angle-bracketed value in prose or a table cell; always wrap it in inline backticks (`` `<value>` ``) or put it inside a fenced code block. Applies to every vault page written or edited (wiki/, session/, docs/, skills/, targets/ host cards, log lines, cmdlog summaries); only bytes already inside a fenced capture block stay verbatim. Same page-breaker class: unclosed `%%` or `<!--` spans and unbalanced code fences; close what you open.
- Do not narrate inside commands (echo/printf label banners, `=== ... ===` separators). The harness shows every command with its output; run commands directly.
- **Concrete values, not shell variables, in target commands.** The operator watches the live terminal: real IPs/URLs/paths inline (`curl -s http://10.1.1.5:8080/api`), not `$VAR` placeholders. Reserve variables for genuinely repeated long secrets (a captured token/cookie). Same bar as walkthrough.md (var-free).
- **Shell interaction: one command, clean output, NO markers** (full mechanics: `docs/shell-interaction.md`). The drivers frame output for you: `bash scripts/win-vm.sh '<cmd>'` (this seat; WSL-side `bash /root/vm.sh '<cmd>'`), and `vm-rsh.sh`/`win-rsh.sh` return ONE command's complete output, echo stripped. So: one command per call; NEVER inject sentinel/marker/delimiter strings or split a literal to dodge the echo; no chaining unrelated actions; type it the way an operator would (plain `$env:`/`$_` - the driver escapes, don't hand-encode). Empty/weird output -> PROBE with a bare `whoami` (a username = alive, the empty result was real; nothing = stuck, stop; a non-username = the shell died back to the ATTACKER prompt, the false-RCE trap - re-pop it), never add instrumentation. `$`-heavy enum -> host a readable `.ps1`, run in-memory via an `IEX(DownloadString(...))` cradle.
- **Recovery ladder before any fallback.** A failed call climbs: retry once -> fix the args (flags re-verified with `-h`) -> heed the identical-retry advisory -> only then fall back (seat, tool, provider), never sooner. The original failure stays visible beside the fallback result (fallback output never overwrites it) and a fallback never widens scope.
- **Send load-bearing requests to Burp, not just curl.** Confirm-worthy requests (SSRF, injection, deser, auth bypass) go to **Burp Repeater** via `Skill(hunt-burp)` / the Burp MCP so the operator can replay them (`scripts/capture.sh burp` for a PoC); brute/fuzz belongs in **Intruder** (`send_to_intruder`), not a hand-rolled loop. Prefer the NATIVE MCP tools (`mcp__burp__*`); the `burp-mcp-cli.py` SSH bridge is the fallback (native attaches only at session start; a restart re-attaches). Burp/MCP down? Same discipline through Caido (`Skill(caido)`, Replay entries) - a fallback lane, not an exemption.
- **Multi-step flows encode as `.hurl` files (hurl on the VM).** A login -> CSRF -> object-create -> cross-account-read sequence ships as a reviewable `.hurl` file beside `poc/` (`hurl --test` reruns the whole chain): one assert per transition, unique canaries per step, the negative-control transition in the same file, `--path-as-is` on any encoding/traversal probe. Ceiling: stack-normalized parser differentials and smuggling stay in Burp (hurl rides libcurl, which normalizes); `wiki/tools/hurl.md`.
- **Burp-first does NOT stop at foothold (anti-drift).** After a shell lands, KEEP driving the requests that matter (post-auth API calls, the flag-reading injection, privesc-relevant fetches) through Repeater - the operator is watching Burp, not your terminal. Quick throwaway loops off-Burp are fine; if you catch yourself scripting the whole post-foothold phase off-Burp, that IS the drift - route it back.
- Never add a `Co-Authored-By` trailer, a "Generated with ZCode" line, or any similar attribution footer to git commit messages or PR bodies. (Overrides the harness default that appends one.)

**Code discipline** (ponytail-core floor; the ponytail plugin enforces the full version when installed):

- Ladder, stop at the first rung that holds: does it need to exist -> already in this codebase -> stdlib / platform-native -> one line -> minimum code that works.
- Root cause before edit: grep every caller of the function you are about to touch.
- Clean up orphans your own change created; flag pre-existing dead code in one line, never delete it unsolicited.
- Mark only shortcuts that cut a real corner with a known ceiling (global lock, O(n^2) scan, naive heuristic) with a `ponytail:` comment naming the ceiling and the upgrade path.
- Non-trivial logic leaves one runnable check behind (an assert-based `__main__` or one small `test_*`).
- Never simplify away: input validation at trust boundaries, error handling that prevents data loss, security measures, anything explicitly requested.
- Push back in one line when a simpler path exists than the one requested.

---

## Image handling

Never copy image embeds (`![[Pasted image *.png]]` or `![](url)`) into wiki pages. Reconstruct commands as code blocks from context. Wiki pages must be image-free.
