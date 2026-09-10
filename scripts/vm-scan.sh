#!/usr/bin/env bash
# Launch a scan inside a named tmux tab on the Kali VM (root, persistent).
# ONE tmux session per engagement; one window (tab) per PARALLEL scan. By default the window is
# named after the target (sanitize(<target>)), so two scans on the SAME host collide in one tab.
# Reuse of an existing window name is PROMPT-GATED: keystrokes only go into a pane that sits at a
# shell prompt again; a LIVE pane gets a -2/-3... suffixed window instead (sending keys into a
# running scan clobbers it - a live feroxbuster died exactly that way once).
# For parallel scans on one host, give each its OWN window with --win <tool> (e.g. --win nuclei):
# same session, distinct window, NO session-per-scan proliferation. (Never bump the SESSION name
# just to avoid a collision -- that scatters tabs across sessions and breaks one-session recon.)
# Dots/colons/spaces in a name -> '-' (they collide with tmux session:window.pane).
# Windows are targeted by stable window_id so the sanitized name never has to be re-parsed.
# Usage: bash vm-scan.sh [--dry-run] [--win <window-name>] <session> <target> <scan-command...>
set -uo pipefail

DRY=0; WIN=""
while [ $# -gt 0 ]; do
  case "${1:-}" in
    --dry-run) DRY=1; shift;;
    --win) WIN="${2:?--win needs a name}"; shift 2;;
    *) break;;
  esac
done
SESSION="${1:?need <session>}"; TARGET="${2:?need <target>}"; shift 2
SCAN="$*"; : "${SCAN:?need <scan-command...>}"
# transport-wrap the scan: base64 charset survives BOTH parse layers (local heredoc build +
# VM-side bash) unchanged, so a nested quote in SCAN ('awk "{print \$1}"') can no longer
# shatter the send-keys arg or kill the whole remote script (an unbalanced quote aborted
# session setup too, and the local tail still exited 0 = silent no-scan). Decoded INSIDE
# the command substitution, so the PANE still receives the readable command (the card's
# content); the RC echo stays outside the decoded text.
B64="$(printf '%s' "$SCAN" | base64 -w0)"

# sanitize: . : and space -> - . Window name = --win override if given, else the target.
NAME="$(printf '%s' "${WIN:-$TARGET}" | tr './: ' '----')"

# remote tmux script: ensure session, pick a free-or-idle window (prompt-gated reuse),
# capture id, send scan.
read -r -d '' REMOTE <<EOF || true
tmux has-session -t $SESSION 2>/dev/null || tmux new-session -d -s $SESSION -n main -x 220 -y 50
# force a WIDE detached geometry so tools (nmap -sV, ffuf) don't soft-wrap output at 80 cols,
# which shows up as mid-line breaks in the screenshot card. window-size manual keeps it fixed.
tmux set-option -t $SESSION window-size manual 2>/dev/null
tmux resize-window -t $SESSION -x 220 -y 50 2>/dev/null
WID=""; WINNAME=""; REUSED=0
# window pick: reuse an existing name ONLY when its pane is back at a shell prompt; a live
# pane moves to the next -N suffix (new window). Never send keys into a running scan.
for N in $NAME $NAME-2 $NAME-3 $NAME-4 $NAME-5; do
  C="\$(tmux list-windows -t '$SESSION' -F '#{window_id} #{window_name}' | awk -v n="\$N" '\$2==n{print \$1; exit}')"
  if [ -z "\$C" ]; then WID="\$(tmux new-window -t '$SESSION' -P -F '#{window_id}' -n "\$N")"; WINNAME="\$N"; break; fi
  if tmux capture-pane -t "\$C" -p 2>/dev/null | grep -vE '^[[:space:]]*\$' | tail -1 | grep -qE '└─#|[#\$][[:space:]]*\$'; then
    WID="\$C"; WINNAME="\$N"; REUSED=1; break
  fi
done
if [ -z "\$WID" ]; then
  echo "vm-scan: refuse - windows '$NAME'..'$NAME-5' all hold LIVE panes; card or kill one first (or use --win <distinct>)"
  exit 1
fi
# the __ZT_RC=$?__ echo lands in the pane as the scan's last output line: autocard
# greps it so a finished tab cards as exit=N (a died scan is visible, not just "done")
tmux send-keys -t "\$WID" "\$(printf %s $B64 | base64 -d); echo __ZT_RC=\$?__" C-m
echo "window=\$WID name=\$WINNAME session=$SESSION reused=\$REUSED"
EOF

if [ "$DRY" = "1" ]; then
  printf '%s\n' "$REMOTE"
  exit 0
fi

VM_SH="${VM_SH:-/root/vm.sh}"
OUT="$(bash "$VM_SH" "$REMOTE")"
printf '%s\n' "$OUT"
if printf '%s' "$OUT" | grep -q 'vm-scan: refuse'; then
  exit 1
fi
# dead-bridge / remote-syntax-abort check: the remote script ALWAYS echoes the window= line
# on success; without this a VM-down or heredoc abort still printed the tip and exited 0
# (silent no-scan - the launch-side twin of the pass-10 RC-trailer gap).
if ! printf '%s' "$OUT" | grep -q 'window='; then
  echo "vm-scan: bridge failed - no window= confirmation (VM down or remote error above). No scan was launched." >&2
  exit 1
fi
ACTUAL="$(printf '%s' "$OUT" | grep -oE 'name=[^ ]+' | head -1 | cut -d= -f2)"
if printf '%s' "$OUT" | grep -q 'reused=1'; then
  # reuse is prompt-gated now (keys only enter an idle shell), so this is informational
  echo "note: reused tab '${ACTUAL:-$NAME}' at an idle prompt. Parallel scans on one host: give each its own --win <tool>." >&2
fi
# reminder at the point of action: card this tab into recon/ WHEN it finishes (every tool, even empty)
echo "tip: card it when done -> scripts/capture.sh recon $SESSION <slug> ${ACTUAL:-$NAME}" >&2
