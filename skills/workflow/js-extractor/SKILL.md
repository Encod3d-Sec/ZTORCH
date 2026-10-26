---
name: js-extractor
description: Full-read JS analysis for the locked vhost. Reads every first-party
  file end to end and emits the js-lists tables (API endpoints, hidden routes,
  third parties, tech versions, DOM/XSS/SQLi/CMDi sinks) that fuel fuzz,
  version research, and hunt selection. Runs as an analysis lane (glm-5.3).
---

# js-extractor

Consumes the js-discover corpus for the locked vhost, applies the full-read
law, and writes `poc/<vhost>/js-lists/`. Dispatch via
`python3 scripts/offensive.py lane-init --vhost <host> --skill js-extractor`.

Entry requirements: js-discover ran on this vhost (manifest present). Read
`workflow.md` before acting; the checklist is machine-gated (completion-gate
`--strict`, G10).

Full-read law (operator directive, carried verbatim): never grep a `.js` file
to summarize it; read it fully end to end. Grep and the AST index only LOCATE;
the read is the analysis.
