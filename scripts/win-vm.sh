#!/usr/bin/env bash
# Windows-seat bridge to the Kali VM: execs /root/vm.sh inside the WSL kali distro
# (the VMware VM's SSH wrapper). Inside WSL it just runs vm.sh directly, so the same
# entry point works from both seats. Usage: bash scripts/win-vm.sh '<remote cmd>'
set -uo pipefail
CMD="${1:?need a command}"
if [ -f /root/vm.sh ]; then
  exec bash /root/vm.sh "$CMD"
fi
exec wsl.exe -d kali-linux -u root -- bash /root/vm.sh "$CMD"
