#!/usr/bin/env python3
"""External-findings import bridge (artex absorption WS-B1).

Reads normalized findings rows from targets/<eng>/ingest/<name>.findings.json,
dedups them against the engagement's FIND cards and prior drafts by fingerprint,
writes RESEARCH drafts to ingest/_imports/ (outside the FIND-*.md lint namespace),
and emits a verify-brief the main model turns into ONE verification lane.

Row schema (the ingest step normalizes ANY external format into this):
  title, class, severity, affected, endpoint, evidence, source, summary?, impact?

Exit 0 ok, 2 = FIX rows (missing required fields) present.
"""
import datetime
import hashlib
import json
import os
import re
import sys

REQUIRED = ("title", "class", "affected", "endpoint", "evidence", "source")
FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def vault_root():
    env = os.environ.get("ZTORCH_VAULT")
    if env:
        return env
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fingerprint(class_, affected, endpoint):
    return hashlib.sha256(
        f"{class_}|{affected}|{endpoint}".encode()
    ).hexdigest()[:12]


def slugify(text, limit=44):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:limit].rstrip("-") or "untitled"


def scan_cards(eng_dir):
    """fingerprint -> (path, title) over FIND cards + existing import drafts."""
    seen = {}
    roots = [os.path.join(eng_dir, "Vulns"), os.path.join(eng_dir, "ingest", "_imports")]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                if not (fn.startswith("FIND-") or fn.startswith("draft-")) or not fn.endswith(".md"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    head = open(path, encoding="utf-8", errors="replace").read(4096)
                except OSError:
                    continue
                m = FM_RE.match(head)
                if not m:
                    continue
                fm = m.group(1)
                fp = re.search(r"^fingerprint:\s*(\S+)", fm, re.M)
                ti = re.search(r'^title:\s*"?([^"\n]+)"?', fm, re.M)
                if fp:
                    seen[fp.group(1).strip('"')] = (path, ti.group(1).strip() if ti else fn)
    return seen


def draft_md(row, fp, date):
    sev = row.get("severity") or "LOW"
    desc = row.get("summary") or row["title"]
    impact = row.get("impact") or "Pending verification - impact assessed at promotion."
    source = row["source"]
    return f"""---
title: "{row['title']}"
type: finding
severity: {sev}
class: "{row['class']}"
status: RESEARCH
cvss: ""
affected: "{row['affected']}"
counterevidence: "External claim imported from {source}; not yet re-captured by a ZTorch lane - the verify step must confirm or disprove it with a fresh capture before promotion."
confidence: "low: imported claim pending verification"
severity_change_conditions: ""
fingerprint: "{fp}"
date_created: "{date}"
sources: ["{source}"]
---

# `{row['title']}`

Imported row: endpoint `{row['endpoint']}` on `{row['affected']}`, source `{source}`,
importer severity {sev}.

## Description

{desc}

## Proof of Concept

Imported evidence (verbatim from {source}):

```
{row['evidence']}
```

## Impact

{impact}

## Remediation

Pending verification.

## Recommended next

Verify via the sibling verify-brief.md, then promote or kill.

## References

.
"""


def main():
    if len(sys.argv) != 3:
        print("usage: finding-import.py <eng> <findings.json>", file=sys.stderr)
        return 2
    eng, rows_path = sys.argv[1], sys.argv[2]
    eng_dir = os.path.join(vault_root(), "targets", eng)
    if not os.path.isdir(eng_dir):
        print(f"FAIL no engagement dir targets/{eng}", file=sys.stderr)
        return 2
    try:
        rows = json.load(open(rows_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"FAIL reading {rows_path}: {e}", file=sys.stderr)
        return 2
    if not isinstance(rows, list) or not rows:
        print("FAIL findings.json must be a non-empty JSON array of rows", file=sys.stderr)
        return 2

    seen = scan_cards(eng_dir)
    imports_dir = os.path.join(eng_dir, "ingest", "_imports")
    os.makedirs(imports_dir, exist_ok=True)
    date = datetime.date.today().isoformat()
    base = os.path.splitext(os.path.basename(rows_path))[0]

    news, dupes, fixes = [], [], []
    for row in rows:
        missing = [k for k in REQUIRED if not str(row.get(k, "")).strip()]
        if missing:
            fixes.append((row.get("title", "?"), missing))
            continue
        fp = fingerprint(row["class"], row["affected"], row["endpoint"])
        if fp in seen:
            path, title = seen[fp]
            dupes.append((row["title"], path, title))
            continue
        n = len(news) + 1
        path = os.path.join(imports_dir, f"draft-{n:02d}-{slugify(row['title'])}.md")
        open(path, "w", encoding="utf-8").write(draft_md(row, fp, date))
        seen[fp] = (path, row["title"])
        news.append((row["title"], path, fp))

    brief = [f"# verify-brief: {base}", "",
             f"Imported {len(rows)} rows: {len(news)} NEW, {len(dupes)} DUPE, {len(fixes)} FIX.", ""]
    if news:
        brief += ["## NEW - one verification lane covers all of these", ""]
        for title, path, fp in news:
            brief += [f"### {title}", f"- draft: `{os.path.relpath(path, eng_dir)}` (fingerprint {fp})",
                      "- replay the imported evidence request exactly, unauth, from the VM",
                      "- negative control before believing it (wrong shape, second account, or nonexistent object)",
                      "- full capture to a poc/ lane dir (headers + body, verbatim files)",
                      "- PROMOTE: write the real card in Vulns/ at CONFIRMED (model prose, FIND numbering now),",
                      "  fold the draft's evidence in, then delete the draft",
                      "- KILL: envelope + log line with the reason; draft stays in _imports/ as the record", ""]
    if dupes:
        brief += ["## DUPE - no new card", ""]
        for title, path, existing in dupes:
            rel = os.path.relpath(path, eng_dir)
            brief += [f"- `{title}` = `{existing}`: append the source to `sources:` of {rel}", ""]
    if fixes:
        brief += ["## FIX - refused rows (fill these fields, re-run)", ""]
        brief += [f"- `{t}` missing: {', '.join(m)}" for t, m in fixes]
        brief += [""]
    brief_path = os.path.join(imports_dir, "verify-brief.md")
    open(brief_path, "w", encoding="utf-8").write("\n".join(brief))

    status = "ok" if not fixes else "fix-required"
    print(f"import {base}: {len(rows)} rows, {len(news)} new drafts, {len(dupes)} dupes, {len(fixes)} fix-required")
    print(f"brief: {brief_path}")
    print(f"log line: {date} | finding | import | {status} | {base}: {len(rows)} rows, "
          f"{len(news)} new, {len(dupes)} dupes, {len(fixes)} fix | ingest/_imports/ |")
    return 2 if fixes else 0


if __name__ == "__main__":
    sys.exit(main())
