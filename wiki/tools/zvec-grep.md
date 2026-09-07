---
title: "zvec-grep (zg)"
type: tool
tags: [search, retrieval, vector-index, bm25, ripgrep, harness, tooling, agent, mcp]
date_created: 2026-09-07
date_updated: 2026-09-07
sources: [git-zvec-ai-zvec-grep]
phase: recon
---

## Purpose

**zvec-grep** (`zg`) is local-first workspace search that unifies three retrieval methods behind one interface: ripgrep (exact/regex), BM25 (lexical), and vector/semantic search. It indexes a workspace once and returns ranked, source-linked hits (file + line range + excerpt), which cuts locate-across-files from many grep passes to one ranked query. For agents the point is fewer tool calls and fewer full-file reads: zg locates, the model then reads only the located blocks.

Position in this harness: zg is the cross-file LOCATE layer for the vault, `targets/`, and `raw/git` clones; qmd stays the wiki semantic primary; grep stays correct inside a single file. Doctrine lives in the AGENTS.md Search rule.

## Install / setup

```bash
npm install -g @zvec/zvec-grep   # Node 22+
zg index --no-ignore -g '!.obsidian/**' -g '!**/poc/cmdlog/**' \
         -g '!**/*.png' -g '!**/*.jpg' -g '!**/*.jpeg' -g '!**/*.pdf' \
         -g '!**/*.zip' -g '!**/*.gif' -g '!**/*.ico' \
         --embedding local/potion-retrieval-32m
                                  # standing vault-root index: targets/ AND raw/git included
zg server on                      # loopback-only MCP daemon, 127.0.0.1:7999/mcp
```

MCP registration (once, user scope): `claude mcp add -s user -t http zvec-grep http://127.0.0.1:7999/mcp`

Notes: `--no-ignore` is required because `targets/` is git-ignored but must stay searchable. `zg index` always climbs to the enclosing workspace root, so per-clone indexes do not exist; `raw/git` clones are covered by the standing index. `poc/cmdlog/` transcripts and images/binaries are excluded: engagement command logs are grep-heavy noise that swamps ranked results (measured in T2), and they stay reachable via grep/Read. Everything stays local (local embedding model, loopback server).

## Usage

```bash
# ranked semantic+lexical search (preferred)
zg query --human "where is the scope guard that blocks out-of-scope hosts" --limit 5
# wiki-scoped query
zg query --human "prefetch runcount artefact" --limit 5 -g 'wiki/**'
# exact pattern with full ripgrep power over the index
zg query --rg -e "CVE-2023-23752"
# MCP tools (agent toolset): zvec_grep_search; full toolset adds *_rg/_index/_status/_server_status
```

## Harness integration

- `scripts/wiki-query.sh -k` prefers zg (hybrid lexical) and falls back to qmd keyword.
- `skills/hooks/zg-nudge.py` (PreToolUse/Bash, advisory): nudges once per 15 min when a plain cross-file `grep -r`/`rg` runs where zg fits; never denies, skips single-file greps and remote/VM piped contexts.
- `scripts/offensive-doctor.py` zg section: CLI on PATH, MCP registered, daemon reachable, standing index present; warn-level, fail-open, prints the fix command.

## When to use vs the alternatives

- **zg**: locating across many files where ranking helps (which page/script/skill covers X, post-foothold "where is auth handled", research repo triage).
- **qmd** (`mcp__wiki-search__qmd_query`): wiki semantic lookup; the wiki-first discipline keeps it primary for doctrine pages.
- **grep/rg**: inside one located file; deterministic counts/existence checks; anything piped through the VM drivers (zg does not exist on the target).

## References

- https://github.com/zvec-ai/zvec-grep (docs/03-mcp.md, docs/06-server.md)
- Design spec: `docs/superpowers/specs/2026-09-07-zvec-grep-design.md`
