---
title: "VPN appliances (SSL-VPN exploitation)"
type: technique
tags: [technique, vpn, ssl-vpn, fortinet, citrix, ivanti, pre-auth]
---

# VPN appliances (SSL-VPN exploitation)

Fingerprint-first exploitation of SSL-VPN concentrators: Fortinet,
Citrix, Ivanti, Cisco, Palo Alto, F5. Full methodology:
`skills/exploit/hunt/hunt-vpn/SKILL.md` (golden-image, mapper-owned).

## Fingerprint ladder (identify before touching CVEs)

| Vendor | Tell |
|---|---|
| Cisco | `+CSCOE+` paths |
| Fortinet | `SVPNCOOKIE`, `/remote/login` |
| Citrix | `NSC_AAA` cookie |
| PAN | `/global-protect/login.esp` |
| Ivanti | `/dana-na/...` |
| F5 | `BIGipServer` cookie |

Version fingerprint from JS file paths, meta tags, admin/config-surface
build strings. Every CVE candidate must cite the EXACT build string
matched.

## High-value pre-auth classes (verify against the wiki arsenal + live
nuclei templates before firing - LINK-ROT rule)

- Path traversal: Cisco CVE-2020-3452 / CVE-2018-0296 (read with
  `--path-as-is`); Fortinet CVE-2018-13379 (session files).
- Memory leak: Citrix CVE-2023-4966 ("CitrixBleed" - large-response
  flag scan for session-token material; replay validates).
- RCE: Fortinet CVE-2024-21762, Ivanti CVE-2024-21887 /
  CVE-2025-0282-style chains, Citrix CVE-2023-3519, PAN CVE-2024-3400.

## Discipline

- Low-volume probes only (no_dos / no_bruteforce RoE): default-cred
  checks are a short known-list, NEVER a wordlist spray.
- Confirmation = the PRIMITIVE exercised (file read returns credential
  structure; Bleed token replays into a session; creds reach an
  authenticated page) - an ACK'd write with no observed state change is
  reachability, not control.
- Remote-access entry historically routes through these boxes:
  cross-ref Skill(hunt-vpn) -> post-auth internal segment.

Related: [[network-service-attacks]], [[default-credentials]],
[[cve-arsenal]]
