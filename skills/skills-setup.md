# Skills & MCP Setup

Operational reference for managing plugins, MCP servers, and hooks in this vault.
Add new entries here whenever a plugin is added, removed, or breaks.

---

## Active MCP Servers

### wiki-search (qmd)

Semantic and keyword search across `wiki/`. Required for all vault search operations.

```json
"wiki-search": {
  "type": "stdio",
  "command": "qmd",
  "args": ["mcp"],
  "env": { "QMD_VAULT": "/mnt/c/Users/{user}/Documents/ObisidianVaults/ZTorch/ZTorch" }
}
```

Replace `{user}` with your Windows username (the WSL path is
`/mnt/c/Users/<you>/Documents/ObisidianVaults/ZTorch/ZTorch`). If you keep a
per-machine table, it lives in the git-ignored `AGENTS.local.md`.

Config location: `~/.zcode/cli/config.json` -> `mcp.servers` (user scope; `setup/bootstrap.sh`
writes it for you). Workspace config lives at `<vault>/.zcode/config.json` (committed, hooks only).
Manage/inspect via Settings -> MCP in ZCode.
Rebuild index: `qmd update && qmd embed` (run from vault root after bulk wiki changes; embed refreshes semantic vectors)

### obsidian-vault (removed)

Previously used `mcp-obsidian` (Obsidian Local REST API). Removed because:
- Requires Obsidian app to be running on Windows - breaks if closed
- Not needed: ZCode's `Read` tool accesses vault files directly via WSL path

**Replacement:** `Read /mnt/c/Users/{user}/Documents/ObisidianVaults/ZTorch/ZTorch/<relative-path>` (see machine usernames above)

---

## Plugin Troubleshooting

### context7 - stale lock files crash the plugin

**Symptom:** context7 fails to start or crashes sessions on startup.

**Cause:** context7 is an external plugin (`npx -y @upstash/context7-mcp`) with no version
in its manifest, so all sessions share one `unknown/` cache directory. When a session exits
uncleanly (WSL restart, force-kill), its PID lock file is never removed. On next startup
ZCode sees orphaned locks and fails to connect.

**Manual fix:**
```bash
rm -f ~/.zcode/cli/plugins/cache/*/context7/unknown/.in_use/*
```
Safe to run any time ZCode is not actively running.

**Automatic fix:** SessionStart hook (see below).

---

## Hooks

### SessionStart - context7 lock cleanup

Stale context7 PID lock files can crash the plugin on startup. The registered
`session-start.sh` SessionStart hook links vault skills and loads `session/hot.md`;
the lock cleanup itself stays a manual/one-off snippet:
the registration ships in the committed `.zcode/config.json`, and
`bash setup/install-hooks.sh` verifies it, so no manual edit is needed.
The cleanup logic:

```bash
LOCK_DIR="$HOME/.zcode/cli/plugins/cache"   # glob every marketplace root
find "$LOCK_DIR" -maxdepth 4 -type d -name .in_use 2>/dev/null | while read -r d; do
  for f in "$d"/*; do
    [ -f "$f" ] || continue
    pid=$(python3 -c "import json; print(json.load(open('$f')).get('pid',''))" 2>/dev/null)
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null || rm -f "$f"
  done
done
```

---

## Disabled Plugins

| Plugin | Reason |
|--------|--------|
| obsidian-vault MCP | Requires Obsidian running; replaced by direct Read tool |
| context7 (was crashing) | Fixed via lock cleanup above; now re-enabled |
