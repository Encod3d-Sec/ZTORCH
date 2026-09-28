#!/usr/bin/env bash
# caido-battery.sh - one-command fuzz battery through the VM's caido instance.
# Builds template + payloads locally, ships both inside ONE vm.sh call and runs
# ~/caido.sh fuzz (the multi-tee stdin dance broke twice; this kills it).
# Usage: caido-battery.sh <host> <payloads-file|-> [request-line]
#          [tls 0|1 def 1] [port] [delay-s def 0.4]
# request-line default: 'GET /{{PAYLOAD}} HTTP/1.1'; must contain {{PAYLOAD}};
# canned Host/UA/Accept/Connection headers are appended (body-bearing POST
# batteries: craft the template by hand + ~/caido.sh fuzz on the VM).
# Authenticated battery: export CAIDO_COOKIE (full 'Cookie: ...' line from
# '~/caido.sh cookies <host>' or a bare value) and it rides every variant.
# Payloads: one per line, 60 max (RoE cap). Delimiters CBTPL/CBPAY must not
# appear as a payload/template line.
set -euo pipefail
host="${1:?host}"; pf="${2:?payloads file or -}"; line="${3:-}"
# default outside ${:-...}: a literal } in the default terminates the expansion
[ -z "$line" ] && line='GET /{{PAYLOAD}} HTTP/1.1'
tls="${4:-1}"; port="${5:-0}"; delay="${6:-0.4}"
[ "$port" = 0 ] && { [ "$tls" = 1 ] && port=443 || port=80; }
grep -q '{{PAYLOAD}}' <<<"$line" || { echo "template lacks {{PAYLOAD}}" >&2; exit 1; }
grep -q '{{COOKIE}}' <<<"$line" && { echo "{{COOKIE}} is not substituted here; export CAIDO_COOKIE and the Cookie header is injected" >&2; exit 1; }
ck=""
[ -n "${CAIDO_COOKIE:-}" ] && ck="Cookie: ${CAIDO_COOKIE#Cookie: }"$'\n'
pay=$(mktemp); [ "$pf" = - ] && cat > "$pay" || cat "$pf" > "$pay"
trap 'rm -f "$pay" "${inner:-}"' EXIT
n=$(grep -c . "$pay" || true)
[ "$n" -gt 60 ] && { echo "$n payloads exceeds the 60 cap (RoE)" >&2; exit 1; }
[ "$n" -gt 0 ] || { echo "no payloads" >&2; exit 1; }
inner=$(mktemp)
{
  printf "cat > /tmp/cb-tpl.txt <<'CBTPL'\n%s\nHost: %s\n%sUser-Agent: Mozilla/5.0 (X11; Linux x86_64) Firefox/128.0\nAccept: */*\nConnection: close\n\nCBTPL\n" "$line" "$host" "$ck"
  printf "cat > /tmp/cb-pay.txt <<'CBPAY'\n"; cat "$pay"; printf "\nCBPAY\n"
  printf "~/caido.sh fuzz /tmp/cb-tpl.txt /tmp/cb-pay.txt %s %s %s %s\n" "$host" "$port" "$tls" "$delay"
} > "$inner"
bash /root/vm.sh 'tee /tmp/cb-run.sh >/dev/null; bash /tmp/cb-run.sh' < "$inner"
