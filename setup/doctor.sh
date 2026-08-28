#!/usr/bin/env bash
# Unified seat doctor -- ONE command, ONE verdict, from either seat:
#
#   bash setup/doctor.sh          # Windows seat (via Git Bash) or WSL seat (auto-detected)
#
# Runs, in order:
#   1. hook registration + interpreters      (setup/install-hooks.sh verify)
#   2. skill links                           (setup/install-skills.sh)
#   3. seat wiring: Windows -> win-seat.sh   |  WSL -> wsl-seat.sh
#   4. VM reachability (fast tier -> bridge fallback)
#   5. campaign driver health                (scripts/campaign-doctor.py)
# Prints each section, then a single ALL GREEN / FIX ABOVE verdict (exit 0/1).
set -uo pipefail
# No global MSYS path-conversion guard here on purpose: it would break nested scripts
# whose embedded Windows-python needs Git Bash automatic /c/... -> C:\... argv
# translation. Each wrapper that talks to wsl.exe guards itself (win-vm/win-qmd/win-seat/vm-ssh).

SD="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
VAULT="$(dirname "$SD")"
IN_WSL=0
[ -n "${WSL_DISTRO_NAME:-}" ] && IN_WSL=1
FAIL=0
section() { echo; echo "== $* =="; }
note_fail() { FAIL=1; }

section "1. hook registration"
bash "$SD/install-hooks.sh" || note_fail

section "2. skill links"
bash "$SD/install-skills.sh" >/dev/null 2>&1 && echo "  [ok] skills linked into .zcode/skills" || { echo "  [FAIL] install-skills.sh"; note_fail; }

if [ "$IN_WSL" = 1 ]; then
  section "3. WSL seat wiring"
  bash "$SD/wsl-seat.sh" || note_fail
else
  section "3. Windows seat wiring"
  bash "$SD/win-seat.sh" || note_fail
fi

section "4. VM reachability"
VM_FAST="$VAULT/scripts/vm-ssh.sh"; VM_BRIDGE="$VAULT/scripts/win-vm.sh"
if [ -x "$VM_FAST" ] && "$VM_FAST" 'true' >/dev/null 2>&1; then
  echo "  [ok] direct ssh (vm-ssh.sh) answers"
elif [ "$IN_WSL" = 1 ]; then
  bash /root/vm.sh 'true' >/dev/null 2>&1 && echo "  [ok] bridge (/root/vm.sh) answers" || { echo "  [FAIL] VM unreachable (vm.sh + vm-ssh.sh)"; note_fail; }
elif [ -x "$VM_BRIDGE" ]; then
  "$VM_BRIDGE" 'true' >/dev/null 2>&1 && echo "  [ok] bridge (win-vm.sh) answers" || { echo "  [FAIL] VM unreachable (win-vm.sh + vm-ssh.sh; check creds/VM boot)"; note_fail; }
else
  echo "  [FAIL] no VM path found"; note_fail
fi

section "5. campaign driver"
CD="$VAULT/scripts/campaign-doctor.py"
command -v cygpath >/dev/null 2>&1 && CD="$(cygpath -w "$CD")"   # Git Bash -> Windows python
python3 "$CD" || note_fail

echo
if [ "$FAIL" = 0 ]; then
  echo "DOCTOR: ALL GREEN -- seat fully wired for engagements."
else
  echo "DOCTOR: INCOMPLETE -- fix the FAIL lines above."
fi
exit $FAIL
