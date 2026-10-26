# active-workflow workflow (Vhost: {{VHOST}})

## Stage table

| stage | name | entry gate | outputs |
|---|---|---|---|
| 0 | lock + attach | vhost lock done | caido project, identities row |
| 1 | surface + context | stage 0 checklist COMPLETE | surface notes, wiki context |
| 2 | JS corpus + extraction | manifest.sha256 | js-lists/* |
| 3 | list-fed fuzz | api+hidden endpoints tables | live_status updates, anomalies |
| 4 | version research | tech-versions table | version-research.md |
| 5 | signal-gated hunts | dispatch-queue cites rows | hunt lane results |
| 6 | RTL pass review | stage 5 lanes COMPLETE | decisions.md, pass-N-summary.md |

## Stage 0: lock + attach

- `python3 scripts/offensive.py vhost lock {{VHOST}}` (workflow-brain does it
  if not done).
- Caido project per engagement: `~/caido.sh project <eng>`; every probe lands
  in History; Replay collections named after the vhost.
- `interceptor` ONLY on demand: login, MFA, CAPTCHA, SPA state needing the
  operator's browser. Export the authenticated session (`export-curl <id>
  --config`) into Caido; record the profile in `ledgers/identities.md`.

## Stage 1: surface + context

- Probe via caido (never bare curl when the engagement rule says Burp/Caido
  class tooling).
- Wiki is primary (~90%): qmd for tech stack, sink behavior, tool syntax.
  graphify has exactly two roles: multi-hop chaining
  (`python3 scripts/wiki-graph.py path "<primitive>" "<impact>"`) and AST
  graphing of large recovered source-map trees before reading.

## Stage 2: JS corpus + extraction

- `js-discover` then `js-extractor` (lane-init both; js-extractor checklist
  gates the outputs).

## Stage 3: list-fed fuzz (no blind generic brute force first)

- Build `poc/{{VHOST}}/js-lists/custom-wordlist.txt` (js-extractor step 9
  did); ffuf/arjun against the locked vhost only; when RoE bars fast
  scanners, run the battery as caido Replay requests instead.
- Probe `hidden-endpoints.md` rows and old API version prefixes; fuzz
  undocumented parameters on `api-endpoints.md` rows.
- Promote anomalies (200 on hidden route, 401-to-200, 500, 403-bypass
  candidates) into named caido Replay collections; update
  `js-lists/api-endpoints.md` rows with `live_status`.

## Stage 4: version/CVE research lane

- Inputs: `tech-versions.md` + stage 1 headers. Vault first
  (`Skill(wiki-arsenal)` + qmd), then searchsploit on the VM, then wigolo
  cached web intel (NVD, GHSA, CISA KEV, vendor changelogs).
- Silent patch detected -> `nday` patch-diffing.
- Verified CVEs + config preconditions -> `poc/{{VHOST}}/version-research.md`.

## Stage 5: signal-gated hunts

- `poc/{{VHOST}}/dispatch-queue.md` (`| signal | source_row | hunt | priority |`):
  a hunt-* dispatches ONLY backed by a concrete row in `sinks-*.md`,
  `api-endpoints.md`, or `version-research.md`.
- Wiki-on-sink lookup before probing (framework + sink type gadgets).
- Lanes climb the hunt-core blocked-handling ladder to the bounded ceiling;
  every request logged in `ledgers/_requests.md`; confirm-worthy requests
  promoted to caido Replay.

## Stage 6: pass review + RTL

- RTL consult (glm-5.3-max) reads `js-lists/*`, `Vuln-index.md`,
  `Deadends.md`; writes 2-4 ranked directions + STOPs to `decisions.md`.
- Pass 2 focus: authed vs unauthed differential, chaining pass-1 partials,
  secondary sinks with new parameter shapes, re-run js-discover/js-extractor
  on post-login bundles.
- Pass 3 focus: cross-feature business logic, races, cache/header anomalies,
  zero untested high-confidence `js-lists/` rows.
- Write `poc/{{VHOST}}/pass-N-summary.md` (what ran, what closed, what
  remains). Close the vhost only via `vhost unlock`.

## N/A escapes

- `N/A: interceptor not needed (no operator-browser interaction this pass)`
- `N/A: no JS on this vhost (0 first-party files)`
- `N/A: RoE bars active fuzzing (passive-only vhost)`
