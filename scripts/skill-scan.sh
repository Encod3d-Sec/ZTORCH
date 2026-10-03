#!/usr/bin/env bash
# SkillSpector sweep over skill dirs.
# Default: vault skills/ against .skillspector-baseline.yaml, INCREMENTAL (only skill
# dirs with files newer than session/.skill-scan-stamp; --all forces a full sweep).
# --root <dir>: one-shot audit of a THIRD-PARTY tree (e.g. ~/.claude/plugins) - full
# scan, no baseline, HIGH/CRITICAL findings printed for triage. Exit 1 = review needed.
# Why per-dir: skillspector --recursive only treats depth-1 children of the target as
# skills; nested layouts (hunt/<name>, plugins/<mp>/<plugin>/skills/<name>) need this.
set -euo pipefail
SELF=$(readlink -f "$0")
ROOT=$(cd "$(dirname "$SELF")/.." && pwd)

FULL=0; SCAN_ROOT="$ROOT/skills"
while [ $# -gt 0 ]; do
  case "$1" in
    --all) FULL=1 ;;
    --root) SCAN_ROOT=$2; FULL=1; shift ;;
    *) echo "usage: skill-scan.sh [--all] [--root <dir>]"; exit 2 ;;
  esac
  shift
done

VAULT_RUN=0
[ "$SCAN_ROOT" = "$ROOT/skills" ] && VAULT_RUN=1
OUT="/tmp/ztorch-skill-scan"
[ "$VAULT_RUN" = 0 ] && OUT="/tmp/ztorch-skill-scan-ext"
BASELINE_FLAG=()
STAMP="$ROOT/session/.skill-scan-stamp"
if [ "$VAULT_RUN" = 1 ] && [ -f "$ROOT/.skillspector-baseline.yaml" ]; then
  BASELINE_FLAG=(--baseline "$ROOT/.skillspector-baseline.yaml")
  INSTALLED=$(skillspector --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
  PINNED=$(grep -E '^scanner_version:' "$ROOT/.skillspector-baseline.yaml" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
  if [ -n "$INSTALLED" ] && [ -n "$PINNED" ] && [ "$INSTALLED" != "$PINNED" ]; then
    echo "WARNING: skillspector $INSTALLED != baseline scanner_version $PINNED - v2 fingerprints fail closed on version mismatch; expect re-flagged accepted findings until the baseline is regenerated."
  fi
fi
[ "${SHOW_SUPPRESSED:-0}" = "1" ] && BASELINE_FLAG+=(--show-suppressed)

mkdir -p "$OUT"
cd "$SCAN_ROOT"
DIRS=$(find . -name SKILL.md -printf '%h\n' | sort)

CANDIDATES=""
for d in $DIRS; do
  if [ "$FULL" = 1 ] || [ ! -f "$STAMP" ] \
     || [ -n "$(find "$d" -type f -newer "$STAMP" -print -quit)" ]; then
    CANDIDATES="$CANDIDATES $d"
  fi
done
[ "$VAULT_RUN" = 1 ] && touch "$STAMP"

for d in $CANDIDATES; do
  name=$(echo "$d" | sed 's|^\./||; s|/|__|g')
  rm -f "$OUT/$name.json"   # drop stale report: skillspector exits 1 on findings, not only on failure
  skillspector scan "$d" --no-llm --format json "${BASELINE_FLAG[@]}" \
    --output "$OUT/$name.json" >/dev/null 2>&1 || true   # exits 1 on findings; report file is the truth
  [ -f "$OUT/$name.json" ] || echo "SCAN-FAIL $d (no report written)"
done
echo "scanned $(echo $CANDIDATES | wc -w)/$(echo $DIRS | wc -w) skill dirs (reports: $OUT)"

python3 - "$OUT" "$VAULT_RUN" <<'EOF'
import json, glob, os, sys
out, vault_run = sys.argv[1], sys.argv[2] == '1'
rows, highs = [], []
for f in sorted(glob.glob(out + '/*.json')):
    d = json.load(open(f))
    ra = d.get('risk_assessment') or {}
    issues = d.get('issues') or []
    name = os.path.basename(f)[:-5].replace('__', '/')
    rows.append((name, ra.get('score', 0), ra.get('severity') or '-', len(issues)))
    for i in issues:
        if i.get('severity') in ('HIGH', 'CRITICAL'):
            loc = (i.get('location') or {})
            highs.append('[%s %s] %s :: %s:%s :: %s'
                         % (i.get('id'), i.get('severity'), name, loc.get('file'),
                            loc.get('start_line'), str(i.get('finding'))[:90].replace('\n', ' ')))
rows.sort(key=lambda r: (-r[1], r[0]))
print("%-52s %5s %9s %12s" % ('skill', 'score', 'severity', 'new-findings'))
for r in rows:
    if r[3] or not vault_run:
        flag = '  <== REVIEW' if r[3] else ''
        print("%-52s %5s %9s %12s%s" % (r[0], r[1], r[2], r[3], flag))
if not vault_run:
    print('\nHIGH/CRITICAL findings (third-party audit - triage these):')
    for h in highs[:40]:
        print('  ' + h)
    if len(highs) > 40:
        print('  ... and %d more' % (len(highs) - 40))
total = sum(r[3] for r in rows)
kind = 'skills with new findings' if vault_run else 'skills with findings'
print('\n%d/%d %s, %d total' % (sum(1 for r in rows if r[3]), len(rows), kind, total))
sys.exit(1 if total else 0)
EOF
