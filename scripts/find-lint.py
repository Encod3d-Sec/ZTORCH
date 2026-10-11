#!/usr/bin/env python3
"""find-lint.py - quality gate for finding files before they reach a report.

Scans targets/<active>/Vulns/**/FIND-*.md and checks each finding is complete +
reproducible: required sections present and non-empty, valid severity in the
filename, and (for HIGH/CRITICAL) a CVSS vector + affected target. Reports gaps.

  python3 scripts/find-lint.py        # lint active engagement's findings
  python3 scripts/find-lint.py -v     # show passing files too

Exit 1 if any finding is incomplete (usable as a pre-report gate).
"""
import os
import re
import sys
from pathlib import Path

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(VAULT, "skills", "hooks"))
import _engagement  # noqa: E402

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")


def cvss_band(score):
    """CVSS v3.1 severity band for a base score, or None if out of range."""
    if score is None:
        return None
    if score == 0:            return "INFO"      # 0.0 = None; findings use INFO
    if score < 4.0:           return "LOW"
    if score < 7.0:           return "MEDIUM"
    if score < 9.0:           return "HIGH"
    if score <= 10.0:         return "CRITICAL"
    return None


# A score after a dash separator ("<vector> - 9.8"). The leading dash is what keeps
# the search from grabbing the "3.1" out of a bare vector like "CVSS:3.1/AV:N/...".
_SCORE_RE = re.compile(r"[—\-]\s*(10(?:\.0)?|\d(?:\.\d)?)\b")
# A value that is ONLY a number ("cvss: 9.8"), with no vector present.
_BARE_SCORE_RE = re.compile(r"^(10(?:\.0)?|\d(?:\.\d)?)$")


def cvss_score(fmt):
    """Extract the numeric CVSS base score from the frontmatter `cvss:` value, or None."""
    m = re.search(r"^cvss:\s*(.+)$", fmt, re.M | re.I)
    if not m:
        return None
    val = m.group(1).strip()
    sm = _SCORE_RE.search(val)
    if not sm and "/" not in val:   # no dash-score form and not a vector -> accept a bare number
        sm = _BARE_SCORE_RE.match(val)
    if not sm:
        return None
    try:
        v = float(sm.group(1))
    except ValueError:
        return None
    return v if 0.0 <= v <= 10.0 else None


# required section -> accepted heading regex (case-insensitive). The canonical
# wording is setup/templates/_find.md (the single source of truth): Description /
# Proof of Concept / Impact / Remediation, with References optional. The extra
# alternations are back-compat aliases for findings written before the templates
# were reconciled, so pre-existing pentest/bugbounty findings still pass. Keep the
# _find.md wording first in each alternation; test_find_md_headings_lock_to_find_lint
# fails if _find.md and this table drift.
REQUIRED = {
    "Description": r"^#+\s*(description|summary)",
    "Proof of Concept": r"^#+\s*(proof of concept|poc|reproduction|repro|steps)",
    "Impact": r"^#+\s*impact",
    "Remediation": r"^#+\s*(remediation|fix|mitigation)",
}
FNAME_RE = re.compile(r"FIND-\d+-([A-Z]+)-", re.I)


def find_files(d):
    """Report-bound findings only: skip Skipped*/False* dirs (not deliverables)."""
    out = []
    vroot = os.path.join(d, "Vulns")
    for r, _, fs in os.walk(vroot):
        low = os.path.basename(r).lower()
        if low.startswith("skip") or low.startswith("false"):
            continue
        for f in fs:
            if f.startswith("FIND-") and f.endswith(".md"):
                out.append(os.path.join(r, f))
    return sorted(out)


def section_nonempty(text, header_re):
    """True if a heading matching header_re exists with non-placeholder body."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if re.match(header_re, ln.strip(), re.I):
            body = []
            for nxt in lines[i + 1:]:
                if re.match(r"^#+\s", nxt):
                    break
                body.append(nxt)
            txt = "\n".join(body).strip()
            txt = re.sub(r"<[^>]+>", "", txt)  # drop <placeholder> angle tags
            return len(txt) >= 15
    return False


def _section_body(text, header_re):
    """Body lines of the first heading matching header_re, or ''."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if re.match(header_re, ln.strip(), re.I):
            body = []
            for nxt in lines[i + 1:]:
                if re.match(r"^#+\s", nxt):
                    break
                body.append(nxt)
            return "\n".join(body)
    return ""


