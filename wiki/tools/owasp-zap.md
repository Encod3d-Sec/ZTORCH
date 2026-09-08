---
title: "OWASP ZAP"
type: tool
tags: [proxy, scanner, fuzzer, tool, web, zap]
date_created: 2026-09-08
date_updated: 2026-09-08
phase: enumerate
---

## OWASP ZAP: proxy, spider, fuzzer, scanner

Free/open-source web proxy, no paid-only features. Default listener `127.0.0.1:8080` (change: `Tools > Options > Network > Local Servers/Proxies`). Browser side: FoxyProxy to `127.0.0.1:8080` plus ZAP's CA cert (Options > Network > SSL, dynamic root CA export), or the HUD in a browser. ZAP auto URL-encodes request data in the background before sending.

### Spider (site tree)

Right-click a request > `Attack > Spider` (or the HUD button); first spider prompts to add the target to scope. **Ajax Spider** additionally fires links reached only via JavaScript/AJAX after page load; run it after the normal Spider to pick up extra endpoints (slower). Results land in the Sites tree.

### Passive and active scanning

The passive scanner runs automatically on every response the Spider/proxy sees (missing headers, DOM XSS hints) and populates Alerts as you browse; no separate launch needed. `Active Scan` (HUD button or right-click) attacks every page in the site tree with payload sets; if no Spider ran yet, ZAP spiders first automatically. Per-alert detail shows the attack string, evidence, and the request/response pair; replay from there in the Request Editor. Report: `Report > Generate HTML Report` (also XML/Markdown).

### ZAP Fuzzer (the free Intruder)

Right-click a request > `Attack > Fuzz`, select the text to fuzz, `Add` to mark the location, then configure:

- **Payloads**: `File` (your wordlist), `File Fuzzers` (built-in wordlist databases, e.g. dirbuster lists; more via Marketplace add-ons), `Numberzz` (numeric sequences).
- **Processors**: per-item transforms, chained: Base64 encode/decode, MD5/SHA-1/256/512, URL encode/decode, Prefix/Postfix String, custom `Script`. Use `Generate Preview` to see the final payload before launching.
- **Options**: `Concurrent Scanning Threads` (raise to ~20 for speed, lower for fragile boxes), follow-redirects toggle, and **depth-first vs breadth-first** ordering: depth-first exhausts the wordlist on one position before moving on (all passwords for one user, then the next user), breadth-first tries one item against all positions first (one password against all users before the next; lockout-friendlier). Burp Intruder has no equivalent ordering control.

Sort results by response code (200 hits), `Size Resp. Body` (a different page), or RTT (time-based SQLi signal).

### Marketplace add-ons

`Manage Add-ons > Marketplace`: Release/Beta/Alpha status shown. **FuzzDB Files** + **FuzzDB Offensive** add attack wordlists to the fuzzer, e.g. `fuzzdb > attack > os-cmd-execution` (`command_execution-unix.txt`) for command-injection sweeps, handy against WAF-fronted apps.

### Encoder/Decoder/Hash

`CTRL+E`: encode/decode/hash any text (URL, HTML, Base64, hex, hashes) while testing.

No request throttling anywhere (unlike Burp Community Intruder's ~1 req/s), so ZAP Fuzzer is the GUI fallback when speed matters and Burp is the Community edition.

<!-- promoted-slug: owasp-zap-proxy-basics -->
