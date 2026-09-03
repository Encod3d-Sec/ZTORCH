---
title: "waybackurls"
type: tool
tags: [recon, urls, osint, bug-bounty, attack-surface]
date_created: 2026-09-03
date_updated: 2026-09-03
sources: []
phase: recon
---

## Purpose

**waybackurls** (tomnomnom) pulls every URL the Wayback Machine has archived for a domain: a fast,
single-source complement to [[gau]] when you just need Wayback coverage without the extra Common
Crawl/OTX/URLScan sources gau also queries.

## Install / setup

```bash
go install github.com/tomnomnom/waybackurls@latest
```

## Core usage

```bash
waybackurls target.com                                  # all archived URLs
echo target.com | waybackurls > urls.txt
cat subdomains.txt | waybackurls                         # feed a subdomain list
```

## Common use cases

```bash
waybackurls target.com | grep -E '\.js(\?|$)' | sort -u   # historical JS bundles
waybackurls target.com | grep -Ei '\?(id|url|file|redirect)='  # param-bearing leads
waybackurls target.com | httpx -silent -mc 200             # which old URLs still live
```

## Tips and gotchas

- Single-source (Wayback only); run [[gau]] alongside for Common Crawl/OTX/URLScan coverage.
- No built-in dedup or filtering; pipe through `sort -u` and [[wiki/tools/httpx]].
- Old archived JS frequently leaks endpoints/keys (see [[javascript-source-map-exploitation]]).

## Related techniques

[[gau]], [[katana]], [[wiki/tools/httpx]], [[web-attack-surface]]

## Sources

Vault-resident; waybackurls project docs.
