#!/usr/bin/env bash
# Persistent WSL kali seat session -- a root tmux session ('seat') inside WSL that
# stays alive between agent passes and that the operator can attach to.
#
#   bash scripts/seat.sh ensure            # create it if missing (root, cwd /opt/ztorch)
#   bash scripts/seat.sh run '<cmd>'       # ONE command in the session, clean output back
#   bash scripts/seat.sh send '<cmd>'      # raw: type into the session, no wait
#   bash scripts/seat.sh capture [lines]   # raw pane read (last <lines>, default 200)
#   bash scripts/seat.sh kill
#
# The session is a clean root bash (PS1='seat# ', no rc files) in /opt/ztorch: state
# (env, cd, functions, background jobs) persists across calls. The operator shares it:
#   powershell.exe -> wsl.exe (kali:kali) -> sudo -s -> tmux attach -t seat
#
# One-shot work that needs NO state should skip this and go direct:
#   wsl.exe -d kali-linux -u root -- bash -lc 'cd /opt/ztorch && /root/vm.sh "hostname"'
#   (Windows seat: bash scripts/win-vm.sh '<cmd>')
#
# Transport note: every tmux line is base64'd and eval'd inside WSL. Raw argv through
# wsl.exe gets word-split/re-expanded by intermediate shells (a '$VAR' in a command
# arrives already expanded), which corrupts exactly the stateful text this session is for.
set -uo pipefail
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"

DISTRO="${ZTORCH_WSL_DISTRO:-kali-linux}"
SEAT="${SEAT_NAME:-seat}"

# sq: single-quote a value for safe embedding in a remote shell line.
sq() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }

# w_line <shell-line>: eval one line inside WSL kali as root, byte-faithful.
# The line rides on STDIN (wsl.exe re-parses argv through the Linux login shell,
# which corrupts quotes/$; /bin/bash -s reads stdin verbatim).
w_line() {
  printf '%s' "$1" | wsl.exe -d "$DISTRO" -u root -- /bin/bash -s
}

_has_session() { w_line "tmux has-session -t $(sq "$SEAT")" >/dev/null 2>&1; }

ensure() {
  if _has_session; then
    echo "seat session '$SEAT' alive"
    return 0
  fi
  # Clean deterministic prompt: PS1='seat# ' with no rc files, so run()'s output
  # framing (echo line / prompt line) is exact. The fancy interactive zsh stays
  # available to the operator in their own shell / attach.
  w_line "tmux new-session -d -s $(sq "$SEAT") -c /opt/ztorch 'exec env PS1=\"seat# \" bash --noprofile --norc'" || return 1
  sleep 1
  echo "seat session '$SEAT' created (root bash @ /opt/ztorch)"
}

run() {
  local c="${1:?need a command}"
  _has_session || { ensure >/dev/null || return 1; }
  w_line "tmux clear-history -t $(sq "$SEAT")"
  w_line "tmux send-keys -t $(sq "$SEAT") -l $(sq "$c")"
  w_line "tmux send-keys -t $(sq "$SEAT") Enter"
  local i=0 pane prev=""
  while [ "$i" -lt 45 ]; do
    sleep 1; i=$((i + 1))
    pane="$(w_line "tmux capture-pane -p -t $(sq "$SEAT") -S -300")"
      if printf '%s\n' "$pane" | tail -3 | grep -q '^seat# *$' && [ "$pane" = "$prev" ]; then
      printf '%s\n' "$pane" | SEAT_CMD="$c" python3 -c '
import os, sys
pane = sys.stdin.read().split("\n")
cmd = os.environ.get("SEAT_CMD", "")[:40]
start, end = 0, len(pane)
for k in range(len(pane) - 1, -1, -1):        # echo line = LAST line carrying the command
    if cmd and cmd in pane[k]:
        start = k + 1; break
for k in range(start, len(pane)):             # output ends at the seat# prompt
    if pane[k].rstrip() == "seat#":
        end = k; break
print("\n".join(pane[start:end]).rstrip())'
      return 0
    fi
    prev="$pane"
  done
  echo "seat: no returning 'seat#' prompt in 45s (long-running? read: bash scripts/seat.sh capture)" >&2
  return 1
}

cmd="${1:-}"; [ $# -gt 0 ] && shift
case "$cmd" in
  ensure)   ensure ;;
  run)      run "${1:?usage: seat.sh run '<command>'}" ;;
  send)     _has_session || { ensure >/dev/null; }
            w_line "tmux send-keys -t $(sq "$SEAT") -l $(sq "${1:?need a command}")"
            w_line "tmux send-keys -t $(sq "$SEAT") Enter" ;;
  capture)  w_line "tmux capture-pane -p -t $(sq "$SEAT") -S -${1:-200}" ;;
  kill)     w_line "tmux kill-session -t $(sq "$SEAT")" 2>/dev/null && echo "seat '$SEAT' killed" ;;
  *)        sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
