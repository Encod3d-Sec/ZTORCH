---
name: hunt-core
description: >
  Shared discipline for every hunt-* skill: scope and authorization gating, the two-account rule,
  the confirmation gate that separates a real finding from a false positive, enumeration limits,
  stop conditions, marker discipline, wiki-first query and self-heal, FIND output, Deadends, and
  wiki distillation. ALWAYS LOADED alongside any hunt skill. Also trigger directly on "is this in
  scope", "is this a real bug", "how do I confirm this", "should I keep going", "how many IDs
  should I test", "what severity", "how do I report this", "I got someone else's data". Every
  hunt-* skill assumes this file; without it they run without their safety and quality layer.
---

# Hunt: Core

The discipline every `hunt-*` skill assumes. Class-specific technique lives in the hunt skills and
the wiki; this file holds what is true regardless of which bug class you are chasing.

**Owned here, never repeated in a hunt skill:** the scope gate, two-account setup, confirmation
gate, enumeration limits, stop conditions, marker discipline, wiki query/self-heal protocol, FIND
output, Deadends, and distillation. A hunt skill that restates any of these will drift from this
one; reference it instead.

## Scope gate

Hunting means reading other people's data, escalating privileges, and creating accounts. Outside
an authorized engagement all of it is a crime. Before any request leaves the machine:

1. **Authorization** - a program with the target in scope, a signed agreement, your own lab, or a
   CTF. "Probably fine" is not authorization.
2. **Scope** - exact hosts. `*.target.com` does not cover `targetapp.io`, an acquisition, or
   `target.com.cdn.net`. Read `targets/<eng>/scope.md`.
3. **Exclusions and forbidden techniques** - check `no_bruteforce`, scanning caps, DoS, social
   engineering, and any per-program rule before the technique that would violate it.
4. **Two accounts, both yours** - see below. Required for any authorization-class bug.
5. **Deadends** - read `targets/<eng>/Deadends.md` and skip what is already exhausted.

Unconfirmed on any of these: ask. Do not infer scope from the fact that a host resolved. Discovery
is not authorization. The `scope-guard` hook enforces the host check on Bash commands; it is a
backstop, not the gate.

## Two-account rule

Authorization findings are "account A reached account B's object." Without B you have two bad
options: test against a real user, or report a guess. Both are worse than not reporting.

- **User A** - resource owner. **User B** - attacker. Separate browser profiles so cookies never
  cross.
- Record both internal IDs in `targets/<eng>/identities.md` as you discover them.
- Cross-tenant work needs two *tenants*, not two users in one. Many apps isolate tenants correctly
  and users not at all.

## Confirmation gate

Nothing becomes a FIND on the strength of a response body. The gate is per class; the hunt skill
owns the specific "NOT confirmation / IS confirmation" list. Universal rules:

1. **Re-verify in a clean session.** Fresh token, new profile, no cached state. If the effect
   vanishes, you changed your own screen.
2. **Exercise the capability.** Not "the server accepted it" but perform the action only the new
   state permits.
3. **Rule out legitimate access.** Before claiming cross-account access, confirm A is not
   *supposed* to see it: shared teams, sharing links, public objects, org-wide visibility. The
   most common false positive in authorization testing.
4. **Blind classes need an OOB HIT.** No inference-only findings. The `oob.md` row must flip to
   HIT before a FIND is scaffolded.
5. **Reproduce from scratch** against your own written steps.
6. **A negative result needs a proven-observable channel.** "No callback / no hits" only means
   something if the channel itself is proven to work: a listener that file-logs AND you have
   actually read, or a self-test hit on the same path. An unobservable channel (a tmux pane that
   captures empty, a log you never opened) produces false negatives that fossilize into dead-ends
   and "it was patched" verdicts.

Failed 1-3 is a Deadend, not a "probably real but hard to prove."

[[wiki/techniques/methodology/safe-probing-and-controls]] carries the other half of this gate: how to probe destructive or
sensitive surface without touching a real record (use an identifier proven not to exist), and how
to fire a control so a NEGATIVE result means something instead of being assumed.

