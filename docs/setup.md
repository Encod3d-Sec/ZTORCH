# Vault Setup

**New machine:** run `bash setup/bootstrap.sh` from the vault root. This verifies the committed hook registration (`.zcode/config.json`), links the vault skills into `~/.claude/skills/`, installs bun + qmd, registers the `wiki-search` and `caveman-shrink` MCP servers at user scope (`~/.zcode/cli/config.json`), and prints the optional-plugin list. ZCode loads `AGENTS.md` and the workspace config natively from the repo, so no user-dir includes are needed. After setup, restart ZCode and run `qmd update && qmd embed` to build the local search index (`update` indexes text, `embed` the semantic vectors; without `embed` new pages answer only keyword queries). ZCode ships with the official plugins (skill-creator, document-skills, browser-use, computer-use, zcode-guide) already available.

**Caveman (both machines):** Output compression skill -- cuts ~65% of output tokens with no accuracy loss. Requires Node >=18. Bootstrap handles install automatically; to install manually: `curl -fsSL https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.sh | bash`. Trigger per session with `/caveman`, or say "talk like caveman". Source: https://github.com/JuliusBrussee/caveman

**Ponytail (both machines):** "lazy senior dev" engineering-discipline plugin -- pushes for the simplest working solution (YAGNI, stdlib/native before dependencies, shortest diff). Governs what you build, not prose (pairs with caveman for terse output). Optional Claude-marketplace plugin; ZCode recognizes `.claude-plugin` manifests, so add `DietrichGebert/ponytail` on the Discover tab (Settings -> Plugin Management) if you want it. Auto-activates at SessionStart (level `full`); switch with `/ponytail lite|full|ultra`. Not required - AGENTS.md routes around it. Source: https://github.com/DietrichGebert/ponytail

**caveman-shrink MCP (both machines):** MCP proxy that wraps `wiki-search` (qmd.mcp_server) and compresses tool descriptions before the model reads them, reducing context token usage. Bootstrap registers it automatically at user scope with the correct `QMD_VAULT` for each machine. To register manually, add to `~/.zcode/cli/config.json` -> `mcp.servers`: `"caveman-shrink": {"type":"stdio","command":"npx","args":["-y","caveman-shrink","qmd","mcp"],"env":{"QMD_VAULT":"<vault-path>"}}`. Both `wiki-search` (raw) and `caveman-shrink` (compressed descriptions) run as separate MCP entries; they share the same underlying data.

**qmd / `wiki-search` index:** Aim the markdown collection (`wiki`, or whichever name your MCP uses) only at **`$(vault-root)/wiki`**. Set `QMD_VAULT` to your vault root (no trailing slash). Remove stale collections that still reference old absolute paths before `qmd update` so indexing never scans the wrong directory. After any bulk refresh, also run `qmd embed` or new pages stay invisible to semantic search.

**Vault file reads:** Use the `Read` tool with the vault path directly. The `obsidian-vault` MCP (`mcp-obsidian`) was removed -- it required the Obsidian app running and offered no advantage over `Read`. See `skills/skills-setup.md` for details.

**Hook symlink (wiki session hooks):** `bootstrap.sh` creates this automatically. To create it manually:

```bash
ZCode needs no per-device hook symlink: registration ships in the committed
`<vault>/.zcode/config.json` and resolves scripts via ${ZCODE_PROJECT_DIR}.
```

The committed `.zcode/config.json` is the live registration on a ZCode build -- nothing to run to
verify it, it ships with the repo (13 hook commands across 6 events -- see below). `bash
setup/install-hooks.sh` provisions the SEPARATE, per-device `~/.claude/settings.json` used by a
Claude Code CLI seat instead (see the section below); it does not read or write `.zcode/config.json`.
On a new machine, re-running `bash setup/bootstrap.sh` handles all steps automatically.

## Claude Code CLI seat (alternate client)

Some seats run the plain **Claude Code CLI** instead of ZCode. ZCode's native `AGENTS.md`
loading (above) does not apply here -- a Claude Code CLI seat needs its own launch-directory
`CLAUDE.md` that imports the vault directly:

