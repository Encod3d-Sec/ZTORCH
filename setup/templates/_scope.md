---
title: "Scope - {{ENGAGEMENT}}"
type: engagement-scope
tags: [engagement, scope, roe]
date_created: "{{DATE}}"
date_updated: "{{DATE}}"
# Rules-of-engagement flags (true = forbidden). Drive what next-move/hunt suggest.
no_bruteforce: false
no_dos: false
passive_only: false
# tunnel_safe (true = scanners exhaust the pivot's conntrack and kill the tunnel):
# AFFIRMS curl+nc as the intended tooling (surfaced as a SessionStart note). Not forbidding.
tunnel_safe: false
# Campaign-driver envelope (required by offensive.py init). Defaults are the full-offense
# posture (operator directive 2026-10-05); TIGHTEN for a real client pentest
# (autonomy, write_policy, scanners, rate_per_host) before testing.
# autonomy envelope (CAI-style; the driver surfaces the level on `next`, advisory only):
#   L0 passive-only - read-only recon, OOB registered but no payload delivery
#   L1 active non-destructive - scans/probing/fuzz within rate limits
#   L2 exploit attempts allowed
#   L3 full - chained ops, anything short of forbidden RoE classes (default; missing field = L3)
autonomy: L3
# hunt mode (engage skill sec 3): quick | standard | deep. deep is the DEFAULT posture:
# full-read source passes, per-route probing with negative controls, chained impact
# escalation, second-order re-tests; long autonomous phases - stop only on a documented
# stop condition or an operator decision, not minutes in.
mode: deep
enum_cap: 50
write_policy: full
oob_allowed: true
scanners: yes
budget_requests: 100000
rate_per_host: 50
target_severity: ""
# Body section guidance (## headings below):
#   In scope             - hosts / domains / CIDRs you are authorised to test, one per line.
#   Out of scope          - explicit exclusions; matched against state entities and suppressed.
#   Allowed tooling        - what you may run; note bans e.g. no automated scanners, no exploit, passive-only.
#   Rules of engagement    - hours, rate limits, notification, contract constraints.
sources: []
---

# Scope - {{ENGAGEMENT}}

Authoritative bounds for this engagement. **Read before any action.** next-move and hunt skills respect this; out-of-scope targets and forbidden techniques are not suggested. Client data, stays under `targets/`.

## In scope
-

## Out of scope
-

## Allowed tooling
-

## Rules of engagement
-
