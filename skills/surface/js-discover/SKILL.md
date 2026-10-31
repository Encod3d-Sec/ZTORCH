---
name: js-discover
description: "Use when a target's JavaScript must be harvested before analysis: spidering JS files and inline scripts, lazy-loaded bundles, historical URLs, and sourcemaps, with anti-automation fetch. Chain with js-parser which consumes this skill's corpus. Assumes hunt-core lane discipline."
metadata:
  hermes:
    tags: [javascript, recon, spider, sourcemaps, waymore, surface]
    related_skills: [js-parser, hunt-core, hunt-secrets]
---

# JS Discover - harvest all JavaScript for a target

Half of the JS analysis pair (this = collect, js-parser = analyze). One skill,
one job: leave with a complete, deduped JS corpus and a manifest. The more
methodology packed into one skill, the more an agent skips - so this stops at
the manifest.

## Paths (binding - define once at the top of the run notes)

    # seat side (WSL) - engagement admin tree lives DOUBLE-NESTED in the
    # VMshare mirror (VMshare/<eng>/<eng> - historical layout, keep it):
    ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>
    RUN=$ENG_DIR/js/<domain>
    # VM side (WHERE THE CORPUS IS WRITTEN - same tree, mount spelling):
    ENG_DIR=/mnt/VMshare/<eng>/<eng>
    RUN=$ENG_DIR/js/<domain>

The VM cannot see the seat tree (/mnt/c does not exist there; the WSL
kali-linux distro is a separate machine from the VMware Kali). All
corpus-writing commands run in the VM against the /mnt/VMshare spelling;
the seat sees the same bytes at /mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>.
The repo tree targets/<eng> (seat) is admin/ingest only - never write
corpus or gate artifacts there.

Transport (unchanged): command blocks below are VM-native; ship each as one
vm-ssh.sh argument:

    bash scripts/vm-ssh.sh '<command>'

vm-ssh lands on the VM as root (key-based; the tz password fallback lives
in /root/vm.sh only). Quoting: vm-ssh.sh takes the command
as ONE argument; commands containing single quotes must ship as a base64
payload (base64-encode the script, then run `echo <b64> | base64 -d | bash`
inside the vm-ssh argument). Blocks below avoid inline single quotes where
possible.

Non-login shells do NOT source /etc/profile.d/scope-shim.sh: over this
transport the PATH scope-shim is NOT active (plain curl resolves to
/usr/bin/curl). Any target-facing fetch MUST go through the shim binaries
by absolute path /opt/scope-shim/bin/{curl,wget,httpx,chromium,scope-check}
(except the documented WSL-side wigolo exception in Step 1). Shim
verdict semantics (verified live): hosts matching an explicit
out-of-scope token DIE rc 126; hosts matching in-scope PASS; UNKNOWN
hosts (neither list, e.g. third-party CDNs) get an ADVISORY and the fetch
PROCEEDS - an advisory is NOT approval: verify the host against scope.md
yourself and self-deny anything not clearly in scope. Never work around
an rc 126.

