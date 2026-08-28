#!/usr/bin/env bash
# WSL-side seat setup for ZTORCH -- run INSIDE WSL kali (root), e.g.:
#
#   sudo -s && cd ~ && bash /opt/ztorch/setup/wsl-seat.sh
#   (or from Windows: wsl.exe -d kali-linux -u root -- bash /mnt/c/.../setup/wsl-seat.sh)
#
# What it does:
#   1. creates /opt/ztorch -> <this vault> so the harness has a short native path in WSL
#   2. marks the vault as a git safe.directory (WSL git refuses /mnt/c repos otherwise)
#   3. verifies the VM bridge files (/root/vm.sh, /root/creds.txt), sshpass, qmd
# The vault stays the SINGLE working copy: /opt/ztorch is a symlink, not a clone, so
# engagement state, wiki, and session files never diverge between seats.
set -uo pipefail

SCRIPT="$(readlink -f "$0")"
VAULT="$(dirname "$(dirname "$SCRIPT")")"
LINK=/opt/ztorch
FAIL=0
ok()   { echo "  [ok] $*"; }
fail() { echo "  [FAIL] $*"; FAIL=1; }

echo "ZTORCH WSL seat setup"
echo "Vault: $VAULT"

echo "1. /opt/ztorch symlink"
if [ -L "$LINK" ] && [ "$(readlink -f "$LINK")" = "$VAULT" ]; then
  ok "$LINK already points at the vault"
else
  [ -e "$LINK" ] && [ ! -L "$LINK" ] && { fail "$LINK exists and is not a symlink"; }
  mkdir -p /opt && ln -sfn "$VAULT" "$LINK" \
    && ok "$LINK -> $VAULT" \
    || fail "could not create $LINK"
fi

echo "2. git safe.directory (WSL git x /mnt/c ownership)"
for u in root kali; do
  if id "$u" >/dev/null 2>&1; then
    if [ "$u" = "$(whoami)" ]; then
      git config --global --add safe.directory "$VAULT" && ok "safe.directory ($u)"
    else
      runuser -u "$u" -- git config --global --add safe.directory "$VAULT" 2>/dev/null \
        && ok "safe.directory ($u)" || echo "  [skip] safe.directory ($u): runuser unavailable"
    fi
  fi
done

echo "3. VM bridge checks"
[ -x /root/vm.sh ]          && ok "/root/vm.sh"          || fail "/root/vm.sh missing"
[ -r /root/creds.txt ]      && ok "/root/creds.txt"      || fail "/root/creds.txt missing"
command -v sshpass >/dev/null 2>&1 && ok "sshpass"       || fail "sshpass not installed"
command -v qmd >/dev/null 2>&1     && ok "qmd"           || echo "  [note] qmd absent (wiki-search MCP rides it; install: bun/npm per docs/setup.md)"
[ -f "$VAULT/scripts/win-vm.sh" ]  && ok "vault bridges present" || fail "vault bridges missing (stale vault?)"

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "WSL seat ready:"
  echo "  cd /opt/ztorch                 # the harness, native path"
  echo "  /root/vm.sh 'id; hostname'     # the VM (~ for root is /root)"
  echo "From the Windows seat the same hops are scripts/win-vm.sh / scripts/win-qmd.sh."
else
  echo "Seat INCOMPLETE -- fix the FAIL lines above and re-run."
fi
exit $FAIL
