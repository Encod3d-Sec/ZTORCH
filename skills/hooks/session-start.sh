#!/usr/bin/env bash
# Self-locate the vault root from this script's real path (resolves the
# ~/.claude/vault-hooks symlink -> skills/hooks/, so ../.. is the vault root).
# Honor explicit overrides first so it works on any user/path/spelling.
VAULT="${ZTORCH_VAULT:-${OBSIDIAN_VAULT:-${QMD_VAULT:-$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)}}}"

# Auto-register vault skills so a freshly-authored skill is invocable without a
# manual `setup/install-skills.sh` run. Idempotent (symlinks each skills/*/SKILL.md
# into ~/.claude/skills/, skipping existing); the harness rescans on session start.
# Output suppressed so it never pollutes the context injected below; fails open.
bash "$VAULT/setup/install-skills.sh" >/dev/null 2>&1 || true

# Inject session hot cache into context, rotating first: keep the preamble + the
# ~3 newest "## " entries in hot.md (the startup injection stays small); older
# entries move verbatim to session/hot-archive.md. Fails open.
HOT="$VAULT/session/hot.md"
if [ -f "$HOT" ]; then
  python3 - "$HOT" "$VAULT/session/hot-archive.md" <<'PYEOF' >/dev/null 2>&1 || true
import sys
hot, arch = sys.argv[1], sys.argv[2]
lines = open(hot, encoding="utf-8").read().splitlines(keepends=True)
pre, entries, cur = [], [], None
for ln in lines:
    if ln.startswith("## "):
        cur = [ln]
        entries.append(cur)
    elif cur is None:
        pre.append(ln)
    else:
        cur.append(ln)
KEEP = 3
changed = False
if len(entries) > KEEP:
    with open(arch, "a", encoding="utf-8") as f:
        f.writelines("".join(e) for e in entries[:-KEEP])
    entries = entries[-KEEP:]
    changed = True
# dual cap: one monster entry (a long session summary) alone can blow the KEEP=3 budget,
# so cap the file at MAXL lines / MAXB bytes too -- drop oldest kept entries first, then
# hard-trim a single oversized entry, leaving a self-describing marker line.
MAXL, MAXB = 200, 25 * 1024
while len(entries) > 1 and (
        len(pre) + sum(len(e) for e in entries) > MAXL
        or len("".join(pre)) + sum(len("".join(e)) for e in entries) > MAXB):
    with open(arch, "a", encoding="utf-8") as f:
        f.writelines("".join(entries.pop(0)))    # dropped-by-cap entries are archived too
    changed = True
if entries:
    blob = "".join(pre) + "".join("".join(e) for e in entries)
    if len(blob.splitlines()) > MAXL or len(blob) > MAXB:
        e = entries[0]
        room = max(0, MAXL - len(pre) - 4)
        with open(arch, "a", encoding="utf-8") as f:
            f.writelines(e[room:])              # the trimmed tail is archived, never lost
        entries[0] = ([e[0]] + e[1:room]
                      + ["<!-- hot-cache cap: entry exceeded %d lines / %dKB; tail trimmed to fit (trimmed part archived) -->\n" % (MAXL, MAXB // 1024)])
        changed = True
if changed:
    with open(hot, "w", encoding="utf-8") as f:
        f.writelines(pre + ["".join(e) for e in entries])
PYEOF
  # byte-cap the injection directly: if the rotation python above failed, the dual
  # cap inside it never ran and cat would inject the whole file (failure-path audit)
  head -c 25600 "$HOT"
fi
exit 0   # fail open: never let a missing hot.md make the SessionStart hook exit non-zero
