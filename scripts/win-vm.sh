#!/usr/bin/env bash
# Windows-seat bridge to the Kali attack VM.
#
# The agent seat is ZCode on Windows (Git Bash); the VM toolchain lives in WSL
# kali-linux (root): /root/vm.sh + /root/creds.txt, sshpass, tmux-on-VM. This
# wrapper execs vm.sh inside WSL so ONE command form works from the Windows seat:
#
#   bash scripts/win-vm.sh '<remote bash command>'
#   bash scripts/win-vm.sh 'id; hostname; ip -4 addr'
#
# It is also the VM_SH implementation for every repo driver on Windows:
#   VM_SH="$(pwd)/scripts/win-vm.sh" bash scripts/win-rsh.sh <session> '<ps command>'
#   VM_SH="$(pwd)/scripts/win-vm.sh" bash scripts/capture.sh req <eng>
#
# MSYS_NO_PATHCONV: Git Bash rewrites leading-slash arguments (e.g. a remote
# command starting with /etc/... or /root/...) into Windows paths before they
# reach the native wsl.exe. Disabling it here protects every invocation.
set -euo pipefail
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"
exec wsl.exe -d kali-linux -u root -- bash /root/vm.sh "$@"
