# js-discover checklist

Copy this file to `$ENG_DIR/js/discover-checklist.md` at run start. Work
top to bottom; `- [ ]` means not finished. Any unchecked box at stop = the
run is not done and must be re-run from the first unchecked step
(completion-gate treats this list as the step ledger). On the gate nudge,
resume at the first unchecked box - do not restart.

## Entry

- [ ] Active engagement confirmed (targets/active.md) and scope checked
- [ ] Toolchain preflight passed (K1: jsluice, katana, jxscout, gau, waymore, python3, jq all present)
- [ ] ENG_DIR and RUN defined once at top of run notes (absolute paths, VM spelling /mnt/VMshare/<eng>)
- [ ] Doctrine tree created (K1b): $RUN/{raw/{inline,external,sourcemaps,historical,katana-responses},beautified/{inline,external},ast/external,analysis/{inline,external},findings}
- [ ] Checklist copied to $ENG_DIR/js/discover-checklist.md
- [ ] Spider branch chosen: katana (default) | Interceptor (section 4 criteria) - decision recorded in manifest
- [ ] JXSCOUT scope pre-flight: every reachable host verified in-scope and listed in raw/sourcemaps/jxscout-hosts-in-scope.txt (N/A: jxscout not run - only if Step 5 jxscout is N/A)

## Collection

- [ ] Step 1 - Inline JS extracted to raw/inline/{page-slug}.{index}.js
  - artifact non-zero bytes + expected format: filename matches slug.index.js; each file parses as JS; page URL in manifest
- [ ] Step 2 - Spider ran (K2); all .js URLs fetched to raw/external/ via K2b @ $RUN/raw/fetch-log.txt
  - artifact non-zero bytes + expected format: katana-urls.txt one URL per line; fetch-log.txt has a terminal state (200 | BLOCKED | 404-archived) per URL
- [ ] Step 3 - Lazy chunks extracted (K4) and fetched @ $RUN/ast/jsluice-urls.jsonl
  - artifact non-zero bytes + expected format: ast/jsluice-urls.jsonl valid JSONL with url keys
- [ ] Step 4 - Historical JS pulled (K5+K6), fetched or snapshotted
  - artifact non-zero bytes + expected format: waymore-urls.txt + gau-urls.txt exist; every historical URL has a terminal state
- [ ] Step 5 - Sourcemaps probed (K7); jxscout run (K8) with mandatory copy into raw/sourcemaps/jxscout/ @ $RUN/raw/sourcemaps/ (jxscout N/A only when corpus is not a bundled app: no chunks, no maps - tick "N/A: not a bundled app")
  - artifact non-zero bytes + expected format: every kept .map parses as JSON with a sources key; jxscout.log non-zero when jxscout ran (N/A note in manifest when skipped)
- [ ] Step 7 - AST + symbols (K3a/K3b/K3c) @ $RUN/ast/symbols.json
  - artifact non-zero bytes + expected format: one .ast.json per raw/external file, each parses; symbols.json parses with >= 1 symbol or explicit "no symbols" note
- [ ] Blocked fetches retried via wigolo, then recorded BLOCKED (none dropped)

## Interceptor branch (skip section with "N/A: not fired" if katana branch)

- [ ] TODO-OPERATOR install status checked: extension loaded + daemon answers `/mnt/c/Users/Lenovo/.bun/bin/bun.exe .../dist/interceptor status` | not installed (INTERCEPTOR-UNAVAILABLE noted in manifest)
- [ ] Every Interceptor-visited host verified in-scope BEFORE click execution (against targets/<eng>/scope.md in-scope list; check recorded per host in manifest)
- [ ] Captures ingested: .js bodies -> raw/external/ (original bytes, manifest source = interceptor); requests log kept under raw/interceptor/
- [ ] raw/interceptor/hosts-seen.txt diffed against in-scope list; any out-of-scope host is an incident row, not a corpus row

## Exit artifact

- [ ] manifest.md written: url | sha256 | bytes | dest | source | dup-of | fetched-at (parses; row count == fetched URLs; dedupe recorded via dup-of) @ $RUN/manifest.md
- [ ] manifest.sha256 sidecar generated; `sha256sum -c` passes from $RUN
- [ ] findings/endpoints.jsonl exists and parses as JSONL (0 rows allowed at discover) @ $RUN/findings/endpoints.jsonl
- [ ] File count > 0 (empty corpus = failed lane)
- [ ] Every fetched host appended as a row in _requests.md ($ENG_DIR/_requests.md - create if absent)
- [ ] When jxscout ran (any branch): -debug log hosts diffed against raw/sourcemaps/jxscout-hosts-in-scope.txt; unlisted host = incident row, not a corpus row (N/A: jxscout not run)
- [ ] js-parser pointed at $RUN (absolute path)

## Stop conditions

- [ ] All fetch attempts have a terminal state (fetched | BLOCKED | 404-archived)
- [ ] Nothing written into the skill dirs (/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/js-{discover,parser}/)
- [ ] No unchecked boxes above

## REVIEW (mandatory final step)

- [ ] REVIEW: re-read every box above; for each, confirm the artifact exists, is non-zero bytes, and matches the expected format
