#!/usr/bin/env bash
# scope-sync: push the scope state (3 files) from the seat repo to the Kali VM.
# Files pushed (design-scope-shim.md section 2):
#   skills/hooks/_engagement.py        -> /opt/scope-shim/vault/skills/hooks/
#   targets/active.md                  -> /opt/scope-shim/vault/targets/
#   targets/<active-eng>/scope.md      -> /opt/scope-shim/vault/targets/<eng>/
# Run from the ZTorch repo root on the seat.
# Exit: 0 = synced; nonzero = transport failure (ssh/scp error). The shim itself
# computes staleness from the stamp - this script has no staleness logic.
#
# ROUTE: direct root@VM ssh needs an accepted root key (this seat's vm-ssh.sh
# route is key-based). If auth differs, override: `VM_SSH=<your-ssh-cmd> bash
# scripts/scope-sync.sh` from a terminal whose root@VM auth works; the
# vm-bridge.sh WSL fallback applies unchanged.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
# SELF-CONTAINED: targets/ in this repo is canonical scope state (never read a
# sibling snapshot tree for it).
VM="${VM_SSH:-root@192.168.23.128}"
DEST="/opt/scope-shim/vault"

ACTIVE="$(cat "$REPO/targets/active.md" 2>/dev/null | head -1 | tr -d '[:space:]')"
if [ -z "$ACTIVE" ]; then
  echo "scope-sync: no active engagement pointer - push aborted (nothing to sync)" >&2
  exit 1
fi

ssh "$VM" "mkdir -p '$DEST/skills/hooks' '$DEST/targets/$ACTIVE'"
scp -q "$REPO/skills/hooks/_engagement.py" "$VM:$DEST/skills/hooks/"
scp -q "$REPO/targets/active.md" "$VM:$DEST/targets/"
if [ -f "$REPO/targets/$ACTIVE/scope.md" ]; then
  scp -q "$REPO/targets/$ACTIVE/scope.md" "$VM:$DEST/targets/$ACTIVE/"
else
  echo "scope-sync: WARNING no scope.md for '$ACTIVE'" >&2
fi
# stamp the sync so the shim can compute staleness:
ssh "$VM" "date -u +%s > '$DEST/.sync-stamp'"
echo "scope-sync: OK (engagement=$ACTIVE)"
