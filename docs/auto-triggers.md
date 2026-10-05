# Auto-Triggers: what fires automatically, and when

What the framework fires on its own, so you know what activates for a given task.

**Core principle:** auto-triggers **inject context** (a suggestion the model reads and acts on, or a warning). They do **not** silently run commands. Every fire is a visible injected line. Nothing executes a tool by itself.

> **During an engagement, the driver supersedes these advisory triggers.** Running an engagement under `Skill(offensive)` (`scripts/offensive.py`) puts the driver in charge: it prints the next required action (wiki-first, tool-first, skill-first, typed evidence) as tool output every turn, which is *enforced* rather than suggested. The hooks below still fire and remain the routing layer for **ad-hoc, non-campaign** work; inside a campaign, follow the driver's `next` block over any hook nudge. Retiring the now-redundant hooks is deliberately deferred: they are harmless and still serve non-campaign work.

**Source of truth** (edit these, not this doc, to change behaviour):
- keyword -> skill: `skills/hunt/triggers.json`
- tech fingerprint -> tests: `scripts/playbook.json`
- finding class -> pivot: `scripts/chains.json` (ingested by `next_move.py`, keyed by finding class; candidates never auto-fire, suggestions only)
- hook logic: `skills/hooks/*.py`
- hook registration: committed `<vault>/.zcode/config.json` (ZCode workspace scope, the live registration on this build) OR the per-device `~/.claude/settings.json` provisioned by `setup/install-hooks.sh` (the legacy Claude-Code-seat path; that script does not read or verify `.zcode/config.json`)

This page is a snapshot; regenerate the tables from those files if they change.

---

## What fires, and when

