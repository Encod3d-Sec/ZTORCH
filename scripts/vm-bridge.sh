#!/usr/bin/env bash
# seat-side vm.sh adapter: routes the remote command through the WSL bridge
# (win-vm.sh wraps wsl.exe + /root/vm.sh inside the kali distro).
#
# QUOTING LAW: wsl.exe re-parses its command line through the WSL default
# shell (as root), so ANY $ construct in the payload is expanded on the WSL
# side before vm.sh/ssh ever sees it - multi-line scripts and \$ escapes die
# there (verified 2026-10-14: $(id -u) returned 0, the WSL uid, not the VM
# uid 1000). This adapter therefore base64-wraps the payload the same way
# scripts/vm-ssh.sh does; the decoded string is pipe-safe through
# wsl.exe -> bash /root/vm.sh -> sshpass ssh -> remote bash.
#
# vm.sh gotchas that apply unchanged: no stdin forwarding; no persistent
# state between calls.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

CMD="${1:-}"
[ -n "$CMD" ] || { echo "vm-bridge: need a remote command" >&2; exit 2; }

# base64 -w0: single line, no wrapping, shell-safe token
B64="$(printf '%s' "$CMD" | base64 -w0)"
REMOTE="echo $B64 | base64 -d | bash"

# shortcut: wsl.exe argv ceiling (~32k chars observed) - payloads beyond it fail
# with 'Argument list too long' (capture.sh's b64-in-command PNG pulls hit this).
# Ceiling: ~30k base64 chars. Upgrade: chunked transfer (split + cat on VM) when
# a caller needs bulk pulls through this bridge.
LEN=${#B64}
if [ "$LEN" -gt 30000 ]; then
  echo "vm-bridge: payload $LEN b64-chars exceeds wsl.exe argv ceiling (~30k); chunk it" >&2
  exit 3
fi

OUTPUT_ECON=0 exec bash "$HERE/win-vm.sh" "$REMOTE"
