#!/usr/bin/env python3
"""stallcheck.py - mechanical wrong-vector tells read from the engagement cmdlog.

hunt-core carries two mechanical stop signals as prose ("Wrong-vector tells"); under
momentum prose is ignored (retro: ~12 rabbit-hole entries, "zero RTL calls despite two
textbook stall triggers"). This script makes them fire from DATA:

1. TARGET STARVATION: the last >= 6 probes against ONE host all failed (000 /
   timeout / empty reply / refused / reset), across any connectivity-shaped tool
   (curl/nc/nxc/ssh/hydra/nmap). hunt-core: "a vector that DoSes or starves the
   box is almost never the intended one" - stop hammering, switch vector.
2. HASH-EXHAUSTION: >= 2 hashcat runs finished Exhausted with nothing cracked.
   hunt-core: "the passwords are not wordlist material - they are handed out
   out-of-band" - stop cracking, find where the creds are DELIVERED.
3. SCANNER ZERO-YIELD: >= 4 nmap/nuclei runs against ONE asset found nothing (all
   ports closed, no nuclei hits). The machine surface is exhausted; go manual.
4. FROZEN BACKGROUND LOG: two identical vm-bg --read captures in a row - the job
   is done or hung; ask --status instead of re-reading.

The capture-poc PostToolUse hook runs this automatically after scan/probe entries
land (deduped); it can also be run by hand. Exit 0 always (a lens, not a gate).

Usage: python3 scripts/stallcheck.py <eng-dir | ledgers/cmdlog path>
"""
import os
import re
import sys

STARVE_MIN = 6              # consecutive failed probes against one host
HASH_MIN = 2                # separate Exhausted hashcat runs
SCAN_ZERO_MIN = 4           # zero-finding scanner runs against one asset
# connectivity-shaped tools whose cmdlog feeds the starvation rule (curl was the
# original; the same tell fires for scanner/probe/spray transports)
STARVE_TOOLS = ("curl", "nc", "nxc", "netexec", "ssh", "hydra", "nmap")
# scanners with a RELIABLE zero-finding signature. ffuf/feroxbuster print dense
# boilerplate banners whose "0 results" shape is not stably greppable - add them
# only with a verified signature (ponytail: no heuristic that can false-positive).
SCAN_TOOLS = ("nmap", "nuclei")

_FAIL_RE = re.compile(
    r"code=000|curl: \(\d+\)|connection (?:timed out|refused|reset)|"
    r"empty reply from server|could not resolve host|operation timed out|"
    r"host seems down|100% packet loss|no route to host|(?:network |host )?unreachable|"
    r"could not connect|connection closed", re.IGNORECASE)
_HASH_DONE_RE = re.compile(r"Status\s*\.*\s*:\s*Exhausted", re.IGNORECASE)
_HASH_CRACKED_RE = re.compile(r"Recovered\s*\.*\s*:?\s*[1-9]\d*\s*/", re.IGNORECASE)
_NMAP_CLOSED_RE = re.compile(
    r"all \d+ scanned ports(?: on [\w.\-]+)? are (?:closed|filtered)", re.IGNORECASE)
_NUCLEI_HIT_RE = re.compile(r"\[[\w.-]+\] \[(?:http|network|dns|file|code)\]", re.I)
_NUCLEI_ERR_RE = re.compile(r"FATAL|no templates found|could not", re.I)
_BG_READ_RE = re.compile(r"vm-bg\.sh\s+--read", re.IGNORECASE)


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


def scan_zero(tools, minimum=SCAN_ZERO_MIN):
    """Hosts with >= minimum zero-finding scanner runs (nmap all-ports-closed /
    nuclei run with no hit lines). A box whose whole machine surface keeps
    coming back empty is dead or hand-crafted: stop re-scanning it."""
    zero = {}
    for tool, entries in tools.items():
        if tool not in SCAN_TOOLS:
            continue
        for cmd, out in entries:
            hit = False
            if tool == "nmap":
                hit = bool(_NMAP_CLOSED_RE.search(out))
            elif tool == "nuclei" and not _NUCLEI_ERR_RE.search(out):
                hit = not _NUCLEI_HIT_RE.search(out)
            if hit:
                h = _host(cmd)
                zero[h] = zero.get(h, 0) + 1
    return sorted(h for h, n in zero.items() if n >= minimum)


def bg_read_stalled(entries):
    """Two consecutive vm-bg --read captures with IDENTICAL output: the log is
    not growing. Re-reading it again is a loop; ask --status and branch."""
    reads = [(c, o) for c, o in entries if _BG_READ_RE.search(c)]
    return (len(reads) >= 2 and reads[-1][1].strip() == reads[-2][1].strip()
            and bool(reads[-1][1].strip()))


def _cmdlog_dir(eng_dir):
    for rel in ("ledgers/cmdlog", "poc/cmdlog"):
        p = os.path.join(eng_dir, rel.replace("/", os.sep))
        if os.path.isdir(p):
            return p
    return os.path.join(eng_dir, "ledgers", "cmdlog")


def _collect(d):
    """engagement dir (or one cmdlog path) -> {tool: entries}."""
    if os.path.isdir(d):
        cdir = _cmdlog_dir(d)
        out = {}
        if os.path.isdir(cdir):
            for f in sorted(os.listdir(cdir)):
                if f.endswith(".md"):
                    out[f[:-3]] = _entries(os.path.join(cdir, f))
        return out
    base = os.path.basename(d)
    return {base[:-3] if base.endswith(".md") else base: _entries(d)}


def check(d):
    """Verdict lines for an engagement dir (or a direct cmdlog path)."""
    tools = _collect(d)
    lines = []
    # starvation, per connectivity-shaped tool (the tool list names WHICH loop starved)
    starvers = {}
    for t in STARVE_TOOLS:
        for h in starvation(tools.get(t, [])):
            starvers.setdefault(h, []).append(t)
    for h, ts in sorted(starvers.items()):
        lines.append(
            "STALL SIGNAL (target starvation): the last %d+ %s probes against %s ALL failed "
            "(timeout/refused/empty). hunt-core: a vector that starves the box is almost "
            "never the intended one. STOP hammering this host: back off, let it drain, and "
            "switch vector (or lower rate/threads and re-check liveness with a bare TCP "
            "connect first)." % (STARVE_MIN, "/".join(ts), h))
    if "hashcat" in tools and hash_exhausted(tools["hashcat"]):
        lines.append(
            "STALL SIGNAL (hash exhaustion): %d+ hashcat runs finished Exhausted with nothing "
            "cracked. hunt-core: these passwords are NOT wordlist material - they are delivered "
            "out-of-band (an email, a note, a config, a second service). STOP cracking; "
            "re-enumerate for where the creds are HANDED OUT." % HASH_MIN)
    for h in scan_zero(tools):
        lines.append(
            "STALL SIGNAL (scanner zero-yield): %d+ nmap/nuclei runs against %s found NOTHING "
            "(all ports closed/filtered, no nuclei hits). The machine surface is exhausted - "
            "STOP re-scanning this asset; go manual (source review, other protocols, UDP, the "
            "wiki page for the tech) or re-check the host is even alive." % (SCAN_ZERO_MIN, h))
    if "vm-bg" in tools and bg_read_stalled(tools["vm-bg"]):
        lines.append(
            "STALL SIGNAL (background log frozen): the last two vm-bg --read captures are "
            "IDENTICAL - the job finished or hung. Stop re-reading: run "
            "`vm-bg.sh --status <eng> <win>` (done exit=N / running / hung?); hung -> "
            "`--kill`, then change one variable before relaunching.")
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
