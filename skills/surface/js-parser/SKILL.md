---
name: js-parser
description: "Use when a harvested JS corpus needs deep analysis: endpoints, params, APIs including old versions, secrets via known regex plus high-entropy strings, vulnerable functions and gadget maps, frameworks, and feature flags. Consumes the js-discover corpus and emits an MD report plus ready-to-run curl commands. Assumes js-discover corpus and hunt-core."
metadata:
  hermes:
    tags: [javascript, jsluice, jxscout, secrets, endpoints, surface]
    related_skills: [js-discover, hunt-secrets, hunt-core, triage]
---

# JS Parser - deep analysis of a harvested JS corpus

Second half of the JS pair. Input = a js-discover corpus at $RUN (absolute
path). Output = analysis notes under $RUN plus the thin pointer
`$ENG_DIR/js-analysis.md` + curl commands + rows in `_requests.md`.
Findings leave only through the G1 proof gate.

## Paths (binding - same scheme as js-discover)

    # seat side (WSL) - engagement tree is DOUBLE-NESTED in VMshare:
    ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>
    RUN=$ENG_DIR/js/<domain>
    # VM side (WHERE analysis tools run, same tree through the VMware share):
    ENG_DIR=/mnt/VMshare/<eng>/<eng>
    RUN=$ENG_DIR/js/<domain>

The corpus lives in the VMshare tree (js-discover wrote it there). The VM
runs jsluice/jxscout against the /mnt/VMshare spelling as user tz (vm-ssh
transport; NOT root - no root-only paths, no sudo assumptions); the seat
reads the same bytes at /mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>.

## Checklist (mandatory)

