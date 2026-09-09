#!/usr/bin/env bash
# Run ONE command in an engagement's reverse-shell tmux tab and return its clean output.
#
# Fixes the recurring drift of hand-driving a reverse shell with `tmux send-keys` +
# `capture-pane` and losing turns to shell-quoting (base64 wrappers, nested quotes). The
# command is base64-wrapped (so ANY quoting/metachars survive the vm.sh -> ssh -> tmux
# bridge), run between unique markers in the shell tab, and only the output between the
# markers is returned.
#
# Usage: bash vm-rsh.sh [--win shell] [--timeout 40] [--create] <session> <command...>
#   bash vm-rsh.sh <eng> 'strings /srv/x | grep -i clearance'
#   bash vm-rsh.sh --win shell <eng> 'cat /root/root.txt'
#   bash vm-rsh.sh --create --win jq1 <eng> 'curl -s http://x/api | jq .'   # window auto-created
#
# Assumes a reverse shell is already live in tmux window <session>:<win> (default 'shell',
# the window scripts/vm-scan.sh --win shell created for the nc listener). With --create the
# session/window is created if missing (lands at a shell prompt), so one call creates the
# named window, runs the command, and returns clean output. VM_SH overridable
# for tests. Fail-soft: prints nothing + exits 1 if the end marker never appears.
set -uo pipefail
VM_SH="${VM_SH:-/root/vm.sh}"
WIN="shell"; TO=40; CREATE=0
while [ $# -gt 0 ]; do
  case "${1:-}" in
    --win) WIN="${2:?--win needs a name}"; shift 2;;
    --timeout) TO="${2:?--timeout needs seconds}"; shift 2;;
    --create) CREATE=1; shift;;
    *) break;;
  esac
done
SESSION="${1:?need <session>}"; shift
CMD="$*"; : "${CMD:?need <command...>}"

# --create: make vm-rsh the generic named-window executor (one call: create the
# session/window if missing, run, return clean output). Same round-trip count as
# one-shot SSH, but the pane stays for operator review + autocard.
if [ "$CREATE" = 1 ]; then
  bash "$VM_SH" "tmux has-session -t $SESSION 2>/dev/null || tmux new-session -d -s $SESSION; \
tmux list-windows -t $SESSION -F '#{window_name}' | grep -qx -- '$WIN' || tmux new-window -t $SESSION -n '$WIN'" >/dev/null 2>&1
fi

# Fixed markers: a real command will not emit these ALONE on a line; the extractor takes the
# LAST start-marker line and the first end-marker line after it, so a prior run's markers still
# in scrollback do not confuse it.
# ponytail: fixed markers (not per-run random) so the output is trivially testable; matching a
# marker only when it is ALONE on its line covers echo-on PTYs (the shell echoes the whole
# command line, markers embedded and narrow-wrapped) and scrollback collisions.
START='__RSH_START_9f3a__'; END='__RSH_END_9f3a__'
B64="$(printf '%s' "$CMD" | base64 | tr -d '\n')"
SEND="echo $START; echo $B64 | base64 -d | bash 2>&1; echo $END"

# send the wrapped command into the shell tab
bash "$VM_SH" "tmux send-keys -t $SESSION:$WIN '$SEND' Enter" >/dev/null 2>&1

# poll the pane until the end marker shows up (or timeout). Circuit-breaker: 3 CONSECUTIVE
# transport failures (vm.sh nonzero - VM down/half-dead bridge) abort the poll instead of
# burning the whole TO budget on blind retries; a successful poll resets the count. The
# window is kept so a recovered bridge resumes where it left off.
PANE=""; FAILS=0
for _ in $(seq 1 "$TO"); do
  PANE="$(bash "$VM_SH" "tmux capture-pane -pS -600 -t $SESSION:$WIN" 2>/dev/null)"; RC=$?
  if [ "$RC" -ne 0 ]; then
    FAILS=$((FAILS+1))
    if [ "$FAILS" -ge 3 ]; then
      echo "vm-rsh: bridge failed ${FAILS}x during poll (VM down?); aborting - window $SESSION:$WIN kept for recovery" >&2
      exit 1
    fi
  else
    FAILS=0
  fi
  # break only on the EXECUTED end marker (alone on its line); an echo-on PTY also shows the
  # marker embedded in the echoed command line, which must not end the poll before output lands.
  printf '%s\n' "$PANE" | grep -qE "^ *$END *$" && break
  sleep 1
done

# extract output between the LAST start-marker LINE and the first end-marker line after it.
# Matching a marker only when it is alone on its line (l.strip() == marker) means the shell-
# echoed command line, and any narrow-wrap fragment of it, is never taken for a boundary, so
# an unstabilized echo-on PTY works without stabilization. ponytail: alone-on-line replaces the
# old rfind + heuristic cmd-line drop; belt of stty -echo skipped, the extractor is the guarantee.
printf '%s' "$PANE" | python3 -c '
import sys
t = sys.stdin.read()
s, e = "'"$START"'", "'"$END"'"
lines = t.split("\n")
starts = [n for n, l in enumerate(lines) if l.strip() == s]
if not starts:
    sys.exit(1)
i = starts[-1]
after = [n for n, l in enumerate(lines) if n > i and l.strip() == e]
if not after:
    sys.exit(1)
out = lines[i+1:after[0]]
while out and not out[0].strip():   # trim leading blanks
    out.pop(0)
while out and not out[-1].strip():   # trim trailing blanks
    out.pop()
print("\n".join(out))
'
