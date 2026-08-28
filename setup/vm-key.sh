#!/usr/bin/env bash
# One-time: authorize the Windows seat's SSH key on the Kali VM so direct
# ssh (scripts/vm-ssh.sh) works without passwords or the WSL hop.
#
#   bash setup/vm-key.sh
#
# Path: generates ~/.ssh/id_ed25519_ztorch if missing, ships the pubkey to the VM
# THROUGH the existing WSL bridge (password auth via /root/creds.txt, base64 so the
# key survives the transport), then verifies a key-auth login. Idempotent.
set -uo pipefail
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
KEY="${ZTORCH_VMKEY:-$HOME/.ssh/id_ed25519_ztorch}"
HOST="${ZTORCH_VMHOST:-192.168.23.128}"

echo "1. seat key"
if [ -f "$KEY" ]; then
  echo "  [ok] $KEY exists"
else
  mkdir -p "$HOME/.ssh"
  ssh-keygen -q -t ed25519 -N "" -f "$KEY" -C "ztorch-windows-seat" && echo "  [ok] generated $KEY"
fi
PUB="$(cat "$KEY.pub")" || { echo "  [FAIL] no pubkey" >&2; exit 1; }
B64="$(printf '%s' "$PUB" | base64 -w0)"

echo "2. install on VM via the WSL bridge (password auth, last time)"
if bash "$SCRIPT_DIR/../scripts/win-vm.sh" \
     "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo $B64 | base64 -d >> ~/.ssh/authorized_keys && sort -u -o ~/.ssh/authorized_keys ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo key-installed" \
     | grep -q key-installed; then
  echo "  [ok] pubkey added to VM authorized_keys"
else
  echo "  [FAIL] install through the bridge failed (is the VM up? win-vm.sh working?)"
  exit 1
fi

echo "3. verify direct key auth from Windows"
if ssh -i "$KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 \
       "root@$HOST" 'echo vm-ssh-ok' | grep -q vm-ssh-ok; then
  echo "  [ok] direct ssh root@$HOST works (key auth)"
  echo ""
  echo "Fast path ready: bash scripts/vm-ssh.sh '<remote command>'"
else
  echo "  [FAIL] key auth rejected -- check VM sshd_config (PermitRootLogin) and try again"
  exit 1
fi
