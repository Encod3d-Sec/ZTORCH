#!/usr/bin/env bash
# Reliable long-running remote tool exec: stage the tool in /dev/shm, run it INSIDE the engagement's
# stabilized tmux window redirected (line-buffered) to /dev/shm/<win>.log, return immediately. Read
# the LOGFILE (never a flaky pane capture). Fixes pspy/linpeas dying over the one-shot SSH bridge.
# Completion signaling: the launch line appends `echo exit=$? > $LOG.done`, so --status can tell
# done/running/hung apart and --wait polls for the marker instead of blind-sleeping.
#   vm-bg.sh <eng> <win> '<remote cmd>'        launch (writes $LOG.done on completion)
#   vm-bg.sh --read   <eng> <win>              cat the log
#   vm-bg.sh --tail   <eng> <win> [n=40]       last n lines of the log
#   vm-bg.sh --delta  <eng> <win>              print only NEW bytes since last --delta
#                                              (byte-offset .off file; --read/--tail unaffected)
#   vm-bg.sh --status <eng> <win> [idle]       'done exit=<c>' | running (Xs since last output) |
#                                              hung? -- idle defaults to the launch-time
#                                              per-tool hint in $LOG.idle (pspy/tail-f 60s,
#                                              scan/crack 600s, else 180s), NOT one global 180
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
  --delta)   MODE=delta; shift;;
  --status)  MODE=status; shift;;
  --wait)    MODE=wait; shift;;
  --kill)    MODE=kill; shift;;
esac
ENG="${1:?need <eng>}"; WIN="${2:?need <win>}"; CMD="${3:-}"
SESSION="$ENG"; LOG="/dev/shm/${SESSION}-${WIN}.log"
# log watchdog, reads only: >200MB gets ONE warning line naming the size; truncation is
# the operator's call, never automatic. Prefixed into read/delta/status remote scripts.
WARN="wsz=\$(stat -c %s '$LOG' 2>/dev/null || echo 0); [ \"\$wsz\" -gt 209715200 ] && echo \"vm-bg: WARNING: '$LOG' is \$((wsz/1048576))MB (>200MB) - consider truncating it\"; "
if [ "$MODE" = read ]; then
  bash "$VM_SH" "${WARN}cat '$LOG' 2>/dev/null || echo '(no log yet: $LOG)'"; exit 0
fi
if [ "$MODE" = tail ]; then
  N="${3:-40}"; bash "$VM_SH" "tail -n $N '$LOG' 2>/dev/null || echo '(no log yet: $LOG)'"; exit 0
fi
if [ "$MODE" = delta ]; then
  # byte-offset incremental read (clone pattern: task-output delta). $LOG.off holds the
  # offset already consumed; prints only NEW bytes and advances it. --read/--tail never
  # touch .off, so a full re-read is always available. A vanished log with a leftover .off
  # (VM reboot / /dev/shm wipe) says so once and drops the offset, so the next run starts
  # fresh instead of silently reading nothing forever.
  bash "$VM_SH" "${WARN}off=\$(cat '$LOG.off' 2>/dev/null || echo 0); sz=\$(stat -c %s '$LOG' 2>/dev/null || echo 0); \
if [ ! -f '$LOG' ] && [ -f '$LOG.off' ]; then echo 'log vanished (VM reboot or /dev/shm wipe) - offset reset'; rm -f '$LOG.off'; \
elif [ \"\$sz\" -gt \"\$off\" ]; then tail -c +\$((off+1)) '$LOG'; echo \$sz > '$LOG.off'; \
else echo \"(no new output; \$sz bytes total)\"; fi"
  exit 0
fi
if [ "$MODE" = status ]; then
  # idle: explicit arg > launch-time $LOG.idle hint > 180. Session-gone clause: no tmux
  # session AND no .done marker = the VM rebooted or the session was killed mid-run;
  # say so instead of a misleading "running" off a stale log mtime.
  IDLE="${3:-}"
  HINT="\$(cat '$LOG.idle' 2>/dev/null || echo 180)"
  bash "$VM_SH" "${WARN}idle=${IDLE:-$HINT}; \
if [ -f '$LOG.done' ]; then echo \"done \$(cat '$LOG.done')\"; \
elif ! tmux has-session -t '$SESSION' 2>/dev/null; then echo 'session gone (VM reboot or kill) - log is stale, last lines:'; tail -n 5 '$LOG' 2>/dev/null; \
elif [ -f '$LOG' ]; then age=\$(( \$(date +%s) - \$(stat -c %Y '$LOG') )); \
if [ \$age -ge \$idle ]; then echo \"hung? no output for \${age}s (idle hint \${idle}s)\"; \
else echo \"running (\${age}s since last output)\"; fi; \
else echo 'no log yet'; fi"
  exit 0
