---
title: "curl"
type: tool
tags: [web, recon, probing, oob]
date_created: 2026-09-10
date_updated: 2026-09-10
sources: []
phase: recon
---

## Purpose

**curl** is the universal HTTP prober: banner grabs, request replay, API poking, and OOB canary delivery. The harness routes `mcp` and `llm` class rows here (manifest and model-endpoint probing are curl-native).

## Core usage

```sh
curl -sS -i https://target/            # status + headers + body, errors visible
curl -sk -X POST https://target/api -H "Content-Type: application/json" -d "{}"
curl -s --max-time 5 http://OOB-SINK/canary   # OOB canary through a suspected sink
```

## Gotchas

- `-s` alone hides real failures; use `-sS` so connect errors surface, and always set `--max-time` on blind probes.
- Burp-visible work does not belong here: load-bearing requests go to Repeater (`Skill(hunt-burp)`); curl is for quick loops and canaries.
- On a tunnel-safe box (conntrack-starved pivot) curl+nc is the sanctioned scanner replacement; see the recon cheatsheet.
