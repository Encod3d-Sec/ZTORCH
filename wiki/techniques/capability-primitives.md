---
title: "Capability primitives"
type: technique
sources: [cyberstrikeai]
date_created: 2026-10-04
tags: [technique, primitives, post-exploitation]
---

# Capability primitives

RCE is not the goal; capabilities are. Treat every shell as six satisfiable equations -
hunt for the cheapest input that satisfies one, not for a CVE:

| Primitive | Equation |
|---|---|
| file read | attacker input -> file content in output |
| file write | attacker input -> file on disk (path controlled) |
| code exec | attacker input -> process spawn |
| outbound net | attacker input -> attacker-controlled listener |
| auth as victim | attacker input -> victim session/token |
| auth as admin | attacker input -> admin session/token |

## Low severity to primitive map

A "low" finding that satisfies an equation is a foothold, not a low:

| Low finding | Primitive it satisfies |
|---|---|
| path traversal (read) | file read |
| arbitrary file upload | file write (webshell -> code exec) |
| SSRF (internal fetch) | outbound net (to internal services) |
| open redirect + token in URL | auth as victim (OAuth code interception) |
| verbose error with file paths | file read (info disclosure -> targeted write) |

## Features are primitives

Any feature that lets a user influence execution or storage is a primitive wearing a
feature badge: task schedulers (delayed code exec), plugin/extension editors (code
exec), SQL consoles (file read/write via `LOAD_FILE`/`COPY ... TO PROGRAM` on misconfig),
report builders (file write), import/export endpoints (file read + write), webhook
URLs (outbound net). Enumerate them BEFORE hunting CVEs - they are authorized by design.

## Usage

When a shell or injection lands, list which equations the current primitive satisfies
and which one the next escalation step needs; pick the move that closes the gap with
the least new machinery. Record the satisfied set in state.md `## Facts`
(`exploit/<name>` keys).
