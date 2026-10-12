---
name: hermes
description: Dispatch a lane to the external hermes-agent engine (one headless one-shot per lane via scripts/hermes.sh; same SKILL.md doctrine, wiki MCP, tier aliases haiku/sonnet/opus). Use for "hermes lane", "external engine", "cheap lane", "run this on hermes", or a mechanical/research/wiki/code-read lane where Claude-tier context economy matters.
---

# Hermes seat: external-engine lanes

One dispatched lane = one headless hermes-agent one-shot (`hermes -z`): the prompt goes
in, the final response comes back on stdout, the process exits. Hermes runs OUTSIDE this
Claude session: its model comes from the seat config (Z.ai gateway, glm tiers), its skills
are the vault's own `skills/` tree mounted read-only, and its wiki access is the same qmd
MCP (`wiki-search`). Cost and context stay out of the Claude session entirely.

## Setup (once per machine)

```
bash setup/hermes-seat-init.sh          # seeds ~/.hermes-ztorch (config + key + skills mount)
bash scripts/hermes.sh check            # static checks, no API spend
```

The seat home is isolated (`ZTORCH_HERMES_HOME`, default `~/.hermes-ztorch`): its own
config.yaml, `.env` key, and session state; nothing touches `~/.hermes`. The curator
(hermes' autonomous skill-editing loop) is disabled in the seat config; the vault skills
mount is read-only to hermes regardless. Vault doctrine changes stay a brain act.

## Dispatch

```
bash scripts/hermes.sh '<lane prompt>' --tier haiku|sonnet|opus \
  --dir <workdir> --capture targets/<eng>/poc/<lane>/
```

- `--tier` mirrors the brain tier table exactly: haiku = glm-5.3-flash (default),
  sonnet = glm-5.3, opus = glm-5.3 on this gateway (glm-5.3-max is rejected by its wire; the wrapper comment marks it).
- `--dir` is the run's working dir; hermes anchors file ops there and loads the vault
  AGENTS.md context chain from it (the vault doctrine rides along automatically).
- `--capture` writes `response.md` (final answer) and `usage.json` (cost/tokens/session
  report) into the lane capture dir; without it the response only hits stdout.
- Exit codes (hermes convention): 0 ok, 1 empty response, 2 failed or partial, 130
  interrupted. The brain reads rc + response + usage.json, never a bare rc.

The lane prompt carries the FULL delegate checklist (slots a-h) plus, verbatim:
the read-first mandate (`cat each file in full, zg/grep only to locate`), the
Obsidian-safe rule (any angle-bracketed value written into a `.md` sits in inline
backticks), the anti-give-up rule (run the full window, report raw output, never invent
a result), and the return envelope (Scope / Result / Key files / Issues, 15 lines or
fewer). Hermes writes its full report to a file in the capture dir and the envelope
summary into `response.md`.

Lane bookkeeping is the standard contract: write the lane line to `targets/<eng>/log.md`
before dispatch (`tmux win -`, `handle hermes:<lane>`), close it on return by appending
`-> VERIFIED: <capture ref>` or `-> NOT VERIFIED: <why>` after the capture cell.

## Hard rules

1. NO live-target packets from a hermes lane, ever. The scope-guard hook sees Claude
   tool calls only; commands inside the hermes process are invisible to it. Target
   interaction stays in Claude tool calls or the VM seat. Hermes lanes are
   research / wiki / code-read / offline-draft lanes by definition.
2. Default toolsets are `file,search,skills,web,todo`: file read/write/edit, wiki and
   web search, skills. NO terminal toolset by default (arbitrary commands); adding it
   (`--toolsets terminal,...`) is a brain decision per lane. `-z` auto-bypasses
   hermes-side approvals, so the toolset list IS the permission boundary.
3. The lane never edits shared vault files; findings come back in the envelope and the
   brain applies them (PENDING-WRITE block if needed).
4. Hard containment when a lane touches untrusted content: switch the seat config to
   the docker terminal backend (`terminal.backend: docker`, CWD-only mount, caps
   dropped); local backend is cwd-anchored by convention only, not a sandbox.

## What hermes adds

- A lane can itself fan out internally (`delegate_task`, capped by
  `delegation.oneshot_max_children`, synchronous in one-shot mode) without costing this
  session a single subagent slot; the 3-concurrent-lane fleet cap counts hermes lanes
  the same as Claude lanes (disjointness rules unchanged).
- `--resume` / `--continue` on the raw CLI lets a follow-up re-enter the same hermes
  session thread with prior context; the wrapper stays one-shot, resume is a manual
  escalation documented here for completeness.
- Self-improvement (skill creation) is OFF in this seat; if an operator wants it, flip
  `curator.enabled` in the seat config, never in the vault.

Mechanics and design evidence: `docs/hermes.md`.
