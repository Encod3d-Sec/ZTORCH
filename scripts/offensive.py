#!/usr/bin/env python3
"""offensive.py - deterministic engagement driver for the ZTorch vault.

Board/next/gates/CLI for a pentest/bb/ctf engagement. The vault-markdown
index compile step (routing table, tool index, hunt-skill methods ->
targets/<eng>/.offensive-index.json) lives in offensive_index.py; this file
consumes it via build_index/load_index/index_stale.

Python 3 stdlib only.
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from offensive_index import (
    build_index, load_index, index_stale, CACHE_NAME, _die,
    parse_routing_table, parse_tool_index, parse_hunt_method, _read, _section,
)

# vault root = the dir containing skills/ and wiki/. Resolve from the script
# location by default; overridable via --vault / --eng path so the driver never
# hardcodes an absolute machine path.
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_VAULT = SCRIPT_DIR.parent

STATE_NAME = ".offensive.json"
TEMPLATE_DIR = SCRIPT_DIR.parent / "setup" / "templates" / "offensive"
TEMPLATE_FILES = ("state.md", "scope.md", "Deadends.md", "loot.md",
                   "Killchain.md", "oob.md", "decisions.md", "Approach.md")

# 4a coverage-matrix columns (header spellings are load-bearing: cells resolve
# by header name). Mirrors campaign.py BOARD_COLS.
BOARD_COLS = ["id", "asset", "vuln class", "arsenal", "skill", "tool",
              "status", "poc", "poc_kind"]

# Base vuln-class set per engagement type (RULING R4: literal dict, no JSON
# file). Each entry MUST be a `class` in the hunt-core routing table so every
# base-superset row resolves to a real skill+arsenal (satisfies board G1/G2).
# tests/test_board.py::test_no_base_row_has_blank_skill enforces this.
BASE_CLASSES = {
    "pentest": ["ad", "windows", "macos", "secrets", "api", "rce", "sqli",
                "ssrf", "auth", "idor"],
    "bb": ["rce", "sqli", "ssrf", "injection", "deserialization", "auth",
           "idor", "federation", "smuggling", "upload", "bizlogic", "api",
           "cache", "secrets", "xss", "cicd", "mcp"],
    "ctf": ["rce", "sqli", "ssrf", "injection", "idor", "upload", "auth",
            "xss", "secrets"],
}

# Per-type close-out chain (Skill names the agent runs in order) + wall-break
# dry-streak threshold. Mirrors campaign.py tconf["closeout"] / dry_streak.
CLOSEOUT_CHAINS = {
    "pentest": ["triage", "evidence", "report", "learn"],
    "bb": ["triage", "evidence", "learn"],
    "ctf": ["walkthrough", "learn"],
}
WALLBREAK_THRESHOLD = {"pentest": 3, "bb": 3, "ctf": 2}

# class -> automated tool slug (wiki/tools/*). Fallback = nuclei. Deterministic
# so the board's `tool` cell is stable per class across runs.
CLASS_TOOL = {
    # pentest
    "adcs": "certipy", "signing-relay": "impacket", "kerberoast": "rubeus",
    "asreproast": "rubeus", "default-creds": "netexec", "privesc": "linpeas",
    "lateral": "netexec", "shares": "netexec", "enum": "nmap",
    # bb / web
    "rce": "metasploit", "sqli": "sqlmap", "ssrf": "nuclei", "ssti": "nuclei",
    "xxe": "nuclei", "deserialization": "metasploit", "auth": "nuclei",
    "idor": "burp-suite", "oauth-saml": "burp-suite",
    "request-smuggling": "nuclei", "jwt": "jwt_tool", "graphql": "nuclei",
    "file-upload": "nuclei", "business-logic": "burp-suite",
    "prototype-pollution": "nuclei", "xss": "dalfox", "csrf": "burp-suite",
    "cors": "nuclei", "web-cache": "nuclei", "host-header": "nuclei",
    "open-redirect": "nuclei", "subdomain-takeover": "nuclei",
    "session": "burp-suite", "race-condition": "burp-suite", "mcp": "curl",
    "cicd": "trufflehog", "recon": "httpx",
    # ctf
    "web": "ffuf", "pwn": "pwntools", "rev": "ghidra", "crypto": "python3",
    "binary": "ghidra", "forensics": "volatility", "stego": "binwalk",
    "osint": "amass",
    # routing-implied classes not otherwise listed
    "api": "nuclei", "injection": "nuclei", "federation": "burp-suite",
    "cloud": "pacu", "secrets": "trufflehog", "smuggling": "nuclei",
    "upload": "nuclei", "vpn": "nmap", "windows": "winpeas", "ad": "netexec",
    "m365": "netexec", "macos": "linpeas", "llm": "curl", "bizlogic": "burp-suite",
    "cache": "nuclei",
}

CLASS_TOOL.update({
    "content-discovery": "ffuf", "js-extract": "linkfinder", "recon-nuclei": "nuclei",
    "recon-nikto": "nikto", "wpscan-scan": "wpscan", "osint-subdomain": "subfinder",
    "osint-leaks": "trufflehog", "linux-svc-enum": "searchsploit",
})

# Vector-workflow pipeline (osint pre-pass, then per-asset web/ad_windows/linux baseline +
# narrow fingerprint-gated exceptions). VECTOR_PRIORITY controls per-asset row emission order;
# osint is handled as a separate pre-pass (target-level, before any asset/IP exists) rather than
# appearing in VECTOR_PRIORITY.
VECTOR_CLASSES = {
    "osint": ["osint-subdomain", "osint-leaks"],
    "web": ["content-discovery", "js-extract", "recon-nuclei", "recon-nikto"],
    "ad_windows": ["ad", "windows"],
    "linux": ["linux-svc-enum"],
}
# (vector, fingerprint substring) -> extra class, only added when BOTH the vector matched AND
# the substring appears in the asset's hay text. Narrow and hand-curated on purpose.
VECTOR_EXCEPTION = {
    ("web", "wordpress"): "wpscan-scan",
}
VECTOR_PRIORITY = ["web", "ad_windows", "linux"]
VECTOR_INDICATOR = {
    "web": re.compile(r"\b(https?|nginx|apache|iis|tomcat)\b"),
    "ad_windows": re.compile(r"\b(smb|ldap|kerberos|winrm|rdp|445|389|88|3389|5985)\b"),
    "linux": re.compile(r"\b(ssh|22|linux|nfs|rsync)\b"),
}


# --------------------------------------------------------------------------- helpers

def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- board (4a matrix)

def _parse_table(path):
    """First markdown table in `path` -> list-of-dicts keyed by lowercased
    header cell. [] on any problem. Mirrors _engagement._parse_table."""
    p = Path(path)
    if not p.is_file():
        return []
    rows, header = [], None
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if header is not None:
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if not any(cells):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _deadend_pairs(eng):
    """{(asset_lower, class_lower)} from Deadends.md (G4 suppression set)."""
    out = set()
    for r in _parse_table(Path(eng) / "Deadends.md"):
        a = (r.get("asset") or "").strip().lower()
        c = (r.get("class") or "").strip().lower()
        if a and c:
            out.add((a, c))
    return out


def read_board(eng):
    """List of 4a row dicts (lowercased keys) from Approach.md. [] if none."""
    return _parse_table(Path(eng) / "Approach.md")


def _fmt_row(r):
    return "| " + " | ".join(str(r.get(c, "") or "") for c in BOARD_COLS) + " |"


_BOARD_RE = re.compile(r"(^\|\s*id\s*\|[^\n]*\n)(\|[-:| ]+\|[^\n]*\n)?((?:\|[^\n]*\n?)*)", re.M)


def write_board(eng, rows):
    """Replace the 4a table body with `rows`, preserving the rest of Approach.md.
    Creates Approach.md (and a 4a section) if absent. Mirrors campaign.write_board."""
    p = Path(eng) / "Approach.md"
    text = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
    header = "| " + " | ".join(BOARD_COLS) + " |\n"
    sep = "|" + "|".join("-" * (len(c) + 2) for c in BOARD_COLS) + "|\n"
    body = "".join(_fmt_row(r) + "\n" for r in rows)
    m = _BOARD_RE.search(text)
    if m:
        new = text[:m.start(1)] + header + sep + body + text[m.end():]
    else:
        base = text.rstrip() + "\n\n" if text.strip() else "# Approach\n\n"
        new = base + "### 4a. Coverage matrix\n\n" + header + sep + body
    p.write_text(new, encoding="utf-8")


def _class_info(index):
    """class -> (skill, arsenal) from the routing index, first routing row per
    class wins (routing dict preserves table order)."""
    info = {}
    for row in (index.get("routing") or {}).values():
        cls = (row.get("class") or "").strip()
        if cls and cls not in info:
            info[cls] = (row.get("skill", ""), row.get("arsenal", ""))
    return info


def _emit_row(out, seen, dead, info, asset, cls):
    """Append a 4a row dict for (asset, cls) unless already seen/deadended. Shared by the
    OSINT pre-pass and the per-asset implied/vector/base emission in derive_rows()."""
    key = (asset.lower(), cls.lower())
    if key in seen or key in dead:
        return
    seen.add(key)
    skill, arsenal = info.get(cls, ("", ""))
    out.append({
        "asset": asset, "vuln class": cls, "arsenal": arsenal,
        "skill": skill, "tool": CLASS_TOOL.get(cls, "nuclei"),
        "status": "[ ]", "poc": "", "poc_kind": "",
    })


def derive_rows(eng, index, etype):
    """Desired 4a rows (dicts, no id) for the engagement, in this order:
    (1) OSINT baseline rows, once, keyed to the engagement name (pre-scan, target-level --
        no asset/IP exists yet at this phase);
    (2) per real asset (from state.md): fingerprint-implied classes, then the baseline classes
        of each matched vector (web > ad_windows > linux, VECTOR_PRIORITY) plus any narrow
        fingerprint-gated VECTOR_EXCEPTION class, then BASE_CLASSES[etype] fallback.
    G4-suppresses any (asset, class) already in Deadends.md. Skill/arsenal from the routing
    index, tool from CLASS_TOOL."""
    routing = index.get("routing") or {}
    info = _class_info(index)
    dead = _deadend_pairs(eng)
    out, seen = [], set()
    base = BASE_CLASSES.get(etype, [])

    # (1) OSINT pre-pass: pre-scan, target-level, engagement name stands in for "asset" since
    # no host/IP exists at this phase.
    osint_asset = Path(eng).name
    for cls in VECTOR_CLASSES["osint"]:
        _emit_row(out, seen, dead, info, osint_asset, cls)

    for r in _parse_table(Path(eng) / "state.md"):
        asset = (r.get("asset") or r.get("host") or r.get("target") or "").strip()
        if not asset or asset == "?":
            continue
        hay = " ".join(str(r.get(k, "")) for k in
                       ("tech", "services", "service", "os", "notes")).lower()
        # fingerprint-implied classes first (ranked above base-only classes)
        implied = []
        for fp, row in routing.items():
            if re.search(r"\b" + re.escape(fp.lower()) + r"\b", hay):
                cls = (row.get("class") or "").strip()
                if cls and cls not in implied:
                    implied.append(cls)
        for cls in implied:
            _emit_row(out, seen, dead, info, asset, cls)

        # (2) vector baseline + narrow exceptions, in VECTOR_PRIORITY order
        for vector in VECTOR_PRIORITY:
            if not VECTOR_INDICATOR[vector].search(hay):
                continue
            for cls in VECTOR_CLASSES[vector]:
                _emit_row(out, seen, dead, info, asset, cls)
            for (v, fp_substr), exc_cls in VECTOR_EXCEPTION.items():
                if v == vector and fp_substr in hay:
                    _emit_row(out, seen, dead, info, asset, exc_cls)

        for cls in [c for c in base if c not in implied]:
            _emit_row(out, seen, dead, info, asset, cls)
    return out


def _next_board_id(rows, prefix="4a"):
    """Highest existing <prefix>:N on the board, so appends never collide. Shared by cmd_board
    (4a, the default) and seed_4b (4b) -- previously seed_4b re-implemented this same scan
    inline with a hardcoded "4b:" pattern instead of parameterizing this helper."""
    mx = 0
    pat = re.compile(re.escape(prefix) + r":(\d+)")
    for r in rows:
        m = pat.match((r.get("id") or "").strip())
        if m:
            mx = max(mx, int(m.group(1)))
    return mx


def cmd_board(args):
    vault = Path(args.vault) if args.vault else DEFAULT_VAULT
    eng = _resolve_eng(args.eng)
    if eng is None or not eng.is_dir():
        print("error: --eng <name|path> required for `board`")
        return 2
    try:
        state = json.loads((eng / STATE_NAME).read_text())
    except FileNotFoundError:
        print("error: %s missing - run `init` first" % STATE_NAME)
        return 2
    etype = state.get("type", "pentest")
    index = load_index(eng)

    existing = read_board(eng)
    have = {((r.get("asset") or "").lower(), (r.get("vuln class") or "").lower())
            for r in existing}
    nid = _next_board_id(existing)

    added = 0
    rows = list(existing)
    for row in derive_rows(eng, index, etype):
        key = (row["asset"].lower(), row["vuln class"].lower())
        if key in have:                       # idempotent: never duplicate a row
            continue
        have.add(key)
        nid += 1
        rows.append(dict(id="4a:%d" % nid, **row))
        added += 1
    write_board(eng, rows)
    print("board: %d rows (%d new) -> %s" % (len(rows), added, eng / "Approach.md"))
    return 0


# --------------------------------------------------------------------------- board (4b post-foothold)
#
# Once an asset is owned, the 4a vuln-class board is spent; the loop pivots to
# privesc + lateral movement. `foothold` (or `done --win`) records the shell and
# re-runs THIS derivation to append 4b rows under a `### 4b` section. Rows are
# non-hollow (skill+arsenal from the routing index, a real privesc/lateral tool)
# and G4-suppressed, exactly like 4a. Models campaign.derive_privesc_rows.

_H4B = "### 4b. Post-foothold (privesc / lateral)"

# Linux privesc has no hunt-<class> skill of its own; its 4b row routes via the
# arsenal hint + tool only (skill cell stays empty, which next/done G2 skip).
LINUX_PRIVESC = "linux-privesc"

# 4b concept -> (routing class for skill+arsenal, tool). OS-picked per foothold
# asset. A concept with no hunt class of its own borrows a sensible one
# (hunt-windows/hunt-macos/hunt-ad) so the row is never hollow (brief rule).
_WIN_RE = re.compile(r"\bwin(dows)?\b|win10|win201[69]|win2022|server 20")
_MAC_RE = re.compile(r"\bmac(os)?\b|darwin|osx\b")


def _os_hint(eng):
    """asset -> os/tech haystack (lowered) from state.md, for 4b OS picking."""
    out = {}
    for r in _parse_table(Path(eng) / "state.md"):
        asset = (r.get("asset") or r.get("host") or r.get("target") or "").strip()
        if asset:
            out[asset] = " ".join(str(r.get(k, "")) for k in
                                  ("os", "tech", "services", "service", "notes")).lower()
    return out


def derive_privesc_rows(eng, index, etype, st):
    """4b post-foothold rows (dicts, no id) for each recorded foothold asset.
    pentest: one privesc row (OS-routed) + one lateral row (ad routing). ctf: two
    privesc rows (auto + manual). bb has no host privesc -> [].

    OS routing (from the asset's state.md fingerprint; unknown -> Linux):
      windows -> hunt-windows + privesc-exploit-arsenal, winpeas
      macos   -> hunt-macos   + macos-app-injection,     pspy/linpeas
      linux   -> NO hunt-linux class: skill EMPTY, arsenal LINUX_PRIVESC hint,
                 linpeas/pspy. A blank skill is correct here (next/done G2 skip
                 an empty skill cell); the row stays routable via G1 arsenal +
                 G8 tool.
    Every row still carries a non-empty arsenal AND tool; G4-suppresses any
    (asset, class) already in Deadends.md."""
    if etype not in ("pentest", "ctf"):
        return []
    foot = st.get("footholds") or {}
    if not foot:
        return []
    info = _class_info(index)          # class -> (skill, arsenal)
    dead = _deadend_pairs(eng)
    oshint = _os_hint(eng)
    out, seen = [], set()
    for asset in foot:
        hay = oshint.get(asset, "")
        is_win = bool(_WIN_RE.search(hay))
        is_mac = bool(_MAC_RE.search(hay))
        # privesc skill+arsenal by OS; linux/unknown default has no hunt class.
        if is_win:
            pv_skill, pv_arsenal, auto_tool, man_tool = (
                *info.get("windows", ("", "")), "winpeas", "winpeas")
        elif is_mac:
            pv_skill, pv_arsenal, auto_tool, man_tool = (
                *info.get("macos", ("", "")), "pspy", "linpeas")
        else:                          # linux / unknown -> Linux tooling, no skill
            pv_skill, pv_arsenal, auto_tool, man_tool = (
                "", LINUX_PRIVESC, "pspy", "linpeas")
        if etype == "pentest":
            specs = [("privesc", pv_skill, pv_arsenal, man_tool)]
            lat_skill, lat_arsenal = info.get("ad", ("", ""))
            specs.append(("lateral", lat_skill, lat_arsenal, "bloodhound"))
        else:  # ctf: boot-to-root privesc, auto + manual
            specs = [("privesc-auto", pv_skill, pv_arsenal, auto_tool),
                     ("privesc-manual", pv_skill, pv_arsenal, man_tool)]
        for cls, skill, arsenal, tool in specs:
            key = (asset.lower(), cls.lower())
            if key in seen or key in dead:
                continue
            seen.add(key)
            out.append({
                "asset": asset, "vuln class": cls, "arsenal": arsenal,
                "skill": skill, "tool": tool,
                "status": "[ ]", "poc": "", "poc_kind": "",
            })
    return out


def _parse_table_text(text):
    """First markdown table in `text` -> list-of-dicts (lowercased headers).
    Text-scoped twin of _parse_table (which reads a whole file); used to parse
    the 4b table out of a slice of Approach.md."""
    rows, header = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if header is not None:
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if not any(cells):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def read_board_4b(eng):
    """4b row dicts from the `### 4b` section of Approach.md. [] if absent."""
    p = Path(eng) / "Approach.md"
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8", errors="ignore")
    idx = text.find("### 4b")
    return _parse_table_text(text[idx:]) if idx >= 0 else []


def write_board_4b(eng, rows):
    """Replace (or append) the `### 4b` section with `rows`. The 4b section is
    always the last block, so its table body up to EOF is regenerated. The 4a
    table (parsed/written separately) is untouched."""
    p = Path(eng) / "Approach.md"
    text = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else "# Approach\n"
    header = "| " + " | ".join(BOARD_COLS) + " |\n"
    sep = "|" + "|".join("-" * (len(c) + 2) for c in BOARD_COLS) + "|\n"
    body = "".join(_fmt_row(r) + "\n" for r in rows)
    block = _H4B + "\n\n" + header + sep + body
    idx = text.find("### 4b")
    new = (text[:idx] + block) if idx >= 0 else (text.rstrip() + "\n\n" + block)
    p.write_text(new, encoding="utf-8")


def seed_4b(eng, index, etype, st):
    """Append the derived 4b rows (idempotent + append-only, like cmd_board).
    Returns the count of new rows written."""
    existing = read_board_4b(eng)
    have = {((r.get("asset") or "").lower(), (r.get("vuln class") or "").lower())
            for r in existing}
    nid = _next_board_id(existing, prefix="4b")
    rows, added = list(existing), 0
    for row in derive_privesc_rows(eng, index, etype, st):
        key = (row["asset"].lower(), row["vuln class"].lower())
        if key in have:
            continue
        have.add(key)
        nid += 1
        rows.append(dict(id="4b:%d" % nid, **row))
        added += 1
    if added:
        write_board_4b(eng, rows)
    return added


# --------------------------------------------------------------------------- next (cursor + gate walk)
#
# The agent loop: run `next`, do exactly what it prints, record, repeat. `next`
# NEVER prints a question (G7) - if nothing is actionable it prints a terminal
# state, not a menu. Cursor + action resolution model campaign.py cmd_next.

# Exploit-shaped classes route load-bearing HTTP requests: G8 also emits a Burp
# Repeater push so the operator watches the exploit live (CLAUDE.md Burp-first).
EXPLOIT_CLASSES = {
    "rce", "sqli", "ssrf", "ssti", "xxe", "idor", "bola", "injection", "xss",
    "deserialization", "auth", "upload", "file-upload", "api", "cache",
    "federation", "oauth-saml", "request-smuggling", "smuggling", "graphql",
    "business-logic", "bizlogic", "csrf", "cors", "jwt", "open-redirect",
    "host-header", "web-cache", "prototype-pollution", "session",
    "race-condition", "m365", "llm", "mcp", "secrets",
}

# Classes where a browser render IS the evidence (an XSS alert, an open-redirect
# hop) - the only ones for which `--kind web` is admissible. For everything else
# a `web` screenshot is indistinguishable from any visitor's, so G3 refuses it.
VISUAL_CLASSES = {
    "xss", "dom-xss", "csrf", "open-redirect", "clickjacking", "cors",
}


def _events(eng):
    """Parsed .events.jsonl rows, or None if the telemetry file is absent (G2
    then fails open - the skill is emitted). Mirrors campaign._events."""
    p = Path(eng) / ".events.jsonl"
    if not p.is_file():
        return None
    out = []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _skill_fired(eng, skill, since_iso):
    """True iff a `Skill(<skill>)` event dated at/after `since_iso` exists in
    .events.jsonl. Missing file or no match -> False (G2 emits the skill)."""
    ev = _events(eng)
    if not ev or not skill:
        return False
    for e in ev:
        if e.get("tool") == "Skill" and e.get("skill") == skill:
            if not since_iso or (e.get("ts") or "") >= since_iso:
                return True
    return False


def _status_of(r):
    return (r.get("status") or "").strip()


def _row_by_id(rows, rid):
    for r in rows:
        if (r.get("id") or "").strip() == rid:
            return r
    return None


def _find_row_any(eng, rid):
    """Locate a row by id across the 4a AND 4b boards. Returns
    (rows, row, writer) where writer(eng, rows) persists the board the row lives
    on, or (None, None, None) if the id is unknown. Lets note/done act on a 4b
    privesc/lateral row the same way as a 4a row."""
    rows = read_board(eng)
    row = _row_by_id(rows, rid)
    if row:
        return rows, row, write_board
    rows = read_board_4b(eng)
    row = _row_by_id(rows, rid)
    if row:
        return rows, row, write_board_4b
    return None, None, None


def _append_line(path, line):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line.rstrip() + "\n")


def _open_assets(rows):
    """Assets (board order, deduped) that still have a [ ]/[~] row."""
    seen, out = set(), []
    for r in rows:
        a = (r.get("asset") or "").strip()
        if _status_of(r) in ("[ ]", "[~]") and a and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def _cursor_asset(rows, st):
    """Depth-first (G5), sticky: an in-progress [~] row's asset wins; else the
    stored asset_cursor if it still has an open row; else the first open asset
    in board order. Finishes one asset before moving on."""
    for r in rows:
        if _status_of(r) == "[~]":
            return (r.get("asset") or "").strip()
    open_a = _open_assets(rows)
    cur = (st or {}).get("asset_cursor")
    if cur and cur in open_a:
        return cur
    return open_a[0] if open_a else None


def _active_row(rows, asset):
    """The one open row for `asset`: its [~] row if any (one-open-at-a-time),
    else the top [ ] row for that asset. None if the asset has no open row."""
    for r in rows:
        if _status_of(r) == "[~]" and (r.get("asset") or "").strip() == asset:
            return r
    for r in rows:
        if (r.get("asset") or "").strip() == asset and _status_of(r) == "[ ]":
            return r
    return None


def cmd_next(args):
    vault = Path(args.vault) if args.vault else DEFAULT_VAULT
    eng = _resolve_eng(args.eng)
    if eng is None or not eng.is_dir():
        print("error: --eng <name|path> required for `next`")
        return 2
    try:
        state = json.loads((eng / STATE_NAME).read_text())
    except FileNotFoundError:
        print("error: %s missing - run `init` first" % STATE_NAME)
        return 2

    # G9: index freshness FIRST. A silent misread of a stale routing table is
    # how a whole campaign runs the wrong checklist - refuse, non-zero.
    if index_stale(eng, vault):
        _die("index stale or missing (a routing/tool/skill source changed) - "
             "run: offensive.py --eng %s index" % (args.eng or eng.name))
    index = load_index(eng)

    # WALL-BREAK (self-correction): a dry streak at/over the type threshold means
    # the agent is grinding a wrong vector. Emit Skill(redteamlead) ONCE for
    # wiki-grounded redirection (reset the streak so the next turn resumes the
    # normal gate walk), never a question (G7).
    threshold = WALLBREAK_THRESHOLD.get(state.get("type"), 3)
    if state.get("dry_streak", 0) >= threshold:
        state["dry_streak"] = 0
        (eng / STATE_NAME).write_text(json.dumps(state, indent=2))
        print("WALL-BREAK: dry_streak reached %d (>= %d) - you are grinding a "
              "wrong vector. Run Skill(redteamlead) for wiki-grounded direction "
              "before the next vector." % (threshold, threshold))
        print("  Skill(redteamlead)")
        return 0

    # Aggregate 4a AND 4b rows so the cursor/gate walk serves both boards. 4a
    # rows come first, so per asset the depth-first cursor exhausts its 4a rows
    # before continuing into that asset's 4b (privesc/lateral) rows once a
    # foothold exists. Closeout only fires when BOTH are exhausted.
    rows = read_board(eng)
    if state.get("foothold"):
        rows = rows + read_board_4b(eng)
    asset = _cursor_asset(rows, state)
    row = _active_row(rows, asset) if asset else None
    if not asset or not row:
        # G7: terminal state, never a question.
        print("board exhausted: no open rows. run the closeout chain.")
        return 0

    state["asset_cursor"] = asset
    (eng / STATE_NAME).write_text(json.dumps(state, indent=2))

    rid = (row.get("id") or "").strip()
    cls = (row.get("vuln class") or "").strip()
    skill = (row.get("skill") or "").strip()
    print("PASS %s | ASSET %s | ROW %s %s" % (state.get("pass", 0), asset, rid, cls))

    # Post-foothold: route load-bearing tool commands through the recorded shell
    # so the operator keeps visibility (CLAUDE.md Burp-first / post-foothold).
    if state.get("foothold"):
        win = (state.get("footholds") or {}).get(asset)
        if win:
            print("POST-EX   route tool cmds for %s through: bash scripts/vm-rsh.sh "
                  "--win %s '<cmd>'  (see the ### 4b rows)" % (asset, win))
        else:
            print("POST-EX   foothold established; route post-ex cmds through the "
                  "recorded vm-rsh shell (see the ### 4b rows)")

    # method block for the row's class (parse_hunt_method result, keyed by skill).
    # Fields may be empty on real skills (Task 13 backfills); print what's present.
    method = (index.get("methods") or {}).get(skill, {})
    if method.get("approach"):
        print("APPROACH  %s" % method["approach"])
    if method.get("avoid"):
        print("AVOID     %s" % method["avoid"])
    if method.get("refs"):
        print("REFS      %s" % method["refs"])
    print("")
    print("REQUIRED, in order:")

    # G1 arsenal-first: no arsenal card -> withhold ALL exploit actions.
    if not (row.get("arsenal") or "").strip():
        print("  1. Skill(wiki-arsenal) %s        [G1: arsenal cell empty -> "
              "exploit actions withheld]" % cls)
        return 0

    # G2 skill-first: mapped hunt skill unfired -> run it, withhold the tool.
    # Fail-open when telemetry is absent (mirrors cmd_done ~:1079), else the
    # tool step is never reached and `next` livelocks on Skill(<skill>) forever.
    if skill and not _skill_fired(eng, skill, state.get("started_at")):
        if _events(eng) is None:
            print("  (G2 advisory: .events.jsonl absent, skill-fired "
                  "unverifiable - proceeding to the tool step)")
        else:
            print("  1. Skill(%s)        [G2: skill unfired in .events.jsonl]" % skill)
            return 0

    # G8 tool-first: emit the tool invocation, then the capture line.
    tool = (row.get("tool") or "").strip()
    inv = (index.get("tools") or {}).get(tool, {}).get("invocation") or (tool + " <target>")
    n = 1
    print("  %d. run: %s        [G8: tool-first; no hand-rolled "
          "/dev/tcp/curl/urllib loops - if no tool fits, say why in one line]" % (n, inv))
    n += 1
    if cls.lower() in EXPLOIT_CLASSES:
        print("  %d. push to Burp Repeater via Skill(hunt-burp)   (load-bearing "
              "exploit req -> operator visibility)" % n)
        n += 1
    print("  %d. capture.sh req <request>   (evidence for %s)" % (n, rid))
    return 0


# --------------------------------------------------------------------------- note / done / park (record + gates)
#
# `next` withholds; these RECORD the outcome and enforce the evidence gates.
# note --arsenal satisfies G1; done enforces G1 (arsenal set) + G2 (mapped skill
# fired) + G3 (exactly one typed disposition). Modelled on campaign.cmd_note /
# cmd_done: gate refusals are hard (_die, non-zero); status transitions mutate
# the board in place. `next` recomputes the cursor each run, so parking/killing
# a row advances the loop with no state write here (G7 no-ask).


def _eng_state(args, cmd):
    """(eng, state) or (None, None) after printing an error. Shared preamble."""
    eng = _resolve_eng(args.eng)
    if eng is None or not eng.is_dir():
        print("error: --eng <name|path> required for `%s`" % cmd)
        return None, None
    try:
        state = json.loads((eng / STATE_NAME).read_text())
    except FileNotFoundError:
        print("error: %s missing - run `init` first" % STATE_NAME)
        return None, None
    return eng, state


def cmd_note(args):
    """G1 release: set the row's arsenal cell (the consulted wiki-arsenal card
    slug) and write the board. Flips a fresh [ ] row to [~] (in-progress),
    mirroring campaign.cmd_note. No card-file validation - the board carries the
    slug; the operator ran Skill(wiki-arsenal) to get it."""
    eng, state = _eng_state(args, "note")
    if eng is None:
        return 2
    rows, row, writer = _find_row_any(eng, args.row)
    if not row:
        _die("no such row: %s" % args.row)
    row["arsenal"] = args.arsenal
    if _status_of(row) == "[ ]":
        row["status"] = "[~]"
    writer(eng, rows)
    print("note: %s arsenal=%s (G1 released; row [~])" % (args.row, args.arsenal))
    return 0


def cmd_park(eng, state, rows, row, reason, writer=write_board):
    """G7 no-ask defer: record the judgment call to decisions.md and mark the row
    [?] (parked - revisitable, distinct from [!] dead). Leaves it off the serve
    loop so `next` advances to the next open asset WITHOUT ever asking."""
    row["status"] = "[?]"
    writer(eng, rows)
    dec = eng / "decisions.md"
    _append_line(dec, "| %s | %s | parked | %s |"
                 % ((row.get("id") or "").strip(), reason, _today()))
    print("done: %s parked (status set for later revisit) -> decisions.md; "
          "loop advances with no operator prompt"
          % (row.get("id") or "").strip())
    return 0


def _set_state_access(eng, asset, win, access="foothold"):
    """Flip the state.md inventory row whose first cell == `asset` to
    access=`access` and append a `tmux:<win>` note. Line-based rewrite of one
    cell (mirrors campaign._set_state_access). Returns True if a row matched;
    fail-soft on IO/absent columns."""
    p = Path(eng) / "state.md"
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").split("\n")
    except OSError:
        return False
    header = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("|"):
            if header is not None:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if not cells or cells[0] != asset:
            continue
        ai = header.index("access") if "access" in header else None
        ni = header.index("notes") if "notes" in header else None
        changed = False
        if ai is not None and ai < len(cells):
            cells[ai] = access
            changed = True
        note = "tmux:%s" % win
        if ni is not None and ni < len(cells) and note not in cells[ni]:
            cells[ni] = (cells[ni] + "; " + note) if cells[ni] else note
            changed = True
        if changed:
            lines[i] = "| " + " | ".join(cells) + " |"
            p.write_text("\n".join(lines), encoding="utf-8")
        return True
    return False


def _record_foothold(eng, st, asset, win):
    """Record an asset's foothold: set the global `foothold` flag, store the tmux
    window under st['footholds'][asset], and flip its state.md row to
    access=foothold. Mutates st; caller saves. Returns the state.md match bool."""
    st["foothold"] = True
    st.setdefault("footholds", {})[asset] = win
    return _set_state_access(eng, asset, win)


def cmd_foothold(args):
    """Record a foothold on <asset> (tmux --win) and re-run board derivation to
    append 4b post-ex rows. `next` then carries a post-ex routing note."""
    eng, state = _eng_state(args, "foothold")
    if eng is None:
        return 2
    asset = args.asset or state.get("asset_cursor")
    if not asset:
        _die("foothold needs an <asset> (or a cursor asset from a prior `next`)")
    matched = _record_foothold(eng, state, asset, args.win)
    (eng / STATE_NAME).write_text(json.dumps(state, indent=2))
    etype = state.get("type", "pentest")
    added = seed_4b(eng, load_index(eng), etype, state)
    print("foothold: %s -> tmux window %s (foothold=true)%s"
          % (asset, args.win, "" if matched else " (no state.md row matched; recorded anyway)"))
    print("  4b: %d post-ex rows appended (privesc/lateral for %s)" % (added, etype))
    print("  post-ex for %s routes through: bash scripts/vm-rsh.sh --win %s '<cmd>'"
          % (asset, args.win))
    return 0


def cmd_done(args):
    """Close a row. Exactly one disposition (G3): --poc P --kind K | --dead | --park.
    --poc closes [x] behind G1 (arsenal) + G2 (skill fired) + G3 (typed kind);
    --dead marks [!] + one Deadends line; --park defers via cmd_park."""
    eng, state = _eng_state(args, "done")
    if eng is None:
        return 2
    rows, row, writer = _find_row_any(eng, args.row)
    if not row:
        _die("no such row: %s" % args.row)

    # G3: exactly one typed disposition, else refuse.
    modes = [m for m in (args.poc, args.dead, args.park) if m]
    if not modes:
        _die("done needs one of --poc P --kind K | --dead | --park [G3: a row "
             "never closes without typed evidence, a dead-end, or a park]")
    if len(modes) > 1:
        _die("done takes exactly one disposition, got %d [G3]" % len(modes))

    cls = (row.get("vuln class") or "").strip().lower()

    # --park: G7 no-ask defer (no G1/G2 - nothing was exploited).
    if args.park:
        return cmd_park(eng, state, rows, row, args.park, writer)

    # --dead: exhausted vector (no G1/G2 - a dead-end needs no evidence).
    if args.dead:
        row["status"] = "[!]"
        writer(eng, rows)
        reason = args.dead if isinstance(args.dead, str) else "exhausted"
        _append_line(eng / "Deadends.md", "| %s | %s | %s | exhausted | %s | |"
                     % (row.get("asset") or "", cls, reason, _today()))
        # WALL-BREAK feed: a no-find outcome bumps the dry streak (next fires
        # Skill(redteamlead) once it hits the type threshold).
        state["dry_streak"] = state.get("dry_streak", 0) + 1
        (eng / STATE_NAME).write_text(json.dumps(state, indent=2))
        print("done: %s dead [!] (dry_streak=%d) -> Deadends.md (loop advances)"
              % (args.row, state["dry_streak"]))
        return 0

    # --poc: the evidence path, behind all three gates.
    # G1 arsenal-first: no consulted arsenal card -> refuse (note --arsenal first).
    if not (row.get("arsenal") or "").strip():
        _die("cannot close %s: arsenal cell empty - run "
             "`note %s --arsenal <slug>` first [G1 arsenal-first]"
             % (args.row, args.row))
    # G3 typed evidence: --poc needs a kind; `web` only for visual classes.
    if not args.kind:
        _die("--poc requires --kind req|burp|web [G3]")
    if args.kind == "web" and cls not in VISUAL_CLASSES:
        _die("a 'web' render is not evidence for class '%s' - it is "
             "indistinguishable from any visitor's screenshot. Use --kind req "
             "(capture.sh req) [G3]" % cls)
    # G2 skill-first: the mapped hunt skill must have fired since started_at. A
    # `--skill <name>` override lets a CORRECTLY-fired skill satisfy G2 when the
    # board mapped the wrong class->skill; the override must itself have fired.
    since = state.get("started_at")
    g2_skill = (args.skill or "").strip() or (row.get("skill") or "").strip()
    if g2_skill and not _skill_fired(eng, g2_skill, since):
        if _events(eng) is None:
            # fail-open: telemetry absent, cannot verify (mirrors next's G2).
            print("offensive: G2 warn: .events.jsonl absent, cannot verify "
                  "Skill(%s) fired - allowing (fail-open)" % g2_skill,
                  file=sys.stderr)
        else:
            tail = ("" if args.skill else
                    ". If you exploited it via a different (correctly-fired) "
                    "skill, pass `--skill <that-skill>`.")
            _die("cannot close %s: Skill(%s) never fired since the row opened "
                 "[G2 skill-first]%s" % (args.row, g2_skill, tail))
    if args.skill and args.skill.strip() != (row.get("skill") or "").strip():
        row["skill"] = args.skill.strip()   # correct the board to what landed

    row["status"] = "[x]"
    row["poc"] = args.poc
    row["poc_kind"] = args.kind
    writer(eng, rows)
    # WALL-BREAK feed: a find resets the dry streak.
    state["dry_streak"] = 0
    (eng / STATE_NAME).write_text(json.dumps(state, indent=2))
    print("done: %s closed [x] (poc=%s kind=%s)" % (args.row, args.poc, args.kind))

    # --win: this row landed a shell (e.g. an RCE) -> record a foothold on its
    # asset and re-run the 4b post-ex re-board, same as `foothold`.
    if args.win:
        asset = (row.get("asset") or "").strip()
        matched = _record_foothold(eng, state, asset, args.win)
        (eng / STATE_NAME).write_text(json.dumps(state, indent=2))
        added = seed_4b(eng, load_index(eng), state.get("type", "pentest"), state)
        print("  foothold recorded on %s (tmux %s%s); 4b: %d post-ex rows"
              % (asset, args.win, "" if matched else ", no state.md row", added))
    return 0


# --------------------------------------------------------------------------- coverage / closeout


def cmd_coverage(args):
    """G7 gap report: per asset, the BASE_CLASSES[type] vuln classes with no
    [x] row on the board (4a + 4b). Untested = no closed evidence row, whether
    the row is open, dead, parked, or absent. Prints no question."""
    eng, state = _eng_state(args, "coverage")
    if eng is None:
        return 2
    etype = state.get("type", "pentest")
    base = BASE_CLASSES.get(etype, [])
    rows = read_board(eng) + read_board_4b(eng)
    assets, seen = [], set()
    for r in rows:
        a = (r.get("asset") or "").strip()
        if a and a not in seen:
            seen.add(a)
            assets.append(a)
    tested = {((r.get("asset") or "").strip().lower(),
               (r.get("vuln class") or "").strip().lower())
              for r in rows if _status_of(r) == "[x]"}
    print("coverage (%s): base vuln classes with no [x] row per asset" % etype)
    gaps_found = False
    for a in assets:
        gaps = [c for c in base if (a.lower(), c) not in tested]
        if gaps:
            gaps_found = True
            print("  %s: %s" % (a, ", ".join(gaps)))
    if not assets:
        print("  no assets on the board yet - run `board` first")
    elif not gaps_found:
        print("  none - every asset carries an [x] row for each base class")
    return 0


def cmd_closeout(args):
    """Print the per-type close-out chain (Skill names, in order) for the
    engagement. G7: no question, just the ordered chain."""
    eng, state = _eng_state(args, "closeout")
    if eng is None:
        return 2
    etype = state.get("type", "pentest")
    chain = CLOSEOUT_CHAINS.get(etype, CLOSEOUT_CHAINS["pentest"])
    print("closeout chain (%s), run in order:" % etype)
    for i, s in enumerate(chain, 1):
        print("  %d. Skill(%s)" % (i, s))
    return 0


def cmd_rebase(args):
    """Instance rotated mid-engagement (old IP/asset value -> new): re-point every
    file that hardcodes it, so the board/cursor keep working instead of the next
    `next` silently serving rows for a dead host. Top-level *.md + the driver
    cache. Idempotent (a second run replaces nothing)."""
    eng, _state = _eng_state(args, "rebase")
    if eng is None:
        return 2
    old, new = args.old, args.new
    if old == new:
        print("rebase: old == new, nothing to do")
        return 0
    n = 0
    for p in sorted(Path(eng).glob("*.md")):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if old in txt:
            p.write_text(txt.replace(old, new), encoding="utf-8")
            print("  %s: re-pointed" % p.name)
            n += 1
    sp = Path(eng) / STATE_NAME
    if sp.is_file():
        raw = sp.read_text(encoding="utf-8", errors="ignore")
        if old in raw:
            sp.write_text(raw.replace(old, new), encoding="utf-8")
            print("  %s: re-pointed (asset_cursor)" % STATE_NAME)
            n += 1
    print("rebase: %s -> %s across %d file(s). Rows derived from state.md: re-run `board` if the matrix predates this." % (old, new, n))
    return 0


# --------------------------------------------------------------------------- cli

def _resolve_eng(eng):
    """--eng may be an engagement name (targets/<name>) or a path."""
    if not eng:
        return None
    p = Path(eng)
    if p.is_dir():
        return p
    cand = DEFAULT_VAULT / "targets" / eng
    return cand


def cmd_index(args):
    vault = Path(args.vault) if args.vault else DEFAULT_VAULT
    eng = _resolve_eng(args.eng)
    if eng is None:
        print("error: --eng <name|path> required for `index`")
        return 2
    idx = build_index(eng, vault)
    print("index built -> %s" % (eng / CACHE_NAME))
    print("  routing: %d fingerprints | tools: %d | methods: %d skills"
          % (len(idx["routing"]), len(idx["tools"]), len(idx["methods"])))
    return 0


def cmd_init(args):
    vault = Path(args.vault) if args.vault else DEFAULT_VAULT
    eng = vault / "targets" / args.name
    eng.mkdir(parents=True, exist_ok=True)

    for name in TEMPLATE_FILES:
        dst = eng / name
        if not dst.exists():
            shutil.copyfile(TEMPLATE_DIR / name, dst)

    state_path = eng / STATE_NAME
    if state_path.exists():
        print("init: %s already initialised (%s untouched)" % (args.name, STATE_NAME))
        return 0

    state = {
        "type": args.type,
        "pass": 0,
        "asset_cursor": None,
        "dry_streak": 0,
        "cmd_ledger": {},
        "req_count": 0,
        "foothold": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    state_path.write_text(json.dumps(state, indent=2))
    print("init: %s type=%s -> %s" % (args.name, args.type, eng))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="offensive.py")
    ap.add_argument("--eng", help="engagement name (targets/<name>) or path")
    ap.add_argument("--vault", help="vault root (default: repo containing this script)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index", help="compile the vault -> .offensive-index.json").set_defaults(fn=cmd_index)

    p_init = sub.add_parser("init", help="scaffold a new engagement under targets/<name>")
    p_init.add_argument("name", help="engagement name (creates targets/<name>)")
    p_init.add_argument("--type", choices=("pentest", "ctf", "bb"), default="pentest")
    p_init.set_defaults(fn=cmd_init)

    sub.add_parser("board", help="write the Approach.md 4a coverage matrix from the index").set_defaults(fn=cmd_board)
    sub.add_parser("next", help="print the next action (cursor + gate walk)").set_defaults(fn=cmd_next)
    sub.add_parser("coverage", help="per-asset untested vuln-class gaps (no [x] row)").set_defaults(fn=cmd_coverage)
    sub.add_parser("closeout", help="print the per-type close-out Skill chain").set_defaults(fn=cmd_closeout)

    p_note = sub.add_parser("note", help="set a row's arsenal cell (G1 release)")
    p_note.add_argument("row", help="board row id, e.g. 4a:3")
    p_note.add_argument("--arsenal", required=True, help="consulted wiki-arsenal card slug")
    p_note.set_defaults(fn=cmd_note)

    p_done = sub.add_parser("done", help="close a row (G1/G2/G3 gates) or --dead / --park")
    p_done.add_argument("row", help="board row id, e.g. 4a:3")
    p_done.add_argument("--poc", help="evidence image path (closes [x])")
    p_done.add_argument("--kind", choices=("req", "burp", "web"), help="evidence kind for --poc")
    p_done.add_argument("--dead", nargs="?", const="exhausted",
                        help="mark the row [!] exhausted (optional reason)")
    p_done.add_argument("--park", help="defer the row [?] with a decision note (G7 no-ask)")
    p_done.add_argument("--skill", help="G2 override: the skill that actually fired")
    p_done.add_argument("--win", help="tmux window: also record a foothold on this "
                        "row's asset + seed the 4b post-ex board")
    p_done.set_defaults(fn=cmd_done)

    p_foot = sub.add_parser("foothold", help="record a foothold (tmux --win) + seed the 4b post-ex board")
    p_foot.add_argument("asset", nargs="?", help="asset that was owned (default: cursor asset)")
    p_foot.add_argument("--win", required=True, help="tmux window running the shell")
    p_foot.set_defaults(fn=cmd_foothold)

    p_rebase = sub.add_parser("rebase", help="re-point a rotated asset value (old -> new) across the engagement")
    p_rebase.add_argument("old", help="stale asset value (e.g. expired instance IP)")
    p_rebase.add_argument("new", help="current value")
    p_rebase.set_defaults(fn=cmd_rebase)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