fi
if [ "$MODE" = wait ]; then
  SECS="${3:-120}"
  # idle: explicit arg > $LOG.idle hint (see --status) > 180.
  HINT="\$(cat '$LOG.idle' 2>/dev/null || echo 180)"
  IDLE="${4:-}"
  # idle-watchdog: a log that stopped growing surfaces as hung? instead of sleeping out the
  # full budget. Suspend detector (clone pattern: tick-gap): if a `sleep 5` took much longer
  # wall-clock, the WSL/VM side was SUSPENDED -- log-mtime ages are garbage across the gap
  # and the budget must not burn while frozen, so the frozen time is subtracted back out.
  bash "$VM_SH" "idle=${IDLE:-$HINT}; start=\$(date +%s); end=\$((start + $SECS)); \
until [ -f '$LOG.done' ] || [ \$(date +%s) -ge \$end ]; do \
if [ -f '$LOG' ]; then age=\$(( \$(date +%s) - \$(stat -c %Y '$LOG') )); \
if [ \$age -ge \$idle ]; then echo \"hung? no output for \${age}s\"; break; fi; fi; \
s=\$(date +%s); sleep 5; e=\$(date +%s); gap=\$((e - s)); \
if [ \$gap -gt 35 ]; then echo \"(suspend detected: \$gap s wall for a 5 s sleep - log-age verdicts unreliable across the gap)\"; \
end=\$((end + gap - 5)); fi; done; \
[ -f '$LOG.done' ] && echo \"done \$(cat '$LOG.done')\"; \
cat '$LOG' 2>/dev/null || echo '(no log: $LOG)'"
  exit 0
fi
if [ "$MODE" = kill ]; then
  bash "$VM_SH" "tmux send-keys -t '$SESSION:$WIN' C-c 2>/dev/null; sleep 1; \
tmux kill-window -t '$SESSION:$WIN' 2>/dev/null; rm -f '$LOG' '$LOG.done' '$LOG.off' '$LOG.idle'; echo 'killed $SESSION:$WIN'"
  exit 0
fi
# launch: run CMD inside the tmux window, line-buffered, to the /dev/shm log; rm a stale marker first.
# Idle hint ladder (clone pattern: 3x the tool's own heartbeat): a pspy/tail -f stream is silent
# for minutes BY DESIGN (60s), a scan/crack run prints progress rarely (600s), default 180s.
# Written to $LOG.idle at launch so --status/--wait judge silence per tool class, not globally.
case "$CMD" in
  *pspy*|*"tail -f"*|*"tail -F"*) IDLE_HINT=60;;
  *nmap*|*masscan*|*hashcat*|*john*|*feroxbuster*|*ffuf*|*nuclei*|*gobuster*|*sqlmap*) IDLE_HINT=600;;
  *) IDLE_HINT=180;;
esac
REMOTE="tmux has-session -t '$SESSION' 2>/dev/null || tmux new-session -d -s '$SESSION'; \
tmux list-windows -t '$SESSION' -F '#{window_name}' | grep -qx '$WIN' || tmux new-window -t '$SESSION' -n '$WIN'; \
rm -f '$LOG.done'; echo $IDLE_HINT > '$LOG.idle'; \
tmux send-keys -t '$SESSION:$WIN' \"stdbuf -oL -eL $CMD > $LOG 2>&1; echo exit=\\\$? > $LOG.done\" Enter; echo 'launched -> $LOG (status: vm-bg.sh --status $ENG $WIN)'"
if [ "$DRY" = 1 ]; then
  printf 'DRY-RUN plan:\n  log: %s\n  idle hint: %ss\n  stage: run in tmux %s:%s via stdbuf, redirect to /dev/shm + .done marker\n  remote: %s\n' "$LOG" "$IDLE_HINT" "$SESSION" "$WIN" "$REMOTE"
  exit 0
fi
# single jittered relaunch (clone pattern), not a retry loop: a transient bridge hiccup gets ONE
# immediate second try with a 1-3s jitter so two agents don't stampede in lockstep. The abort
# line is followed by the last 512 bytes of the retry stderr (the WHY the bridge died).
ERRF="$(mktemp)"; trap 'rm -f "$ERRF"' EXIT
if ! bash "$VM_SH" "$REMOTE" 2>"$ERRF"; then
  cat "$ERRF" >&2
  sleep "1.$((RANDOM % 3))"
  bash "$VM_SH" "$REMOTE" 2>"$ERRF" || { echo "vm-bg: launch failed twice (VM unreachable via $VM_SH?)" >&2; tail -c 512 "$ERRF" >&2; exit 1; }
fi
