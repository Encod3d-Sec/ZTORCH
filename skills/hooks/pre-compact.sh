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
# Compaction ledger: one JSON line per compaction to targets/<eng>/.compact-log.jsonl
# (ts, driver state, board counts, gates pending). Correlating compactions against
# driver state is how a compaction-induced doom loop becomes visible (same
# asset_cursor/dry_streak recurring across compactions = the loop re-entering the
# same move post-compact). SILENT - stdout here is the summarizer's instruction
# channel; this only writes the private per-engagement file. Fail-open.
python3 - "$HOOKDIR" <<'PY' 2>/dev/null
import importlib.util, json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
try:
    import _engagement
    d = _engagement.active_dir()
    if d:
        d = Path(d)   # board/state helpers take a Path, active_dir returns str
        sys.path.insert(0, str(Path(_engagement.VAULT) / "scripts"))  # offensive_index dep
        spec = importlib.util.spec_from_file_location(
            "offensive", Path(_engagement.VAULT) / "scripts" / "offensive.py")
        off = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(off)
        state = json.loads((d / ".offensive.json").read_text())
        rows = off.read_board(d)
        if state.get("foothold"):
            rows += off.read_board_4b(d)
        counts = {"open": 0, "closed": 0, "stuck": 0}
        gates = 0
        for r in rows:
            s = off._status_of(r)
            if s in ("[ ]", "[~]"):
                counts["open"] += 1
                if not (r.get("arsenal") or "").strip():
                    gates += 1   # G1 pending; ponytail: G2 half skipped (needs .events walk)
            elif s == "[x]":
                counts["closed"] += 1
            elif s in ("[?]", "[!]"):
                counts["stuck"] += 1
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "pass": state.get("pass", 0),
               "asset_cursor": state.get("asset_cursor"),
               "dry_streak": state.get("dry_streak", 0),
               "last_row": (state.get("last_move") or {}).get("row"),
               "board": counts, "gates_pending": gates}
        with open(d / ".compact-log.jsonl", "a") as fh:
            fh.write(json.dumps(rec) + "\n")
except Exception:
    pass
PY
{
  echo "SUMMARIZER INSTRUCTIONS (what the post-compact context must keep):"
  if [ -n "$ENG" ]; then
    echo "- Active engagement: $ENG (keep the name VERBATIM; it keys targets/<eng>/ paths)."
  fi
  echo "- PRESERVE: Approach.md board phase + every open ([ ]/[~]) row verbatim; each open FIND with its next action; the last offensive.py next move; OOB HIT rows + sink tokens (verbatim); active/unconfirmed creds by NAME only (redact values); the tmux window map (name -> purpose); exact working commands, endpoints, file paths, and service versions."
  echo "- DROP: raw tool output, scan dumps, file listings, narrated prose (one line each at most)."
  echo "- Do NOT inline full state files: the SessionStart(compact) hook re-injects engagement state after compaction."
  echo "- Framework/generic work: one-line pointers to session/hot.md only; no client specifics ever."
} 2>/dev/null
exit 0