Copy checklist.md (this skill's dir) to $ENG_DIR/js/parser-checklist.md at
run start. Tick boxes as steps finish; unchecked at stop = UNCHECKED lane,
re-run from the first unchecked step.

## Nudge

Review-skill re-injection text (pinned for vocabulary match; NOTE: the
completion-gate script itself emits a different generic nudge - see
scripts/completion-gate.py NUDGE - both strings mean the same thing:
resume at the first unchecked box):

    Your work was just reviewed by the review skill and it was found that you
    either missed a step of analysis, or didn't generate an artifact of
    sufficient proof. Look at the markdown based checklist and the output for
    each step, find what you missed, and complete that step.

On this nudge: resume at the FIRST unchecked box of
$ENG_DIR/js/parser-checklist.md - never restart the run from zero. REVIEW
may only be ticked after every earlier box is ticked.

## Entry gate

The js-discover corpus at $RUN (absolute path, VMshare spelling) must
satisfy ALL of:
- manifest.md exists AND `sha256sum -c` passes via the manifest.sha256
  sidecar (run from $RUN on the VM)
- ast/symbols.json exists and parses
- findings/endpoints.jsonl exists and parses as JSONL
- raw/ contains at least one file (empty corpus = dispatch discover; an
  empty tree is a failed discover lane, not a parser input)

If any fail, dispatch js-discover first - never analyze a partial corpus
silently.

Re-verify ALL four checks as the FIRST checklist box at run start, not
just at dispatch time - a long engagement may hold a corpus from an
earlier, since-fixed discover bug. Record the verification timestamp in
analysis/site-summary.md's header.

## Step 1 - Normalize

Detect per file: minified (single-line, avg token density), beautified-
already, or obfuscated (packer signatures: `eval(function(p,a,c,k,e`,
`_0x` hex renaming, long string-array rotations).

Primary beautifier = jsluice format (jsbeautifier-go inside jsluice - no
install, no npm). Write beautified/{inline,external}/ with filenames
IDENTICAL to raw/:

    for f in "$RUN"/raw/external/*.js; do
      /home/tz/go/bin/jsluice format "$f" > "$RUN/beautified/external/$(basename "$f")"
    done
    for f in "$RUN"/raw/inline/*.js; do
      /home/tz/go/bin/jsluice format "$f" > "$RUN/beautified/inline/$(basename "$f")"
    done

Fallback ONLY if jsluice format emits empty output: js-beautify is
installed on the VM at /home/tz/.npm-global/bin/js-beautify (v2.0.3):
`/home/tz/.npm-global/bin/js-beautify -f <in.js> -o <out.js> -s 2`.

Mark packer-packed files; beautify after unpacking when feasible, else note
`OBFUSCATED` in the report - do not burn the lane on one file.

## Step 2 - Endpoints and params (bulk jsluice pass)

One bulk pass over the whole beautified tree (files are positional; -R
resolves relative paths):

    find "$RUN/beautified" -name "*.js" -print0 | xargs -0 -r \
      /home/tz/go/bin/jsluice urls -u -S -c 5 -R "https://<domain>" \
      > "$RUN/findings/jsluice-urls.jsonl"

Normalize into findings/endpoints.jsonl. Required keys on EVERY line:
url, method, params, source_file, line, live_guess. jsluice emits
url/queryParams/bodyParams/method/source/filename and NO line numbers -
set line = 0 (the source snippet is the evidence); source_tool
recommended. The reducer runs on the VM; pass RUN through the environment
(quoted heredoc keeps the python verbatim, env expands $RUN):

    cat > /tmp/normalize.py <<'PY'
    import json, os
    run = os.environ["RUN"]
    # TRUNCATE, not append: discover seeds the file empty; append would
    # duplicate every row on a re-run from the first unchecked box
    out = open(run + "/findings/endpoints.jsonl", "w")
    seen = set()
    n = 0
    for line in open(run + "/findings/jsluice-urls.jsonl"):
        line = line.strip()
        if not line.startswith("{"): continue
        r = json.loads(line)
        rec = {
            "url": r.get("url",""),
            "method": r.get("method",""),
            "params": (r.get("queryParams") or []) + (r.get("bodyParams") or []),
            "source_file": r.get("filename",""),
            "line": 0,                      # jsluice does not emit lines; source snippet is evidence
            "live_guess": "high" if (r.get("url","").startswith("/") or os.environ.get("DOMAIN","") and os.environ["DOMAIN"] in r.get("url","")) else "medium",
            "source_tool": "jsluice",
            "evidence": r.get("source",""),
        }
        k = (rec["url"], rec["method"], tuple(rec["params"]), rec["source_file"])
        if k in seen: continue
        seen.add(k)
        out.write(json.dumps(rec) + "\n"); n += 1
    out.close(); print(n)
    PY
    RUN="$RUN" DOMAIN="<domain>" python3 /tmp/normalize.py

The markdown endpoint table is a GENERATED view of endpoints.jsonl, never
the primary store.

Live-guess heuristics: relative `/api/...` paths = high; full URLs to the
target host = high; template-string hosts = medium; dead prefixes = low
(low is assigned during Step 4 triage, not by the reducer - the reducer
emits only high/medium; adjust in endpoints.jsonl when triage proves a
prefix dead).

Call-site enrichment (merge-by-url, never overwrite): for each distinct
url in endpoints.jsonl, run a second jsluice pass over the owning file
to pull the fetch/axios/XHR verb and the object literal passed
alongside, then MERGE that signal into the existing row by url (append
method/params/auth_header context to the row already there; add a new
row only for a url not present). A verb that cannot be resolved
statically leaves the row's method as-is - never guess. Merging by url
keeps the reducer's idempotency: re-running from the first unchecked
box cannot duplicate rows.

## Step 3 - jxscout cross-check

CONSUME the discover-side output: $RUN/raw/sourcemaps/jxscout/ +
$RUN/raw/sourcemaps/jxscout.log. Diff the jxscout endpoint set against
findings/endpoints.jsonl and record the diff; differences between jsluice
and jxscout endpoint sets are themselves signal (chunk-only routes).

ONLY if discover ran WITHOUT jxscout AND the corpus is bundled may the
parser start it once, using the SAME canonical block K8 from js-discover
(labeled K8 at its Step 5 jxscout launch)
SKILL.md Step 5 (never a second copy of the command in this skill),
followed by its mandatory project-dir copy. The parser-side launch
inherits the SAME compensating controls (they are part of block K8's
contract): run the entry-gate scope pre-flight (verify every known host
against scope.md, write $RUN/raw/sourcemaps/jxscout-hosts-in-scope.txt)
BEFORE starting the server, and after the run diff the -debug log hosts
against that file; an unlisted host is an incident row.

## Step 4 - Params and routes triage

Flag rows matching:

- admin: `/admin|/manage|/internal|/backoffice|/dashboard`
- feature flags: `feat|flag|toggle|experiment|rollout|ab-?test`
- interesting comments: `TODO|FIXME|HACK|XXX|NOTE:|BUG:|password|secret|
  internal only|staging|do not ship`

Flagged rows are adjusted in endpoints.jsonl (live_guess, flag note).
Developers comment truthfully; comments carry context production code
hides.

## Step 5 - API analysis

Group endpoint rows by function prefix (`/api/v1/user/*` = user group).
Extract version families (`/api/v[0-9]+`): every OLD version still
referenced is a prime test target - old versions often lack the
auth/rate patches newer ones grew. Output: API inventory table (group |
versions seen | oldest | sample curl) in analysis/site-summary.md.

## Step 6 - Secrets

Pass A0 first (tool pass): jsluice secrets over the whole beautified tree
with the house patterns file (flat array of {name, regex, value|key}
objects - jsluice UserPatterns, verified semantics on this build: `value`
= a SECOND regex tested against each string-literal candidate, fires
anywhere with `data.match`; `key` = a regex tested against object-pair
KEY NAMES ONLY (never fires on assignments - pair it with a value-matching
`regex`); entries lacking both are rejected with a stderr error). The
file lives in repo scripts/ (NEVER the skill dir); vendor regexes
(AWS/Google/Slack/JWT/Stripe/GitHub) are jsluice built-ins - the skill
does not restate them. The VM cannot read the seat repo (/mnt/c absent),
so SHIP the file first - one time per engagement. NOTE: jsluice exits
rc=0 even on a stderr patterns error - treat ANY stderr line as a loud
failure, never as "no hits":

    # seat side, once per engagement:
    #   (the patterns file is the K12 contract - repo scripts/jsluice-patterns.json
    #    is canonical; js-discover never restates it)
    #   cp scripts/jsluice-patterns.json /mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>/js/jsluice-patterns.json
    # VM side reads it at: $ENG_DIR/js/jsluice-patterns.json

    find "$RUN/beautified" -name "*.js" -print0 | xargs -0 -r \
      /home/tz/go/bin/jsluice secrets -c 5 \
      -p "$ENG_DIR/js/jsluice-patterns.json" \
      > "$RUN/findings/secrets-jsluice.jsonl" 2> "$RUN/findings/secrets-jsluice.err"
    [ -s "$RUN/findings/secrets-jsluice.err" ] && { echo "PATTERNS ERROR - ABORT"; cat "$RUN/findings/secrets-jsluice.err"; exit 1; }

Pass A - house patterns (via the same K12 patterns file) complete.

Pass B - high entropy (catches what regexes miss): all quoted strings
`[A-Za-z0-9_-]{20,}`, Shannon entropy > 4.5, excluding a small allowlist of
known-library constants and hex color/hash-looking false positives. Every
pass-B hit becomes a `suspected` row with file:line - volume is expected;
precision comes from the proof gate.

Findings route through the G1 proof gate (a secret is Completed only
with proof the key is live - diff-observed use on the target's own
service where RoE allows, e.g. a validated request that only succeeds
with the secret; else it stays `suspected`).

Interceptor-sourced files: hits on authorization headers/cookies of the
operator's own session are tagged provenance=self-identity and never
promoted.

Masking rule: any human-readable artifact (analysis notes,
site-summary, reports) carries the secret masked - first/last 4
characters only (e.g. `sk_l*******wXyz`), plus file:line. Raw values
live only in findings/*.jsonl and the corpus files themselves, which
are the evidence store. Do NOT auto-validate a candidate by calling
the provider: validation is a separate, scope-shim-gated, read-only,
single low-impact call (a harmless whoami/metadata GET for that
credential type), run only when the operator explicitly asks - never
speculatively against every candidate.

## Step 7 - Library and framework analysis

Fingerprint libraries + versions (banner comments, `vX.Y.Z` strings, file
paths `/jquery-3.4.1.min.js`). For each: outdated vs latest? known CVEs?
(wigolo fetch the library's release page; cite the fetched release-page
URL). Fingerprint the framework (React/Next/Vue/Nuxt/Angular/Svelte) from
bundle markers - framework choice drives route-guess patterns and known
gadget classes. Name the framework in the site-summary.md stack section.

## Step 8 - Gadget map

Locate dangerous sinks and build source->sink chains, joining against
$RUN/ast/symbols.json for what each sink actually receives:

    sinks: innerHTML, outerHTML, eval(, new Function(, document.write,
    location=|location.href=, postMessage, src=, href=, jQuery .html(

For each sink: can lane-controlled input (URL param, postMessage,
fragment, stored field) reach it without sanitization? Output a gadget
table: `source | sink | file:line | chain guess | candidate class (DOM
XSS, postMessage hijack, open redirect)`. Chains route to the triage
proof gate.

## Step 9 - Output

1. Per-file notes, two tiers (a full LLM read of every file is the
   wrong default - most of a minified corpus is boilerplate):
   Tier A (cheap, non-LLM, every file): BUILD the indicator list first
   from what is already known, then grep the raw trees with it:

       mkdir -p "$RUN/ast"
       jq -r '.url' "$RUN/findings/endpoints.jsonl" > "$RUN/ast/js-parser-indicators.txt"
       printf '%s\n' key token secret password auth eval innerHTML \\
         document.write dangerouslySetInnerHTML 'exec(' isAdmin role \\
         premium entitlement debug >> "$RUN/ast/js-parser-indicators.txt"
       rg -n -i -F -f $RUN/ast/js-parser-indicators.txt \\
         "$RUN"/raw/external "$RUN"/raw/inline > "$RUN/ast/grep-hits.txt"

   (-F: the indicator list is literal strings - endpoint urls and
   identifiers - not a regex; a '?' or '+' in a url would otherwise
   distort the pattern.) Indicators = every url already in
   endpoints.jsonl (a hit means
   "this file is where that endpoint call lives"), secret-adjacent
   keywords (key, token, secret, password, auth), sink names (eval,
   innerHTML, document.write, dangerouslySetInnerHTML, exec(), and the
   Step 8 sink list), and auth/role keywords (isAdmin, role, premium,
   entitlement, debug). This yields a per-file hit density at zero
   LLM-read cost.
   Tier B (full read, only files that earn it): a file gets a full
   analysis/external/{name}.md or analysis/inline/{name}.md note when
   it clears the Tier A hit-density gate, OR regardless of hit count
   when it is a jxscout-recovered / sourcemap-restored original, is
   referenced by >= 2 rows in endpoints.jsonl, or has >= 1 row in the
   secrets findings. Full notes keep the existing contract: endpoints
   referenced (row pointers), secret candidates (file:line only, never
   the value repeated), interesting exported/global names from
   symbols.json, and client-side logic reading like an authorization or
   feature-flag check - noted as LEADS, not findings.
   Every OTHER file still gets its note - one line, sourced from the
   Tier A summary alone: "grep-only pass: no indicators in
   grep-hits.txt, not promoted to full read". One note per corpus
   file, counts matching disk, "no findings" rows explicit - nothing
   silently skipped; promotion needs a new reason.
2. Cross-file picture in analysis/site-summary.md: auth flow, API
   surface, stack, version families, gadget rollup - and the
   ready-to-run curl one-liners live here (inline the command; auth
   headers by `identities.md` profile name):
       curl -s 'https://<host>/<path>?<params>' -H 'X: <from profile>'
3. `$ENG_DIR/js-analysis.md` becomes a thin pointer that ALSO carries the
   `PARSER-DONE` + counts line (endpoints, secrets suspected/confirmed,
   gadgets) - the gate and downstream readers key on both.
4. Append executed requests to `_requests.md` (lane = js-parser). The
   canonical file is $ENG_DIR/_requests.md (VMshare engagement tree) -
   create it if absent; a missing ledger silently drops the audit trail.
5. Push new endpoint rows to the offensive surface: append significant
   new endpoints as rows in the engagement `state.md` asset table
   (`asset | url | endpoint | param | tech | access | notes` - access
   starts at `recon`, source noted as js-parser; dedupe by url+endpoint
   before appending) so /fuzz and /next pick them up.

Empty endpoint AND empty secret tables with no empty-state notes = failed
lane (an explicit "no hits" note on either table is a valid clean-target
outcome, not a failure).

Auth note (dual): structured fetches keep `identities.md` profiles;
Interceptor-sourced endpoints replay ONLY GETs inside the logged-in
session (captured headers), never synthesized profiles, never
write-actions unless the lane explicitly authorizes.

Interceptor replay step (GET-only, scope-shim): for endpoint rows whose
source is an interceptor capture, replay once with the SAME captured
session headers to confirm the endpoint still resolves and to sniff its
shape:

    /opt/scope-shim/bin/curl -sS --max-time 20 -H "<captured-session-header>" \
      -o /dev/null -w "%{http_code} %{content_type}\n" "<captured-url>"

Append the result to the EXISTING endpoints.jsonl row as
`verified: true` plus status/content-type - never a competing row for
the same url. A non-GET verb is never replayed here; mutating requests
belong to the authorized test lane the triage hands off to. N/A when
the manifest has no interceptor-sourced rows.

## Bitter-pill variant

When the kickoff designates this run freehand ("just hack it, no
mistakes", bitter pill), skip the checklist copy and the numbered steps:
one freehand pass over the $RUN corpus (raw/ + beautified/), chase
whatever looks exploitable. Output lands ONLY in
$RUN/analysis/bitter-pill.md (tried / found / dismissed; every claim
carries file:line). Never edit or delete structured outputs; nothing in
bitter-pill.md overwrites site-summary.md or endpoints.jsonl. Secrets
still route through the G1 proof gate - freehand never skips proof.
Declare the firing with one _requests.md row (lane = js-parser-bitterpill,
summary = "bitter-pill fired") so the completion-gate routes the run to
this artifact contract instead of the checklist ledger. Findings enter
the merged report only through js-conglomerate with provenance
bitter-pill; they never auto-promote past triage.

## Wiki

Hub: [[web-moc]] | Primary page: [[static-code-analysis]] | Arsenal: [[recon-dorks]]
Anchors: [[javascript-source-map-exploitation]], [[secret-hunting]], [[api-testing]]

## Validation

- Proof = the endpoints/symbols artifacts reconcile with the manifest:
  every analyzed file appears in the run ledger; endpoint counts match
  the per-file pass logs; normalize is idempotent (re-run diff = empty).
- Negative control: a bundle with no endpoints yields an explicit
  zero-row note, never a silent skip.

## False Positives

- Minified false "endpoints" (string concatenations, sourcemap paths).
- Dead routes from a stale chunk (version-prefixed chunk dirs - flag
  version-bearing paths for the mapper's freshness check).
- Secrets hits that are public keys/Twitter-widget IDs by shape (the
  secrets pass triages its own hits; parser only tags).
- Entropy-only secret hits (base64 asset hashes, CSS-in-JS class
  hashes, build IDs): entropy raises confidence, it never CREATES a
  row - require a known key-shape prefix match first.
- Endpoints/secrets sourced from bundled test fixtures
  (/test/, /__mocks__/, /fixtures/ paths): tag `confidence: low` on
  those rows, never drop them silently.
- Source-map `sources` entries that are webpack virtual paths
  (`webpack:///...`): not a repo-structure leak unless the path
  actually resolves to something.

## Deadends

Append per dead analysis path: unparseable bundle format (record the
first bytes + headers), sourcemap without `sources` content, framework
the reducer does not recognize (feeds the wiki harvest list).

## Stop conditions

All manifest files terminal (parsed | deadend row); PARSER-DONE pointer
written; no unchecked boxes in the copied checklist.
