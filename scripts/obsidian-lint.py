#!/usr/bin/env python3
"""obsidian-lint.py - readability gate for vault notes (operator rule 2026-10-15:
"mangled text I cannot read in Obsidian" - raw Killchain/JSON dumps filed as notes).

Checks every .md under the given path (default: an engagement dir):
  FIND-*.md    must carry YAML frontmatter with title/type/severity/status keys;
               no literal \\n escape walls, no CRLF, no >400-char unbroken lines.
  all .md      no literal \\"  or \\n dumps (raw JSON pasted), no CR chars,
               warn (not fail) on lines >400 chars.

Exit 0 clean; exit 1 with one line per violation. Fail-soft on unreadable files.
Usage: python3 scripts/obsidian-lint.py targets/<eng>
"""
import re
import sys
import pathlib

REQUIRED_FM_KEYS = ("title", "type", "severity", "status", "date_created")
WALL = 400
# Transcription mangles (content copied from web/PDF/other reports into notes):
MOJIBAKE = re.compile(r"Ã[\x80-\xBF]|Â[\x80-\xBF]|â€|Ã¢|â€™|â€œ|â€\x9d")  # UTF-8 double-encode
HTML_ENT = re.compile(r"&amp;|&quot;|&#39;|&lt;|&gt;|&nbsp;")                # un-rendered entities
GLUED_MD = re.compile(r"[^#\s]#{1,6}\s")                                      # heading glued mid-line (text## Heading)
UNBAL_BOLD = "**"                                                             # odd per-file count = truncated emphasis
INVISIBLE = re.compile(r"\ufeff|\u200b|\u200e|\u200f")                        # BOM/zero-width/direction marks
NON_ASCII = re.compile(r"[\u2010-\u2015\u2018-\u201f\u2026\u00a0\u2212]")      # dashes/smart quotes/ellipsis/nb-sp/minus


