# osint-workflow workflow

## Lane osint-archive (slot 1, glm-5.3-flash)

1. Sources: Wayback (waymore), CommonCrawl index, URLScan, OTX; gau for URL
   harvest; wigolo for cached page intel. All passive.
2. Extract per in-scope root: historical JS URLs, `.js.map` files, retired
   API paths (`/api/v1/`, `/v0/`, versioned prefixes), query parameter names.
3. Write `osint/wayback-urls.md` (`| url | year | source |`). Rows for the
   LOCKED vhost are the stage 2-3 bonus inputs (old bundles, dead endpoints).

## Lane osint-infra (slot 2, glm-5.3-flash)

1. CT logs (crt.sh) for the root; historical DNS/ASN; public repos; 3rd-party
   service references (wigolo).
2. Classify EVERY discovered domain: in-scope -> Pending-Writes row for
   `lists/inscope-hosts.md`; out-of-scope (CDN, SaaS, analytics, external
   API, vendor) -> Pending-Writes row for `lists/outscope-3rdparty.md` with
   the `reason_excluded` clause.
3. Write `osint/infra-intel.md` (`| finding | source | confidence |`) and
   `osint/osint-findings.md` (prose, operator-readable).

## Fan-in (workflow-brain executes)

- Append classified rows to the two lists, then `bash scripts/scope-sync.sh`
  so the VM scope shim sees new in-scope hosts.
- OSINT exhausts when both lanes return `(none found)`-equivalent results on
  a re-run; then slots 1-2 close.

## N/A escapes

- `N/A: single-host scope (no subdomain expansion possible)`
- `N/A: no archived history for this root`
