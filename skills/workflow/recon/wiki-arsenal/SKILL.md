---
name: wiki-arsenal
description: Fast PARALLEL wiki lookup engine over wiki/techniques + wiki/payloads + wiki/tools + wiki/cheatsheets for a surface/service/vuln-class. Two modes - quick (one qmd search, cheap, fire constantly) and deep (4 parallel subagents, one per area, merged ready-to-use arsenal card, cached). The hunt-* skills each inline their own qmd_query and can hand off here for a parallel lookup. Use for "what do I use against <surface>", "arsenal for <X>", "deep/full arsenal", "tool + payload + technique + cheatsheet for <X>", "fast wiki lookup", "parallel wiki search", any "how do I attack/exploit <service|vuln-class>" where you want the documented tooling + payloads before hand-rolling.
---

# wiki-arsenal

The fast, wiki-first lookup engine for "what do I use against this surface". Runs the four
knowledge areas in parallel so a deep lookup is one wall-clock, not four serial reads. The
`hunt-*` skills each carry their own wiki-first `qmd_query` (MCP-independent) and
can hand off here for a fast parallel lookup. Never hand-roll from memory when the wiki has the answer.

Input: a surface, service, or vuln-class (e.g. `Jenkins on 8080`, `SSRF`, `Kerberoasting`).

## 0. Cache check first (0 tokens on a repeat)

Slug the surface (lowercase, non-alnum -> `-`). If `targets/<active-eng>/arsenal/<slug>.md`
exists, read and return it. Do not re-spend. (`<active-eng>` = the dir named in `targets/active.md`.)

## Mode: quick (DEFAULT - fire it constantly)

One `mcp__wiki-search__qmd_query` over the whole index (add a `qmd_search` keyword pass when the
surface is an exact product/CVE string). Group the hits under the four areas and return each as
`path -> one-line snippet`:

- **Techniques** (`wiki/techniques/`)
- **Payloads** (`wiki/payloads/`)
- **Tools** (`wiki/tools/`)
- **Cheatsheets** (`wiki/cheatsheets/`)

Cost ~1-2k tokens, no subagents. Fire it on
every new surface to raise wiki coverage cheaply. Stop here unless the surface is worth deep prep.

## Mode: deep (opt-in - "deep"/"full arsenal", or a whole service/target worth prepping)

Dispatch FOUR parallel subagents in a SINGLE message (Agent tool), one per area, with
on the cheap tier (glm-5.3-flash; pin `model` only if your ZCode build exposes per-agent selection) - each only
reads its area and distils a card, which a lightweight model does well at a fraction of the cost (a
full-model fan-out measured ~170k tokens; the cheap tier cuts that hard). Each
is told to search only its area, read the top 2-3 matching pages, and return a compact ready-to-use
card for its area ONLY (nothing else), citing the page paths it used:

| Agent | Searches | Returns |
|---|---|---|
| tools | `wiki/tools/` | the automated tool(s) to run + the exact command line |
| payloads | `wiki/payloads/` | ready-to-send payloads for the vuln-class |
| techniques | `wiki/techniques/` | the attack steps / chain |
| cheatsheets | `wiki/cheatsheets/` | quick copy-paste commands |

Each agent scopes its search to its area: pass a path filter to `qmd`, or query the whole index
and keep only `wiki/<area>/` hits, then read those pages. The pages an agent reads stay in that
agent's context and are discarded; you ingest only its card.

Merge the four returned cards into one arsenal card, four labelled sections plus a final
`Sources:` line listing every page used.

### Persist the deep card

Write the merged card to `targets/<active-eng>/arsenal/<slug>.md` (create the dir on demand) with
frontmatter `surface:` and `generated:`. That is the cache step 0 reads next time.

## Guardrails (token control)

- Default is quick (~1-2k tokens). Only go deep on request or for a real service/target.
- Deep is bounded: exactly 4 agents on the cheap tier, each capped to the top 2-3 pages. The cost
  is isolated to the subagents; your main context only gains the merged card.
- The cache prevents re-spend on the same surface.

## Hand off

The full class-specific methodology lives in the matching `hunt-*` skill. After the arsenal card,
hand off to it (e.g. `Skill(hunt-ssrf)`) for the actual exploitation loop.

## At-a-glance index (folded in from the retired arsenal skill)

Sanity-check the lookup against these tables; they are not a substitute for the qmd pass. Order:
automated tool -> technique/payload -> capture.

### Tool first (`wiki/tools/` - don't improvise)

Fingerprint the surface -> reach for the tool we already document. `ls wiki/tools/` for all of them.

| Surface / service | Automated tools (`wiki/tools/<name>.md`) |
|---|---|
| Web HTTP(S) | httpx, whatweb, nikto -> ffuf/feroxbuster/gobuster (content) -> katana/gau (crawl) -> arjun (params) -> nuclei (CVE/misconfig) -> dalfox (XSS) -> wpscan (WP); gowitness, burp-suite/burp-mcp |
| Ports / host | nmap, rustscan, naabu |
| DNS / subdomains | subfinder, amass, dnsx, gau |
| SMB / Windows / AD | netexec, responder, impacket, bloodhound/powerview, kerbrute, certipy/rubeus, evil-winrm |
| Login / creds | hydra, medusa (brute) -> hashcat, john (crack) -> jwt_tool (JWT) -> swaks (SMTP) |
| Post-shell privesc | pspy + linpeas/peass (ALWAYS, first) |
| Pivot / tunnel | chisel, ligolo-ng |
| Cloud | pacu, scoutsuite, roadtools, trivy |
| Binary / RE / pwn | ghidra, radare2, gdb-gef, pwntools, angr, binwalk, jadx, apktool, frida |
| Secrets / SAST / forensics | trufflehog, trivy, semgrep, codeql, volatility, tshark |

Read the tool page for exact flags before running; no page -> `qmd_query`/`Skill(wiki)`.

### Then technique / payload (`wiki/payloads/` + `wiki/cheatsheets/`)

- **Vuln class -> `wiki/payloads/<class>.md`**: sqli, xss, ssrf, ssti, xxe, idor, nosql, jwt,
  deserialization, command-injection, lfi-path-traversal, csrf, cors, crlf, graphql, api,
  auth-bypass, session, race-conditions, prototype-pollution, open-redirect, host-header,
  smuggling, web-cache, oauth-saml, mfa-bypass, crypto, ldap, xpath, webauthn-passkey,
  file-upload, imds-cloud-metadata, llm-prompt-injection, modbus, cicd.
- **Exploitation / privesc / chains -> `wiki/cheatsheets/*`**: privesc-exploit-arsenal,
  cve-arsenal, attack-chains, linux-privesc / windows-privesc, default-credentials,
  nuclei-arsenal, sqlmap, password-attacks.

Read the matching page(s) BEFORE hand-rolling a payload/exploit. The full class-specific
methodology lives in the matching `hunt-*` skill - hand off to it.
