#!/usr/bin/env bash
# A/B benchmark runner: measure what one harness run costs (tokens, activity,
# outcome) so the upgraded branch can be compared against the old one on the
# same CTF. Measurement lives OUTSIDE git (session/ is gitignored), and
# `install` copies this script + cost-log.py to ~/.ztorch-bench/ so the OLD
# branch measures with the identical tool.
#
# Usage:
#   bash scripts/harness-bench.sh start --label new-harness     # stamp the window start
#   ... run the CTF engagement normally (any branch) ...
#   bash scripts/harness-bench.sh stop --eng ctf-x              # collect + append CSV row
#   bash scripts/harness-bench.sh report                        # print all rows
#   bash scripts/harness-bench.sh install                       # copy to ~/.ztorch-bench/
# On the OLD branch:   bash ~/.ztorch-bench/harness-bench.sh start --label old-harness
set -uo pipefail
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
VAULT="$(cd "$HERE/.." && pwd)"
BENCH="$VAULT/session/bench"
MARKER="$BENCH/marker.json"
RES="$BENCH/results.jsonl"
mkdir -p "$BENCH"

cmd="${1:-}"; shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --label) LABEL="$2"; shift 2 ;;
    --eng) ENG="$2"; shift 2 ;;
    *) shift ;;
  esac
done
LABEL="${LABEL:-unlabeled}"

case "$cmd" in
  start)
    SINCE=$(date -u +%Y-%m-%dT%H:%M:%S)
    GIT_HEAD=$(git -C "$VAULT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "nogit")
    printf '{"since": "%s", "label": "%s", "branch": "%s"}\n' "$SINCE" "$LABEL" "$GIT_HEAD" > "$MARKER"
    echo "bench window OPEN: label=$LABEL branch=$GIT_HEAD since=$SINCE"
    echo "run the engagement now; close it with: harness-bench.sh stop --eng <name>"
    ;;
  stop)
    [ -f "$MARKER" ] || { echo "no open window (run: harness-bench.sh start --label X)" >&2; exit 2; }
    ENG="${ENG:?stop needs --eng <engagement-name>}"
    SINCE=$(python3 -c "import json;print(json.load(open('$MARKER'))['since'])")
    LABEL=$(python3 -c "import json;print(json.load(open('$MARKER'))['label'])")
    BRANCH=$(python3 -c "import json;print(json.load(open('$MARKER'))['branch'])")
    export ZT_COST_VAULT="$VAULT"
    OUT=$(python3 "$HERE/cost-log.py" --eng "$ENG" --since "$SINCE" --json)
    python3 - "$OUT" "$RES" "$LABEL" "$BRANCH" "$ENG" <<'PY'
import json, sys
out, res_path, label, branch, eng = sys.argv[1:6]
d = json.loads(out)
t, a, c = d["tokens"], d["activity"], d["outcome"]
row = {"ts": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
       "label": label, "branch": branch, "eng": eng,
       "tokens_total": t["total"], "tokens_input": t["input"], "tokens_output": t["output"],
       "tokens_cache_read": t["cache_read"], "tokens_cache_write": t["cache_write"],
       "subagent_tokens": t["subagent_tokens"], "turns": t["turns"],
       "agent_launches": a["agent_launches"], "bash_commands": a["bash_commands"],
       "tool_calls": a["tool_calls"], "skills_fired": a["skills_fired"],
       "out_bytes": a["out_bytes"], "flags": c["flags"], "finds": c["finds"],
       "status": c["status"]}
with open(res_path, "a") as f:
    f.write(json.dumps(row) + "\n")
print("row appended:", json.dumps(row))
PY
    python3 "$HERE/cost-log.py" --eng "$ENG" --since "$SINCE"
    rm -f "$MARKER"
    echo "bench window CLOSED (full row in $RES)"
    ;;
  report)
    python3 - "$BENCH" <<'PY'
import json, os, sys
bench = sys.argv[1]
def rows(name):
    p = os.path.join(bench, name)
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p) if l.strip()]
def table(rs):
    if not rs:
        return ["  (none yet)"]
    cols = ["ts", "label", "branch", "eng", "tokens_total", "tokens_input",
            "tokens_output", "subagent_tokens", "turns", "agent_launches",
            "bash_commands", "tool_calls", "flags", "finds", "status"]
    cols = [c for c in cols if any(c in r for r in rs)]
    w = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rs)) for c in cols}
    out = ["  " + "  ".join(c.ljust(w[c]) for c in cols)]
    for r in rs:
        out.append("  " + "  ".join(str(r.get(c, "")).ljust(w[c]) for c in cols))
    return out
print("== per-session auto log (session/bench/auto.jsonl) ==")
print("\n".join(table(rows("auto.jsonl"))))
print()
print("== A/B runs (session/bench/results.jsonl) ==")
print("\n".join(table(rows("results.jsonl"))))
PY
    ;;
  install)
    mkdir -p ~/.ztorch-bench
    cp "$HERE/harness-bench.sh" "$HERE/cost-log.py" ~/.ztorch-bench/
    echo "installed to ~/.ztorch-bench/ - on the OLD branch run:"
    echo "  bash ~/.ztorch-bench/harness-bench.sh start --label old-harness"
    ;;
  *)
    sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
