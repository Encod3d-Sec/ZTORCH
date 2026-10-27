---
title: Pooled lane archetype
type: workflow-reference
tags: [workflow, lane, archetype, pooling]
date_created: "2026-10-27"
---

# Pooled lane (D21 consumer, D26)

One lane, one vuln class, N distinct hosts. Use when `offensive.py next`
prints a `POOL:` line (open rows share a class across 2+ distinct assets).
Same-asset rows NEVER pool - that is depth, not duplication; give them a
dedicated lane.

## Brief shape

- Hosts: the POOL line's asset list, each with its `## Anchors` row checked
  (ONE md5 request per host; mismatch/stale = re-probe that host only).
- Per-host request cap stated per host (bb profile: low rate + jitter;
  the pooled budget is the SUM of per-host caps, not a shared pool to burn
  on one host).
- DROP any probe row whose class `platform-patterns.md` refutes
  platform-wide, unless the brief states the host's delta.
- Run `python3 scripts/terminal_hosts.py <ENG>` first; listed hosts are
  excluded, not probed.
- Rules carried verbatim: full-read mandate (`cat` each file in full,
  zg/grep only to locate) and Obsidian-safe rule (any `<token>` written
  into a `.md` wrapped in inline backticks).

## Envelope shape (per host, not per lane)

```
Scope: <host> <class> (pooled lane <LANE_ID>)
Result: <verdict for THIS host> (clean | confirmed | blocked-edge | sealed)
Key files: <captures this host>
```

Close with ONE class-level line: all hosts agree = platform-pattern
candidate row (append to `platform-patterns.md` with cap citations); any
host deviates = the class is NOT platform-uniform, name the delta host.

## Escalation

A host showing signal (not clean/blocked) breaks out of the pool: record
its per-host envelope lines, then the brain dispatches a dedicated lane for
that host. The pool never depth-probes a signaling host - pooling is for
closing uniform classes cheap, not for exploiting the exception.

## Stop

Pool closes when every host has a per-host verdict line. A host that hit
its per-host cap without a verdict is reported `cap-reached` (revisitable),
never silently dropped.
