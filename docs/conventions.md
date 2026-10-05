# Wiki Conventions

## Cross-referencing

- Use Obsidian wiki links: `[[Page Title]]` or `[[Page Title|display text]]`
- Link to the exact page title as it appears in `index.md`.
- In technique pages, link tools on first mention. In tool pages, link techniques on first mention.
- Every course page must link to all technique and tool pages it covers.
- Target pages link to technique pages used during the engagement.

## Log format

Each entry must start with a consistent header (grep-parseable):

```
## [YYYY-MM-DD] ingest:cpts | Module Name
## [YYYY-MM-DD] ingest:portswigger | Module Name
## [YYYY-MM-DD] ingest:thm | Section Name (N rooms)
## [YYYY-MM-DD] ingest:research | Source Title
## [YYYY-MM-DD] target | Target Name -- phase
## [YYYY-MM-DD] query | Brief description
## [YYYY-MM-DD] lint | pass N
```

Followed by 2-4 bullet points summarising what changed.

## Hunt skill skeleton

Canonical section set for every `skills/hunt/hunt-*/SKILL.md` (13 slots; order as
listed, class-specific reference sections slot in where marked). Enforced in part by
`tests/test_hunt_use_when.py`.

1. Frontmatter: `name` + `description` ending with a "Use when ..." trigger sentence.
2. `# Hunt: <Class>` opener + the assumes-`hunt-core` block (scope gate, two-account
   rule, confirmation gate, enum limits, stop conditions, FIND output).
3. `## Wiki`: hub, primary page, payload arsenal, anchors, REFS line.
4. `## Confirmation gate`: what IS and IS NOT confirmation for this class.
5. `## Attack surface (signals | ranked)`: where the class lives, ranked.
6. `## Methodology`: numbered steps.
7. Class-specific references (quick references, payload tables, lessons, matrices)
   as needed.
8. `## Chaining` / `## Evasion` where they apply to the class.
9. `## Validation` (MANDATORY): the proof contract, the negative control, the
   counterevidence to seek. Distinct from the confirmation gate: the gate says what
   counts as confirmation, Validation says how to prove AND disprove the finding.
10. `## False Positives` (MANDATORY): the ranked FP list for this class, each with the
    distinguishing control (a safety claim names its control: encoder/sanitizer/block
    and where observed).
11. `## Cross-routing`: "Load hunt-X when ..." escalation lines plus at least one
    "Not this skill when ..." negative route; must name at least one other hunt skill.
12. `## Severity`: per-class rubric.
13. `## Deadends`: class deadend line format (where not covered by hunt-core).

## Style guide

- Write in clear, precise prose. No filler.
- All commands in fenced code blocks with the appropriate language tag (`bash`, `sql`, `python`, etc.).
- Use `**bold**` for defined terms on first use.
- Flag uncertainty with `[uncertain]` inline.
- Flag contradictions between sources with `[contradicts: [[Other Page]]]` inline.
- Cheatsheets use `#` comments for annotations, not prose.
- Do not add warnings or legal disclaimers to technique or cheatsheet pages.
- Never use em-dashes (--) in any output or wiki pages. Use a comma, semicolon, or rewrite the sentence instead.
- Never use emojis in any output or wiki pages.
- Angle-bracket tokens (`<value>`, `<marker>`) are never bare in page prose or tables: Obsidian parses them as HTML tags and one unclosed token breaks the whole page's rendering. Always inline-backtick them (`` `<value>` ``) or put them in a fenced code block.

## Tag taxonomy

Controlled vocabulary lives in `scripts/tag-vocab.json` (canonical `keep` set, `aliases` for synonyms, `keep_patterns` like `esc\d+`/`cve-*`, `drop` for vague tags). A tag survives only if it is canonical or used >=3x across the corpus; tool names, protocol names, and one-off vague tags are dropped.

- New pages: tag with **domain** (matches the wiki dir), **phase** (recon/enumeration/exploitation/post-exploitation/lateral-movement/privilege-escalation/persistence/evasion), **source** (thm/htb/h1/reference-import/writeup/cve), and specific **topic** tags from the vocabulary. Prefer existing canonical tags over inventing new ones.
- Don't tag with tool names (find tools by page title) or vague words (meta, technique, session, scripting).
- After bulk tag edits or before a lint pass, run `python3 scripts/normalize-tags.py` (dry-run) then `--apply`. Idempotent. **Excludes CTF and courses.**
- To add a synonym merge or rescue a wrongly-dropped tag, edit `tag-vocab.json` and re-run.
