---
title: "LinkFinder"
type: tool
tags: [web, js-analysis, endpoint-discovery, recon]
date_created: 2026-09-03
date_updated: 2026-09-03
sources: []
phase: recon
---

# LinkFinder

## Purpose

LinkFinder is a Python tool (and matching Burp Suite extension) that parses JavaScript source,
including minified and bundled files, to extract endpoint paths, API routes, and absolute/relative
URLs referenced in the code. Applications routinely wire up API calls, admin routes, and internal
endpoints directly in client-side JS that never appear in any HTML link or sitemap -- a directory
wordlist brute-force would never guess `/api/v2/internal/export-users`, but it's sitting in plain
text (or barely obfuscated) inside `app.bundle.js`. LinkFinder turns every JS file the target ships
into an endpoint list.

## Installation

```bash
git clone https://github.com/GerbenJavado/LinkFinder.git
cd LinkFinder
pip3 install -r requirements.txt
python3 setup.py install
```

Also available as a Burp Suite extension (via the BApp Store or manual Jython load) for running the
same extraction against traffic already captured in Burp's proxy history.

## Core usage

```bash
python3 linkfinder.py -i https://target.example/app.js -o cli
```

`-i` takes a single file, a URL, a local folder, or a burp/har export; `-o` selects the output
format (`cli` for direct terminal output, or an HTML filename for a browsable report).

### Single file, printed to terminal

```bash
python3 linkfinder.py -i https://target.example/static/js/app.js -o cli
```

### Recursive crawl: pull every JS file on the target first

```bash
python3 linkfinder.py -i 'https://target.example/*' -d -o cli
```

`-d` tells LinkFinder to crawl the target starting from the given URL, follow links, and pull down
every JavaScript file it discovers before running extraction against all of them -- use this over
single-file mode whenever you don't already have a specific bundle URL, since a modern SPA usually
ships many chunked JS files, not one.

### Regex-filtering the output

```bash
# Only show results matching a pattern, e.g. narrow to interesting-looking API paths
python3 linkfinder.py -i https://target.example/app.js -o cli | grep -Ei '/(api|admin|internal|v[0-9])/'
```

## Common use cases

- **Surfacing undocumented API routes before fuzzing.** Run LinkFinder against every JS bundle a
  target ships as an early recon step, before or alongside directory fuzzing -- endpoints it finds
  are confirmed to exist in the code (not guessed), so they're worth manually probing first. See
  [[web-attack-surface]].

```bash
python3 linkfinder.py -i 'https://target.example/*' -d -o cli
# /api/v1/users/export
# /internal/debug/status
# /api/v2/admin/impersonate
```

- **Pairing with a source-map check for readable output.** A minified bundle's variable/function
  names are meaningless, but if the target accidentally ships a `.js.map` file alongside it
  (`app.js.map`), the source map reverses the minified code back to original filenames and readable
  source -- often revealing routes, comments, and internal naming LinkFinder's regex pass on the raw
  minified JS would miss entirely. Check for the sourcemap first (`curl -I
  https://target.example/app.js.map`), and if present, use it before or alongside LinkFinder. See
  [[javascript-source-map-exploitation]].

- **Chained recon after a JS crawl tool.** Feed URLs already gathered by something like `gau`/`waybackurls`
  filtered down to `.js` files straight into LinkFinder, rather than re-crawling the site yourself:

```bash
gau target.example | grep '\.js$' | while read js; do
  python3 linkfinder.py -i "$js" -o cli
done
```

- **Burp extension mode for traffic you've already captured.** If you're already driving the target
  through Burp, load the LinkFinder extension and run it against proxy history directly instead of
  re-fetching every JS file with the CLI tool.

## Tips and gotchas

- **A found endpoint is a lead, not a confirmed vulnerability.** LinkFinder only extracts strings
  that look like paths/URLs from the JS regex-wise; it does not test whether the endpoint exists,
  requires auth, or does anything interesting. Manually probe every promising result.

- **Expect noise.** Minified/bundled JS often embeds third-party library internals, CDN URLs, and
  dead/unused routes alongside real API paths. Skim the full output rather than grepping for one
  keyword -- the endpoint you actually want may not match an obvious filter, and a narrow grep can
  hide exactly the AJAX/admin route you're looking for.

- **`-d` crawl scope can run away on a large SPA.** A recursive crawl on a big single-page app can
  pull down hundreds of chunked JS files; if it's taking too long, target a specific bundle
  (`main.js`, `vendor.js`, or the app's largest chunk) directly instead of the wildcard crawl.

- **Always check for the source map first.** If `app.js.map` (or similar) is present and
  accessible, reversing it gives far cleaner results than regexing the minified original -- do this
  before spending time manually chasing LinkFinder matches through obfuscated code. See
  [[javascript-source-map-exploitation]].

- **Re-run after every meaningful app interaction.** A SPA often lazy-loads additional JS chunks
  only after a specific user action (opening a settings panel, hitting an admin-gated route); a
  single crawl at page-load may miss endpoints that only ship in a chunk loaded later. Re-run against
  freshly captured traffic after exploring the app's UI.

## Related

- [[web-attack-surface]]: where JS-derived endpoint discovery fits in overall recon
- [[javascript-source-map-exploitation]]: reversing a `.js.map` back to original source for cleaner results

## Sources

- LinkFinder GitHub: https://github.com/GerbenJavado/LinkFinder