_POC_RE = REQUIRED["Proof of Concept"]
_PLACEHOLDER_RE = re.compile(r"<[A-Za-z#][^>\n]{0,80}>")


def _evidence_issues(body, base_dir):
    """Finalization contract (cyberstrikeai L1): CONFIRMED/EXPLOITED need
    (a) referenced poc/ files on disk, (b) a fenced block with a non-empty line,
    (c) no unfilled <...> placeholders in the PoC section. One combined issue
    line so the report reads as a single still-verifying verdict.
    ponytail: 'runnable' is structural (fenced + non-empty), not a shell parse;
    the placeholder rule carries the 'not prose' half."""
    missing = []
    refs = sorted(set(re.findall(r"poc/[^\s\)\]\|]+", body)))
    gone = [r.rstrip(".,") for r in refs
            if not os.path.isfile(os.path.join(base_dir, r.rstrip(".,")
                                               .split("#")[0].strip()))]
    if gone:
        missing.append("capture files absent (%s)" % ", ".join(gone))
    poc = _section_body(body, _POC_RE)
    fenced = re.findall(r"```[^\n]*\n(.*?)```", poc, re.S)
    if not any(b.strip() for b in fenced):
        missing.append("no fenced command block in PoC")
    # fence sizing (strix): a backtick run inside the content that is >= the fence
    # breaks the render; the fence must be strictly longer than the longest run.
    for fence_lang, fbody in re.findall(r"(`{3,})[^\n]*\n(.*?)\1", poc, re.S):
        if max((len(m) for m in re.findall(r"`+", fbody)), default=0) >= len(fence_lang):
            missing.append("PoC fence too short: content contains a backtick run >= the "
                           "fence; open the fence one backtick longer than the longest run")
            break
    # diff-base ladder (strix): a piped git lookup silently swallows a failed base
    # resolution and diffs against the wrong ref.
    if re.search(r"\bgit\s+(?:diff|log|show)\b[^\n]*\|", poc):
        missing.append("piped git diff/log/show: resolve the base via the ladder "
                       "(origin/HEAD -> origin/main|master|develop -> FAIL asking for "
                       "DIFF_BASE); never pipe the lookup")
    # pasted captures (html/xml/http/json fences) legitimately contain markup
    scanned = re.sub(r"```(?:html|xml|http|json)[^\n]*\n.*?```", "", poc, flags=re.S)
    if _PLACEHOLDER_RE.search(scanned):
        missing.append("unfilled placeholder in PoC")
    return ("STILL VERIFYING - missing: %s" % ", ".join(missing)) if missing else ""


SUCCESS_VERBS = (
    "confirmed", "exploited", "dumped", "cracked", "bypassed",
    "executed", "compromised", "exfiltrated", "rooted", "overwrote",
)


def _claim_issues(body, dirname):
    """Success-verb sentences in PoC/Impact must cite a capture path that exists."""
    issues = []
    for header in ("Proof of Concept", "Impact"):
        section = _section_body(body, REQUIRED[header])
        if not section:
            continue
        prose = re.sub(r"```.*?```", " ", section, flags=re.S)
        for sentence in re.split(r"(?<=[.!?])\s+|\n", prose):
            words = sentence.split()
            if not words:
                continue
            if not any(re.search(r"\b%s\b" % v, sentence.lower()) for v in SUCCESS_VERBS):
                continue
            cited = [w.strip("`.,;:()[]") for w in words]
            ok = any(
                "/" in w and len(w) > 3 and not w.startswith("http")
                and ((dirname / w).exists() or Path(w).exists())
                for w in cited
            )
            if not ok:
                issues.append(
                    "STILL VERIFYING - claim without fresh capture: %s"
                    % " ".join(words[:8])
                )
    return issues