def lint_file(p: pathlib.Path, is_find: bool):
    issues = []
    try:
        raw = p.read_bytes()
        text = raw.decode("utf-8", "replace")
    except OSError as e:
        return ["%s: unreadable (%s)" % (p, e)]
    if b"\r" in raw:
        issues.append("%s: CR characters (CRLF) - normalize to LF" % p)
    stripped = re.sub(r"```.*?```", "", text, flags=re.S)
    # literal \n mid-text is the #1 mangle (JSON/killchain dumps pasted as prose) -
    # ANY occurrence outside code fences fails, even a single one
    if "\\n" in stripped:
        issues.append("%s: literal \\n in prose (raw dump mid-text; unwrap to real newlines)" % p)
    if '\\"' in stripped:
        issues.append("%s: literal escaped quotes \\\" outside code fences (JSON paste)" % p)
    # transcription-artifact gate (content copied in from web/PDF/other reports)
    prose = re.sub(r"`[^`]*`", "", stripped)  # inline code may legitimately show any of these
    if MOJIBAKE.search(prose):
        issues.append("%s: mojibake (double-encoded UTF-8: Ã/Â/â€ sequences) - fix encoding on re-transcribe" % p)
    if HTML_ENT.search(prose):
        issues.append("%s: un-rendered HTML entities (&amp; &quot; &#39;) in prose" % p)
    if GLUED_MD.search(prose):
        issues.append("%s: heading glued mid-line (text## Heading) - missing newline before ##" % p)
    if prose.count(UNBAL_BOLD) % 2 == 1:
        issues.append("%s: unbalanced ** emphasis (transcription truncated one side)" % p)
    if INVISIBLE.search(text):
        issues.append("%s: invisible characters (BOM / zero-width / direction marks)" % p)
    bad_ascii = sorted(set(NON_ASCII.findall(stripped)))
    if bad_ascii:
        issues.append("%s: non-ASCII typography %s (AGENTS.md rule 7: em/en-dashes and smart quotes -> ASCII \" - \" and \\')" % (p, " ".join(bad_ascii)))
    if stripped.count("```") % 2 == 1:
        issues.append("%s: unbalanced code fences (transcription truncated one side)" % p)
    for i, ln in enumerate(text.split("\n"), 1):
        m = re.match(r"^\s*```\S*\s+\S", ln)  # fence line carrying prose ("``` EXPECTED ...")
        if m and not re.match(r"^\s*```[a-z]+\s*$", ln):
            issues.append("%s:%d: fence glued to prose on one line - close fences on their own line" % (p, i))
            break
    fence_state = False
    for i, ln in enumerate(text.split("\n"), 1):
        if ln.strip().startswith("```"):
            fence_state = not fence_state
            continue
        if fence_state:
            continue  # fenced content: URLs/payloads are legitimately long
        if ln.startswith(("|", "- ")) or re.match(r"^\d+\. ", ln):  # table rows / list items can run long
            continue
        if len(ln) > WALL:
            issues.append("%s:%d: unbroken %d-char line (wall text; split into sections)" % (p, i, len(ln)))
            break
    # hard-wrap mangle: prose reflowed with mid-sentence breaks (textwrap-style repair
    # damage) - a long line NOT ending a sentence, followed by a lowercase continuation
    fm_end = 0
    if text.startswith("---"):
        m2 = re.search(r"\n---\s*\n", text[3:])
        fm_end = m2.end() + 3 if m2 else 0
    lines2 = [l for l in text.split("\n")[fm_end:]] if fm_end else [l for l in text.split("\n")]
    for i in range(len(lines2) - 1):
        a, b = lines2[i].rstrip(), lines2[i + 1].lstrip()
        if (len(a) > 60 and len(b) > 25 and b[:1].islower()
                and not a.endswith((".", ":", "!", "?", ")", "`", ">", "|"))
                and not a.lstrip().startswith(("#", "|", ">", "-", "*", "```"))
                and not b.lstrip().startswith(("#", "|", ">", "-", "*", "```", "1.", "2.", "3."))):
            issues.append("%s:%d-%d: mid-sentence hard wrap ('...%s' / '%s...') - rejoin into one line"
                          % (p, i + 1, i + 2, a[-25:], b[:25]))
            break
    if is_find:
        m = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, flags=re.S)
        if not m:
            issues.append("%s: FIND file without YAML frontmatter" % p)
        else:
            missing = [k for k in REQUIRED_FM_KEYS
                       if not re.search(r"^%s\s*:" % re.escape(k), m.group(1), flags=re.M)]
            if missing:
                issues.append("%s: frontmatter missing keys: %s" % (p, ", ".join(missing)))
        if re.match(r"\A## FIND-", text):
            issues.append("%s: starts with a Killchain-style '## FIND-' section - convert to a proper report" % p)
        # bounty-report law: no internal machinery in the company-facing body
        body = text[fm_end:] if fm_end else text
        body_nofence = re.sub(r"```.*?```", "", body, flags=re.S)
        lanes = sorted(set(re.findall(r"\blane[A-Z]\b", body_nofence)))
        if "agent-reports" in body_nofence:
            lanes.append("agent-reports")
        if lanes:
            issues.append("%s: internal machinery in FIND body (%s) - bounty-facing prose must not name lanes/evidence trees; move to frontmatter sources or the Evidence section" % (p, ", ".join(lanes)))
    return issues


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "targets")
    bad = []
    n = 0
    for p in sorted(root.rglob("*.md")):
        if any(part in ("node_modules", ".git", "evidence") for part in p.parts):
            continue  # evidence/ = verbatim lane captures, never prose-normalized
        n += 1
        bad += lint_file(p, bool(re.match(r"FIND-", p.name)))
    if bad:
        print("OBSIDIAN-LINT FAIL (%d files checked):" % n)
        for b in bad:
            print(" -", b)
        sys.exit(1)
    print("OBSIDIAN-LINT PASS (%d files checked)" % n)


if __name__ == "__main__":
    main()