```
@<vault-root>/AGENTS.md
@<vault-root>/AGENTS.local.md
```

If the seat talks to a non-Anthropic-hosted backend (a compatible proxy, a different model
provider) instead of the Anthropic API directly, that is per-seat config too -- a
`.claude/settings.local.json` next to the launch-directory `CLAUDE.md`, with an `env` block
(`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, and the `ANTHROPIC_DEFAULT_*_MODEL` /
`ANTHROPIC_SMALL_FAST_MODEL` aliases if the backend uses different model names). This is
seat-local machine config, same category as `AGENTS.local.md`'s vault path -- never commit
it, and never put the auth token in `AGENTS.local.md` itself (that file is for vault paths,
not API credentials).

Hook registration for this seat kind is the WSL-Claude-Code-seat pattern documented in
`AGENTS.local.md`'s "This seat" section (`~/.claude/settings.json` + a `vault-hooks` symlink
into this vault's `skills/hooks/`), not the ZCode `.zcode/config.json` path above.

## Engagement-state automation (both machines)

**Transport is Obsidian Sync** for everything: the markdown knowledge base AND the automation code (`.py`, `.json`, `.sh`). There is no git push; a local git repo may exist per-device as offline history only (Obsidian does not sync `.git`).

**Hard requirement:** Obsidian Sync must be set to carry non-markdown files, or the hook code never reaches the other device and automation is dead there. In Obsidian: **Settings -> Sync -> turn ON "Sync all other file types"**, and confirm **Selective Sync** is not excluding `skills/`, `scripts/`, or `setup/`. By default Obsidian also skips dotfiles, but nothing runtime-critical is a dotfile (the engagement pointer is `targets/active.md`, not `.active`), so that exclusion is harmless.

**Device-2 / new-device procedure:**

```bash
# 1. let Obsidian Sync finish pulling the vault (incl. skills/, scripts/, setup/)
# 2. then, once per device:
cd <vault-root>
bash setup/install-hooks.sh    # provisions ~/.claude/settings.json for a Claude-Code-CLI seat
# 3. restart ZCode
```

`install-hooks.sh` is self-locating (works on any user/path/spelling) and idempotent. It registers the canonical set (mirrored in `scripts/check-hooks.py` `EXPECTED_HOOKS`; `engagement-init` warns at SessionStart if any is unregistered) -- 13 hook commands across 6 events:
- **SessionStart** -- `session-start.sh` (skill auto-register + hot.md cache), `engagement-init.py` (self-heals the per-type core set: ctf gets `state/loot/Approach/...`, pentest/bugbounty add `Killchain`; injects the state summary + plan board status + top next-moves + one compact `harness:` maintenance line).
- **UserPromptSubmit** -- `hunt-trigger.py` (fires hunt skills from `skills/hunt/triggers.json`).
- **PreToolUse (Bash)** -- `scope-guard.py` (ENFORCES: denies out-of-scope host/IP (IPv4+IPv6, CIDR-aware; query-param/fragment values exempt) or RoE-forbidden tooling; fail-open + `skills/hooks/.enforce-off` escape hatch; also logs each block as a drift signal).
- **PreToolUse (Bash)** -- `sleep-guard.py` (ENFORCES: denies a blind `sleep N` wait, N >= 10, with no poll loop watching output; fail-open + `.enforce-off` escape hatch).
- **PreToolUse (Write)** -- `session-guard.py` (client-marker leak guard: session/* AND git-tracked framework trees; targets/ + docs/superpowers/ exempt; logs a boundary-drift signal).
- **PreToolUse (Bash)** -- `drift-guard.py` (keeps the offensive driver in view: on an off-board exploit-shaped command during an active engagement at pass>=5 -- a NET_BINS/handroll call whose binary no open board row names -- escalates an `off_board_streak` in `.offensive.json` and injects a "run offensive.py next" advisory; an `offensive.py next|board|done` call resets it. Advisory-only, fail-open; shares the `.enforce-off` escape hatch).
- **PostToolUse (Bash)** -- `recon-capture.py` (fingerprint router + OOB callback correlation + a once-per-engagement GATE-1 wiki-first nudge; a framework-meta guard suppresses false fires; advisory).
- **PostToolUse (all)** -- `tool-telemetry.py` (per-box telemetry: appends every tool/skill call to `targets/<eng>/.events.jsonl`, stamps `started_at`, records the session `transcript_path`; feeds `scripts/eval_metrics.py`. Silent, fail-open).
- **PostToolUse (Write/Edit)** -- `wiki-reindex.py` (auto-reindex: a Write/Edit to `wiki/**/*.md` fires a debounced background `qmd update && qmd embed` so the change is searchable (text AND semantic) without a manual reindex; off the blocking path, fail-open).
- **Stop** -- `close-out.py` (close-out reflex: when the engagement is SOLVED but its walkthrough is unassembled / the learn harvest is due, nudges Skill(walkthrough) then Skill(learn); advisory, self-clearing).
- **PreCompact** -- `pre-compact.sh` (fires before a context compaction).

**Hooks self-locate the vault** via `realpath(__file__)` from `${ZCODE_PROJECT_DIR}/skills/hooks/...` -- no hardcoded paths, so the same code runs unmodified on every device.

**Active engagement pointer:** `targets/active.md` (one line: engagement dir name). It is markdown, so it syncs via Obsidian to both devices. Engagement files: `targets/<eng>/{state,loot,Approach,scope,Deadends}.md` + `ingest/` for ctf; pentest/bugbounty add `Killchain,log,walkthrough,eval`. Scaffolded from `setup/templates/<type>/` via `bash setup/new-engagement.sh <name> <pentest|bugbounty|ctf>`.

**Hook registration is committed** (`<vault>/.zcode/config.json`, portable via `${ZCODE_PROJECT_DIR}`), so it syncs with the repo; what stays machine-local are the `~/.claude/skills/` links and the user-scope MCP servers. Run `bash setup/install-skills.sh` (or let the SessionStart hook self-heal) after the first git pull; `bash setup/install-hooks.sh` is only needed on a Claude-Code-CLI seat (it provisions that seat's separate `~/.claude/settings.json`, not `.zcode/config.json`).

## Burp GUI automation: the Kali seat must stay UNLOCKED (gotcha)

`capture.sh burp` (burpshot) and any xdotool driving of Burp inject **synthetic input** into the Kali
desktop. A screen LOCK (xfce4-screensaver on seat0) or a blanked display routes that input to the locker,
not to Burp: `import -window` still grabs the window pixmap, but keys/clicks never land, so a grab silently
shows the WRONG Repeater tab. Symptom: `capture.sh burp` prints `GRAB_FAIL ... not interactive` even though
Burp is clearly on screen, and `getmouselocation` over Burp reports `window:0`.

- **Per-run (automatic):** `capture.sh burp` self-heals, it runs `loginctl unlock-session <seat0-sid>` +
  `xset` wake before the precheck, so a transient lock no longer blocks it.
- **Permanent (once per Kali box):** `sudo bash setup/burp/disable-lock.sh` disables the xfce4-screensaver
  saver + lock, removes its autostart, and kills DPMS/blanking (xfconf + `~/.xprofile` + an autostart
  override). Re-run after a box rebuild. Detail: `setup/burp/README.md`.
- **`wmctrl -lG` is NOT a reliable interactivity check** here, it reports "no managed windows" on this
  no-WM seat even when input lands (false negative). Use the pointer test (`getmouselocation` == the app
  WID), which is what `capture.sh burp` uses.

Burp MCP install (the "MCP Server" BApp, native vs `scripts/burp/burp-mcp-cli.py` bridge,
`burp-transport.sh`, the BApp loadout) lives in `wiki/tools/burp-mcp.md`. Driver scripts are in
`scripts/burp/`, skills in `skills/burp/` (`hunt-burp`, `screenshot-burp`), host setup in `setup/burp/`.
