---
title: "wigolo"
type: tool
tags: [osint, recon, mcp, research]
date_created: 2026-09-10
date_updated: 2026-09-10
sources: [wigolo-repo]
phase: recon
---

# wigolo

Local-first web-intelligence MCP server (Node >= 20, keyless, everything cached under
`~/.wigolo/`). One surface for search / fetch / crawl / extract / cache / find-similar /
research / autonomous gather / page-diff / watch. No API keys, no cloud; `research` and
`agent` synthesis want an LLM provider (`WIGOLO_LLM_PROVIDER=ollama` stays fully local)
but hand back a structured brief + evidence without one.

## Core usage

```sh
npx wigolo search "vendor product unauthenticated advisory" --json
```

## Purpose

Replace metered WebSearch/WebFetch round-trips during OSINT and vuln research, and keep
every fetched page in a local, queryable knowledge store (grep the whole engagement's web
history later without re-fetching).

## Install / setup

```sh
npx wigolo init          # local engine: browser engine + on-device models (~1.5 GB), health report
npx wigolo doctor        # component health check anytime
```

MCP registration (stdio): `{"command": "npx", "args": ["-y", "wigolo"]}`.

## Tools

| tool | use |
|---|---|
| `search` | 18-engine fused web search, per-result score + verbatim excerpt + citation ID; query ARRAY for parallel breadth; domain/time filters |
| `fetch` | one URL via tiered router (plain HTTP -> headless browser on anti-bot/SPA); clean markdown + metadata; PDFs, CSS `section`, click/type/scroll/screenshot actions |
| `crawl` | BFS/DFS/sitemap/map-only crawl, per-domain rate limit, robots.txt respected |
| `extract` | structured pull: tables, JSON-LD, metadata, named schemas, or any custom JSON Schema |
| `cache` | keyword + hybrid semantic search over everything already seen; stats, clear, change detection |
| `find_similar` | pages similar to a URL or concept (keyword + semantic + live-web fusion) |
| `research` | decompose question -> parallel sub-queries -> cited synthesis (or keyless brief for the host LLM to write from) |
| `agent` | autonomous plan -> search -> fetch -> extract loop with time budget + output schema |
| `diff` / `watch` | what changed on a page since last visit; lazy re-check jobs + SSRF-guarded webhook |

Every tool also runs CLI-side: `wigolo search "..." --json`, `wigolo shell` (NDJSON pipe), REST, SDK.

## Pentest use cases

- **OSINT rows (osint-subdomain / osint-leaks):** `search` with domain scope + time range
  beats manual dorking; `crawl` map-only mode enumerates a vendor's doc/blog surface.
- **Vuln research:** `research` keyless brief = decomposed sub-queries + cited evidence,
  exactly the input the recon workflow (`Skill(wiki-recon)`) wants before a CVE is trusted.
- **Target changelog / login-page monitoring (bug bounty):** `watch` a page, `diff` on
  check; webhook delivery for a deployed panel. Detects new JS bundles / version bumps.
- **Evidence store:** every fetched page lands in `cache`; re-query the whole research
  history semantically at writeup time without re-fetching (full-fidelity, local).
- **JS-heavy recon reads:** `fetch`'s browser escalation reads SPA shells plain curl cannot.

## Tips and gotchas

- No internal LLM: outputs are structured evidence; the calling model writes the final
  answer from `search format=highlights` citations / `research` brief fields.
- Public targets only: it fetches what a browser can see; authed client portals do not
  belong in a local cache (client-data boundary still applies to what you point it at).
- `--no-warmup` defers the 1.5 GB component download to first use (a failed download
  never fails init; doctor reports the fix).
- Uninstall cleanly: `npx wigolo config --uninstall --yes`.

## Related techniques

- [[osint-moc]] - dorking and leak-hunting hub it accelerates
- [[secret-hunting]] - secret patterns to grep the cached pages for
