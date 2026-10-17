---
name: wiki
description: Wiki lookups and edits over the qmd-indexed knowledge base. Use when a task needs a wiki search, a page written or updated, or a re-index after adding pages.
type: cli
metadata:

  hermes:

    tags: [wiki, qmd, search, promote]

    related_skills: [research-ingest, wiki-arsenal]

---

# Wiki Search and Maintenance

qmd is a CLI + MCP server that provides semantic and keyword search over `wiki/`. The MCP server (`wiki-search`) exposes two tools consumed by the seat agent (Hermes) directly. The CLI is used for maintenance (re-index, status).

All paths are relative to the vault root (`$QMD_VAULT`).

---

## Prerequisites

`QMD_VAULT` must point to your vault root (no trailing slash). Export it in your shell profile:

```bash
export QMD_VAULT="/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch"
```

If a new session does not inherit it, prefix commands with `QMD_VAULT=... qmd ...` or source your profile. `qmd` is installed as a bun global (`bun add -g @tobilu/qmd`); it lives at `~/.bun/bin/qmd` - ensure `~/.bun/bin` is on `PATH`. INCIDENT 2026-10-13: a hermes/tools reclaim pass gutted an older qmd install mid-session (emptied bin/ + dist/ under a `.reclaim-*` dir) - if `qmd` dies with MODULE_NOT_FOUND, reinstall: `~/.bun/bin/bun add -g @tobilu/qmd` (the index at ~/.cache/qmd survives reinstalls).

---

## Searching via MCP (preferred in-session path)

When the `wiki-search` MCP is active, prefer these tools over the CLI - they avoid the 3-4 second model load on every invocation:

| Tool | Purpose |
|---|---|
| `mcp__wiki-search__query` | Typed sub-queries: `lex` = keyword (exact strings, tool names, CVE IDs), `vec` = semantic (concepts, techniques, intent), `hyde` = hypothetical answer passage |
| `mcp__wiki-search__get` / `multi_get` | Fetch page(s) by path or docid (`file.md`, `file.md:100`, `#abc123`, glob) |

AGENTS.md rule: **never read `wiki/index.md` to find pages - always search first.**

Relational queries (how pages connect, hub or orphan detection) use the `graphify` skill (`scripts/wiki-graph.py`, reads `wiki/` live).

---

## Searching via CLI

Use when MCP is unavailable or for one-off maintenance.

**Semantic query (5 results, default):**

```bash
qmd query "CDN bypass origin IP"
```

**Semantic query (custom result count):**

```bash
qmd query -n 10 "JWT empty secret"
```

**Keyword search:**

```bash
qmd keyword "pnpm"
```

Output format: `[score] path/relative/to/wiki/` followed by a chunk of the matching content.

---

## Maintenance

**Re-index after adding or editing pages** (run once after a bulk write, not per file):

```bash
qmd update && qmd embed   # update indexes text; embed refreshes the semantic vectors
```

Expected output: `Indexing wiki... Done. N chunks indexed.`

The CUDA warning about an old driver is harmless - the model runs on CPU.

Embed quirks on this seat (VRAM 0, `--no-gpu`): long embed passes die partway with
`LLM session expired before embedding chunk` (~150-400 chunks per pass). Vectors still
catch up a few hundred per pass - just re-run `qmd embed --no-gpu` later (or on a nightly
cron) until `qmd status` Vectors stops climbing. STOP CONDITION: once a pass lands ZERO
new vectors (session expiry hits from chunk 0), rerunning is dead weight - the embedding
session needs a qmd server restart, not another embed pass; park the tail (BM25 is the
primary rung) and restart qmd at the next maintenance window instead of relaunching.
Never block a session on embed: the BM25/keyword lane is fully current after
`qmd update` alone and is the primary search path per doctrine; vectors only serve the
semantic rung.

**Check index size:**

```bash
qmd status
```

Output: `Collection: wiki  Chunks: N`

### Integrity and catalog upkeep

These run automatically at SessionStart (via `engagement-init.py`); run them by hand after a bulk edit, rename, or before sharing:

```bash
python3 scripts/gen_index.py     # rebuild wiki/index.md catalog (idempotent; --check tests only)
python3 scripts/lint-wiki.py     # broken links, dead script refs, frontmatter gaps, stale index, lean areas
python3 scripts/build_moc.py     # rebuild graph hubs so every page stays reachable
```

`lint-wiki.py` exits non-zero on hard problems - use it as a pre-share / pre-commit gate. `index.md` and the `*-moc.md` hubs are generated; never hand-edit them.

---

## Promote candidates

Generic, reusable knowledge found live during an engagement is staged to a review
queue under `targets/<eng>/wiki-candidates/` (gitignored) the moment it is confirmed,
not at engagement end. It reaches `wiki/` only through the leak-gated promoter.

```bash
python3 scripts/wiki-promote.py --list             # pending candidates (slug, kind, page)
python3 scripts/wiki-promote.py --review <slug>    # read one candidate in full
python3 scripts/wiki-promote.py --promote <slug>   # or: --promote all
```

`--promote` runs `scripts/check-leaks.sh --file` on the candidate BODY. If a client
marker is present it refuses and writes nothing; if clean it merges into
`wiki/<target_page>` (dedup by slug), sets `status: promoted`, archives the file to
`wiki-candidates/_promoted/`, and re-indexes (`gen_index.py` + `qmd update && qmd embed`). Stage a
new candidate with `scripts/wiki-stage.py --kind <default-cred|api-pattern|technique>
--slug <slug>`. This is the only path that writes engagement-derived knowledge into
`wiki/`, so the client-data boundary is enforced by code, not prose.

---

## Broken install recovery

If `qmd` fails:

1. Confirm the `qmd` binary is on `PATH` (`command -v qmd`); it installs to `~/.bun/bin/qmd` via `bun install -g @qmd/cli`.
2. Check `QMD_VAULT` is set and points to the current vault path (no trailing slash, no spaces encoded).
3. The index lives under `~/.qmd/` - if the collection is missing, run `qmd update && qmd embed` to rebuild from scratch.

---

## Files

| Path | Purpose |
|---|---|
| `~/.bun/bin/qmd` | qmd CLI + MCP binary (bun global) |
| `~/.qmd/` | local search index |
| `$QMD_VAULT/wiki/` | the markdown corpus that gets indexed |
