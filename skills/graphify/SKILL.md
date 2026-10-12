---
name: graphify
description: >
  Relational queries over link graphs: how pages or code files CONNECT (paths,
  hubs, orphans, neighbors). Wiki layer is scripts/wiki-graph.py (stdlib
  wikilink parser, live read, no LLM, no keys); the graphify CLI covers code
  trees (raw/git clones, scripts/) in structural code-only mode. Which page
  mentions a term is qmd's job. Never run over targets/.
---
state: active
created: 2026-10-12
last_used: 2026-10-12

# Graphify: relation queries (wiki wikilinks + code trees)

One question class, two layers: "how do these nodes connect", not "what does
this node say". Content questions go to qmd (`wiki-search` MCP); relations
come here. Multi-hop exploration composes them: wiki-graph.py first for the
chain, then qmd to read the pages it names.

## Wiki layer: scripts/wiki-graph.py (default)

Zero dependencies; reads `wiki/` live on every run, so there is no index to
build and nothing to rebuild after promote. Resolves `[[target]]`,
`[[target|alias]]`, `[[target#anchor]]` by relative path then unique
basename; code fences are skipped so quoted link syntax adds no edges.

```bash
python3 scripts/wiki-graph.py path "SSRF" "RCE"    # shortest link chain (undirected)
python3 scripts/wiki-graph.py hubs 15              # degree-ranked god-nodes (in/out)
python3 scripts/wiki-graph.py orphans              # zero in-links (isolated flagged)
python3 scripts/wiki-graph.py neighbors "kerberos relay"  # direct links in + out
```

Page arguments accept a relative path, a unique basename, or a unique
substring; ambiguous names list candidates. `orphans` finds unlinked pages
(`scripts/wiki-gaps.py` covers missing pages); `hubs` spots pages that became
dumping grounds; `path` answers multi-hop pivot questions the MOC hubs miss.

## Code layer: graphify CLI (code trees ONLY)

The `graphify` CLI (uv tool `graphifyy`) builds AST-level code graphs:
imports, calls, definitions. It hard-classifies markdown as prose and skips
it in structural mode, so it is useless for `wiki/`; the script above owns
that.

```bash
uv tool install graphifyy                            # once per seat
graphify extract raw/git/<repo> --code-only          # structural, no LLM
graphify update raw/git/<repo>                       # incremental, code-only
graphify query "auth" --graph raw/git/<repo>/graphify-out/graph.json
graphify path moduleA moduleB --graph raw/git/<repo>/graphify-out/graph.json
```

Use it when mapping a cloned codebase: entry points, dead code, who calls
the auth function. Verify flags on the installed build with `graphify --help`
(subcommand `-h` output is unreliable in 0.9.76).

## Rules

- NEVER run `graphify extract` without `--code-only`: the semantic tier
  dispatches every document through the configured LLM provider (metered when
  ANTHROPIC_* is set in the environment). Structural mode only.
- Never point either layer at `targets/`, `session/`, or the vault root:
  client data must not enter a graph or its caches.
- `graphify-out/` dirs are derived state, gitignored.

Source: https://github.com/Graphify-Labs/graphify (Apache-2.0), absorbed
2026-10-05. Wiki layer re-scoped to a local stdlib script 2026-10-05 after
0.9.76 proved unable to build a keyless markdown graph (markdown rides the
LLM tier).
