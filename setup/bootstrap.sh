#!/usr/bin/env bash
# ZTORCH vault bootstrap for ZCode (Z.AI) -- run once per machine from the vault root.
# Usage: bash setup/bootstrap.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT="$(bash "$SCRIPT_DIR/vault-path.sh")"

if [ -z "$VAULT" ]; then
  echo "ERROR: could not resolve vault path. Set OBSIDIAN_VAULT env var or add path to setup/vault-path.sh" >&2
  exit 1
fi

echo "Vault: $VAULT"
echo "Machine: $(hostname)"

# 1. Instructions + hooks need no user-dir writes on ZCode:
#    - AGENTS.md at the repo root is loaded automatically (workspace instruction file).
#    - Hook registration ships in the committed .zcode/config.json; install-hooks.sh
#      below verifies it and checks python3/bash are callable.
echo "[..] hooks + instructions: verified by install-hooks.sh below"
bash "$SCRIPT_DIR/install-hooks.sh"  || echo "[warn] install-hooks.sh failed (run it manually)"
bash "$SCRIPT_DIR/install-skills.sh" || echo "[warn] install-skills.sh failed (run it manually)"
echo "[ok] Hook registration verified (.zcode/config.json) + vault skills linked into .zcode/skills"

# 2. Install qmd if missing
if ! command -v qmd >/dev/null 2>&1; then
  echo "Installing bun + qmd..."
  curl -fsSL https://bun.sh/install | bash
  export PATH="$HOME/.bun/bin:$PATH"
  bun install -g @qmd/cli
  echo "[ok] qmd installed"
else
  echo "[ok] qmd already installed: $(qmd --version 2>/dev/null || echo 'version unknown')"
fi

# 3. Register MCP servers at USER scope (~/.zcode/cli/config.json -> mcp.servers).
#    User scope keeps machine-specific absolute paths out of the tracked workspace
#    config, and every scope auto-connects at session start.
if command -v python3 >/dev/null 2>&1; then
  echo "Registering MCP servers (user scope)..."
  ZCODE_CONFIG="$HOME/.zcode/cli/config.json"
  mkdir -p "$(dirname "$ZCODE_CONFIG")"
  [ -f "$ZCODE_CONFIG" ] || echo '{}' > "$ZCODE_CONFIG"
  cp "$ZCODE_CONFIG" "$ZCODE_CONFIG.bak-$(date +%s)"

  python3 - "$ZCODE_CONFIG" "$VAULT" <<'PY'
import json, os, sys
p, vault = sys.argv[1], sys.argv[2]
d = json.load(open(p))
servers = d.setdefault("mcp", {}).setdefault("servers", {})
changed = False

def upsert(name, spec):
    global changed
    if servers.get(name) != spec:
        servers[name] = spec
        changed = True
        print("  [ok] %s registered (QMD_VAULT=%s)" % (name, vault))
    else:
        print("  [ok] %s already registered" % name)

upsert("wiki-search", {
    "type": "stdio",
    "command": "qmd",
    "args": ["mcp"],
    "env": {"QMD_VAULT": vault},
})
upsert("caveman-shrink", {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "caveman-shrink", "qmd", "mcp"],
    "env": {"QMD_VAULT": vault},
})
# Prune stale absolute paths from a previous vault location.
for name, spec in list(servers.items()):
    if isinstance(spec, dict):
        env = spec.get("env") or {}
        old = env.get("QMD_VAULT")
        if old and old != vault and os.path.isdir(old) is False:
            del servers[name]
            changed = True
            print("  [prune] %s (old vault path gone: %s)" % (name, old))

json.dump(d, open(p, "w"), indent=2)
json.load(open(p))
print("  [ok] %s valid" % p)
PY
else
  echo "[warn] python3 not found -- register MCPs manually (Settings -> MCP, or edit ~/.zcode/cli/config.json):"
  echo '  mcp.servers["wiki-search"] = {"type":"stdio","command":"qmd","args":["mcp"],"env":{"QMD_VAULT":"'"$VAULT"'"}}'
  echo '  mcp.servers["caveman-shrink"] = {"type":"stdio","command":"npx","args":["-y","caveman-shrink","qmd","mcp"],"env":{"QMD_VAULT":"'"$VAULT"'"}}'
fi

# 4. Optional plugins (Settings -> Plugin Management in ZCode).
#    ZCode ships with official plugins (skill-creator, document-skills, browser-use,
#    computer-use, zcode-guide) already available. The extras below are optional
#    quality-of-life plugins; ZCode recognizes .claude-plugin manifests, so a
#    Claude marketplace repo can be added on the Discover tab if you want it.
cat <<'EOF'
[note] Optional plugins (add via Settings -> Plugin Management -> Discover):
  - superpowers   (github: obra/superpowers)   planning/execution workflow skills
  - ponytail      (github: DietrichGebert/ponytail) lazy-code discipline
  - caveman       (github: JuliusBrussee/caveman)   prose compression (/caveman)
None are required: AGENTS.md routes around them when absent.
EOF

# Kali VM capture deps (screenshot + tmux scan-runner). Best-effort; needs the VM configured.
if [ -f /root/vm.sh ] && [ -f /root/creds.txt ]; then
  echo "[..] provisioning Kali VM capture deps"
  bash "$VAULT/scripts/vm-provision.sh" || echo "[warn] vm-provision failed; run scripts/vm-provision.sh later"
else
  echo "[note] Kali VM not configured; after setup run: bash scripts/vm-provision.sh (see docs/virtual-machine.md)"
fi

echo ""
echo "Done. Restart ZCode, then run: qmd update"
