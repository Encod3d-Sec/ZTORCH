---
name: obsidian-lint
description: "Use when notes are written into the vault (findings, reports, transcriptions, syncs from VMshare/lanes) or before close-out: run scripts/obsidian-lint.py to catch mangled text before the operator reads it in Obsidian."
metadata:
  hermes:
    version: 1
    author: seat
    license: MIT
    tags: [obsidian, vault, quality, lint]
    related_skills: [evidence, close-out]
---

# Obsidian lint - readability gate for vault notes

Operator rule (2026-10-15): mangled notes are unreadable in Obsidian. Raw
Killchain/JSON dumps, double-encoded transcriptions, and escape walls filed as
prose are defects, not evidence.

## When to run

- After ANY note is written under `targets/<eng>/` by an agent, lane, or sync
  (especially FIND reports and anything transcribed from web/PDF/other reports).
- Before close-out / FIND registration (pairs with the evidence skill's
  registration law).

## Command

    python3 scripts/obsidian-lint.py targets/<eng>

Exit 0 = clean; exit 1 lists every violation. Scope it narrower
(`targets/<eng>/Vulns`) for a quick gate.

## What it catches

1. **Literal `\n` mid-text** - the #1 mangle: JSON/killchain dumps pasted as
   prose. ANY occurrence outside code fences fails.
2. **Transcription artifacts** - mojibake (double-encoded UTF-8), un-rendered
   HTML entities, markdown glued mid-line (`text## Heading`), invisible
   characters (BOM/zero-width), unbalanced code fences (truncated transcription).
3. **Non-ASCII typography** - em/en-dashes, smart quotes, ellipsis, nbsp
   (repo rule: ASCII ` - ` and `'` instead).
4. **CRLF** - Windows line endings (NOTE: Python `write_text`/text-mode on this
   box emits CRLF; write bytes or normalize - the lint will catch yours too).
5. **Wall lines** - unbroken 400+ char lines outside code fences (split into
   sections); table rows and list items exempt, fenced URLs/payloads exempt.
6. **Mid-sentence hard wraps** - textwrap-style repair damage (a long line not
   ending a sentence followed by a lowercase continuation) and hyphen-split
   tokens (`X-Amz-` / `Security-Token`).
7. **Glued fences** - a closing fence carrying prose on the same line
   (````EXPECTED OUTCOME: ...````); this shape also HIDES content from the
   fence-stripper, so it can mask lane references inside broken blocks.
8. **FIND-*.md shape** - YAML frontmatter with title/type/severity/status/
   date_created required; a file starting `## FIND-` is a Killchain dump, not
   a report - convert before filing.

`evidence/` subdirs are skipped: they are verbatim lane captures, never
prose-normalized.

## Fix law

Fix the FILE, never the lint: re-transcribe with correct encoding, unwrap
escapes to real newlines, split walls into sections, add frontmatter. Do not
wrap mangled content in code fences to silence the gate - fences are for
commands and payloads only.

## Bounty-report law (FIND files are company-facing, operator 2026-10-15)

The bug bounty company does not care about our internal machinery. A FIND
report body must read like a normal, compact vulnerability report:

- NO lane names (laneA..laneZ, laneM etc.), NO agent/session handles, NO
  `agent-reports/` paths inside the PROSE. Evidence pointers belong in the
  frontmatter `sources:` block or one Evidence section at the end - never
  woven through the narrative.
- NO irrelevant dates (test-session timestamps, run dates that add nothing).
  Keep only verification dates that change the reader's understanding
  (e.g. "re-verified after the 2026-10-13 patch").
- Compact structure: Summary, Preconditions, Reproduction (numbered,
  copy-pasteable), Impact, What-is-NOT-possible (negative controls),
  Remediation, References. No meta-sections about our process.
- Perfect markdown (the reason this lint exists): no weird wrapping, no
  weird new lines, no broken structure.

Lint enforces this: `lane<X>` / `agent-reports` tokens in a FIND body are
flagged. When flagged, rewrite the sentence without the internal reference
(keep the fact, drop the machinery).

## Repair discipline (hard, learned 2026-10-15)

Never bulk-rewrite notes with scripted reflow (textwrap/join loops): it
shatters code fences, hyphen-splits tokens and collapses frontmatter.
Repair ONE file at a time: read it, patch the specific broken lines with
targeted edits, verify by reading it back, THEN move to the next file.
Lint after each file. Test a repair pipeline on ONE finding and verify it
visually before running anything on the whole tree - a broken repair script
applied everywhere multiplies the damage across every note.

Rewrite mechanics (the file tools enforce read-before-write): a partial read
(offset/limit, or an offset past end-of-file) marks the file as not-fully-read
and a full overwrite is refused. Read EVERY page of the file before rewriting
it, or patch the specific lines instead of rewriting. sed for exact-token
swaps (single words, paths) is safe; sed never reflows lines.
