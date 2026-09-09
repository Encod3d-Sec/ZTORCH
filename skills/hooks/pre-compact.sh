#!/usr/bin/env bash
# PreCompact hook (steers the compaction summarizer).
#
# Channel semantics (host-internals pass 1, 2026-09-09): at PreCompact, PLAIN STDOUT is
# appended to the summarizer prompt as "Additional Instructions"; the JSON
# additionalContext field is IGNORED at this event, and exit 2 is fail-open ignored. So
# this script must stay PLAIN TEXT (never hook JSON) and steer the summarizer directly.
# The post-compact RE-INJECTION (what the next context actually receives verbatim) lives
# in engagement-init.py's source=="compact" branch: SessionStart(compact) is the only
# channel whose output is injected after compaction.
#
# Fail-open: any python/vault failure still prints the generic directives.
HOOKDIR="$(cd "$(dirname "$0")" && pwd)"
ENG="$(python3 - "$HOOKDIR" <<'PY' 2>/dev/null
import sys
sys.path.insert(0, sys.argv[1])
try:
    import _engagement
    d = _engagement.active_dir()
    if d:
        print(d.rstrip("/").split("/")[-1])
except Exception:
    pass
PY
)"
{
  echo "SUMMARIZER INSTRUCTIONS (what the post-compact context must keep):"
  if [ -n "$ENG" ]; then
    echo "- Active engagement: $ENG (keep the name VERBATIM; it keys targets/<eng>/ paths)."
  fi
  echo "- PRESERVE: Approach.md board phase + every open ([ ]/[~]) row verbatim; each open FIND with its next action; the last offensive.py next move; OOB HIT rows + sink tokens; active/unconfirmed creds by NAME only (redact values); the tmux window map (name -> purpose)."
  echo "- DROP: raw tool output, scan dumps, file listings, narrated prose (one line each at most)."
  echo "- Do NOT inline full state files: the SessionStart(compact) hook re-injects engagement state after compaction."
  echo "- Framework/generic work: one-line pointers to session/hot.md only; no client specifics ever."
} 2>/dev/null
exit 0
