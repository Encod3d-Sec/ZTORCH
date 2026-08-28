#!/usr/bin/env bash
# Windows-seat setup for ZTORCH on ZCode -- run once per Windows machine, from the vault root.
#
#   bash setup/win-seat.sh [--index]
#
# Architecture (docs/virtual-machine.md): ZCode desktop runs on WINDOWS (Git Bash shell);
# the vault lives on the Windows filesystem; the offensive toolchain lives in WSL kali-linux
# (root: /root/vm.sh + /root/creds.txt, sshpass) and the VMware Kali VM sits behind it.
# This script wires the seat:
#   1. verifies the WSL distro, the vm.sh bridge files, and VM reachability
#   2. links the vault skills into .zcode/skills/ (junctions)
#   3. writes the .zcode/win-seat marker (gates the qmd-in-WSL fallbacks)
#   4. registers the wiki-search MCP at user scope: ZCode (Windows) -> wsl.exe -> qmd mcp
#   5. with --index: builds/refreshes the search index now (qmd update + embed through WSL)
set -uo pipefail
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"   # keep /root/... args native for wsl.exe

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
VAULT="$(cd "$SCRIPT_DIR/.." && pwd)"
DISTRO="${ZTORCH_WSL_DISTRO:-kali-linux}"
MCP_CONFIG="$HOME/.zcode/cli/config.json"
FAIL=0

ok()   { echo "  [ok] $*"; }
fail() { echo "  [FAIL] $*"; FAIL=1; }

echo "ZTORCH Windows seat setup"
echo "Vault:  $VAULT"
echo "Distros:"
wsl.exe -l -v 2>/dev/null | tr -d '\0' | sed 's/^/  /'

echo "1. WSL bridge checks"
if wsl.exe -l -q 2>/dev/null | tr -d '\0\r ' | grep -qx "$DISTRO"; then
  ok "distro '$DISTRO' installed"
else
  fail "distro '$DISTRO' not found (set ZTORCH_WSL_DISTRO or install it)"
fi
if wsl.exe -d "$DISTRO" -u root -- test -x /root/vm.sh 2>/dev/null; then
  ok "/root/vm.sh present"
else
  fail "/root/vm.sh missing in $DISTRO (the SSH bridge to the VM)"
fi
if wsl.exe -d "$DISTRO" -u root -- test -r /root/creds.txt 2>/dev/null; then
  ok "/root/creds.txt present (VM ip/user/password)"
else
  fail "/root/creds.txt missing in $DISTRO"
fi
if command -v python3 >/dev/null 2>&1; then
  ok "python3 on PATH (hook interpreter)"
else
  fail "python3 not on PATH -- ZCode hooks need it"
fi

echo "2. VM reachability (direct tier first, then WSL bridge)"
if bash "$SCRIPT_DIR/../scripts/vm-ssh.sh" 'true' 2>/dev/null; then
  ok "direct ssh tier answers (bash scripts/vm-ssh.sh 'id; hostname')"
  if bash "$SCRIPT_DIR/../scripts/win-vm.sh" 'true' 2>/dev/null; then
    ok "WSL bridge tier answers too (fallback healthy)"
  else
    echo "  [warn] WSL bridge tier failed (password in /root/creds.txt rejected?) -- direct tier covers engagement work; re-arm with: bash setup/vm-key.sh needs a working bridge, so fix creds.txt first if you want the fallback"
  fi
else
  if bash "$SCRIPT_DIR/../scripts/win-vm.sh" 'true' 2>/dev/null; then
    ok "WSL bridge tier answers (direct tier down -- re-arm the key: bash setup/vm-key.sh)"
  else
    fail "VM unreachable on BOTH tiers -- boot the VMware VM / check /root/creds.txt / re-run setup/vm-key.sh"
  fi
fi

echo "3. Skills -> .zcode/skills (junctions)"
bash "$SCRIPT_DIR/install-skills.sh" >/dev/null 2>&1 && ok "install-skills.sh" || fail "install-skills.sh failed"

echo "4. Seat marker + user-scope wiki-search MCP (qmd via wsl.exe)"
mkdir -p "$VAULT/.zcode"
: > "$VAULT/.zcode/win-seat" && ok ".zcode/win-seat marker"
mkdir -p "$(dirname "$MCP_CONFIG")"
[ -f "$MCP_CONFIG" ] || echo '{}' > "$MCP_CONFIG"
cp "$MCP_CONFIG" "$MCP_CONFIG.bak-$(date +%s)"

POSIX_VAULT="$(cygpath -u "$VAULT")"
drive="$(printf '%s' "${POSIX_VAULT:1:1}" | tr 'A-Z' 'a-z')"
WSL_VAULT="/mnt/$drive/${POSIX_VAULT:3}"
python3 - "$(cygpath -w "$MCP_CONFIG")" "$DISTRO" "$WSL_VAULT" <<'PY'
import json, sys
p, distro, wsl_vault = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(p, encoding="utf-8"))
servers = d.setdefault("mcp", {}).setdefault("servers", {})
servers["wiki-search"] = {
    "type": "stdio",
    "command": "wsl.exe",
    "args": ["-d", distro, "-u", "root", "--", "/usr/bin/env",
             "QMD_VAULT=" + wsl_vault, "HF_HUB_DISABLE_PROGRESS_BARS=1", "qmd", "mcp"],
    "timeoutMs": 60000,
}
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
json.load(open(p, encoding="utf-8"))
print("  [ok] wiki-search registered (user scope): ZCode -> wsl.exe -> qmd mcp")
PY
[ $? -eq 0 ] || fail "MCP registration failed"

echo "5. Index"
if [ "${1:-}" = "--index" ]; then
  echo "  building/updating the search index (qmd update + embed through WSL; can take minutes)..."
  bash "$SCRIPT_DIR/../scripts/win-qmd.sh" update && bash "$SCRIPT_DIR/../scripts/win-qmd.sh" embed && ok "qmd update+embed" || fail "qmd update+embed"
else
  echo "  skipped. Build it once now with:  bash setup/win-seat.sh --index"
  echo "  (or later: bash scripts/win-qmd.sh update)"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "Seat ready. Restart ZCode, then smoke-test:"
  echo "  bash scripts/win-vm.sh 'id; hostname'      # VM bridge"
  echo "  bash scripts/win-qmd.sh query \"ssrf cloud metadata\"   # wiki search"
else
  echo "Seat INCOMPLETE -- fix the FAIL lines above and re-run."
fi
exit $FAIL
