# js-discover workflow (stage 2a)

1. Corpus root: `targets/<eng>/js/<domain>/` with `raw/{inline,external,
   sourcemaps,historical}`, `beautified/`, `findings/endpoints.jsonl`,
   `manifest.md` + `manifest.sha256`.
2. Sources: live pages of the locked vhost, sourcemaps, wayback historical
   JS URLs from `osint/wayback-urls.md`.
3. Beautify everything (prettier/js-beautify on the VM); write the manifest
   with sha256 per file. The manifest gate (js-extractor entry) depends on it.

## N/A escapes

- `N/A: no JS reachable on this vhost`
