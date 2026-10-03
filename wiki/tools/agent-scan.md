---
title: "Agent-Scan (Snyk)"
type: tool
tags: [mcp, ai, llm, scanning, automation]
date_created: 2026-09-09
date_updated: 2026-10-04
sources: [git-snyk-agent-scan]
phase: enumerate
---

## Purpose

**Snyk Agent-Scan** (`snyk-agent-scan`) scans AI-agent setups for MCP server configs AND
agent skill folders (SKILL.md): prompt injection in tool descriptions, tool shadowing,
skill poisoning, malware payloads, insecure credential handling, hardcoded secrets.
Snyk's continuation of the acquired Invariant Labs [[mcp-scan]]; the second pass behind
`hunt-mcp` because it adds the skills layer mcp-scan does not cover.

## Install / setup

Python/uv-based (macOS, Linux, Windows), runs on Kali; no npm package exists. Requires a
Snyk account + API token: analysis runs through Snyk's Agent Scan API and secrets are
redacted before transmission. Standalone binaries (SBOM + GPG-signed checksums) are on
GitHub Releases if uv is unwanted.

```bash
export SNYK_TOKEN=your-api-token-here
uvx snyk-agent-scan@0.6.8           # pinned (skillspector RP1); bump deliberately on release notes
```

## What it detects

15 risk indicators. v0.6+ uses scored, named risks (`docs/risks.md`); the older v0.5.x
line used E/W issue codes and is deprecated.

| Surface | v0.6+ risks |
|---|---|
| MCP tools | `prompt_injection_tool_desc`, `dangerous_words`, `untrusted_content`, `private_data`, `destructive_capabilities` |
| Skills (SKILL.md) | `prompt_injection_skill_instructions`, `suspicious_download_url`, `malicious_code`, `insecure_credential_handling`, `secret_detection` |

Legacy v0.5.x codes worth recognising in old reports: E001 prompt injection / tool
poisoning, E002 tool shadowing, E004 skill prompt injection, E006 malware payloads,
W007/W008/W011 credential handling / hardcoded secrets / untrusted content. Output is
experimental and may change between releases; pin a version when stable output matters.

Auto-discovery covers Claude Desktop, Claude Code, Cursor, Windsurf, VS Code, Gemini CLI,
Codex, Amazon Q and more (per-scope matrix in the README).

## Core usage

```bash
snyk-agent-scan scan [CONFIG_FILE...]     # explicit paths: mcp.json, SKILL.md, a skills dir
snyk-agent-scan inspect [CONFIG_FILE...]  # full detail after a finding
snyk-agent-scan --json --ci               # machine-readable, non-zero exit on findings
```

No args scans all auto-discovered configs. `--skills` / `--no-skills` toggles the skills
layer; `--scan-all-users` widens beyond the current user; `--server-timeout` (default 10s)
for slow stdio servers; `--storage-file` (default `~/.mcp-scan`) holds scan state;
`--show-full-discovery` expands the compact default output.

## What a HIT looks like

v0.6+ prints scored risk indicators (risk name, score, evidence) per scanned path; with
`--json` the detail lands under `scan_path_responses`. As with [[mcp-scan]]: a scored risk
is a LEAD, never confirmation. The `hunt-mcp` Confirmation gate demands the injection
actually execute via the client in a clean session, and any exfil claim needs an OOB
callback ([[oob-callbacks]]).

## Common use cases

```bash
# Manifest pulled during enum: tool poisoning + scored risks
uvx snyk-agent-scan@0.6.8 targets/<eng>/ingest/found.mcp.json

# Skill-poisoning pass over a discovered skills dir
uvx snyk-agent-scan@0.6.8 ~/path/to/skills

# CI-style unattended run on a config you control
snyk-agent-scan --ci --json --no-skills path/to/mcp.json
```

## Tips and gotchas

- **Scanning executes the configured servers.** MCP configs contain commands and a scan
  runs them: interactive runs prompt y/n per stdio server (declined servers log
  `user_declined`), and `--dangerously-run-mcp-servers` bypasses the prompt in CI. Never
  use the bypass on untrusted configs; expect the config's commands to run on this host.
- Data leaves the box to Snyk's API. Same third-party-API caution as [[mcp-scan]]: check
  the client-data boundary before scanning engagement loot.
- Old v0.5.x reports use E/W codes, new ones use risk names; match the version when
  comparing two scans.
- Findings feed `hunt-mcp`: read the FULL flagged description or SKILL.md, replay the
  poisoned/shadowed call through Burp ([[burp-mcp]]), demonstrate client-side execution.

## Related techniques

[[mcp-server-attacks]], [[llm-prompt-injection]], [[mcp-scan]] (description-level
poisoning and rug pulls), [[burp-mcp]] (manual Repeater verification).

## Sources

- github.com/snyk/agent-scan (README, docs/risks.md, platform matrix)
