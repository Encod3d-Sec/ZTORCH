# js-extractor workflow (Vhost: {{VHOST}})

## Entry Gate

0.1 Verify the js-discover corpus: `manifest.sha256` passes `sha256sum -c`
    semantics (checklist rule does it). If the manifest is missing, STOP:
    run `js-discover` first.
0.2 Populate `ledgers/source-ledger.md`: one row per first-party file
    (`| file | bytes | lines | read |` with `read: no` until read).

## Execution

1. Classify files: first-party app code vs stock third-party bundles. A bundle
   is skippable ONLY if its SHA256 or banner matches a known stock library
   (jquery.min.js, react-dom.production.min.js class); record its name and
   exact version in `tech-versions.md` and mark it `read: skipped-stock` in the
   source ledger. Anything unmatched is first-party: read it.
2. Full read. Files under 2000 lines: read whole. Over 2000 lines: build the
   AST symbol index first (`jsluice` + `scripts/tells.py` if available), then
   read sequentially in chunks, updating `ledgers/source-ledger.md` offsets
   per chunk, until every first-party file is `read: yes`.
3. Extract API endpoints -> `js-lists/api-endpoints.md`
   (`| method | path | params | auth_required | source_file |`; source_file
   carries `file:line`; auth_required is yes/no/unknown from token checks in
   code).
4. Extract hidden endpoints (unlinked, admin/internal/debug, feature-flagged,
   deprecated version prefixes) -> `js-lists/hidden-endpoints.md`
   (`| path | kind | evidence |`).
5. Extract third-party links -> `js-lists/third-party-links.md`
   (`| domain | kind | source_file |`). Cross-check every domain against
   scope: in-scope subdomains are appended to `lists/inscope-hosts.md` (via
   the returned envelope Pending-Writes; the lane NEVER edits the list),
   out-of-scope to `lists/outscope-3rdparty.md`. An empty result writes the
   literal line `(none found)` under the table.
6. Map tech + versions -> `js-lists/tech-versions.md`
   (`| tech | version | evidence |`).
7. Sinks, each with source-to-sink taint notes (`| sink | file_line | taint_note |`):
   - `sinks-dom.md` + `sinks-xss.md`: innerHTML, dangerouslySetInnerHTML,
     document.write, location assignment, postMessage handlers, eval, Function.
   - `sinks-sqli.md` (`| pattern | file_line | note |`): client-side query
     builders, raw GraphQL fragments, filter/sort constructors, NoSQL operators.
   - `sinks-cmdi.md` (`| param_shape | file_line | note |`): server-reported
     exec/template/render/export/webhook/import params, file-path and
     command-shaped parameters.
8. Log every request the lane made into `ledgers/_requests.md` with the lane
   id (passive analysis usually makes zero requests; the entry gate still
   requires the lane id line).

## Exit Gate

9. Build `js-lists/custom-wordlist.txt` (paths, route prefixes, parameter
   names, one per line, deduped) for stage 3.
10. Return the 15-line envelope (Scope, Result, Key files, Issues,
    Pending-Writes). The checklist gate must print VERDICT: COMPLETE first.

## N/A escapes

- `N/A: not a bundled app (0 chunks, 0 sourcemaps)`
- `N/A: zero third-party scripts on this vhost`
- `N/A: no API surface in first-party JS`
