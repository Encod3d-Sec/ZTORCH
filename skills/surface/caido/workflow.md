# caido workflow (always on engagement)

1. Per engagement: `~/caido.sh project <eng>` on the VM; every probe lands in
   History. Replay collections are named after the vhost.
2. Confirm-worthy requests (SSRF, injection, deser, auth bypass) go to Replay
   (or Burp Repeater when Burp is the seat of record); fuzz belongs in Replay
   batteries or Intruder, never a hand-rolled loop.
3. Auth export: `export-curl <id> --config` -> profile row in
   `ledgers/identities.md`.
4. RoE bars scanners? The same battery runs as Replay requests (slower,
   compliant).

## N/A escapes

- `N/A: Burp seat of record this engagement`
