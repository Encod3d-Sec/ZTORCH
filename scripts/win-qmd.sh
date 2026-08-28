#!/usr/bin/env bash
# Windows-seat qmd shim: run the WSL kali (root) qmd against this vault, with the
# vault path mapped to its /mnt/<drive> form. Native qmd does not exist on the
# Windows seat; this is what wiki-query.sh and the wiki-reindex hook fall back to.
#
#   bash scripts/win-qmd.sh update
#   bash scripts/win-qmd.sh query "jenkins rce exploit"
#   bash scripts/win-qmd.sh -k "CVE-2023-23752"        # (subcommand passthrough)
set -euo pipefail
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"

VAULT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
# C:\...\vault -> /mnt/c/... (cygpath gives /c/...; WSL wants /mnt/c/...)
POSIX_VAULT="$(cygpath -u "$VAULT")"
drive="$(printf '%s' "${POSIX_VAULT:1:1}" | tr 'A-Z' 'a-z')"
WSL_VAULT="/mnt/$drive/${POSIX_VAULT:3}"
[ -n "$WSL_VAULT" ] || { echo "win-qmd: cannot map vault path" >&2; exit 2; }

DISTRO="${ZTORCH_WSL_DISTRO:-kali-linux}"
exec wsl.exe -d "$DISTRO" -u root -- /usr/bin/env \
  QMD_VAULT="$WSL_VAULT" HF_HUB_DISABLE_PROGRESS_BARS=1 qmd "$@"