Run protocol: run-protocol.md (this skill's dir); copy target stays EXACTLY
$ENG_DIR/js/discover-checklist.md (completion-gate contract). checklist.md is
the machine-gate lane template `offensive.py lane-init` substitutes - never
copied by hand.

## Entry gate

1. Active engagement must exist (`targets/active.md`); scope-guard is the deny.
2. All target-facing fetches run ON THE VM through the scope-shim binaries
   (absolute path /opt/scope-shim/bin/... - the PATH shim is NOT active
   over vm-ssh; explicit out-of-scope hosts die rc 126 - never work
   around it; unknown hosts raise an ADVISORY, which is not approval -
   self-deny anything not clearly in scope). Corpus paths below live in
   the engagement dir. Sole documented exception: WSL-side wigolo fetch
   (Step 1) - pre-verify each wigolo URL against scope.md by hand before
   fetching; wigolo prints advisories to stderr, so do NOT silence them
   (keep stderr visible).
3. Toolchain preflight - fail loudly on any missing binary (js-beautify is
   NOT required here; jsluice format covers beautify, and js-beautify is
   installed anyway at /home/tz/.npm-global/bin/js-beautify):

    for t in /home/tz/go/bin/jsluice /home/tz/go/bin/katana /home/tz/go/bin/jxscout /home/tz/go/bin/gau /home/tz/.local/bin/waymore python3 jq; do
      command -v "$t" >/dev/null 2>&1 || { echo "MISSING TOOL: $t - ABORT RUN"; exit 1; }
    done

4. JXSCOUT SCOPE PRE-FLIGHT (binding compensating control): jxscout fetches
   with its own HTTP client and NEVER transits the scope-shim, and its
   -scope flag is a substring glob (matches <domain>.evil.example style
   hosts). Before starting jxscout (Step 5), verify every host ALREADY
   KNOWN to the run - the seed host plus every host in $RUN/raw/js-urls.txt
   and fetch-log.txt - against the engagement scope.md in-scope list
   (targets/<eng>/scope.md in the repo tree is the source of truth; the
   VMshare scope.md copy mirrors it). Record the verified host list
   verbatim in $RUN/raw/sourcemaps/jxscout-hosts-in-scope.txt (one host
   per line, "verified-in-scope <host>"). Any known out-of-scope host:
   drop its URLs from the corpus BEFORE launching jxscout, and note it in
   the manifest as OUT-OF-SCOPE-SKIPPED. Mid-crawl chunk hosts CANNOT be
   pre-enumerated (jxscout discovers them at runtime) - the BINDING
   control for those is the post-run diff: after the run, extract every
   host from the -debug log and diff against the verified list in REVIEW;
   an unlisted host is an incident row, not a corpus row. This is a
   detective control for mid-crawl hosts (honest limitation - the
   nftables egress allowlist is the real fix, still deferred). Same
   pattern as the Interceptor box.

## Checklist (mandatory)

Copy run-protocol.md (this skill's dir) to $ENG_DIR/js/discover-checklist.md
at run start. Tick boxes as steps finish; an unchecked box at stop means the
run is not done - re-run from the first unchecked step. The completion-gate
ledger mirrors this list. (checklist.md is NOT this list: it is the
machine-gate lane template `offensive.py lane-init` materializes per lane -
never copy it by hand.)

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
$ENG_DIR/js/discover-checklist.md - never restart the run from zero. REVIEW
may only be ticked after every earlier box is ticked.

## Corpus layout (doctrine tree)

    $RUN/
      raw/
        inline/            one file per script block: {page-slug}.{index}.js
        external/          every .js fetched, original bytes, unmodified
        sourcemaps/        .map files + restored original sources
        historical/        wayback/gau-only files (ADDITIONAL branch, may 404 today)
        katana-responses/  (scratch; deleted after URL extraction)
      beautified/
        inline/            same filenames as raw/inline/
        external/          same filenames as raw/external/
      ast/
        external/          {name}.ast.json per file (JSON envelope, see Step 7)
        symbols.json       globals, exports, and where each is defined
        jsluice-urls.jsonl
      analysis/
        inline/            {name}.md - one note per inline block
        external/          {name}.md - one note per JS file
        site-summary.md    cross-file picture: auth flow, API surface, stack
      findings/
        endpoints.jsonl
      manifest.md          human table (exit artifact, gate anchor)
      manifest.sha256      machine sidecar (see Step 6)

Skeleton:

    mkdir -p "$RUN"/raw/{inline,external,sourcemaps,historical,katana-responses} \
             "$RUN"/beautified/{inline,external} \
             "$RUN"/ast/external \
             "$RUN"/analysis/{inline,external} \
             "$RUN"/findings

The doctrine tree is the floor, not the ceiling. Old->new mapping for
existing corpora (migration is a js-discover job, mechanical, recorded in
the manifest): inline/ -> raw/inline/, files/ -> raw/external/, historical/
-> raw/historical/, maps/ -> raw/sourcemaps/, manifest.md regenerated with
the dest column.

## Step 1 - Inline JS

For each page you touch, get RENDERED html (inline scripts differ from raw).
Pre-verify the URL against scope.md by hand (wigolo runs on the WSL seat
at /opt/wigolo - NOT the VMware VM, NOT behind the
scope-shim; its advisories print on stderr - keep stderr visible):

    cd /opt/wigolo && ./node_modules/.bin/wigolo fetch '<url>'

If the WSL distro is down, fall back to the shim binary:
/opt/scope-shim/bin/curl.

If a wigolo fetch fails or a page needs interaction, use the chrome devtools
MCP (seat-side) and save the rendered DOM. Extract `<script>` bodies WITHOUT
`src=` into $RUN/raw/inline/{page-slug}.{index}.js: slug = the page URL path
slugified ([^a-z0-9]+ -> '-'), root page = 'index'; index = 0-based order of
the script block in the rendered DOM. Record the page URL in the manifest row
(source = inline).

## Step 2 - JS files via spider (katana)

    /home/tz/go/bin/katana -u "https://<domain>" -d 3 -jc -jsl -kf all -fs rdn -iqp \
      -timeout 15 -retry 2 -ct 30m -rl 10 -hrl 2 -c 5 -p 2 \
      -sr -srd "$RUN/raw/katana-responses" \
      -nc -silent -o "$RUN/raw/katana-urls.txt" -elog "$RUN/raw/katana-errors.log"

    grep -E "[.]js(\?|$)" "$RUN/raw/katana-urls.txt" | sort -u > "$RUN/raw/js-urls.txt"
    rm -rf "$RUN/raw/katana-responses"   # scratch; delete after URL extraction

Flags verified against --help: -jc, -jsl, -kf all, -fs rdn (default, pinned),
-iqp, -retry (not -retries), -ct, -rl/-hrl, -sr/-srd, -elog. NEVER add -ns
or -do (scope), and never -download-refered-js anywhere. Rate caps respect
no_dos RoE. Fetch every js-urls.txt entry to a terminal state per URL:

    while read -r u; do
      # hash the full URL (querystring included) into the stored filename so
      # distinct ?v= variants never collide in raw/external/
      b=$(printf "%s" "$u" | sha256sum | cut -c1-16)_$(basename "$u" | tr '/?&=' '____' | cut -c1-100)
      code=$(/opt/scope-shim/bin/curl -sS --max-time 30 --retry 2 --retry-delay 2 \
        -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
        -o "$RUN/raw/external/$b" -w "%{http_code}" "$u")
      echo "$code $u" | tee -a "$RUN/raw/fetch-log.txt"
      case "$code" in
        200) : ;;
        404) rm -f "$RUN/raw/external/$b"; echo "404-archived $u" >> "$RUN/raw/fetch-log.txt" ;;
        *)
          rm -f "$RUN/raw/external/$b"
          # retry once via wigolo fetch (seat side - pre-verify URL against
          # scope.md first); on repeated failure record the terminal state:
          echo "BLOCKED/$code $u" >> "$RUN/raw/fetch-log.txt"
          # never silently dropped
          ;;
      esac
    done < "$RUN/raw/js-urls.txt"