When the hunt spans many hosts, sessions, or parallel agents, the coordination layer adds failure
modes this gate does not cover: claims nobody re-checked, requests nobody counted, the same finding
filed twice, and severity drifting upward as work is summarised. See
[[wiki/techniques/methodology/multi-agent-campaign-orchestration]].

## Enumeration limits

**Prove the boundary is missing, not how much is behind it.**

The server does not check *any* object. Demonstrating that takes two or three identifiers. A
thousand-ID sweep does not raise severity; it collects real users' data and converts a critical
finding into an incident report naming you.

- **Default: 5 identifiers.** Enough to show a sequential pattern and a missing check.
- **Ceiling without explicit operator approval: 20.**
- **Beyond that, and for any range sweep: stop and ask.** State why the extra volume changes the
  finding. Usually it does not.
- **`no_bruteforce` in scope means range 0.** No sweep, no ffuf over an ID list, no exception.
- **Never enumerate writes.** Read at volume is a rate problem; write at volume is destruction.

For scale evidence, cite a `total` field, a pagination header, or a result count. "The response
reports 41,180 records; none beyond my two test accounts were retrieved" proves scale without
retrieving anything.

**Scope of these limits.** They govern OBJECT and RECORD enumeration (guessing identifiers to pull
other users' data). They do NOT cap legitimate service discovery: an SSRF internal port sweep or a
network map is bounded by the engagement RoE (`no_dos`, scan-rate caps), not by the 5-to-20 object
ceiling. Thread it and honor the cap; do not clamp a port sweep to 20.

## Stop conditions

Stop and report rather than continuing when:

- **You received real user data.** An ID you guessed belonged to someone real, a cache served
  another session, a beacon fired in a live employee context. Do not re-request to confirm, do not
  save it, do not use anything in it. Report immediately, state what you received and that you
  destroyed it, and note it in the FIND rather than hiding it.
- **The next step is destructive or persistent** - deleting objects, modifying another tenant's
  config, planting content that outlives the session.
- **You have a traffic-affecting primitive** - desync, cache poisoning, connection-pool effects.
  The mechanism is the finding.
- **The last step needs volume** beyond the limits above.
- **You already have the severity ceiling.** More escalation, more risk, no more payout.
- **You left scope.** Even one hop. Especially one hop.

Stopping is not failure. "Confirmed and did not exploit" is worth more than a forfeited payout.

## Published chains: exact-first

When a writeup / published chain exists for the box or the vuln class, fire its EXACT form first:
same payload, same framing, same delivery channel (chat UI vs raw API, browser vs curl). An
adaptation is a one-variable experiment that needs a known-good baseline; adapt before the baseline
exists and every failure is unattributable (payload? delivery? box version?). Transcribe EVERY
writeup artifact, not just prose (screenshots carry source-IP / UA / Origin ground truth about
where execution happens), and re-test a published chain verbatim on each new instance before
believing it was patched. Method: [[wiki/techniques/methodology/writeup-reproduction]].

**Wrong-vector tells (switch the vector, do not tune the tooling).** A vector is exhausted the
moment it starts fighting you; grinding harder is the sunk-cost trap. Two mechanical signals mean the
current vector is the wrong door, not that your tooling needs another pass:

- **The target starves under your own exploit loop** (repeated `000` / connection-timeout /
  empty-reply while you hammer one endpoint). A vector that DoSes a lab box is almost never the
  intended one. Stop, let it drain, and enumerate a DIFFERENT class (source-read: LFI /
  alias-traversal / `.git` / backup; a second service or vhost's own app; OOB creds) before returning.
- **Two verified hashes in a row fail the primary wordlist.** The passwords are not wordlist
  material - they are delivered out-of-band (an email/note/KeePass, a config, a second service). Stop
  cracking and re-enumerate for where the creds are HANDED OUT; do not extract a third hash. (Engineering
  around a hostile channel - per-char verify-fix, min-of-2 sampling, gentler pacing - is the tell you
  are on the wrong vector, not a reason to keep going.)

When a wrong-vector tell fires and the next door is not obvious, **call `Skill(redteamlead)`** before
grinding further - it reads the engagement state + evidence + wiki and returns ranked directions with
an explicit STOP. That is exactly what it is for ("I'm stuck / which vector / should I keep hammering
this"); one RTL call at the first sign a vector is fighting back beats hours of sunk-cost grind.

## Marker discipline

Any class where you inject a value and look for it later (xss, ssti, sqli error strings, crlf, log
injection, open redirect): use a unique 8+ char alphanumeric canary (e.g. `x4hd2k9pq`), never
`test`/`marker`/`evil`/`payload`. Check the baseline response for the canary BEFORE claiming
reflection; a value already present is not proof you put it there.

## Wiki lookup (reference-map first, qmd on a hint)

`qmd_query` is powerful but ~15-30s per call, so it is a TARGETED deepen, not a pre-attack ritual.
Three tiers, in order:

1. **Reference map FIRST (instant `Read`).** Your hunt skill's `## Wiki` section names the class's
   domain MOC + primary page + a few anchors. `Read` those directly, and one-hop from the MOC for a
   sibling technique. This answers the anticipated case with zero qmd latency.
2. **`qmd_query` ONLY on a concrete hint the map does not cover** - a specific sink/function (an
   SSRF-reaching `requests.get(user_input)`), an observed escape (a `<script>` context that could be
   XSS), a fingerprinted version/CVE, or a service the MOC does not list:
   `qmd_query "<the specific thing>" via wiki-search MCP`. It auto-surfaces pages added since the
   skill was written. Do NOT blanket-qmd every action (too slow); do NOT hand-roll from memory when a
   targeted qmd would answer (that is the opposite failure). Fire it when you have the hint, then act.
3. **Self-heal** only if neither the map nor a targeted qmd has it: stub
   `wiki/techniques/<area>/<slug>.md` (frontmatter + `## Observed during <engagement>`) so the gap fills.

Payload arsenals live in `wiki/payloads/`. If the MCP is down, `bash scripts/wiki-query.sh "<terms>"`
wraps the same qmd index (`-k` for an exact CVE/string).

## Hunt approaches (which skill for the signal)

`hunt-core` is the hub: route from the observed signal to the class skill, load it, then use that
skill's `## Wiki` map. The `recon-capture` fingerprint router auto-suggests many of these from tool
output; this table is the manual reference when it does not fire or you are reasoning about approach.

| Signal / surface | Skill |
|---|---|
| reflected/stored input, `<script>` / `onerror` / `javascript:` / a DOM sink | `Skill(hunt-xss)` |
| a param/body reaching a DB; an error / boolean / time oracle | `Skill(hunt-sqli)` |
| a URL/host param, a fetch/preview/import sink, `?url=` | `Skill(hunt-ssrf)` |
| an object id, `/users/{id}`, two-account cross-access | `Skill(hunt-idor)` |
| template `{{ }}` render, XXE (SVG/DOCX/SAML), GraphQL | `Skill(hunt-injection)` |
| a command sink, template-injection-to-exec, a version+CVE | `Skill(hunt-rce)` |
| a serialized blob (`rO0` / `AAEAAAD` / `O:`), viewstate, a signed cookie | `Skill(hunt-deserialization)` |
| login / reset / session / JWT, a legacy-protocol endpoint | `Skill(hunt-auth)` |
| OAuth / SAML redirect_uri or assertion | `Skill(hunt-federation)` |
| file upload / avatar / document import | `Skill(hunt-upload)` |
| REST/GraphQL/gRPC, BOLA / BFLA / mass-assignment | `Skill(hunt-api)` |
| checkout / price / coupon / workflow logic, a race | `Skill(hunt-bizlogic)` |
| CL.TE / TE.CL / HTTP-2 downgrade desync | `Skill(hunt-smuggling)` |
| an unkeyed header/param reaching a cache | `Skill(hunt-cache)` |
| exposed `.git` / `.env` / keys, secrets in a JS bundle | `Skill(hunt-secrets)` |
| LLM prompt-injection / excessive agency | `Skill(hunt-llm)` |
| MCP tool-poisoning / indirect injection | `Skill(hunt-mcp)` |
| AD: kerberoast / AS-REP / ADCS / DCSync / delegation (dotted-FQDN domain / a DC) | `Skill(hunt-ad)` |
| Windows LOCAL privesc: service misconfig / autologon reg / SeImpersonate-Potato / scheduled-task / DLL hijack (standalone/workgroup box, or a local shell on a member) | `Skill(hunt-windows)` |
| AWS/Azure/GCP metadata or IAM | `Skill(hunt-cloud)` |
| Microsoft 365 / Entra tenant | `Skill(hunt-m365)` |
| CI/CD pipeline (Actions / runners / OIDC) | `Skill(hunt-cicd)` |
| macOS TCC / SIP / keychain / XPC | `Skill(hunt-macos)` |
| SSL-VPN appliance (Fortinet/Citrix/Ivanti/Cisco/PAN) | `Skill(hunt-vpn)` |
| Modbus / S7 / EtherNet-IP / PLC / HMI | `Skill(hunt-ics)` |

Process skills (not vuln classes): `Skill(ctf-box)` boot-to-root, `Skill(wiki-recon)` external recon,
`Skill(wiki-arsenal)` tool+payload lookup, `Skill(triage)` -> `Skill(evidence)`
finding validation, `Skill(hunt-burp)` drive Burp. Coverage gaps and move ranking come from the
driver itself (`scripts/offensive.py coverage` / `offensive.py next`).

## Routing table (machine-readable)

The prose table above is for a human reasoning about approach; this table is the parse contract
`offensive.py index` reads (fixed columns, one row per hunt class plus one row per tech-fingerprint
token). Seeded from the 24 `hunt-*` classes above and the fingerprint keys in ClaudeBrain's
`scripts/playbook.json` that route to a hunt skill (kernel-CVE/metasploit-only fingerprints are out
of scope here - they carry no hunt skill). `primary wiki` and `arsenal slug` come from each class's
own `## Wiki` block. Extend this table, not `playbook.json`, when a driver-side signal is added.

| fingerprint | class | hunt-skill | primary wiki | arsenal slug |
|---|---|---|---|---|
| ad | ad | hunt-ad | active-directory | netexec |
| api | api | hunt-api | api-security | payloads/api |
| auth | auth | hunt-auth | authentication-attacks | payloads/auth-bypass |
| bizlogic | bizlogic | hunt-bizlogic | business-logic | race-conditions |
| cache | cache | hunt-cache | web-cache-poisoning | payloads/web-cache |
| cicd | cicd | hunt-cicd | cicd-github-actions | payloads/cicd |
| cloud | cloud | hunt-cloud | cloud-iam-attacks | payloads/imds-cloud-metadata |
| deserialization | deserialization | hunt-deserialization | insecure-deserialization | payloads/deserialization |
| federation | federation | hunt-federation | oauth-attacks | payloads/oauth-saml |
| ics | ics | hunt-ics | ics-scada-modbus | payloads/modbus |
| idor | idor | hunt-idor | access-control | payloads/idor |
| injection | injection | hunt-injection | ssti | payloads/ssti |
| llm | llm | hunt-llm | llm-attacks | payloads/llm-prompt-injection |
| m365 | m365 | hunt-m365 | azure-ad-enumerate | azure-ad-conditional-access-policy |
| macos | macos | hunt-macos | macos-tcc | payloads/macos-app-injection |
| mcp | mcp | hunt-mcp | mcp-server-attacks | payloads/llm-prompt-injection |
| rce | rce | hunt-rce | os-command-injection | payloads/command-injection |
| secrets | secrets | hunt-secrets | secret-hunting | recon-dorks |
| smuggling | smuggling | hunt-smuggling | http-request-smuggling | payloads/smuggling |
| sqli | sqli | hunt-sqli | sql-injection | payloads/sqli |
| ssrf | ssrf | hunt-ssrf | ssrf | payloads/ssrf |
| upload | upload | hunt-upload | file-upload | payloads/file-upload |
| vpn | vpn | hunt-vpn | network-service-attacks | cheatsheets/cve-arsenal |
| windows | windows | hunt-windows | windows-privesc | privesc-exploit-arsenal |
| xss | xss | hunt-xss | xss | payloads/xss |
| dom-xss | xss | hunt-xss | xss | payloads/xss |
| graphql | injection | hunt-injection | ssti | payloads/graphql |
| minio | secrets | hunt-secrets | secret-hunting | default-credentials |
| login-form | sqli | hunt-sqli | sql-injection | payloads/sqli |
| sqlstate | sqli | hunt-sqli | sql-injection | payloads/sqli |
| ssti | injection | hunt-injection | ssti | payloads/ssti |
| xxe | injection | hunt-injection | ssti | payloads/xxe |
| lfi | rce | hunt-rce | os-command-injection | payloads/lfi-path-traversal |
| phpipam | sqli | hunt-sqli | sql-injection | payloads/sqli |
| spring | injection | hunt-injection | ssti | api-request-findings |
| supabase | auth | hunt-auth | authentication-attacks | supabase-attacks |
| wordpress | rce | hunt-rce | os-command-injection | cms-exploitation |
| laravel | rce | hunt-rce | os-command-injection | payloads/deserialization |
| nextjs | auth | hunt-auth | authentication-attacks | nextjs-middleware-bypass |
| firebase | idor | hunt-idor | access-control | payloads/idor |
| magento | rce | hunt-rce | os-command-injection | cms-exploitation |
| jenkins | rce | hunt-rce | os-command-injection | default-credentials |
| tomcat | rce | hunt-rce | os-command-injection | attack-chains |
| aria2 | rce | hunt-rce | os-command-injection | attack-chains |
| gitlab | rce | hunt-rce | os-command-injection | cve-arsenal |
| elasticsearch | injection | hunt-injection | ssti | api-request-findings |
| influxdb | injection | hunt-injection | ssti | api-request-findings |
| redis | rce | hunt-rce | os-command-injection | attack-chains |
| mssql | sqli | hunt-sqli | sql-injection | mssql-command-execution |
| jwt | auth | hunt-auth | authentication-attacks | payloads/jwt |
| oauth | federation | hunt-federation | oauth-attacks | payloads/oauth-saml |
| s3 | cloud | hunt-cloud | cloud-iam-attacks | aws-service-s3-buckets |
| m365-tenant | m365 | hunt-m365 | azure-ad-enumerate | identity-fabric |
| azure-imds | cloud | hunt-cloud | cloud-iam-attacks | azure-managed-identity-abuse |
| vpn-appliance | vpn | hunt-vpn | network-service-attacks | cheatsheets/cve-arsenal |
| kubernetes | ssrf | hunt-ssrf | ssrf | kubernetes-attacks |
| docker | rce | hunt-rce | os-command-injection | docker-attacks |
| api-docs | api | hunt-api | api-security | api-testing |
| ldap | ad | hunt-ad | active-directory | ad-enumeration |
| winrm | windows | hunt-windows | windows-privesc | windows-using-credentials |
| rdp | windows | hunt-windows | windows-privesc | rdp-persistence |
| smb | windows | hunt-windows | windows-privesc | internal-shares |
| ad-domain | ad | hunt-ad | active-directory | ad-enumeration |
| windows-version | windows | hunt-windows | windows-privesc | windows-enumeration |
| cache-headers | cache | hunt-cache | web-cache-poisoning | payloads/web-cache |
| nosql | injection | hunt-injection | ssti | payloads/nosql |
| confluence | rce | hunt-rce | os-command-injection | cve-arsenal |
| drupal | rce | hunt-rce | os-command-injection | cms-exploitation |
| joomla | rce | hunt-rce | os-command-injection | cms-exploitation |
| grafana | idor | hunt-idor | access-control | default-credentials |
| phpmyadmin | rce | hunt-rce | os-command-injection | default-credentials |
| weblogic | deserialization | hunt-deserialization | insecure-deserialization | payloads/deserialization |
| aspnet | deserialization | hunt-deserialization | insecure-deserialization | payloads/deserialization |
| struts | rce | hunt-rce | os-command-injection | payloads/command-injection |
| jira | ssrf | hunt-ssrf | ssrf | api-request-findings |
| github-actions | cicd | hunt-cicd | cicd-github-actions | payloads/cicd |
| grpc | api | hunt-api | api-security | api-testing |
| exchange | rce | hunt-rce | os-command-injection | cve-arsenal |
| ivanti | vpn | hunt-vpn | network-service-attacks | cheatsheets/cve-arsenal |
| moveit | sqli | hunt-sqli | sql-injection | cve-arsenal |
| crushftp | auth | hunt-auth | authentication-attacks | authentication-attacks |
| geoserver | rce | hunt-rce | os-command-injection | cve-arsenal |
| sharepoint | rce | hunt-rce | os-command-injection | cve-arsenal |
| activemq | deserialization | hunt-deserialization | insecure-deserialization | payloads/deserialization |
| coldfusion | deserialization | hunt-deserialization | insecure-deserialization | cve-arsenal |
| php-cgi | rce | hunt-rce | os-command-injection | payloads/command-injection |
| vcenter | rce | hunt-rce | os-command-injection | cve-arsenal |
| screenconnect | auth | hunt-auth | authentication-attacks | cve-arsenal |
| papercut | rce | hunt-rce | os-command-injection | cve-arsenal |
| ofbiz | rce | hunt-rce | os-command-injection | cve-arsenal |
| aws-keys | cloud | hunt-cloud | cloud-iam-attacks | aws-access-token-secrets |
| cognito | cloud | hunt-cloud | cloud-iam-attacks | aws-service-cognito |
| dynamodb | cloud | hunt-cloud | cloud-iam-attacks | aws-service-dynamodb |
| ec2 | cloud | hunt-cloud | cloud-iam-attacks | aws-service-ec2 |
| lambda | cloud | hunt-cloud | cloud-iam-attacks | aws-service-lambda-api-gateway |
| ssm | cloud | hunt-cloud | cloud-iam-attacks | aws-service-ssm |
| azure-devops | cicd | hunt-cicd | cicd-github-actions | cicd-azure-devops |
| buildkite | cicd | hunt-cicd | cicd-github-actions | cicd-buildkite |
| circleci | cicd | hunt-cicd | cicd-github-actions | cicd-circleci |
| drone-ci | cicd | hunt-cicd | cicd-github-actions | cicd-drone-ci |
| gitlab-ci | cicd | hunt-cicd | cicd-github-actions | cicd-gitlab-ci |
| as400 | auth | hunt-auth | authentication-attacks | as400 |
| telnet | auth | hunt-auth | authentication-attacks | telnet |
| liferay | rce | hunt-rce | os-command-injection | cve-arsenal |
| macos-host | macos | hunt-macos | macos-tcc | macos-loot-locations |

## FIND output

On confirmation:

```
Create Vulns/Research/FIND-XXX-SEVERITY-<class>-<host>[-<resource>].md
Add row to Vuln-index.md
```

**Severity is rated on demonstrated impact, not theoretical maximum.** Preconditions lower it
(victim interaction, an unguessable identifier you cannot show leaking, a race you win one time in
twenty). Scale raises it, when you can show the identifier is enumerable without enumerating. State
impact in the program's terms (customer data, account security, financial exposure), not in
vulnerability classes.

On exhaustion:

```
Append to Deadends.md: - [ ] <class> on <host> <param/endpoint> -- <why it failed>
```

The reason matters more than the entry. `403 on cross-account, authorization enforced` stops you
retesting; a bare entry does not.

## Distillation

When a confirmed finding is a reusable technique rather than a target quirk, stage it:

```
python3 scripts/wiki-stage.py --kind technique --slug <slug> --target-page <area>/<page>.md
```

**GENERIC only - no client host, no real identifier, no customer data.** Promote later via
`scripts/wiki-promote.py`. Run `scripts/check-leaks.sh` before any push. Engagement data lives
under `targets/` and is git-ignored.
