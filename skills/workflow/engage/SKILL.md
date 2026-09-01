---
name: engage
description: >
  Orchestrator and skill router for any engagement: the single situation -> Skill(name) map
  across the whole library. Picks the offensive driver (Skill(offensive)), routes every
  fingerprint to the right hunt-* skill, and surfaces the process skills (ingest, wiki-arsenal,
  redteamlead, delegate, fuzz, metasploit, kali-seat, ...) at the
  phase they belong. Load FIRST in every session and consult whenever between phases or unsure
  which skill is next. Pure router: owns no methodology itself.
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
| Raw tool output landed (scans, crawls, recon dumps) -> state/loot/Killchain | `Skill(ingest)` (cheap-tier subagent; bounded job) |
| "Which tool/payload for this surface" - wiki lookup (quick or deep) | `Skill(wiki-arsenal)` |
| External recon / OSINT / attack-surface mapping | `Skill(wiki-recon)` |
| Targeted web fuzzing needed (deterministic wordlist pick) | `Skill(fuzz)` |
| Driving Burp (proxy triage, Repeater/Intruder/Collaborator) | `Skill(hunt-burp)`; PoC capture from Burp: `Skill(screenshot-burp)` |
| Manual login / MFA / CAPTCHA the agent cannot do headlessly | `Skill(chrome-devtools-browser)` |
| msfconsole work (recon DB, exploits, handler, pivots, post-ex) | `Skill(metasploit)` |
| Fully-specified exploit compile / escalation run to hand off | `Skill(delegate)` (mechanical, cheap tier; false-root guardrail mandatory) |
| Stalled, wrong-vector tell fired, "should I keep hammering?" | `Skill(redteamlead)` - NEVER grind; ranked directions + explicit STOP |
| A vuln class never tested on this asset (4a coverage gap) | `python3 scripts/offensive.py coverage` (the driver ranks the gaps) |
| Vuln/CVE research on a binary/repo/app/firmware | `Skill(research)`; ingest a CVE writeup: `Skill(nday)` / `Skill(research-ingest)` |
| "Is this valid / should I report it" - validating a finding | `Skill(triage)` |
| Evidence hygiene before a report or any share | `Skill(evidence)`; screenshots: `Skill(screenshot)` |
| Wiki maintenance (re-index, status, page types) | `Skill(wiki)` |

Discipline spine for every hunt: `Skill(hunt-core)` loads alongside any hunt skill (scope gate,
two-account rule, confirmation gate, enumeration limits, stop conditions, FIND output).

## 3. Fingerprint -> hunt skill

`hunt-core`'s `## Hunt approaches` table is the authority (read it; do not duplicate it here).
Memory index, one line per class, so no hunt skill is forgotten:

- Input reflection / DOM sink -> `hunt-xss`; DB oracle -> `hunt-sqli`; URL/fetch sink -> `hunt-ssrf`
- Object IDs / cross-account -> `hunt-idor`; template/XXE/GraphQL -> `hunt-injection`; exec sink / version+CVE -> `hunt-rce`
- Serialized blob / viewstate -> `hunt-deserialization`; login/session/JWT -> `hunt-auth`; OAuth/SAML -> `hunt-federation`
- File upload -> `hunt-upload`; API BOLA/BFLA -> `hunt-api`; price/coupon/race -> `hunt-bizlogic`; desync -> `hunt-smuggling`
- Cache key -> `hunt-cache`; exposed `.git`/`.env`/keys -> `hunt-secrets`; LLM app -> `hunt-llm`; MCP server -> `hunt-mcp`
- AD / DC -> `hunt-ad`; Windows local privesc -> `hunt-windows`; macOS -> `hunt-macos`; cloud metadata/IAM -> `hunt-cloud`
- M365 / Entra tenant -> `hunt-m365`; CI/CD pipeline/runners -> `hunt-cicd`; VPN appliance -> `hunt-vpn`; PLC/Modbus -> `hunt-ics`

## 4. Close-out

- CTF: `Skill(walkthrough)` -> `Skill(learn)`.
- bb/pt: `Skill(triage)` -> `Skill(evidence)` -> `Skill(walkthrough)` -> `Skill(learn)`
  (walkthrough assembles the report-ready document; there is no separate report skill).

## Maintenance rule

A skill added to `skills/` without a routing row in this file or in `hunt-core`'s table is an
orphan by definition: nothing will ever name it mid-engagement. New skill -> add its row to the
section above that fits.