## Step 2b - Dynamic-site branch (Interceptor)

CHOOSE INTERCEPTOR when ANY of:
- katana returned < 5 same-host .js URLs, or a bot wall / JS challenge /
  403-429 wall appeared in Step 2 or in wigolo fetches
- the surface is auth-gated (sessions get minted INSIDE the automation
  instance with the engagement's own accounts, per identities.md)
- chunks load from domains other than the main host (cross-domain chunked
  JS; the composed spider follows them, katana -fs rdn does not)
- scripts only appear in the rendered DOM after hydration

Otherwise katana (cheap, shim-visible) stays the default; wigolo remains
the single-page rendered-DOM fallback. katana first, escalate to
Interceptor on any trigger, merge URL lists (dedupe by URL) before the
Step 2 fetch pipeline. Record the branch decision in the manifest.

Interceptor runs SEAT-SIDE driving a DEDICATED Edge automation instance -
its own --user-data-dir, CDP on 9334, NEVER the operator's personal
browser profiles (BROWSER LAW, hook-enforced). The composed spider loop
(open -> links -> act click -> net capture) executes every control,
visits every link, and captures chunked JavaScript including chunks
loaded from other domains.

STACK (DONE - no operator step left). Bring the automation instance up
with `bash scripts/interceptor-automation.sh up`, and export
INTERCEPTOR_CONTEXT from its `context` output before every CLI call.
Invoke the compiled CLI directly:
/mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor/dist/interceptor
(no bun prefix for the built exe). If the stack fails to come up, this
branch is unavailable: run katana+wigolo and note
INTERCEPTOR-UNAVAILABLE in the manifest; tick the checklist Interceptor
boxes with "N/A: not fired".

Invocation (seat-side, full paths; there is NO -spider/-out surface on
this build - verify with `interceptor manifest` before relying on any
verb; compose the spider from verbs per skills/surface/interceptor/
SKILL.md, which owns the canonical recipe - verb block and loop live
THERE (open/links/act/net; verify against `interceptor manifest`).
js-discover owns only the corpus side: every .js body in the capture ->
raw/external/ (dedupe by sha256 via manifest dup-of); non-JS captures
stay under
/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>/js/<domain>/raw/interceptor/
as evidence; pull the HAR with `save --out <corpus-path> <expr>` (-out
does not exist as a capture verb).

Capture mapping: every .js body in the capture -> raw/external/ (original
bytes, dedupe by sha256 via manifest dup-of; manifest source =
interceptor; cross-domain chunk hosts recorded in the url column for
provenance). Non-JS captures stay under raw/interceptor/ as evidence.
Write raw/interceptor/hosts-seen.txt (one host per line) and diff it
against the in-scope list in REVIEW.

Auth model: sessions are minted INSIDE the automation instance with the
engagement's own accounts (identities.md owns the credentials; the
instance only holds the resulting cookies). Record which account produced
the capture in the manifest. js-parser replays interceptor-sourced
endpoints GET-only, with captured session headers, inside that session.
Teardown = UI logout-all + verify.

SCOPE COMPENSATING CONTROL (binding): the scope-shim cannot see
real-browser traffic. Spider targets come from the engagement in-scope
list ONLY; every host the spider may touch - including cross-domain chunk
hosts discovered mid-crawl - is verified in-scope BEFORE click/navigation
execution; out-of-scope chunk hosts are recorded OUT-OF-SCOPE-SKIPPED,
never fetched. The nftables egress allowlist is the real fix and remains
deferred.

## Step 3 - Lazy-loaded bundles

Primary: jsluice urls over ALL of raw/external with -R resolution (chunk
paths are relative). Files are POSITIONAL arguments to jsluice - there is
no input -f in urls mode (-f exists only in query mode = include-filename):

    find "$RUN/raw/external" -name "*.js" -print0 | xargs -0 -r \
      /home/tz/go/bin/jsluice urls -u -S -c 4 -R "https://<domain>" \
      > "$RUN/ast/jsluice-urls.jsonl"

    jq -r ".url" "$RUN/ast/jsluice-urls.jsonl" | sort -u >> "$RUN/raw/js-urls.txt"
    sort -u "$RUN/raw/js-urls.txt" -o "$RUN/raw/js-urls.txt"

Fetch new URLs via the Step 2 loop. Fallback cross-check ONLY (not a
primary instruction), regex on ONE line:

    grep -oE "import\(|static/chunks|\.chunk\.js|webpackChunk" <main-bundle> | sort | uniq -c

Do not skip this step: lazy chunks carry the bulk of modern SPA code.

## Step 4 - Historical JS

    /home/tz/.local/bin/waymore -i "<domain>" -mode U \
      -oU "$RUN/raw/historical/waymore-urls.txt" \
      -mt application/javascript,text/javascript \
      -t 30 -r 2 -p 3

(-mt MATCHES mimes; -ft would EXCLUDE them - do not use.)

    /home/tz/go/bin/gau --threads 4 --timeout 45 --retries 2 --subs \
      --providers wayback,commoncrawl,otx,urlscan \
      --blacklist png,jpg,jpeg,gif,css,woff,woff2,ttf,svg,ico,mp4 \
      --o "$RUN/raw/historical/gau-urls.txt" "<domain>"

(gau output flag is --o, not -o.)

    grep -hE "[.]js(\?|$)" "$RUN/raw/historical/waymore-urls.txt" \
      "$RUN/raw/historical/gau-urls.txt" | sort -u \
      > "$RUN/raw/historical/js-urls.txt"

Fetch live candidates via the Step 2 loop. 404-today URLs stay in the
historical URL list with their wayback snapshot URL (terminal state
404-archived) - never silently dropped; old bundles expose retired
endpoints that often still resolve on origin.

## Step 5 - Sourcemaps

Probe every collected .js URL for a sibling .map:

    while read -r u; do
      b=$(basename "$u")
      code=$(/opt/scope-shim/bin/curl -sS --max-time 20 -o "$RUN/raw/sourcemaps/$b.map" -w "%{http_code}" "$u.map")
      echo "map $code $u.map" >> "$RUN/raw/fetch-log.txt"
      if [ "$code" = "200" ]; then
        python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if 'sources' in d else 1)" \
          "$RUN/raw/sourcemaps/$b.map" || { echo "map-not-json $u.map" >> "$RUN/raw/fetch-log.txt"; rm -f "$RUN/raw/sourcemaps/$b.map"; }
      else
        rm -f "$RUN/raw/sourcemaps/$b.map"
      fi
    done < "$RUN/raw/js-urls.txt"

