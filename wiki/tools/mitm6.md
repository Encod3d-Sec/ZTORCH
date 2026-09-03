---
title: "mitm6"
type: tool
tags: [active-directory, ipv6, relay, mitm, windows, network]
date_created: 2026-09-03
date_updated: 2026-09-03
sources: []
phase: exploit
---

## Purpose

**mitm6** exploits Windows' default IPv6 preference: on a network with no real IPv6 infrastructure,
Windows hosts still send DHCPv6 solicitations. mitm6 answers them, becomes the hosts' default IPv6
DNS server, and captures WPAD/DNS queries it can point at an attacker-controlled endpoint -- pairs
with [[impacket]]'s `ntlmrelayx` to relay the resulting NTLM authentication (often straight to LDAP/S
for a machine-account or DC-relay-based domain compromise, e.g. the `ldaps://` relay-to-DA chain).

## Install / setup

```bash
apt install mitm6      # or: pip3 install mitm6
```

## Core usage

```bash
mitm6 -d domain.local                                    # answer DHCPv6 for the whole domain
mitm6 -i eth0 -d domain.local --ignore-nofqdn             # bind a specific interface
```

## Common use cases

```bash
# Terminal 1: relay WPAD/DNS-poisoned NTLM auth to LDAPS (add a computer / delegate rights)
impacket-ntlmrelayx -6 -t ldaps://<dc> -wh fakewpad.domain.local --delegate-access

# Terminal 2: start the poison
mitm6 -d domain.local
```

## Tips and gotchas

- Needs to run on the same broadcast domain as the targets (no IPv6 routing needed, just local
  DHCPv6 solicitation traffic).
- Noisy and disruptive by design (it becomes hosts' DNS server) -- confirm RoE allows active
  MITM/relay before running; not for `passive_only` engagements.
- `--relay <domain>` restricts poisoning to hosts of that DNS suffix, reducing blast radius on a
  mixed network.
- The relay target (`-t`) is what turns this into a finding: LDAPS relay to add a computer /
  shadow credentials is the highest-value chain. See [[ad-lateral-movement]], [[kerberos-attacks]].

## Related techniques

[[impacket]], [[ad-lateral-movement]], [[active-directory]], [[netexec]]

## Sources

Vault-resident; mitm6/Fox-IT project docs.
