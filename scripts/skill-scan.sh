#!/usr/bin/env bash
# SkillSpector sweep over every vault skill dir.
# Why per-dir: skillspector --recursive only treats depth-1 children of the target as
# skills; the vault nests them (hunt/<name>, workflow/<group>/<name>), so we scan each
# SKILL.md's parent ourselves.
# Baseline: uses .skillspector-baseline.yaml at vault root automatically when present,
# so re-scans surface only NEW findings. SHOW_SUPPRESSED=1 to list accepted ones too.
set -euo pipefail
SELF=$(readlink -f "$0")
ROOT=$(cd "$(dirname "$SELF")/.." && pwd)
OUT="/tmp/ztorch-skill-scan"
BASELINE_FLAG=()
[ -f "$ROOT/.skillspector-baseline.yaml" ] && BASELINE_FLAG=(--baseline "$ROOT/.skillspector-baseline.yaml")
[ "${SHOW_SUPPRESSED:-0}" = "1" ] && BASELINE_FLAG+=(--show-suppressed)

rm -rf "$OUT"; mkdir -p "$OUT"
cd "$ROOT/skills"
for d in $(find . -name SKILL.md -printf '%h\n' | sort); do
  name=$(echo "$d" | sed 's|^\./||; s|/|__|g')
  skillspector scan "$d" --no-llm --format json "${BASELINE_FLAG[@]}" \
    --output "$OUT/$name.json" >/dev/null 2>&1 || true
done

python3 - "$OUT" <<'EOF'
import json, glob, os, sys
out = sys.argv[1]
rows = []
for f in sorted(glob.glob(out + '/*.json')):
    d = json.load(open(f))
    ra = d.get('risk_assessment') or {}
    issues = d.get('issues') or []
    rows.append((os.path.basename(f)[:-5].replace('__', '/'), ra.get('score', 0),
                 ra.get('severity') or '-', len(issues)))
rows.sort(key=lambda r: (-r[1], r[0]))
print("%-40s %5s %9s %12s" % ('skill', 'score', 'severity', 'new-findings'))
for r in rows:
    flag = '  <== REVIEW' if r[3] else ''
    print("%-40s %5s %9s %12s%s" % (r[0], r[1], r[2], r[3], flag))
total = sum(r[3] for r in rows)
print()
print("%d/%d skills with new findings, %d total" % (sum(1 for r in rows if r[3]), len(rows), total))
sys.exit(1 if total else 0)
EOF
