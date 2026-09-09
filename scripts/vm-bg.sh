#!/usr/bin/env bash
# Reliable long-running remote tool exec: stage the tool in /dev/shm, run it INSIDE the engagement's
# stabilized tmux window redirected (line-buffered) to /dev/shm/<win>.log, return immediately. Read
# the LOGFILE (never a flaky pane capture). Fixes pspy/linpeas dying over the one-shot SSH bridge.
# Completion signaling: the launch line appends `echo exit=$? > $LOG.done`, so --status can tell
# done/running/hung apart and --wait polls for the marker instead of blind-sleeping.
#   vm-bg.sh <eng> <win> '<remote cmd>'        launch (writes $LOG.done on completion)
#   vm-bg.sh --read   <eng> <win>              cat the log
#   vm-bg.sh --tail   <eng> <win> [n=40]       last n lines of the log
#   vm-bg.sh --status <eng> <win> [idle=180]   'done exit=<c>' | running (Xs since last output) | hung?
#   vm-bg.sh --wait   <eng> <win> [secs=120] [idle=180]  poll $LOG.done up to secs (abort early
#                                                if the log went silent for idle), then cat the log
#   vm-bg.sh --kill   <eng> <win>              C-c the window, kill it, drop log + marker
#   vm-bg.sh --dry-run <eng> <win> '<cmd>'     print the plan, run nothing
set -uo pipefail
VM_SH="${VM_SH:-/root/vm.sh}"
DRY=0; MODE=launch
case "${1:-}" in
  --dry-run) DRY=1; shift;;
  --read)    MODE=read; shift;;
  --tail)    MODE=tail; shift;;
  --status)  MODE=status; shift;;
  --wait)    MODE=wait; shift;;
  --kill)    MODE=kill; shift;;
esac
ENG="${1:?need <eng>}"; WIN="${2:?need <win>}"; CMD="${3:-}"
SESSION="$ENG"; LOG="/dev/shm/${SESSION}-${WIN}.log"
if [ "$MODE" = read ]; then
  bash "$VM_SH" "cat '$LOG' 2>/dev/null || echo '(no log yet: $LOG)'"; exit 0
fi
if [ "$MODE" = tail ]; then
  N="${3:-40}"; bash "$VM_SH" "tail -n $N '$LOG' 2>/dev/null || echo '(no log yet: $LOG)'"; exit 0
fi
if [ "$MODE" = status ]; then
  IDLE="${3:-180}"
  bash "$VM_SH" "if [ -f '$LOG.done' ]; then echo \"done \$(cat '$LOG.done')\"; \
elif [ -f '$LOG' ]; then age=\$(( \$(date +%s) - \$(stat -c %Y '$LOG') )); \
if [ \$age -ge $IDLE ]; then echo \"hung? no output for \${age}s\"; \
else echo \"running (\${age}s since last output)\"; fi; \
else echo 'no log yet'; fi"
  exit 0
fi
if [ "$MODE" = wait ]; then
  SECS="${3:-120}"; IDLE="${4:-180}"
  # idle-watchdog: a log that stopped growing surfaces as hung? instead of sleeping out the
  # full budget (--status's hung condition, re-checked every poll; partial log still catted).
  bash "$VM_SH" "t=0; until [ -f '$LOG.done' ] || [ \$t -ge $SECS ]; do \
if [ -f '$LOG' ]; then age=\$(( \$(date +%s) - \$(stat -c %Y '$LOG') )); \
if [ \$age -ge $IDLE ]; then echo \"hung? no output for \${age}s\"; break; fi; fi; \
sleep 5; t=\$((t+5)); done; \
[ -f '$LOG.done' ] && echo \"done \$(cat '$LOG.done')\"; \
cat '$LOG' 2>/dev/null || echo '(no log: $LOG)'"
  exit 0
fi
if [ "$MODE" = kill ]; then
  bash "$VM_SH" "tmux send-keys -t '$SESSION:$WIN' C-c 2>/dev/null; sleep 1; \
tmux kill-window -t '$SESSION:$WIN' 2>/dev/null; rm -f '$LOG' '$LOG.done'; echo 'killed $SESSION:$WIN'"
  exit 0
fi
# launch: run CMD inside the tmux window, line-buffered, to the /dev/shm log; rm a stale marker first
REMOTE="tmux has-session -t '$SESSION' 2>/dev/null || tmux new-session -d -s '$SESSION'; \
tmux list-windows -t '$SESSION' -F '#{window_name}' | grep -qx '$WIN' || tmux new-window -t '$SESSION' -n '$WIN'; \
rm -f '$LOG.done'; \
tmux send-keys -t '$SESSION:$WIN' \"stdbuf -oL -eL $CMD > $LOG 2>&1; echo exit=\\\$? > $LOG.done\" Enter; echo 'launched -> $LOG (status: vm-bg.sh --status $ENG $WIN)'"
if [ "$DRY" = 1 ]; then
  printf 'DRY-RUN plan:\n  log: %s\n  stage: run in tmux %s:%s via stdbuf, redirect to /dev/shm + .done marker\n  remote: %s\n' "$LOG" "$SESSION" "$WIN" "$REMOTE"
  exit 0
fi
bash "$VM_SH" "$REMOTE" || { echo "vm-bg: launch failed (VM unreachable via $VM_SH?)" >&2; exit 1; }
