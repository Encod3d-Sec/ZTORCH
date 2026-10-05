---
name: graphify
description: >
  Relational queries over the wiki link graph: paths between techniques, hub
  (god-node) detection, orphans, neighbors. Structural only, local, no LLM.
  Use when the question is how pages CONNECT; which page mentions a term is
  qmd's job. Never run over targets/.
---

# Graphify: wiki relation layer

`graphify` builds and queries a structural link graph over `wiki/` (pages,
headings, wikilinks, frontmatter attributes). It is the relational complement
to qmd: qmd answers "which page is about X", graphify answers "how do X and Y
connect".

## Rules

- Scope is `wiki/` ONLY. Never point graphify at `targets/`, `session/`, or
  the vault root: client data must not enter the graph or any of its caches.
- Structural mode only (`--code-only`): deterministic, local, no LLM, no API
  keys. The semantic LLM pass stays OFF unless the operator explicitly asks;
  if ever run, still `wiki/`-only.
- `graphify-out/` is derived state, gitignored, rebuilt incrementally.

## Build / update

One-time seat install (isolated env):

```bash
uv tool install graphifyy
```

First build, from the vault root:

```bash
graphify extract wiki/ --code-only
```

Incremental rebuild (also runs automatically at promote via
`scripts/wiki-promote.py`):

```bash
graphify update
```

Verify flag spelling on the installed version before relying on any command:

```bash
graphify extract -h
graphify query -h
```

## Queries

```bash
graphify query "kerberos relay"    # free-text entry into the graph
graphify path "SSRF" "RCE"         # multi-hop connection between pages
graphify explain "god-nodes"       # hub report: over-connected pages
```

## When to use

- "What connects A to B": multi-hop pivots between technique pages.
- Hub or orphan detection feeding `scripts/wiki-gaps.py`.
- Cross-community links the hand-maintained MOC hubs miss.

Source: https://github.com/Graphify-Labs/graphify (Apache-2.0), absorbed 2026-10-05.
