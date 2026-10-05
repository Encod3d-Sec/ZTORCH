---
name: engage
description: Orchestrator and skill router: the single situation-to-skill map across the whole library (driver, hunt-*, process skills). Use at session start, whenever between phases, or unsure which skill is next.
---

# engage

Router, not method. The driver owns the loop (`Skill(offensive)`, `scripts/offensive.py`),
the hunt skills own exploitation classes, `hunt-core` owns discipline. This file exists so no
skill is ever forgotten: every situation below names the exact skill to load. When the
deterministic driver (`scripts/offensive.py`) is present, its printed next-action wins; when it
is absent, this map IS the router.

## 1. Pick the driver (it owns the loop)

| Situation | Skill |
|---|---|
| Any offensive engagement (box/IP foothold->root, bug-bounty *.scope, or client SoW/CIDR/domain) | `Skill(offensive)` - `offensive.py --type ctf\|bb\|pentest` picks the flavor |
| A standalone challenge (pwn/rev/crypto/forensics/stego/osint/hash/cloud) | `Skill(ctf-category)` |
| Driver missing or behaving wrong on this machine | `Skill(offensive)`'s "If the driver is unavailable" section + `offensive-doctor` (`scripts/offensive-doctor.py`) to diagnose |
| First session on a new machine / VM seat questions | `offensive-doctor` (`scripts/offensive-doctor.py`), then `Skill(kali-seat)` for the Windows -> WSL -> VM seat |

## 2. Phase and situation routing (all engagement types)

| Phase / situation | Skill |
|---|---|
| Board has 2+ open assets/vectors (the DEFAULT execution posture; `offensive.py next` prints `PARALLEL`) | `Skill(brain)` - driver/board/triage stay in the main session, execution dispatched to 2-3 concurrent disjoint-lane subagents |
| Raw tool output landed (scans, crawls, recon dumps) -> state/loot/Killchain | `Skill(ingest)` (cheap-tier subagent; bounded job) |
| "Which tool/payload for this surface" - wiki lookup (quick or deep) | `Skill(wiki-arsenal)` |
| External recon / OSINT / attack-surface mapping | `Skill(wiki-recon)` |
| Targeted web fuzzing needed (deterministic wordlist pick) | `Skill(fuzz)` |
| Driving Burp (proxy triage, Repeater/Intruder/Collaborator) | `Skill(hunt-burp)`; PoC capture from Burp: `Skill(screenshot-burp)` |
| Burp/MCP down, per-engagement isolated proxy project wanted, or Caido-native features (Automate, Replay fuzz batteries) | `Skill(caido)` (headless Caido on the VM; same load-bearing-visibility discipline, Replay entries instead of Repeater tabs) |
| Manual login / MFA / CAPTCHA the agent cannot do headlessly | `Skill(chrome-devtools-browser)` |
| msfconsole work (recon DB, exploits, handler, pivots, post-ex) | `Skill(metasploit)` |
| Windows standard-user foothold on a CTF/lab box needs a kernel/LPE shortcut | `Skill(nightmare)` (recompiled Windows LPE arsenal with recorded Defender verdicts; authorized CTF/lab only; hub [[privesc-exploit-arsenal]]) |
| Fully-specified exploit compile / escalation run to hand off | `Skill(delegate)` (mechanical, cheap tier; false-root guardrail mandatory) |
| Stalled, wrong-vector tell fired, "should I keep hammering?" | `Skill(redteamlead)` - NEVER grind; ranked directions + explicit STOP |
| A vuln class never tested on this asset (4a coverage gap) | `Skill(offensive)` - `offensive.py coverage` ranks the gaps |
| Vuln/CVE research on a binary/repo/app/firmware | `Skill(research)`; ingest a CVE writeup: `Skill(nday)` / `Skill(research-ingest)` |
| "Is this valid / should I report it" - validating a finding | `Skill(triage)` |
| Evidence hygiene before a report or any share | `Skill(evidence)`; screenshots: `Skill(screenshot)` |
| Confirmed/proven finding needs responsible disclosure | `Skill(disclosure)` |
| "Why is this row on the board" / which vector baseline applies | `Skill(vector-workflow)` |
| Wiki maintenance (re-index, status, page types) | `Skill(wiki)` |

Discipline spine for every hunt: `Skill(hunt-core)` loads alongside any hunt skill (scope gate,
two-account rule, confirmation gate, enumeration limits, stop conditions, FIND output).

## 3. Scan-mode overlay (quick / standard / deep)

A named mode changes the SKIP LIST and PRIORITY ORDER only - never the evidence bar: a
CONFIRMED needs the same working PoC (OOB callback where blind) at every mode; a mode may
defer work, never weaken proof. State the mode out loud when the engagement shifts.

| Mode | What it is | Skip list | Priority order |
|---|---|---|---|
| quick | triage / time-boxed pass; surface map + cheap high-signal | full JS bundle reads, exhaustive param mining, chained CVE research, deep source audits | in-scope auth surfaces, known-CVE versions, tells.json hits, exposed secrets |
| standard | the default: the flow as written, every surfaced class hunted | nothing the flow mandates | driver order (`offensive.py next`) |
| deep | standard + full-read source passes, second-order re-tests, chained impact escalation, negative controls on every CONFIRMED | nothing | confirmed-finding neighborhoods first, then driver order |

Shift up (quick -> standard -> deep) when: a confirmed finding changes the model of the
app, the operator asks for depth, or a `status.py` budget band (70/85/95) says there is
room. Shift down when a band says wrap-up. Whatever quick mode skipped is UNEXAMINED, not
clean: record it as reopen-if rows in Deadends.md so close-out counts it.

## 4. Fingerprint -> hunt skill

`hunt-core`'s `## Hunt approaches` table is the authority (read it; do not duplicate it here).
Memory index, one line per class, so no hunt skill is forgotten:

- Input reflection / DOM sink -> `hunt-xss`; DB oracle -> `hunt-sqli`; URL/fetch sink -> `hunt-ssrf`
- Object IDs / cross-account -> `hunt-idor`; template/XXE/GraphQL -> `hunt-injection`; exec sink / version+CVE -> `hunt-rce`
- Serialized blob / viewstate -> `hunt-deserialization`; login/session/JWT -> `hunt-auth`; OAuth/SAML -> `hunt-federation`
- File upload -> `hunt-upload`; API BOLA/BFLA -> `hunt-api`; price/coupon/race -> `hunt-bizlogic`; desync -> `hunt-smuggling`
- Cache key -> `hunt-cache`; exposed `.git`/`.env`/keys -> `hunt-secrets`; LLM app -> `hunt-llm`; MCP server -> `hunt-mcp`
- AD / DC -> `hunt-ad`; Windows local privesc -> `hunt-windows`; macOS -> `hunt-macos`; cloud metadata/IAM -> `hunt-cloud`
- M365 / Entra tenant -> `hunt-m365`; CI/CD pipeline/runners -> `hunt-cicd`; VPN appliance -> `hunt-vpn`; PLC/Modbus -> `hunt-ics`

## 5. Close-out

Run `python3 scripts/offensive.py --eng <name> closeout` and follow its printed order - the chain
lives only in `CLOSEOUT_CHAINS` (`scripts/offensive.py`), not restated here to avoid drift.

## Maintenance rule

A skill added to `skills/` without a routing row in this file or in `scripts/routing.json` is an
orphan by definition: nothing will ever name it mid-engagement. New skill -> add its row to the
section above that fits.
