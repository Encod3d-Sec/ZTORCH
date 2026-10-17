# js-parser checklist

Copy this file to `$ENG_DIR/js/parser-checklist.md` at run start. `- [ ]`
means not finished; an unchecked box at stop means the lane is UNCHECKED
and must be re-run from the first unchecked step (mirrors the
completion-gate ledger). Bitter-pill runs (see SKILL.md) copy NO checklist
and are declared by a _requests.md row (lane = js-parser-bitterpill).

## Entry

- [ ] js-discover corpus at $RUN (VMshare spelling): manifest.md + manifest.sha256 (sha256sum -c passes), ast/symbols.json parses, findings/endpoints.jsonl parses as JSONL, raw/ has >= 1 file
- [ ] Checklist copied to $ENG_DIR/js/parser-checklist.md
- [ ] Exit contract RE-VERIFIED at run start (not just dispatch): manifest sha256 passes, symbols.json parses, endpoints.jsonl parses, raw/ >= 1 file; verification timestamp recorded in analysis/site-summary.md header

## Analysis

- [ ] Step 1 - Normalization done via jsluice format (K10) to beautified/{inline,external}/, same filenames as raw/; OBFUSCATED files noted, none skipped silently @ $RUN/beautified/external
  - artifact non-zero bytes + expected format: beautified/external count == raw/external count (each gap justified by an OBFUSCATED row); beautified files are multi-line
- [ ] Step 2 - Bulk jsluice pass (K11) + endpoints.jsonl normalized (K11b) @ $RUN/findings/endpoints.jsonl
  - artifact non-zero bytes + expected format: findings/endpoints.jsonl valid JSONL; every line has url, method, params, source_file, line, live_guess
- [ ] Step 3 - jxscout output CONSUMED from raw/sourcemaps/jxscout/ (server re-run ONLY if absent AND corpus is bundled, same K8 block + its scope pre-flight and post-run host diff); endpoint-set diff recorded (N/A: discover skipped jxscout - not a bundled app)
  - artifact non-zero bytes + expected format: diff note in site-summary.md ("no differences" is a valid non-zero note)
- [ ] Step 4 - Routes triaged: admin / feature flags / interesting comments flagged
  - artifact non-zero bytes + expected format: flagged rows present in endpoints.jsonl with adjusted live_guess; zero-row tables stated explicitly empty
- [ ] Step 5 - API version families grouped; old versions flagged as prime targets
  - artifact non-zero bytes + expected format: inventory table (group | versions | oldest | sample curl) in site-summary.md
- [ ] Step 6 - Secrets pass A0 (jsluice secrets, K12) complete @ $RUN/findings/secrets-jsluice.jsonl
  - artifact non-zero bytes + expected file format: findings/secrets-jsluice.jsonl valid JSONL (empty allowed only with explicit "no hits" note)
- [ ] Step 6 - Secrets pass A (house patterns via K12 file) complete
- [ ] Step 6 - Secrets pass B (high entropy > 4.5) complete; every hit carries file:line
- [ ] Step 6 - Every secret carries proof-gate status (confirmed = diff-observed live-key proof where RoE allows | suspected); interceptor self-identity hits tagged, never promoted
- [ ] Step 7 - Libraries fingerprinted; outdated/CVE noted with citations; frontend framework identified
  - artifact non-zero bytes + expected format: each row cites a fetched release-page URL; framework named in site-summary.md stack section
- [ ] Step 8 - Gadget map built from sinks + symbols (sources -> sinks, candidate classes)
  - artifact non-zero bytes + expected format: gadget rows have source | sink | file:line | chain guess | candidate class

## Output

- [ ] Tier A indicator grep pass over raw/external + raw/inline @ $RUN/ast/grep-hits.txt (indicators: known endpoint urls, secret keywords, sink names, auth/role keywords)
- [ ] Per-file notes: Tier B full notes only for files clearing the hit-density gate or qualifying (jxscout/sourcemap original | >= 2 endpoint refs | >= 1 secrets row); every OTHER file carries its one-line "grep-only pass" note - note counts still match disk, nothing silently skipped
- [ ] Secrets masked in every human-readable artifact (first/last 4 chars + file:line, raw values only in findings/*.jsonl); no validation call fired without an explicit operator ask
- [ ] Interceptor-sourced rows replayed GET-only via scope-shim, result merged into the EXISTING row as verified:true (N/A: no interceptor-sourced rows in the manifest)
- [ ] analysis/site-summary.md written: auth flow, API surface, stack sections all present; curl one-liners inline @ $RUN/analysis/site-summary.md
- [ ] $ENG_DIR/js-analysis.md pointer updated AND carries PARSER-DONE + counts (endpoints, secrets suspected/confirmed, gadgets)
- [ ] Every high live-guess endpoint has a ready-to-run curl one-liner (GET-only for interceptor-sourced endpoints)
- [ ] Executed requests appended to _requests.md ($ENG_DIR/_requests.md - create if absent)
- [ ] New endpoint rows pushed to the offensive surface (state.md asset table, dedupe by url+endpoint)

## Stop conditions

- [ ] findings/endpoints.jsonl AND the secrets table each non-empty OR carry an explicit empty-state note ("no hits"); both empty with no notes = failed lane
- [ ] Nothing written into the skill dirs
- [ ] No unchecked boxes above

## REVIEW (mandatory final step)

- [ ] REVIEW: re-read every box above; for each, confirm the artifact exists, is non-zero bytes, and matches the expected format
