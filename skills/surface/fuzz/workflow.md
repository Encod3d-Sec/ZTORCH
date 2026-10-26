# fuzz workflow (stage 3, list-fed)

NO blind generic directory brute force first. Inputs are the js-lists:

1. `custom-wordlist.txt` (paths, prefixes, params) -> ffuf on the locked
   vhost only; arjun for parameter mining. `-t 5`, one scanner at a time.
2. Probe every `hidden-endpoints.md` row + old API version prefixes; fuzz
   undocumented params on `api-endpoints.md` rows.
3. Anomalies (200, 401-to-200, 500, 403-bypass candidates) -> caido Replay
   collection named `<vhost>-anomalies`; update api-endpoints rows with
   `live_status`.
4. RoE bars fast scanners -> identical battery as Replay requests.

## N/A escapes

- `N/A: RoE passive-only`
- `N/A: no js-lists yet (stage 2 not complete)`