def lint_file(path, base_dir=None):
    # base_dir defaults to the card's dir (tests co-locate cards+captures); the
    # main loop passes the engagement root so `poc/...` refs in Vulns/ resolve.
    if base_dir is None:
        base_dir = os.path.dirname(path)
    text = open(path, encoding="utf-8", errors="ignore").read()
    issues = []
    m = FNAME_RE.search(os.path.basename(path))
    sev = m.group(1).upper() if m else None
    if sev not in SEVERITIES:
        issues.append(f"bad/missing severity in filename ({sev})")
    for label, rx in REQUIRED.items():
        if not section_nonempty(text, rx):
            issues.append(f"missing/empty {label}")
    fm = re.search(r"^---\r?\n(.*?)\r?\n---", text, re.S)   # tolerate CRLF
    fmt = fm.group(1) if fm else ""
    if sev in ("CRITICAL", "HIGH"):
        # require a real CVSS v3 vector, not just the literal string "cvss:3" in prose
        blob = (fmt + "\n" + text).lower().replace(" ", "")
        if not re.search(r"av:[nalp]", blob):   # real vector token, not just the word "cvss" in prose
            issues.append("no CVSS vector (HIGH/CRITICAL should have an AV:... vector)")
    if re.search(r"^affected:\s*[\"']?\s*[\"']?\s*$", fmt, re.M):
        issues.append("empty 'affected' target")
    warnings = []
    band = cvss_band(cvss_score(fmt))
    if band and sev in SEVERITIES and band != sev:
        warnings.append(f"CVSS score maps to {band} but filename severity is {sev} "
                        f"(intentional? otherwise fix the label or the score)")
    m = re.search(r"^class:[ \t]*(.*)$", fmt, re.M)
    cls_val = m.group(1).split("#", 1)[0].strip().strip('"').strip("'").strip() if m else ""
    if not cls_val:
        warnings.append("no `class:` set (canonical vuln class sharpens chain triggers + coverage)")
    m = re.search(r"^status:\s*(\w+)", fmt, re.M)
    status = (m.group(1).upper() if m else "")
    body = text[fm.end():] if fm else text   # same frontmatter boundary as the fm match above
    if status in ("FALSE_POSITIVE", "IGNORED"):
        prefix = "FP:" if status == "FALSE_POSITIVE" else "IGNORED:"
        desc = re.sub(r"\s+", " ", _section_body(body, REQUIRED["Description"]).strip())
        if not desc.upper().startswith(prefix):
            issues.append("status %s needs a first-sentence reason starting %s in "
                          "Description" % (status, prefix))
        elif not re.search(r"because\s+\S+", desc, re.I):
            warnings.append("%s reason names no control: name what makes it not-real "
                            "(encoder/sanitizer/block observed where)" % status)
    elif status in ("CONFIRMED", "EXPLOITED"):
        if "poc/" not in body.lower():
            issues.append("status %s but no capture path (poc/...) referenced - CONFIRMED needs "
                          "a validated PoC capture, EXPLOITED a chain use" % status)
        for fld, hint in (("counterevidence", "strongest case against"),
                          ("confidence", "level + basis"),
                          ("severity_change_conditions", "what changes the rating")):
            mv = re.search(r"^%s:\s*(.+)$" % fld, fmt, re.M | re.I)
            val = mv.group(1).strip().strip('"').strip("'") if mv else ""
            if not val or _PLACEHOLDER_RE.search(val) or val.lower() in ("todo", "tbd", "n/a"):
                issues.append("status %s needs non-empty %s: (%s)" % (status, fld, hint))
        ev = _evidence_issues(body, base_dir)
        if ev:
            issues.append(ev)
        issues.extend(_claim_issues(body, Path(base_dir)))
    return issues, warnings


def main():
    verbose = "-v" in sys.argv
    d = _engagement.active_dir()
    if not d:
        print("No active engagement.")
        return 0
    files = find_files(d)
    eng = os.path.basename(d)
    if not files:
        print(f"find-lint ({eng}): no FIND-*.md files yet.")
        return 0
    bad = 0
    for f in files:
        issues, warnings = lint_file(f, d)
        rel = os.path.relpath(f, d)
        if issues:
            bad += 1
            print(f"  FAIL {rel}")
            for i in issues:
                print(f"       - {i}")
        elif verbose:
            print(f"  ok   {rel}")
        for w in warnings:      # warnings print regardless of pass/fail, do not gate
            print(f"  WARN {rel}")
            print(f"       - {w}")
    print(f"\nfind-lint ({eng}): {len(files)-bad}/{len(files)} complete, {bad} need work.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