| Event | Hook(s) | What happens |
|---|---|---|
| **SessionStart** | `session-start.sh`, `engagement-init.py` | Loads `session/hot.md` (after rotating it to its ~3 newest entries, older ones archived verbatim to `hot-archive.md`); injects the active-engagement summary + top next-moves + recent log + wiki-health line (only if broken) + active research status (`research_status.py`); regenerates `index.md` if stale; self-heals the engagement file set. |
| **UserPromptSubmit** | `hunt-trigger.py` | Keyword-matches the prompt against `triggers.json` (code-stripped, intent-gated): a hard hit surfaces the relevant **Skill(x)** to load (routing; the skill carries the mandate), a surface hit a softer "consider Skill(x)". Leak-safe telemetry to `.trigger-fire.jsonl`. |
| **PreToolUse (Bash)** | `scope-guard.py` | The ONE enforcement left (operator directive 2026-10-05): DENIES an out-of-scope host/IP (CIDR-aware). RoE-forbidden tooling (`no_bruteforce`/`no_dos`/`passive_only`) is an OPERATOR DECISION: the hook asks (`permissionDecision: "ask"`); `ZT_ROE_OK=1` env prefix on the command or a `.roe-ok` marker in the engagement dir pre-approves. Fail-open; `.enforce-off` downgrades both to advisory. |
| **PreToolUse (Bash)** | `sleep-guard.py` | ADVISES on a blind wait (`sleep N`, N >= 10, no `while`/`until` poll watching output). Reason carries the fix (`until <check>; do sleep 2; done`). Settling sleeps < 10s and poll loops pass; heredoc bodies exempt (payload, not a wait). Advisory-only (operator directive 2026-10-05). |
| **PreToolUse (Bash)** | `drift-guard.py` | Advisory at every tier (operator directive 2026-10-05): nudges when shell work drifts off the `Approach.md` plan board (off-board commands; streak 1-3 then every 25th; silent post-foothold/post-SOLVED). Two HARD-advisory triggers, most specific first: (1) IDENTICAL-RETRY loop-break, the same unchanged off-board command 3x (the run before it gets a "next identical run gets the loop-break advisory" warning; a driver call clears the ring); (2) streak >= 6 exploit-shaped calls with zero driver contact (board has open rows, not post-foothold), naming the `offensive.py next`/`note` step that clears it. Every 20 cumulative hard advisories the message grows a `Skill(redteamlead)` escalation; hard advisories cap at 5 fires per engagement. The operator-opt-in spend cap (`ZT_MAX_ENG_USD`) is the one deny left; `.enforce-off` downgrades it. |
| **PreToolUse (Bash)** | `zg-nudge.py` | Advisory: fires when a command OPENS with a recursive/single-file-crossing grep or rg (the cross-file "locate" shape); ADVISES `zg query --human` / the zvec-grep MCP tool. Rate-limited to one nudge per 15 min (`session/.zg-nudge-stamp`); skips remote/VM contexts and framework-meta. |
| **PreToolUse (Bash)** | `tmux-nudge.py` | Advisory: fires when a heavy tool (nmap/sqlmap/msf/hydra/nc -l/...) is invoked at command position (outer or inside a vm.sh/ssh/vm-ssh wrapper) with no tmux token and not already routed via a tmux-aware driver; ADVISES the `vm-scan.sh --win` / `vm-bg.sh` / `vm-rsh.sh --create` launch. Rate-limited to one nudge per 15 min (`session/.tmux-nudge-stamp`); skips pane readbacks, `--version`/`--help`, framework-meta. |
| **PreToolUse (Bash)** | `burp-nudge.py` | Advisory: fires on a body-ful curl carrying a payload signature (`' or '`/`union select`/`sleep(`/`benchmark(`/`%27`) or a Cookie/Authorization header, or on a handrolled network loop; ADVISES Burp Repeater (`Skill(hunt-burp)` / `burp-hunt.sh`) for single requests and Intruder (`send_to_intruder`) for loops. Rate-limited to one nudge per 15 min (`session/.burp-nudge-stamp`); skips commands already routed to the Burp tooling. |
| **PreToolUse (Write)** | `session-guard.py` | Warns when a write would put a client marker into a generic `session/*` file OR a git-tracked framework tree (`wiki/`, `scripts/`, `skills/`, `docs/`, `tests/`, `setup/`); `targets/` and `docs/superpowers/` are exempt. Catches the codename-in-a-tracked-file leak at write-time. |
| **PreToolUse (Read)** | `big-read.py` | Advisory: a full Read of a file >200KB with no offset/limit (bundled JS, scan dumps, raw logs) gets one nudge per file per 15 min (`session/.big-read-stamps/`) with the exact size and the locate-first ladder (zg / `grep -n` / js-beautify, then a narrow Read). Explicitly "locates, does not replace the read": the read-first mandate still rules for intended whole-file review, chunked via offset/limit. |
| **PostToolUse (Bash)** | `recon-capture.py` | Fingerprint auto-route (to the hunt Skill) + OOB callback correlation + a once-per-engagement GATE-1 wiki-first nudge (exploit-shaped command while `Approach.md` Weaponize is undone). A framework-meta guard suppresses false fires. Advisory. |
| **PostToolUse (all)** | `tool-telemetry.py` | Per-box telemetry: appends every tool/skill call to `targets/<eng>/.events.jsonl`, stamps `started_at`, records the transcript path; feeds `eval_metrics.py`. Silent, fail-open. |
| **PostToolUse (Bash)** | `capture-poc.py` | Appends every meaningful command + its output to `targets/<eng>/poc/cmdlog/<tool>.md` (grouped by the inner binary, vm.sh-unwrapped), so the operator has a readable per-tool record with no manual capture. Skips framework/dev commands; capped; fail-open. Three reflexes on top of the log: empty-output streak (>=2 empties -> `whoami`-probe advisory per docs/shell-interaction.md; a real output resets), finding-grade auto-cards (flag token / root banner / hashcat cracked -> `poc/NN-<kind>-auto.md`, token-deduped), and the stall battery (after any of 12 scan/probe tools: `scripts/stallcheck.py` verdicts deduped 30 min; a STALL SIGNAL on the driver's last-served row auto-runs `offensive.py done <rid> --dead` so the cursor advances instead of re-serializing a row the data says can never land). |
| **PostToolUse (Write/Edit)** | `wiki-reindex.py` | Auto-reindex: a Write/Edit to `wiki/**/*.md` fires a debounced background `qmd update && qmd embed`, so the change is searchable (text AND semantic) without a manual reindex. Off the blocking path, fail-open. |
| **Stop** | `close-out.py` | Close-out reflex: when the engagement is SOLVED but its walkthrough is unassembled (or the learn harvest is due), nudges Skill(walkthrough) then Skill(learn). Advisory, self-clearing. |
| **PreCompact** | `pre-compact.sh` | Registered in `.zcode/config.json`; fires before a context compaction. |

All 17 hooks (across 6 events) inject context, route to a skill, capture telemetry, or fire a deterministic safety guard; none prescribes methodology, none launches a scan, and all fail open. Only `scope-guard` ENFORCES (deny out-of-scope host/IP; RoE-forbidden tooling ASKS the operator, operator directive 2026-10-05); `sleep-guard` and `drift-guard` are advisory at every tier (drift's repeat tiers are HARD advisories - un-throttled, loop-breaking - but never denies; the sole exception is the operator-opt-in spend cap `ZT_MAX_ENG_USD`); the rest are advisory-only (inject context, never deny). **Output channels differ by event** (what a hook may print; pinned by `tests/test_hook_outputs.py`):
- **Context channels** -- SessionStart, UserPromptSubmit, Stop (+ PreCompact's plain-text stdout): plain prose on stdout IS the injection mechanism (the state block, the skill directive, the close-out nudge). Deliberately not JSON.
- **Decision channels** -- PreToolUse, PostToolUse: stdout feeds the permission/context machinery, so a hook prints either SILENCE or exactly ONE JSON object carrying `hookSpecificOutput` (deny decisions, advisories as `additionalContext`). A diagnostic line here corrupts any JSON-parsing consumer; half-built dicts (JSON without `hookSpecificOutput`) are a contract violation.

Canonical set: `scripts/check-hooks.py` `EXPECTED_HOOKS`. (Removed 2026-08-04: `web-recon.py`, which auto-launched `recon-web.sh` + a chromium page render on every newly-seen in-scope surface. It fired on tool OUTPUT, so merely PRINTING a hostname re-launched scans and a render against hosts already retired, and the render leg was producing empty `poc/` dirs rather than evidence. Run `scripts/recon-web.sh <eng> <url>` by hand instead.)

Dormant and offline machinery, documented so nothing looks missing:
- `skills/hooks/eng-ckpt.py`: dormant checkpoint helper, unregistered by design; never delete (a PreToolUse Write/Edit checkpoint of the pre-edit engagement state, kept for a possible future registration; fires nowhere today).
- Wiring subsystem (offline scripts, no hook wiring): `wiki-wiring-audit.py` (audits which wiki pages surface "by context" during an engagement: playbook refs, hunt-skill links, one hub hop), `apply-wiring.py` (applies a merged wiring-proposal JSON to `playbook.json` / `triggers.json` / hub pages / hunt SKILL.mds), `wiring-exempt.txt` (pages deliberately excluded from the wiring audit), `bench.py` (scores a completed engagement dir against an expected-coverage manifest).

---

## 2. What you TYPE -> hunt / workflow skill

Prompt contains the keyword (case-insensitive) -> that skill is suggested. Multiple can fire at once.

| Keywords | Skill |
|---|---|
| ssrf, server-side request forgery | hunt-ssrf |
| xss, cross-site scripting | hunt-xss |
| prototype pollution, dom clobbering | hunt-xss |
| sqli, sql injection | hunt-sqli |
| idor, broken access control, access control | hunt-idor |
| rce, command injection, remote code execution | hunt-rce |
| auth bypass, account takeover, ato | hunt-auth |
| csrf, cross-site request forgery | hunt-auth |
| oauth, saml, sso, federation | hunt-federation |
| graphql, xxe, ssti | hunt-injection |
| active directory, kerberoast, as-rep, dcsync, adcs, bloodhound, golden/silver ticket, pass-the-hash, ntds, esc[0-9], ntlm relay | hunt-ad |
| aws, s3 bucket, gcp, imds, metadata service, 169.254.169.254, iam privesc, ec2, service account key, cloud credential | hunt-cloud |
| m365, entra, azure ad, exchange online | hunt-m365 |
| fortigate, pulse secure, cisco vpn, palo alto, vpn appliance | hunt-vpn |
| deserialization, ysoserial, gadget chain, pickle, viewstate, marshal.load, phpggc | hunt-deserialization |
| request smuggling, http smuggling, cl.te, te.cl, desync, h2c smuggling | hunt-smuggling |
| file upload, unrestricted upload, upload (web)shell, malicious file upload, zip slip | hunt-upload |
| business logic, workflow bypass, price manipulation, coupon abuse, mass assignment, parameter tampering | hunt-bizlogic |
| web cache poisoning, cache deception, unkeyed input/header | hunt-cache |
| ctf challenge, crackme, capture the flag, pwn this/challenge, reverse this binary, solve this challenge, stego | ctf-category (routes to crypto/rev/forensics/stego/pwn) |
| research ingest, wiki ingest, ingest this cve/writeup/advisory/blog/url/repo, add to wiki | research-ingest |
| find a cve, vuln research, analyze this binary/library/firmware, audit this code, 0day | research (CVE-discovery loop; scaffolds raw/research/&lt;project&gt;/) |
| prompt injection, jailbreak, llm attack, excessive agency, indirect prompt | hunt-llm |
| api security/testing, bola, bfla, swagger/openapi, grpc | hunt-api |
| n-day, patch diff, bindiff, silent patch, 1-day | nday |
| disclose, request a cve, report to vendor, coordinated disclosure, security.txt | disclosure (finding -> CVE) |
| what next, next move, where to focus, prioritize, what should I attack/test | offensive.py next |
| ingest, synthesize findings/recon/output, process recon | ingest |
| coverage, what haven't we tested, test gaps, are we thorough, untested | offensive.py coverage |

51 triggers total (37 vuln-type + 14 attack-surface). xxe/ssti/graphql route to hunt-injection (no separate skills). azure ad -> hunt-m365 (not hunt-cloud) by design. (Counts drift as `triggers.json` grows; recount with `python3 -c "import json;d=json.load(open('skills/hunt/triggers.json'));print(len(d['triggers']),len(d['surface_triggers']))"`.)

A third advisory tier, `relational_triggers` (3 rows -> `graphify`), fires on wiki-relation phrasing (how pages connect, hub or orphan pages, the wikilink graph): page-noun-gated so engagement prose ("path between the two hosts") never fires it. It nudges `Skill(graphify)` with the lane rule baked in: qmd answers content, graphify answers relations.

---

## 3. What you RUN -> command-time triggers

### Before the command: scope enforcement + RoE operator gate (`scope-guard.py`, PreToolUse)
The ONE hard enforcement left (operator directive 2026-10-05):
- **DENIES** (`.enforce-off` marker downgrades it to an advisory warning) when the command targets an out-of-scope host/IP (CIDR-aware: `10.0.3.9` caught by out-of-scope `10.0.3.0/24`). Out-of-scope denies even under RoE pre-approval.
- **ASKS the operator** when the command uses RoE-forbidden tooling given `scope.md` flags: `no_bruteforce` (hydra/medusa/kerbrute/...), `no_dos` (slowloris/--min-rate huge/nmap -T5/...), `passive_only` (any active scanner). Running it is the OPERATOR's call - the hook raises `permissionDecision: "ask"` instead of silently blocking. Pre-approval paths: a `ZT_ROE_OK=1` env prefix on this command (the operator just said yes), a `.roe-ok` marker file in the engagement dir (approved engagement-wide), or flipping the flag in `scope.md`.

Fails open: a missing scope entry = no denial. No active engagement = silent.

### Before the command: blind-wait advisory (`sleep-guard.py`, PreToolUse)
**ADVISES** (advisory-only, operator directive 2026-10-05) when the command contains a timed `sleep N` (N >= 10) with no `while`/`until` structure. The recurring cost: a blind `sleep 120; <check>` burns wall-clock twice (the guess is usually wrong in both directions) and the operator loses the tmux window to a dead wait. The advisory carries the fix: poll on a CONDITION, `until <check>; do sleep 2; done`. Settling sleeps under 10s (`sleep 2` after a restart) and any poll loop pass; heredoc bodies are exempt (payload content, not a wait in this shell). Telemetry via `_telemetry.drift("sleep-guard", ...)`.

### After a bash command: fingerprint router + OOB correlation + GATE-1 nudge (`recon-capture.py`, PostToolUse)

**Fingerprint auto-route** - scans the command + its output for tech and injects the hunt skill to fire. A framework-meta guard suppresses false fires when the command reads/edits the vault's own playbook/hook/wiring machinery (its output is full of playbook tokens). Detected tech (from `playbook.json`):

```
graphql  spring  supabase  wordpress  laravel  next.js  firebase  magento
jenkins  tomcat  gitlab  elasticsearch  influxdb  redis  mssql  jwt  oauth  s3
azure  fortigate  kubernetes  docker  swagger  ldap  smb  x-cache  mongodb
confluence  drupal  joomla  grafana  phpmyadmin  weblogic  iis  struts  jira
llm  mcp  github actions  grpc  exchange  ivanti  moveit  sharepoint  activemq
coldfusion  php-cgi  vcenter  screenconnect  papercut  ofbiz
```
(109 fingerprints. Each emits the hunt skill to load, e.g. `jenkins detected -> load Skill(hunt-rce)`. The tech list above is an illustrative subset; regenerate from `playbook.json`.)

**OOB callback correlation** - flips a waiting `oob.md` row to HIT when its planted token appears in the command + output blob (operator polling OAST/Collaborator), so a confirmed blind-bug callback is surfaced immediately instead of being missed.

**GATE-1 wiki-first nudge** - the only enforcement the plan board's GATE lines get. When an exploit-shaped command runs (`sqlmap`/`hydra`/`medusa`/`msfconsole`/`evil-winrm`/`nxc ... -x`/a reverse shell, incl. inside a vm.sh/ssh/wsl wrapper) while the active `Approach.md` `## 2. Weaponize` section has no `[~]`/`[x]` progress, it nudges once per engagement to query the wiki + pick the payload + mark the Weaponize item BEFORE hand-rolling. Fire-once (`.gate1-nudged` marker), framework-meta exempt, advisory + fail-open.

Tools whose output is fingerprinted (matched at command position, including inside `vm.sh`/`ssh`/`wsl` bridge wrappers): `nmap masscan nxc netexec crackmapexec ffuf httpx subfinder rustscan naabu dnsx katana gau amass gowitness arjun nuclei gobuster feroxbuster curl wget whatweb wpscan nikto nslookup dig sqlmap dalfox swaks`. (Capturing results into `state.md`/`loot.md` is now state-first discipline, not a hook nudge.)

**`fuzz` skill routing** - three independent paths, no single point of failure: typed discovery vocabulary (`fuzz`, `vhost`, `hidden param`, ...) hits `triggers.json` `surface_triggers` (§2); a live recon gap fires one of `recon-capture.py`'s two content-discovery nudges (RECON COMPLETENESS when a web probe ran but discovery didn't, and the new-surface-class nudge after a foothold); and a precise discoverable-surface signal (dir listing, robots `Disallow`, swagger/openapi) in `playbook.json` routes straight to `Skill(fuzz)` rather than a generic "http service" fingerprint.

---

## By task - concrete examples

| You do | Auto-fires |
|---|---|
| type "test login.x.com for sql injection" | hunt-sqli (wiki query + payloads) |
| run `nmap -sV host` -> output shows Jenkins + GraphQL | router: jenkins + graphql detected -> load hunt-rce / hunt-injection |
| run `hydra ...` with `no_bruteforce: true` in scope | scope-guard ASKS the operator (deny only if out of scope; `ZT_ROE_OK=1`/`.roe-ok` pre-approves) |
| run `nmap 10.0.3.9` where `10.0.3.0/24` is out of scope | scope-guard denies the command |
| type "solve this crackme" | ctf-category -> reverse-engineering page + radare2/pwntools |
| type "what next" | offensive.py next (ranked moves) |
| start a session on an engagement | engagement-init: state + top-3 next moves + wiki health |

---

## How you know it fired

Every trigger prints a visible line the model then acts on:
- `MANDATORY ... load Skill(<skill>)` (hard keyword hit) / `consider Skill(<skill>)` (surface hit)
- `Fingerprint auto-route (playbook.json) ...` (a recon command found tech)
- a `scope-guard` block with the scope/RoE reason (out-of-scope = deterministic deny; RoE tooling = operator ask; a `SCOPE/RoE ADVISORY` line instead when `.enforce-off` is set)
- `=== Engagement state ===` (session start)

Nothing runs a command on its own. To change what fires: edit `triggers.json` (keywords), `playbook.json` (fingerprints + tests), or the hook `.py` files; the registration itself lives in the committed `.zcode/config.json` on a ZCode build (`bash setup/install-hooks.sh` provisions the separate, per-device `~/.claude/settings.json` for a Claude-Code-seat build -- it does not touch or verify `.zcode/config.json`).

---

## ZCode hook mechanics (output contract)

ZCode registers six events in the committed `.zcode/config.json`: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, and `PreCompact` (`pre-compact.sh` IS registered there, contrary to an earlier version of this doc). Registration: `.zcode/config.json` -> `hooks.events` (`hooks.enabled: true` required -- hooks are off by default); commands resolve scripts via the `${ZCODE_PROJECT_DIR}` template var; matchers are case-sensitive regexes on the tool name (`Bash`, `Write|Edit`, ...).

Output contract (enforced by schema validation -- violations are logged and the output discarded, never fatal):
- stdout must be strict hook JSON or empty. Plain text fails validation and is silently dropped, so every context-injecting hook prints its own `{"hookSpecificOutput": {"hookEventName": "<Event>", "additionalContext": "..."}}` directly (each hook builds the payload inline; there is no shared emit helper).
- Exit codes: `0` pass, `2` a deliberate deny (PreToolUse/PermissionRequest), anything else logs a non-blocking error. The hooks fail open: any internal error exits `0`.
- Advisory guards (`session-guard`, `recon-capture`, `sleep-guard`) emit `additionalContext` only; `scope-guard` emits `permissionDecision: "deny"` (out-of-scope host/IP) or `"ask"` (RoE-forbidden tooling, operator decision) with a reason; `drift-guard` emits `additionalContext` at every tier including its hard advisories (identical-retry 3x, off-board streak >= 6 pre-foothold) - its only deny is the operator-opt-in spend cap (`ZT_MAX_ENG_USD`). `recon-capture` also emits a `systemMessage` on an OOB HIT correlation (operator-visible alert, excluded from model context; the model-visible half stays in `additionalContext`). Drift-guard treats an OPEN, FRESH lane line (`in flight @<HH:MM>` younger than the 45-min stale window, delegate contract, log.md) as driver contact: calls during lane flight never feed the streak hard advisory (the checklist was authored from `next`); the identical-retry hard advisory still fires mid-lane, and a stale line stops exempting.
