#!/usr/bin/env bash
# FASTEST seat path: direct Windows -> Kali VM ssh, key-based (no WSL hop, no sshpass).
#
#   bash scripts/vm-ssh.sh '<remote bash command>'
#   bash scripts/vm-ssh.sh 'hostname; whoami; ip -4 addr show tun0'
#
# Also the VM_SH implementation for every repo driver on Windows when you want the
# direct path (each call is a fresh key-auth connection; no ControlMaster on Win32):
#   VM_SH="$(pwd)/scripts/vm-ssh.sh" bash scripts/win-rsh.sh <session> '<ps command>'
#   VM_SH="$(pwd)/scripts/vm-ssh.sh" bash scripts/capture.sh req <eng>
#
# Fails fast (BatchMode: never hangs on a password prompt) -> fall back to the WSL
# bridge: bash scripts/win-vm.sh '<cmd>' (or re-run setup/vm-key.sh to re-arm the key).
set -uo pipefail
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"

HOST="${ZTORCH_VMHOST:-192.168.23.128}"
VMUSER="${ZTORCH_VMUSER:-root}"
KEY="${ZTORCH_VMKEY:-$HOME/.ssh/id_ed25519_ztorch}"

[ -f "$KEY" ] || { echo "vm-ssh: no key at $KEY -- run: bash setup/vm-key.sh" >&2; exit 2; }
exec ssh -i "$KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout=8 "$VMUSER@$HOST" "$@"
