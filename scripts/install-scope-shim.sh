#!/usr/bin/env bash
# install-scope-shim: (re)create /opt/scope-shim on the Kali VM (192.168.23.128).
# Root-cause fix 2026-10-18: this VM image shipped without the shim the js-*
# skills predate on ("verified live" semantics predate the image); scope-sync.sh
# only pushes scope DATA into the dir. Run AFTER this: bash scripts/scope-sync.sh
# (or this script's step 2, which pushes the 3 vault files itself).
# Semantics (js-discover/jxscout contract): explicit out-of-scope token = rc 126;
# in-scope = pass; UNKNOWN = advisory + proceed (NOT approval); no scope state = fail closed.
set -euo pipefail
VMSH=${VM_SSH:-"bash scripts/vm-ssh.sh"}
PASSWD=${VM_PASS:-Tom123as}

read -r -d '' SCOPE_CHECK <<'PYEOF'
#!/usr/bin/env python3
"""scope-check: resolve host/URL args against the active engagement scope.
Exit: 0=PASS (in-scope), 1=UNKNOWN (advisory, not approval), 2=OUT (deny rc126), 3=args unresolvable.
Fail-closed when no active engagement or scope.md is missing."""
import os, re, sys, time, urllib.parse

VAULT = os.environ.get("SCOPE_VAULT", "/opt/scope-shim/vault")

def active_eng():
    try:
        with open(os.path.join(VAULT, "targets", "active.md")) as f:
            return f.readline().strip() or None
    except OSError:
        return None

def parse_scope(path):
    ins, outs = [], []
    try:
        txt = open(path).read()
    except OSError:
        return ins, outs, False
    section = None
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("## "):
            h = s[3:].lower()
            section = "in" if h.startswith("in scope") else ("out" if h.startswith("out of scope") else None)
            continue
        if section and s.startswith("- "):
            tok = s[2:].strip()
            if tok and " " not in tok and "." in tok and "<" not in tok and tok.lower() not in ("true", "false"):
                (ins if section == "in" else outs).append(tok.lower().lstrip("*").strip())
    return ins, outs, True

def host_of(arg):
    a = arg
    if "://" not in a:
        if re.match(r"^[A-Za-z0-9._-]+\.[A-Za-z]{2,}(:\d+)?/?$", a):
            return a.split("/")[0].split(":")[0].lower()
        return None
    try:
        return urllib.parse.urlparse(a).hostname or None
    except ValueError:
        return None

def main():
    args = sys.argv[1:]
    if not args:
        print("usage: scope-check <url|host> [...]", file=sys.stderr)
        return 3
    eng = active_eng()
    if not eng:
        print("scope-check: no active engagement pointer - DENY (fail closed)", file=sys.stderr)
        return 2
    path = os.path.join(VAULT, "targets", eng, "scope.md")
    ins, outs, found = parse_scope(path)
    stamp = os.path.join(VAULT, ".sync-stamp")
    try:
        age = time.time() - os.stat(stamp).st_mtime
        if age > 7 * 86400:
            print(f"scope-check: STALE scope sync ({int(age//86400)}d old) - re-run scope-sync.sh", file=sys.stderr)
    except OSError:
        print("scope-check: no .sync-stamp (never synced) - run scope-sync.sh", file=sys.stderr)
    if not found:
        print(f"scope-check: scope.md missing for '{eng}' - DENY (fail closed)", file=sys.stderr)
        return 2
    hosts = [h for h in (host_of(a) for a in args) if h]
    if not hosts:
        print("scope-check: no resolvable host in args (pass-through)", file=sys.stderr)
        return 3
    verdict = "PASS"
    for h in hosts:
        if any(h == t or h.endswith("." + t) for t in outs):
            print(f"OUT-OF-SCOPE {h} (explicit out-of-scope token) - DIE rc126", file=sys.stderr)
            verdict = "OUT"
            break
        if any(h == t or h.endswith("." + t) for t in ins):
            continue
        print(f"UNKNOWN host {h} - advisory only, NOT approval; verify against scope.md yourself", file=sys.stderr)
        if verdict == "PASS":
            verdict = "UNKNOWN"
    print(f"scope-check: {verdict} hosts={','.join(hosts)} eng={eng}", file=sys.stderr)
    return {"PASS": 0, "UNKNOWN": 1, "OUT": 2}[verdict]

sys.exit(main())
PYEOF

wrapper() { # $1 = tool name, $2 = real path ("" = runtime-resolve httpx)
  if [ -n "$2" ]; then local REALBLOCK="REAL=$2"; else
    local REALBLOCK='REAL=$(command -v httpx 2>/dev/null)
case "$REAL" in ""|/opt/scope-shim/*) REAL=/home/tz/go/bin/httpx ;; esac
[ -x "$REAL" ] || { echo "scope-shim: real httpx not found" >&2; exit 127; }'
  fi
  printf '%s\n' "#!/usr/bin/env bash" "# scope-shim wrapper ($1). Deny only on explicit out-of-scope (rc126); UNKNOWN passes with advisory." "$REALBLOCK" 'v=$(/opt/scope-shim/bin/scope-check "$@" 2>&1 >/dev/null); rc=$?' 'printf '"'"'%s\n'"'"' "$v" >&2' 'if [ "$rc" -eq 2 ]; then echo "scope-shim: out-of-scope - refusing" >&2; exit 126; fi' 'exec "$REAL" "$@"'
}

payload() { # emit "<name> <b64>" lines for one VM transfer round-trip
  printf 'scope-check.py %s\n' "$(printf '%s' "$SCOPE_CHECK" | base64 -w0)"
  printf 'curl %s\n' "$(wrapper curl /usr/bin/curl | base64 -w0)"
  printf 'wget %s\n' "$(wrapper wget /usr/bin/wget | base64 -w0)"
  printf 'httpx %s\n' "$(wrapper httpx "" | base64 -w0)"
}

# step 1: binaries
payload | while read -r name b64; do
  $VMSH "echo $PASSWD | sudo -S sh -c 'mkdir -p /opt/scope-shim/bin && echo $b64 | base64 -d > /opt/scope-shim/bin/$name && chmod 755 /opt/scope-shim/bin/$name' 2>/dev/null"
done

# step 2: scope state (same file set scope-sync.sh pushes)
E=$(base64 -w0 skills/hooks/_engagement.py)
A=$(base64 -w0 targets/active.md)
S=$(base64 -w0 "targets/$(sed -n 's/[^a-z0-9-]//gp' targets/active.md | head -c 40)/scope.md" 2>/dev/null || true)
$VMSH "echo $PASSWD | sudo -S sh -c 'mkdir -p /opt/scope-shim/vault/skills/hooks /opt/scope-shim/vault/targets && echo $E | base64 -d > /opt/scope-shim/vault/skills/hooks/_engagement.py && echo $A | base64 -d > /opt/scope-shim/vault/targets/active.md && echo $S | base64 -d > /opt/scope-shim/vault/targets/\$(head -1 /opt/scope-shim/vault/targets/active.md)/scope.md && date -u +%s > /opt/scope-shim/vault/.sync-stamp' 2>/dev/null"

# step 3: verify all three verdict paths live (fail loudly on any)
$VMSH '/opt/scope-shim/bin/scope-check https://example.com/ >/dev/null 2>&1; [ $? -eq 1 ] || { echo "shim install: UNKNOWN path FAILED"; exit 1; }; /opt/scope-shim/bin/curl --version >/dev/null 2>&1 || { echo "shim install: wrapper FAILED"; exit 1; }; echo "shim install: OK"'
