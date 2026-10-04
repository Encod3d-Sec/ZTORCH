---
title: "strix"
type: tool
tags: [ai, pentest, automation, agent]
date_created: 2026-09-24
date_updated: 2026-09-25
sources: [github-usestrix-strix]
phase: exploit
---

# strix

Multi-agent AI pentester (usestrix/strix, Python, `strix 1.6.2`). One root agent fans out
subagents that run tools inside a sandbox container and report findings; targets are web
apps, source dirs, GitHub repos, domains, IPs, OpenAPI/Postman specs. LLM routing is
litellm-style (`STRIX_LLM=provider/model` + `LLM_API_KEY` + optional `LLM_API_BASE`);
results land in `./strix_runs/<run-name>` (view with `strix view <run-name>`, continue
with `strix --resume <run-name>`).

## Core usage

```sh
sudo -i                                                    # env lives in root's interactive shell
strix --target https://target.example.com                  # web app, TUI
strix --target ./source-dir -m quick --max-budget 1 -n     # local code, headless
```

## Provider: GLM via Z.ai

`STRIX_LLM="anthropic/glm-5.3"` + `LLM_API_BASE="https://api.z.ai/api/anthropic"` +
`LLM_API_KEY=<zai key>`. Gotcha: Z.ai keys can carry no balance on the OpenAI-format
endpoint (`api.z.ai/api/paas/v4` returns error 1113 "Insufficient balance") while the
Anthropic-format endpoint on the same key works — so use the `anthropic/` prefix, not
`openai/`. Verified live: glm-5.3 round-trips and a full quick-mode run (185K input /
2.1K output tokens) completed through this route.

## Model tiering (1.6.2)

One main model serves every agent (root planner + all testing subagents; factory pins
`model=None` to `STRIX_LLM`). The only native per-role hook is finding dedupe, framed by
the docs as a cheap classification task: `STRIX_DEDUPE_MODEL="anthropic/glm-5.3-flash"`
(+ `DEDUPE_LLM_API_KEY` / `DEDUPE_LLM_API_BASE`) keeps glm-5.3 on the agents and flash on
dedupe. 2026-09-26: cost override — `STRIX_LLM` itself moved to
`anthropic/glm-5.3-flash` (everything on flash; the tier patch env becomes a no-op);
revert `STRIX_LLM` to `anthropic/glm-5.3` in `/root/.bashrc` when PoC/exploit
intelligence matters more than token cost. Scan work itself (nuclei/ffuf/http) is sandbox tool execution, not LLM calls, so
"cheap model for scans" has no tier to land on inside strix. True per-subagent tiers need
a factory patch (source install makes that possible, at the cost of upstream drift).

**Applied local patch** (`/opt/strix/strix-subagent-llm.patch`, reapply after `git pull`):
children default to the main model; `STRIX_SUBAGENT_LLM` (set to
`anthropic/glm-5.3-flash`) downgrades a child only when its name/task matches
`STRIX_SCAN_TIER_KEYWORDS` (default recon/enumerat/scan/fuzz/brute/subdomain/crawl/
spider/wordlist/discover). Misroute direction is cost-only: unmatched scans stay on
glm-5.3, PoC/exploit children never match. Unset the env for exact upstream behavior.

**Output-budget fix** (same patch file): reasoning models share one `max_tokens`
ceiling between thinking and tool-call JSON, and strix never sets `max_tokens`, so
the SDK default let long thinking truncate tool args mid-string (litellm
`BadRequestError: ... Failed to parse tool call arguments ... Unterminated string`,
seen on `create_agent`). `STRIX_MAX_OUTPUT_TOKENS=16384` (env, in `/root/.bashrc`)
makes `make_model_settings` pass an explicit `max_tokens`. Unset = upstream behavior.

## Install pattern on the Kali VM (source, root)

```sh
git clone https://github.com/usestrix/strix /opt/strix
python3 -m venv /opt/strix/.venv && /opt/strix/.venv/bin/pip install -e /opt/strix
ln -sf /opt/strix/.venv/bin/strix /usr/local/bin/strix
```

- No Docker on the box: `systemctl enable --now podman.socket` and
  `DOCKER_HOST="unix:///run/podman/podman.sock"` — strix's docker-py client works through
  the podman compat API (image pull + sandbox verified).
- The four env exports sit in `/root/.bashrc` below Kali's interactivity guard, so they
  only load in `sudo -i` shells; `sudo strix` (non-login) misses them.
- First run pulls `ghcr.io/usestrix/strix-sandbox` and compiles a Go TUI (both cached
  after); headless `-n` skips the TUI entirely.
- Update from source with `git -C /opt/strix pull` + reinstall `-e`; avoid
  `strix --update` on a source install (it overlays the PyPI build).

## Key flags

| Flag | Purpose |
|---|---|
| `-m quick\|standard\|deep` | depth; deep is default, quick for fast checks |
| `-n` | headless (no TUI) — required for piped/tmux-detached runs |
| `--instruction "Focus on IDOR"` | steer the test; `--instruction-file` for long briefs |
| `--max-budget USD` / `--max-turns N` | hard cost/turn caps (default 500 turns/agent) |
| `--target` repeatable | white-box combo: `--target ./src --target https://staging` |
| `--workspace-file f:dest` | drop a wordlist/spec into the sandbox workspace |
| `--target-list FILE` | one target per line |
| `--resume RUN_NAME` | pick up a prior run with full agent history |

## Operational notes

- Budget discipline: `--max-turns` default of 500 per agent makes an unbounded run
  expensive; set `--max-budget` for anything unattended.
- CPU-bound VM: one strix run at a time (sandbox + agent turns are heavy).
- `~/.strix/cli-config.json` stores wizard answers; `~/.strix/mcp-servers.json` adds MCP
  tools into the agents.

## Related

Doctrine distilled from the strix codebase (2026-10-05 deep-dive): fleet orchestration and
budget-band doctrine in [[multi-agent-campaign-orchestration]], closure/evidence/severity
discipline in [[safe-probing-and-controls]], and the full pattern-to-ZTorch absorption map in
[[agentic-harness-patterns]].
