#!/usr/bin/env bash
# Per-device: expose the vault's skills to ZCode's skill picker by linking each
# SKILL.md-bearing directory into <vault>/.zcode/skills/ (a workspace skill root).
# The hunt skills also auto-fire via the hunt-trigger.py hook (keyword -> invoke);
# this makes them ALSO manually invocable from the skill picker. Idempotent.
#
#   bash setup/install-skills.sh
#
# Symlinks on Linux/macOS; directory junctions on Windows (no admin/dev-mode
# needed). Restart ZCode (or start a new session) afterwards so it rescans.
set -euo pipefail

VAULT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
DEST="$VAULT/.zcode/skills"
mkdir -p "$DEST"

IS_WINDOWS=0
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) IS_WINDOWS=1 ;;
esac

n=0
while IFS= read -r skill; do
  d="$(dirname "$skill")"
  name="$(basename "$d")"
  link="$DEST/$name"
  # Replace any stale copy (real dir, dead link, or junction pointing elsewhere)
  # so the vault stays the single source of truth.
  if [ -e "$link" ] || [ -L "$link" ]; then
    if [ "$IS_WINDOWS" = 1 ]; then
      wlink="$(cygpath -w "$link")"
      cmd //c rmdir //q "$wlink" >/dev/null 2>&1 || rm -rf "$link"
    else
      rm -rf "$link"
    fi
    echo "replaced stale link: $name"
  fi
  if [ "$IS_WINDOWS" = 1 ]; then
    wlink="$(cygpath -w "$link")"
    wtarget="$(cygpath -w "$d")"
    cmd //c mklink //J "$wlink" "$wtarget" >/dev/null
  else
    ln -sfn "$d" "$link"
  fi
  echo "linked $name"
  n=$((n + 1))
done < <(find "$VAULT/skills" -name SKILL.md)

echo "linked $n vault skills into $DEST"
echo "Restart ZCode or start a new session to see them (hunt-*, research, disclosure, ...)."