On a hit: restore the original sources into $RUN/raw/sourcemaps/sources/.
A .map hit is a finding-adjacent informational row in the report (source
exposure).

For bundled apps (chunk-loading or source-map-bearing builds), run jxscout
(THIS launch+copy block is labeled **K8** - js-parser inherits it BY REFERENCE,
in server mode for chunk + source recovery (the SINGLE canonical block -
js-parser references THIS block, never a copy; all flags verified against
--help). Non-bundled corpora (no chunks, no maps): tick the Step 5 jxscout
box "N/A: not a bundled app" and skip - do not force a server for a
corpus with nothing to recover.

    nohup /home/tz/go/bin/jxscout \
      -project-name "<eng>-<domain>" \
      -scope "*<domain>*" \
      -port 3333 -hostname 127.0.0.1 \
      -fetch-concurrency 3 -save-concurrency 3 -beautifier-concurrency 3 \
      -chunk-discoverer-concurrency 2 -ast-analyzer-concurrency 3 \
      -rate-limiter-max-requests-per-second 2 \
      -chunk-discoverer-bruteforce-limit 1000 \
      -js-requests-cache-ttl 30m -html-requests-cache-ttl 30m \
      -debug > "$RUN/raw/sourcemaps/jxscout.log" 2>&1 &

NEVER pass -download-refered-js (pulls out-of-scope JS - scope-guard
contract). Increment -port (3334, ...) if another lane holds 3333. jxscout
has NO -save-dir/-beautified-dir; the project dir is tool-internal cache,
NEVER an artifact of record. After the run: locate the project dir via the
-debug log, then copy it into the corpus (MANDATORY):

    cp -r <jxscout-project-dir>/* "$RUN/raw/sourcemaps/jxscout/"
(end of block K8; the scope pre-flight above rides with every K8 use)

and copy beautified chunk sources into $RUN/beautified/external/.

## Step 6 - Manifest (the exit artifact)

manifest.md - one row per FETCHED URL (bodies are deduped on disk, every
fetched URL keeps a row):

    url | sha256 | bytes | dest | source | dup-of | fetched-at

dest = corpus-relative path; source in inline|spider|lazy|historical|
sourcemap|interceptor; dup-of = sha256 of the kept twin or '-'. Record
tool versions as a manifest note. File count > 0 or the run FAILED (an
empty corpus is a failed lane, not a quiet success). Generate the machine
sidecar (sha256sum -c cannot parse a markdown table), verify it, and seed
endpoints.jsonl as valid JSONL (0 rows allowed at discover):

    sed 's/ *| */|/g; s/^|//; s/|$//' "$RUN/manifest.md" | awk -F"|" 'NR>2 {print $2 "  " $4}' > "$RUN/manifest.sha256"
    (cd "$RUN" && sha256sum -c manifest.sha256)
    [ -s "$RUN/findings/endpoints.jsonl" ] || : > "$RUN/findings/endpoints.jsonl"

Append katana/jxscout endpoint exports to findings/endpoints.jsonl when
present. Append every host you fetched from as a row in the engagement
`_requests.md` (lane = your lane id, summary = "js-discover"). The
canonical _requests.md lives in the engagement tree at
$ENG_DIR/_requests.md (VMshare spelling); create it if absent - it is the
host-audit ledger the leak-gate reads, a missing file silently drops the
audit trail.

After writing `endpoints.jsonl`, import it into the hunt feed with the
`surface_backlog.py import-jsonl` subcommand: `python3
scripts/surface_backlog.py <eng> import-jsonl <corpus>/endpoints.jsonl
--source js-discover` (rows need `surface` and `class_hint`; class_hint
from the endpoint shape: api-ish -> `api`, param-heavy -> `sqli`/`xss`
per param context).

## Step 7 - AST + symbols

Per-file AST (jsluice tree emits tree-sitter s-expressions with a
"filename:" header, NOT JSON - wrap in a JSON envelope via python3):

    for f in "$RUN"/raw/external/*.js; do
      /home/tz/go/bin/jsluice tree "$f" | python3 -c \
        'import json,sys; print(json.dumps({"file": sys.argv[1], "tree": sys.stdin.read()}))' \
        "$f" > "$RUN/ast/external/$(basename "$f").ast.json"
    done
    # note: python3 -c payload above contains single quotes - ship the whole
    # loop as a base64 payload through vm-ssh, not inline

Symbols via VERIFIED query shapes ONLY (right-side alternations like
right: [(function_expression) (arrow_function)] match NOTHING - EXPR
placeholder substitution; do not use them). In query mode -f =
include-filename; files are positional:

    /home/tz/go/bin/jsluice query -q "(function_declaration name: (identifier) @fn)" -f "$RUN"/raw/external/*.js > "$RUN/ast/symbols-functions.jsonl"
    /home/tz/go/bin/jsluice query -q "(assignment_expression left: (member_expression property: (property_identifier) @prop))" -f "$RUN"/raw/external/*.js > "$RUN/ast/symbols-assignments.jsonl"
    /home/tz/go/bin/jsluice query -q "(variable_declarator name: (identifier) @name)" -f "$RUN"/raw/external/*.js > "$RUN/ast/symbols-vars.jsonl"

Reduce the three JSONL files into $RUN/ast/symbols.json
({"symbols": [{name, kind, file}]}, kind = function|assignment|var). The
heredoc below is UNQUOTED so $RUN expands; ship via the base64 payload
transport when quoting gets hairy:

    cat > /tmp/symbols.py <<PY
    import json, os
    run = os.environ["RUN"]
    out = []
    for kind, path in [("function","symbols-functions.jsonl"),("assignment","symbols-assignments.jsonl"),("var","symbols-vars.jsonl")]:
        for line in open(run + "/ast/" + path):
            line = line.strip()
            if not line.startswith("{"): continue
            r = json.loads(line)
            name = r.get("fn") or r.get("prop") or r.get("name")
            if name: out.append({"name": name, "kind": kind, "file": r.get("filename","")})
    json.dump({"symbols": out}, open(run + "/ast/symbols.json","w"), indent=1)
    print(len(out))
    PY
    RUN="$RUN" python3 /tmp/symbols.py

Placed discover-side so the parser entry gate can verify it.

## Wiki

Hub: [[web-moc]] | Primary page: [[static-code-analysis]] | Arsenal: [[recon-dorks]]
Anchors: [[javascript-source-map-exploitation]], [[secret-hunting]]

## Handoff

Point js-parser at $RUN (absolute path); the parser must find
$RUN/manifest.md + manifest.sha256, ast/symbols.json, and
findings/endpoints.jsonl there. Do not start analyzing here - the split
exists so each skill stays small enough that an agent executes all of it.

## Validation

- Proof = the exit manifest: every corpus file sha256'd, sources
  attributed, counts match the fetch log (js-urls attempted vs
  corpus rows). A manifest row without a file on disk (or the
  reverse) fails REVIEW.
- Negative control: a deliberately bogus URL in the fetch set lands
  in fetch-log.txt as a non-200 and NEVER in the corpus.

## False Positives

- A 200 that returns an HTML error/SPA-shell instead of JS (content-
  sniff before corpus insert - first bytes `<!DOCTYPE`/`<html`).
- Cross-origin chunks attributed to the wrong host (provenance column
  is load-bearing for the scope audit).
- Duplicate bundles under different names (sha256 dup-of rows collapse
  them; never delete the original bytes).

## Deadends

Append per dead source: host unreachable, JS behind auth the corpus
session lacks (record the auth shape for the auth lane), source maps
404 across the corpus. A deadend names WHAT new input would reopen it.

## Stop conditions

Manifest complete + REVIEW box checked; or the remaining un-fetched
set is all-deadend; or the operator stops the collection window. Never
abandon a corpus mid-write (partial manifest = rerun from fetch-log).
