#!/usr/bin/env python3
"""stallcheck.py - mechanical wrong-vector tells read from the engagement cmdlog.

hunt-core carries two mechanical stop signals as prose ("Wrong-vector tells"); under
momentum prose is ignored (retro: ~12 rabbit-hole entries, "zero RTL calls despite two
textbook stall triggers"). This script makes them fire from DATA:

1. TARGET STARVATION: the last >= 6 curl probes against ONE host all failed (000 /
   timeout / empty reply / refused / reset). hunt-core: "a vector that DoSes or
   starves the box is almost never the intended one" - stop hammering, switch vector.
2. HASH-EXHAUSTION: >= 2 hashcat runs finished Exhausted with nothing cracked.
   hunt-core: "the passwords are not wordlist material - they are handed out
   out-of-band" - stop cracking, find where the creds are DELIVERED.

The capture-poc PostToolUse hook runs this automatically after curl/hashcat entries
land (deduped); it can also be run by hand. Exit 0 always (a lens, not a gate).

Usage: python3 scripts/stallcheck.py <eng-dir | poc/cmdlog path>
"""
import os
import re
import sys

STARVE_MIN = 6              # consecutive failed probes against one host
HASH_MIN = 2                # separate Exhausted hashcat runs

_FAIL_RE = re.compile(
    r"code=000|curl: \(\d+\)|connection (?:timed out|refused|reset)|"
    r"empty reply from server|could not resolve host|operation timed out", re.IGNORECASE)
_HASH_DONE_RE = re.compile(r"Status\s*\.*\s*:\s*Exhausted", re.IGNORECASE)
_HASH_CRACKED_RE = re.compile(r"Recovered\s*\.*\s*:?\s*[1-9]\d*\s*/", re.IGNORECASE)


def _entries(path):
    """cmdlog entries -> [(cmd, output)] in file order, from the '## ts' + two-fence
    format capture-poc.py writes. Fail-open: [] on any problem."""
    try:
        text = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return []
    out = []
    for block in text.split("\n## ")[1:]:
        fences = re.findall(r"```\n(.*?)\n```", block, re.S)
        if len(fences) >= 2:
            out.append((fences[0], fences[1]))
    return out


def _host(cmd):
    m = re.search(r"https?://([^/\s:'\"]+)", cmd) or re.search(
        r"-H ['\"]?Host:\s*([^'\"\s]+)", cmd, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    m = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", cmd)
    return m.group(1) if m else "?"


def starvation(host_entries, minimum=STARVE_MIN):
    """Hosts whose trailing probe window is ALL failures (>= minimum). A success resets
    the run; only the tail matters (an old outage must not fire forever)."""
    runs, hosts = {}, {}
    for cmd, out in host_entries:
        h = _host(cmd)
        if _FAIL_RE.search(out):
            runs[h] = runs.get(h, 0) + 1
        else:
            runs[h] = 0
        hosts[h] = runs[h]
    return sorted(h for h, n in hosts.items() if n >= minimum)


def hash_exhausted(hash_entries, minimum=HASH_MIN):
    # a run counts only if it finished Exhausted AND cracked nothing (a run that
    # recovered digests did its job; the rule is about wordlist-only failures)
    return sum(1 for _cmd, out in hash_entries
               if _HASH_DONE_RE.search(out) and not _HASH_CRACKED_RE.search(out)) >= minimum


def check(d):
    """Verdict lines for an engagement dir (or a direct cmdlog path)."""
    if os.path.isdir(d):
        cdir = os.path.join(d, "poc", "cmdlog")
        curl_p = os.path.join(cdir, "curl.md")
        hash_p = os.path.join(cdir, "hashcat.md")
    else:
        curl_p = d if os.path.basename(d).startswith("curl") else None
        hash_p = d if "hashcat" in os.path.basename(d) else None
    lines = []
    if curl_p:
        starved = starvation(_entries(curl_p))
        if starved:
            lines.append(
                "STALL SIGNAL (target starvation): the last %d+ probes against %s ALL failed "
                "(000/timeout/empty reply). hunt-core: a vector that starves the box is almost "
                "never the intended one. STOP hammering this host: back off, let it drain, and "
                "switch vector (or lower rate/threads and re-check liveness with a bare TCP "
                "connect first)." % (STARVE_MIN, ", ".join(starved)))
    if hash_p and hash_exhausted(_entries(hash_p)):
        lines.append(
            "STALL SIGNAL (hash exhaustion): %d+ hashcat runs finished Exhausted with nothing "
            "cracked. hunt-core: these passwords are NOT wordlist material - they are delivered "
            "out-of-band (an email, a note, a config, a second service). STOP cracking; "
            "re-enumerate for where the creds are HANDED OUT." % HASH_MIN)
    return lines


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__.strip().splitlines()[-1])
        return 0
    for line in check(argv[0]):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
