---
# CAI-style autonomy envelope; the driver surfaces the level on `next` (advisory only).
#   L0 passive-only - read-only recon, OOB registered but no payload delivery
#   L1 active non-destructive - scans/probing/fuzz within rate limits
#   L2 exploit attempts allowed
#   L3 full - chained ops, anything short of forbidden RoE classes (default; missing = L3)
autonomy: L3
# hunt mode (engage skill sec 3): quick | standard | deep. deep is the DEFAULT posture:
# full-read source passes, per-route probing with negative controls, chained impact
# escalation, second-order re-tests; long autonomous phases - stop only on a documented
# stop condition or an operator decision, not minutes in.
mode: deep
---

# Scope

## In scope
-

## Out of scope
-

## Allowed tooling
-

## Rules of engagement
-
