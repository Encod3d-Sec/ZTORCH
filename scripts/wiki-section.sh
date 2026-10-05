#!/usr/bin/env bash
# wiki-section.sh <page> [<slug>] - print one '## ' section body from a wiki/skill
# page, or --list to print section slugs. Slug = heading lowercased, spaces->dashes.
# Resolves <page> as: given path, wiki/<page>.md, or wiki/**/<page>.md (first hit).
set -euo pipefail

V="$(cd "$(dirname "$0")/.." && pwd)"
PAGE="${1:-}"
SLUG="${2:-}"
[ "$SLUG" = "--list" ] && SLUG=""  # --list = list mode; empty slug already prints slugs

resolve() {
  if [ -f "$PAGE" ]; then echo "$PAGE"; return 0; fi
  for cand in "$V/wiki/$PAGE.md" \
              $(find "$V/wiki" -name "$(basename "${PAGE%.md}").md" 2>/dev/null | head -5); do
    if [ -f "$cand" ]; then echo "$cand"; return 0; fi
  done
  return 1
}

P="$(resolve)" || { echo "wiki-section: page not found: $PAGE" >&2; exit 1; }

awk -v slug="$SLUG" '
  BEGIN { found = (slug == "") }
  /^## / {
    h = tolower($0)
    gsub(/^## +/, "", h); gsub(/ +$/, "", h); gsub(/[^a-z0-9]+/, "-", h)
    sub(/^-+|-+$/, "", h)
    if (slug == "") { print h; next }
    inme = (h == slug)
    if (inme) found = 1
    next
  }
  inme { print }
  END { if (!found) exit 1 }
' "$P"
