---
title: "MCP-Scan"
type: tool
tags: [mcp, ai, llm, scanning, automation]
date_created: 2026-09-09
date_updated: 2026-10-04
sources: [invariant-mcp-scan-blog, git-invariantlabs-mcp-scan]
phase: enumerate
---

## Purpose

**MCP-Scan** is Invariant Labs' security scanner for Model Context Protocol setups: it
reads the MCP configs on a host, connects to each configured server, pulls every tool
description, and flags tool poisoning, prompt injection, rug-pull description changes, and
cross-origin shadowing. The automated first pass of the `hunt-mcp` skill; confirmation
stays manual, via the client and Burp. Snyk acquired Invariant Labs and the GitHub repo
now redirects to Snyk's [[agent-scan]] (same lineage: agent-scan's `--storage-file` default
is `~/.mcp-scan`); the PyPI package still installs and runs standalone.

## Install / setup

Needs [`uv`](https://docs.astral.sh/uv/) (uvx resolves and runs the PyPI package, no
install step). Runs fine on Kali.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # uv, once
uvx mcp-scan@0.4.3                                  # pinned (skillspector RP1); bump deliberately
```

By default it scans the well-known client config locations (Claude Desktop, Cursor,
Windsurf, VS Code). Pass a discovered manifest path to scan exactly that file.

```bash
uvx mcp-scan@0.4.3 /path/to/.mcp.json               # ponytail: unverified (path arg from the original README, not in the current docs)
```

## What it detects

| Class | Mechanism |
|---|---|
| Tool Poisoning Attacks | hidden malicious instructions embedded in tool descriptions (`<IMPORTANT>` blocks, unicode-tag / zero-width text) |
| Prompt Injection Attacks | instructions in descriptions the agent would execute |
| MCP Rug Pulls | description mutated server-side AFTER the user approved the tool; **Tool Pinning** hashes each tool across scans and flags the change |
| Cross-Origin Escalations | cross-references among the configured servers, i.e. one server shadowing another's trusted tool |

Detection is local checks plus the Invariant Guardrails API: tool names and descriptions
leave the box (no tool-call contents). Mind the client-data rule before pointing it at
engagement loot on a third-party API.

## Core usage

```bash
uvx mcp-scan@0.4.3                 # scan all discovered configs
uvx mcp-scan@0.4.3 inspect         # after a HIT: dump the full offending description
```

## What a HIT looks like

Per-server console output listing each discovered tool, then a flagged finding with its
class (prompt injection / cross-origin escalation / rug pull) and the offending tool name.
`inspect` prints the full description so the hidden instruction can be read and quoted
verbatim into the FIND. A flag is a LEAD, never confirmation: the injection must execute
via the client in a clean session (`hunt-mcp` Confirmation gate). For any exfil claim,
fire an OOB payload and wait for an operator callback ([[oob-callbacks]]); a flagged
description alone is inference.

## Common use cases

```bash
# Enum found an MCP manifest - scan it in place
uvx mcp-scan@0.4.3 targets/<eng>/ingest/found.mcp.json

# Re-scan an approved setup later: same tool hash = benign, changed hash = rug-pull evidence
uvx mcp-scan@0.4.3

# Read the exact hidden text behind a flag before writing the PoC
uvx mcp-scan@0.4.3 inspect
```

## Tips and gotchas

- Scanning CONNECTS to every configured server and launches stdio servers; a malicious
  server sees the scan and can serve a different description per client. Expect execution
  on the scanning host; treat untrusted configs accordingly.
- Rug-pull detection needs two scans over time (the hash baseline); a single scan only
  snapshots.
- A Node distribution (`npx @invariantlabs-ai/mcp-scan`) existed in early versions
  [uncertain]; uvx is the documented path now.
- Findings feed `hunt-mcp`: read the FULL description plus every parameter description,
  replay the poisoned/shadowed call through Burp ([[burp-mcp]]), and demonstrate the
  client acting on it.

## Related techniques

[[mcp-server-attacks]] (the full hunt), [[llm-prompt-injection]] (payloads), [[burp-mcp]]
(Repeater verification + Collaborator OOB), [[agent-scan]] (Snyk's successor scanner, adds
agent skills and scored risks).

## Sources

- invariantlabs.ai/blog/introducing-mcp-scan (detection classes, Tool Pinning, privacy notes)
- github.com/invariantlabs-ai/mcp-scan (now redirects to github.com/snyk/agent-scan)
