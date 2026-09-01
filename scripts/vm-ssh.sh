#!/usr/bin/env bash
# Direct driver to the Kali VM (fastest path on a WSL seat). Prefers key-based SSH
# as root when /root/.ssh/ztorch_vm is authorized on the VM; otherwise delegates to
# the machine-side /root/vm.sh (password path, creds in /root/creds.txt). VM_KEY and
# VM_SH overridable for tests. Usage: bash scripts/vm-ssh.sh '<remote bash command>'
set -uo pipefail
CMD="${1:?need a command}"
KEY="${VM_KEY:-/root/.ssh/ztorch_vm}"
HOST="$(awk -v h=IP '$0 ~ "^# *"h" *$"{f=1;next} f&&NF{print;exit}' /root/creds.txt 2>/dev/null)"
if [ -f "$KEY" ] && [ -n "$HOST" ] && \
   ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 -o LogLevel=ERROR \
       -o StrictHostKeyChecking=accept-new "root@$HOST" true 2>/dev/null; then
  B64="$(printf '%s' "$CMD" | base64 -w0)"
  exec ssh -i "$KEY" -o BatchMode=yes -o LogLevel=ERROR \
    -o StrictHostKeyChecking=accept-new "root@$HOST" \
    "bash -c \"\$(printf %s '$B64' | base64 -d)\""
fi
exec bash "${VM_SH:-/root/vm.sh}" "$CMD"
