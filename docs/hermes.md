---
title: "Hermes external-engine seat"
type: docs
tags: [docs, harness, hermes, lanes]
date_created: "2026-10-12"
sources: []
---

# Hermes seat: how it works

Hermes-agent (NousResearch, MIT) is a standalone agent harness. ZTORCH uses it as an
EXTERNAL LANE ENGINE: one headless `hermes -z` one-shot per dispatched lane, running the
same vault doctrine with its own model budget, fully outside the Claude session's context
and cost. It is a seat, not a replacement brain: strategy, the driver, triage, and all
shared-file writes stay in the main session (`Skill(brain)`, `Skill(delegate)`).

## Pieces

| Piece | Path | Role |
|---|---|---|
| Seat seed | `setup/hermes-seat-init.sh` | Writes the isolated seat home (default `~/.hermes-ztorch`): config.yaml + `.env` key. Idempotent; `--force` regenerates config, never clobbers a hand-set key |
| Lane wrapper | `scripts/hermes.sh` | One prompt in, final response out; `--tier`, `--dir`, `--capture`, `--toolsets`, `check` |
| Seat skill | `skills/workflow/exec/hermes/SKILL.md` | Dispatch doctrine (hard rules, envelope, lane-line contract) |
| Tests | `tests/test_hermes_seat.py` | Static suite (no API spend) + `ZT_HERMES_LIVE=1` live smoke |
| Engine | `raw/git/hermes-agent/` (shallow clone) | The hermes monorepo; never edited |
| Runtime | `~/.hermes/tools/python-3.14*/bin/python3` | PM-provisioned interpreter with the deps; see the launcher trap below |

## Seat config (what init writes)

- `providers.ztorch-gw`: the box's Z.ai gateway (`ANTHROPIC_BASE_URL` at seed time),
  `api_mode: anthropic_messages`, key in `.env` as `ZTORCH_HERMES_KEY` (mode 600).
- `model_aliases` + wrapper tier map: `haiku` = glm-5.3-flash, `sonnet` = glm-5.3,
  `opus` = glm-5.3 (glm-5.3-max is rejected by this gateway's wire; the comment in the
  init script and wrapper marks it). Tiers mirror the brain table names.
- `skills.external_dirs`: the vault `skills/` tree. Hermes parses Claude-Code-format
  SKILL.md natively (agentskills.io base standard), treats external skills as READ-ONLY,
  and its security scanner does not run on this tier (the offensive prose would
  false-positive on the project tier).
- `mcp_servers.wiki-search`: `qmd mcp` with `QMD_VAULT` = vault root, so hermes lanes
  query the same wiki index the brain does.
- `curator.enabled: false`: hermes' autonomous skill-editing loop is OFF; vault doctrine
  changes remain a brain/operator act.
- `terminal.backend: local`: cwd-anchored by convention only, NOT a sandbox; hard
  containment is the docker backend (CWD-only mount, caps dropped) when a lane touches
  untrusted content.

## Dispatch flow

1. Brain writes the lane line to `targets/<eng>/log.md` (standard grammar,
   `tmux win -`, `handle hermes:<lane>`).
2. Brain runs `bash scripts/hermes.sh '<prompt>' --tier haiku --dir <workdir> --capture targets/<eng>/poc/<lane>/`.
   The prompt carries the delegate slots a-h + read-first/Obsidian-safe/anti-give-up
   mandates verbatim (the prompt is the lane's only law).
3. Hermes runs with the vault AGENTS.md context chain loaded from the workdir, vault
   skills mounted, wiki MCP available. `-z` prints only the final response; approvals
   inside hermes are auto-bypassed (YOLO), so the TOOLSET LIST IS THE PERMISSION BOUNDARY.
4. Wrapper tees the response to `capture/response.md`, hermes writes `capture/usage.json`
   (cost/tokens/session/exit-reason, written even on failure). Exit codes: 0 ok, 1 empty,
   2 failed/partial, 130 interrupted.
5. Brain verifies the envelope (Scope/Result/Key files/Issues, 15 lines or fewer) against
   the capture, appends `-> VERIFIED:` or `-> NOT VERIFIED:` to the lane line, applies any
   PENDING-WRITE blocks itself.

Default toolsets: `file,search,skills,web,todo` (no terminal; adding terminal is a
per-lane brain decision via `--toolsets`).

## Hard rules (why this is safe inside ZTORCH)

1. NO live-target packets from hermes lanes, ever: the scope-guard hook sees Claude tool
   calls only; commands inside the hermes process are invisible to it. Research, wiki,
   code-read, offline-draft lanes only. Target interaction stays in Claude tool calls or
   the Kali VM seat.
2. Hermes lanes never edit shared vault files; the brain is the sole APPLIER.
3. Fleet accounting unchanged: hermes lanes count against the same 3-concurrent-disjoint
   lane cap; a hermes lane may fan out internally (`delegate_task`, capped, synchronous
   in one-shot mode) without consuming Claude subagent slots.

## Traps found while building (do not re-learn these)

- The published `~/.local/bin/hermes` shim runs its python with `-I` (isolated mode),
  which strips user-site where the checkout deps live: every run dies on
  `ModuleNotFoundError: No module named 'ruamel'`. The wrapper therefore drives the clone
  directly via the PM toolchain python without `-I` (`run_hermes()` in the wrapper).
- `scripts/run-in-hermes-env` intermittently bails with "no bootstrap Python found" on
  this checkout (no `.venv` is ever created); the sourced `./activate` flow works but is
  interactive-shaped. The wrapper's direct-python path avoids both.
- The gateway rejects `glm-5.3-flash[1m]` (the anthropic-wire context-suffix name) and
  `glm-5.3-max` on its model wire; plain `glm-5.3` / `glm-5.3-flash` work. Tier maps use
  the plain names.
- Inherited `ANTHROPIC_*` shell env makes provider autodetect shadow the seat config;
  the wrapper strips `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` from the run env.
- `hermes doctor --non-interactive` is not a flag; plain `hermes doctor` is interactive-ish
  but runs its checks fine non-TTY.

## Test evidence (2026-10-12, this machine)

- `python3 tests/test_hermes_seat.py`: 6/6 static (config keys, idempotency, key
  non-clobber, base-url guard, wrapper validation, check subcommand).
- Live through the wrapper: haiku `OK` (rc 0, usage.json `completed: true`,
  model glm-5.3-flash); sonnet listed mounted vault skills (agents-md-improver, caido,
  caveman, disclosure, graphify, research, vector-workflow, wiki, hunt-burp, ...);
  opus `OK` after the alias fix.

## Ops

- Re-seed after gateway change: `bash setup/hermes-seat-init.sh --force` (key survives).
- Update the engine: `cd raw/git/hermes-agent && git pull` (shallow), then
  `bash scripts/hermes.sh check`; deps re-sync on first run via PM.
- Spend telemetry: read `usage.json` in each lane capture dir; stats are computed by the
  brain from captures, never self-reported by lanes.
