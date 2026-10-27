#!/usr/bin/env bash
# Deterministic wordlist selector: (surface [fingerprint] [ctf|pt|bb]) -> ordered
# absolute wordlist paths + profile-tuned flags. Reads wordlist-map.json (sibling).
# Resolves the seclists base from the map; installs seclists if none is present.
# The skill (skills/surface/fuzz) calls this for WHAT to run; judgment stays in the skill.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAP="$HERE/wordlist-map.json"
surface="${1:-}"; fp="${2:-}"; etype="${3:-ctf}"

# --- compose mode: theme matrix + JS-corpus stems -> one deduped inline list ---
# No seclists needed seat-side; the matched seclists tech list is emitted as
# `# vm-wordlist:` comment lines for the VM to fetch.
if [ "$surface" = "compose" ]; then
  stems="${4:-}"; cap="${5:-200}"
  if [ -n "$stems" ] && [ ! -f "$stems" ]; then
    echo "compose: stems file not found: $stems" >&2; exit 4
  fi
  python3 - "$HERE" "$fp" "$etype" "$stems" "$cap" <<'PY'
import json, os, sys
here, fp, etype, stems, cap = sys.argv[1:6]
cap = int(cap)
m = json.load(open(os.path.join(here, "wordlist-map.json")))
cm = json.load(open(os.path.join(here, "config-exposure-map.json")))
prof = m["profiles"].get(etype) or m["profiles"]["ctf"]
themes = cm["themes"]
key = fp.strip().lower() if fp and fp.strip().lower() in themes else ""
out = list(themes[key]) if key else []
out += themes["generic"]
if stems:
    for ln in open(stems):
        p = ln.strip().lstrip("/")
        if not p or p.startswith("#"):
            continue
        out.append(p)
        parent = p.rsplit("/", 1)[0]
        if "/" in p and parent:
            out.append(parent)
seen = set(); rows = []
for p in out:
    if p and p not in seen:
        seen.add(p); rows.append(p)
rows = rows[:cap]
path = os.path.join(os.environ.get("TMPDIR", "/tmp"),
                    "wl-compose-%s-%s.txt" % (key or "generic", etype))
with open(path, "w") as f:
    f.write("\n".join(rows) + "\n")
print("# seclists: (compose: inline theme list, %d entries, cap %d)" % (len(rows), cap))
print("# flags: threads=%s rate=%s recursion=%s jitter=%s (profile=%s)"
      % (prof["threads"], prof["rate"], prof["recursion"], prof["jitter"], etype))
if key:
    for name, paths in m.get("fingerprints", {}).items():
        if name.lower() == key:
            for r in paths:
                print("# vm-wordlist: %s" % r)
            break
print(path)
PY
  exit 0
fi

if [ -z "$surface" ] || ! python3 -c "import json,sys
sys.exit(0 if '$surface' in json.load(open('$MAP'))['surfaces'] else 1)" 2>/dev/null; then
  echo "usage: wl-pick.sh <content|files|vhost|api|params|artifacts|compose> [fingerprint] [ctf|pt|bb]" >&2
  echo "  compose <fingerprint> <etype> [stems-file] [cap=200]" >&2
  exit 2
fi

# --- resolve seclists base (first existing candidate; else install) ---
base="$(python3 -c "import json,os,sys
m=json.load(open('$MAP'))
for b in m['seclists_bases']:
    if os.path.isdir(b): print(b); sys.exit(0)
sys.exit(1)" 2>/dev/null || true)"
if [ -z "$base" ]; then
  echo "# seclists not found -> installing" >&2
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get install -y seclists >/dev/null 2>&1 || true
  fi
  base="$(python3 -c "import json,os,sys
m=json.load(open('$MAP'))
for b in m['seclists_bases']:
    if os.path.isdir(b): print(b); sys.exit(0)" 2>/dev/null || true)"
  [ -n "$base" ] || { echo "seclists unavailable and install failed" >&2; exit 3; }
fi

# --- emit header lines (base, flags); surface already validated above ---
python3 - "$MAP" "$base" "$surface" "$fp" "$etype" "$HERE" <<'PY'
import json, os, sys
mapf, base, surface, fp, etype, here = sys.argv[1:7]
m = json.load(open(mapf))
prof = m["profiles"].get(etype) or m["profiles"]["ctf"]
print("# seclists: %s" % base)
print("# flags: threads=%s rate=%s recursion=%s jitter=%s (profile=%s)"
      % (prof["threads"], prof["rate"], prof["recursion"], prof["jitter"], etype))
out = []
# T0 harness first (repo-relative -> absolute under scripts/)
hf = m.get("harness_first", {}).get(surface)
if hf:
    p = os.path.join(here, hf)
    if os.path.exists(p):
        out.append(p)
# T3 fingerprint jump (only if the fp matches a known key)
for name, paths in m.get("fingerprints", {}).items():
    if fp and name.lower() == fp.strip().lower():
        out += [os.path.join(base, r) for r in paths]
        break
# T1 surface lists, size-ordered
out += [os.path.join(base, r) for r in m["surfaces"][surface]]
# dedup preserving order
seen = set()
for p in out:
    if p not in seen:
        seen.add(p); print(p)
PY
