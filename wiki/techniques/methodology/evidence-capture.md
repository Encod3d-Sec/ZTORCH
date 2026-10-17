---
title: "Evidence capture"
type: technique
tags: [technique, evidence, screenshots, har, poc-hygiene]
---

# Evidence capture

Turning live findings into reproducible, sanitizable evidence. The
closeout chain consumes what lands here: triage -> evidence ->
walkthrough.

## The capture rules

- Capture LIVE, not at close-out: re-running stateful steps is unsafe
  (a spent padding-oracle or a zeroing transfer cannot be re-fired for
  a clean card). One capture per landing step.
- Terminal output as card PNGs (`Skill(screenshot) --term`); browser
  states via chromium cards; Burp GUI via `Skill(screenshot-burp)`
  (keyboard-only Swing automation, tab-select oracle).
- Walkthrough embedding: description line on top, indented embed below,
  NEVER table cells (Obsidian renders image-in-cell unreliably) -
  Skill(walkthrough) owns the canonical rule.
- Exploit scripts keep their .md fence; evidence tables carry the
  desc-line + indented embed shape.
- Redaction happens at the evidence skill stage (HAR sanitize, PoC
  scrub) - never ship raw captures.

## Storage

Curated PoC/flag shots under `targets/<eng>/poc/`; raw tool output
under `targets/<eng>/ingest/`. Both client-confidential (gitignored);
check-leaks before any share.

Related: [[vulnerability-reports]], [[safe-probing-and-controls]]
