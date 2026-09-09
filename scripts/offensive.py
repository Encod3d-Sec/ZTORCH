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
# by header name).
BOARD_COLS = ["id", "asset", "vuln class", "arsenal", "skill", "tool",
              "status", "poc", "poc_kind"]

# Base vuln-class set per engagement type (literal dict, no JSON file). Each
# entry MUST be a `class` in the hunt-core routing table so every
# base-superset row resolves to a real skill+arsenal (satisfies board G1/G2).
# tests/test_board.py::test_no_base_row_has_blank_skill enforces this.
BASE_CLASSES = {
    "pentest": ["ad", "windows", "macos", "secrets", "api", "rce", "sqli",
                "ssrf", "auth", "idor"],
    "bb": ["rce", "sqli", "ssrf", "injection", "deserialization", "auth",
           "idor", "federation", "smuggling", "upload", "bizlogic", "api",
           "cache", "secrets", "xss", "cicd", "mcp", "llm"],
    "ctf": ["rce", "sqli", "ssrf", "injection", "idor", "upload", "auth",
            "xss", "secrets"],
}

# Per-type close-out chain (Skill names the agent runs in order) + wall-break
# dry-streak threshold.
CLOSEOUT_CHAINS = {
    "pentest": ["triage", "evidence", "walkthrough", "learn"],
    "bb": ["triage", "evidence", "walkthrough", "learn"],
    "ctf": ["walkthrough", "learn"],
}
WALLBREAK_THRESHOLD = {"pentest": 3, "bb": 3, "ctf": 2}

# class -> automated tool slug (wiki/tools/*). Fallback = nuclei. Deterministic
# so the board's `tool` cell is stable per class across runs.
CLASS_TOOL = {
    "rce": "metasploit", "sqli": "sqlmap", "ssrf": "nuclei",
    "deserialization": "metasploit", "auth": "nuclei", "idor": "burp-suite",
    "xss": "dalfox", "subdomain-takeover": "nuclei", "mcp": "curl",
    "cicd": "trufflehog", "api": "nuclei", "injection": "nuclei",
    "federation": "burp-suite", "cloud": "pacu", "secrets": "trufflehog",
    "smuggling": "nuclei", "upload": "nuclei", "vpn": "nmap",
    "windows": "peass", "ad": "netexec", "m365": "netexec",
    "macos": "linpeas", "llm": "curl", "bizlogic": "burp-suite",
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
    "osint": ["osint-subdomain", "osint-leaks", "subdomain-takeover"],
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
    for lineno, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
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
        _warn_ragged(p.name, lineno, header, cells)
        rows.append(dict(zip(header, cells)))
    return rows


# Ragged-row surface (pass 10): dict(zip(header, cells)) silently truncates a short
# row and shifts every later cell of an over-long one (an unescaped | in a cell); an
# unrecognized status cell ([X] uppercase, [x) typo) makes the row INVISIBLE to
# open/closed accounting - which once printed a false "board exhausted". Parsers
# stay best-effort (read paths never brick); they just announce the damage here,
# and cmd_board/cmd_next drain it. The clone's filterInvalidPermissionRules
# coerce+warn pattern: one bad member never poisons the file silently.
BOARD_WARNINGS = []
_STATUS_CELLS = ("[ ]", "[~]", "[x]", "[?]", "[!]")


def _warn_ragged(src, lineno, header, cells):
    if len(cells) != len(header):
        BOARD_WARNINGS.append("%s:%d: %d cells vs %d header columns - later cells "
                              "shifted (unescaped | in a cell?)" % (src, lineno, len(cells), len(header)))
    if "status" in header:
        st = dict(zip(header, cells)).get("status", "").strip()
        if st and st not in _STATUS_CELLS:
            BOARD_WARNINGS.append("%s:%d: status cell %r not recognized - row is "
                                  "invisible to open/closed accounting" % (src, lineno, st))


def _drain_board_warnings():
    out = list(BOARD_WARNINGS)
    BOARD_WARNINGS.clear()
    return out


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
    """List of 4a row dicts (lowercased keys) from Approach.md's `### 4a` section.
    Slicing from the heading (like read_board_4b) instead of taking the FIRST table
    keeps an agent-added table higher in the file from silently becoming the board
    (blank status/class cells -> empty cursor -> permanent 'board exhausted')."""
    p = Path(eng) / "Approach.md"
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8", errors="ignore")
    idx = text.find("### 4a")
    return _parse_table_text(text[idx:]) if idx >= 0 else []


def _fmt_row(r):
    return "| " + " | ".join(str(r.get(c, "") or "") for c in BOARD_COLS) + " |"


_BOARD_RE = re.compile(r"(^\|\s*id\s*\|[^\n]*\n)(\|[-:| ]+\|[^\n]*\n)?((?:\|[^\n]*\n?)*)", re.M)


def write_board(eng, rows):
    """Replace the 4a table body with `rows`, preserving the rest of Approach.md.
    Creates Approach.md (and a 4a section) if absent."""
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
    eng = _resolve_eng(args.eng)
    if eng is None or not eng.is_dir():
        print("error: --eng <name|path> required for `board`")
        return 2
    state = _load_state(eng)
    if state is None:
        return 2
    etype = state.get("type", "pentest")
    index = load_index(eng)

    existing = read_board(eng)
    for w in _drain_board_warnings():
        print("BOARD (parsed best-effort): %s" % w)
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
        _stamp_row_opened(state, row["asset"], row["vuln class"])
        added += 1
    write_board(eng, rows)
    if added:
        (eng / STATE_NAME).write_text(json.dumps(state, indent=2))
    print("board: %d rows (%d new) -> %s" % (len(rows), added, eng / "Approach.md"))
    return 0


# --------------------------------------------------------------------------- board (4b post-foothold)
#
# Once an asset is owned, the 4a vuln-class board is spent; the loop pivots to
# privesc + lateral movement. `foothold` (or `done --win`) records the shell and
# re-runs THIS derivation to append 4b rows under a `### 4b` section. Rows are
# non-hollow (skill+arsenal from the routing index, a real privesc/lateral tool)
# and G4-suppressed, exactly like 4a.

_H4B = "### 4b. Post-foothold (privesc / lateral)"

# Linux privesc has no hunt-<class> skill of its own; its 4b row routes via the
# arsenal hint + tool only (skill cell stays empty, which next/done G2 skip).
LINUX_PRIVESC = "linux-privesc"

# 4b tools that are mechanical/wait-heavy (a watch window, a known checklist) rather
# than judgment-heavy -> cmd_next nudges Skill(delegate) for these, never unconditionally.
MECHANICAL_4B_TOOLS = {"pspy", "linpeas", "winpeas"}

# Route+advise (spec 2026-09-08): G8 tool steps launch through the tmux-aware
# drivers instead of a bare invocation (one-shot SSH loses the pane + evidence).
# SCAN_CLASS = fire-and-forget (output lives in the named tab, autocard cards it);
# OUTPUT_CLASS = output must come back (vm-bg log). Others keep the bare line.
SCAN_CLASS = {"nmap", "masscan", "rustscan", "nuclei", "feroxbuster", "ffuf",
              "whatweb", "nikto", "wpscan", "gobuster", "dirb", "dirsearch"}
OUTPUT_CLASS = {"sqlmap", "hashcat", "john", "hydra", "medusa", "patator"}

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
                *info.get("windows", ("", "")), "peass", "peass")
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
    for lineno, line in enumerate(text.splitlines(), 1):
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
        _warn_ragged("Approach.md(4b)", lineno, header, cells)
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
        _stamp_row_opened(st, row["asset"], row["vuln class"])
        added += 1
    if added:
        write_board_4b(eng, rows)
        (Path(eng) / STATE_NAME).write_text(json.dumps(st, indent=2))
    return added


# --------------------------------------------------------------------------- next (cursor + gate walk)
#
# The agent loop: run `next`, do exactly what it prints, record, repeat. `next`
# NEVER prints a question (G7) - if nothing is actionable it prints a terminal
# state, not a menu.

# Exploit-shaped classes route load-bearing HTTP requests: G8 also emits a Burp
# Repeater push so the operator watches the exploit live (CLAUDE.md Burp-first).
EXPLOIT_CLASSES = {
    "rce", "sqli", "ssrf", "ssti", "xxe", "idor", "bola", "injection", "xss",
    "deserialization", "auth", "upload", "file-upload", "lfi",
    "api", "cache",
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

# CAI-style autonomy envelope (scope.md frontmatter `autonomy:`). ADVISORY only:
# the driver carries the level in the `next` banner and advises on exploit-class
# rows at L0/L1; it never hard-denies (the RoE flags stay enforced by the
# scope-guard hook). Missing field = L2 (back-compat: old engagements keep working).
AUTONOMY_LEVELS = ("L0", "L1", "L2", "L3")
AUTONOMY_DEFAULT = "L2"
_AUTONOMY_MAP = {"l0": "L0", "l1": "L1", "l2": "L2", "l3": "L3", "full": "L3"}
AUTONOMY_DESC = {
    "L0": "passive-only (no active packets beyond fetches, no payload delivery)",
    "L1": "active non-destructive (scans/probing/fuzz within rate limits)",
    "L2": "exploit attempts allowed",
    "L3": "full (chained ops, anything short of forbidden RoE classes)",
}


def autonomy_of(eng):
    """scope.md frontmatter `autonomy:` -> (level, note). Level is always one of
    AUTONOMY_LEVELS: a clean value maps through _AUTONOMY_MAP (case-insensitive;
    legacy `full` -> L3), a missing or unknown value assumes AUTONOMY_DEFAULT and
    note carries the one-line reason ("" when clean; the doctor surfaces it)."""
    p = Path(eng) / "scope.md"
    raw = ""
    if p.is_file():
        m = re.search(r"(?m)^\s*autonomy:\s*(.+?)\s*$",
                      p.read_text(encoding="utf-8", errors="ignore"))
        if m:
            raw = m.group(1).strip()
    lvl = _AUTONOMY_MAP.get(raw.lower(), "")
    if lvl:
        return lvl, ""
    if raw:
        return AUTONOMY_DEFAULT, "scope.md autonomy=%s unknown, assumed %s" % (raw, AUTONOMY_DEFAULT)
    return AUTONOMY_DEFAULT, "scope.md has no autonomy: field, assumed %s" % AUTONOMY_DEFAULT


def cmd_autonomy(args):
    """Mid-session envelope change (set_permission_mode pattern): rewrite
    scope.md's autonomy: line, append an autonomy_change event to
    .events.jsonl for the audit trail. Still advisory-only - the RoE flags
    stay enforced by the scope-guard hook."""
    eng, state = _eng_state(args, "autonomy")
    if eng is None:
        return 2
    lvl = _AUTONOMY_MAP.get(args.level.lower(), "")
    if not lvl:
        _die("level must be one of %s (got %r)" % ("/".join(AUTONOMY_LEVELS), args.level))
    p = eng / "scope.md"
    if not p.is_file():
        _die("scope.md missing - the autonomy envelope lives in its frontmatter")
    prev, _note = autonomy_of(eng)
    text = p.read_text(encoding="utf-8")
    new_line = "autonomy: %s" % lvl
    if re.search(r"(?m)^\s*autonomy:\s*.*$", text):
        text = re.sub(r"(?m)^(\s*)autonomy:\s*.*$", new_line, text, count=1)
    else:
        close = text.find("---", 3)      # frontmatter close, not the opener at 0
        if close == -1:
            _die("scope.md has no frontmatter to hold an autonomy: field")
        text = text[:close] + new_line + "\n" + text[close:]
    p.write_text(text, encoding="utf-8")
    ev = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
          "event": "autonomy_change", "from": prev, "to": lvl,
          "reason": args.reason or ""}
    with open(eng / ".events.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev) + "\n")
    print("AUTONOMY %s -> %s: %s" % (prev, lvl, AUTONOMY_DESC[lvl]))
    if args.reason:
        print("  reason: %s" % args.reason)
    print("advisory layer only (RoE flags stay hook-enforced); scope.md + .events.jsonl updated")
    return 0


def _events(eng):
    """Parsed .events.jsonl rows, or None if the telemetry file is absent (G2
    then fails open - the skill is emitted)."""
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


def _opened_key(asset, cls):
    return "%s|%s" % ((asset or "").strip().lower(), (cls or "").strip().lower())


def _stamp_row_opened(state, asset, cls):
    """Record now() as this (asset, class) row's open-time, so G2 can anchor
    'skill fired since' to when THIS row appeared rather than engagement start.
    Rows born together in one board/vector-workflow batch share a birth moment,
    so one post-batch Skill() invocation still satisfies all of them; a row
    seeded later (new asset, new fingerprint) gets its own later timestamp and
    needs a fresh invocation -- closing the loophole where a single Skill(x)
    call at minute 1 silently covered a same-class row discovered hours later
    on an unrelated asset."""
    state.setdefault("row_opened_at", {})[_opened_key(asset, cls)] = \
        datetime.now(timezone.utc).isoformat()


def _row_since(state, asset, cls):
    """G2's 'since' anchor for this row: its own opened_at if stamped, else
    engagement start (fail-safe for rows that predate this tracking)."""
    return (state.get("row_opened_at") or {}).get(_opened_key(asset, cls)) \
        or state.get("started_at")


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


def _next_json_payload(eng, state, vault):
    """cmd_next's cursor+gate walk as one dict (`next --json`). Consumers:
    brain-lane dispatchers + programmatic steering. Gates in walk order:
    gates_remaining holds 'arsenal' then 'skill' until released; terminal is
    null while a move is servable, else stale-index|wall-break|walled|exhausted."""
    out = {"eng": eng.name, "pass": state.get("pass", 0), "asset": None,
           "row": None, "class": None, "skill": None, "tool": None,
           "invocation": None, "board": {}, "gates_remaining": [],
           "autonomy": autonomy_of(eng)[0], "warnings": [], "terminal": None}
    if index_stale(eng, vault):
        out["terminal"] = "stale-index"
        out["warnings"].append("run: offensive.py --eng %s index" % eng.name)
        return out
    index = load_index(eng)
    threshold = WALLBREAK_THRESHOLD.get(state.get("type"), 3)
    if state.get("dry_streak", 0) >= threshold:
        state["dry_streak"] = 0
        (eng / STATE_NAME).write_text(json.dumps(state, indent=2))
        out["terminal"] = "wall-break"
        out["skill"] = "redteamlead"
        out["warnings"].append("dry_streak hit %d - wrong vector, ask redteamlead "
                               "for a re-plan" % threshold)
        return out
    rows = read_board(eng)
    if state.get("foothold"):
        rows = rows + read_board_4b(eng)
    dead = _deadend_pairs(eng)
    if dead:
        _low = lambda r: ((r.get("asset") or "").strip().lower(),
                          (r.get("vuln class") or "").strip().lower())
        zombie = [r for r in rows if _status_of(r) in ("[ ]", "[~]") and _low(r) in dead]
        if zombie:
            out["warnings"].append("G4: %d hand-revived row(s) match a Deadends.md "
                                   "pair - suppressed" % len(zombie))
        rows = [r for r in rows if _low(r) not in dead]
    out["warnings"].extend("board: %s" % w for w in _drain_board_warnings())
    out["board"] = {
        "open_assets": len(_open_assets(rows)),
        "open": sum(1 for r in rows if _status_of(r) in ("[ ]", "[~]")),
        "closed": sum(1 for r in rows if _status_of(r) == "[x]"),
        "stuck": sum(1 for r in rows if _status_of(r) in ("[?]", "[!]")),
    }
    asset = _cursor_asset(rows, state)
    row = _active_row(rows, asset) if asset else None
    if not asset or not row:
        out["terminal"] = "walled" if (out["board"]["closed"] == 0
                                       and out["board"]["stuck"]) else "exhausted"
        if out["terminal"] == "walled":
            out["skill"] = "redteamlead"
        return out
    rid = (row.get("id") or "").strip()
    cls = (row.get("vuln class") or "").strip()
    skill = (row.get("skill") or "").strip()
    tool = (row.get("tool") or "").strip()
    out.update({"asset": asset, "row": rid, "class": cls,
                "skill": skill or None, "tool": tool or None})
    out["pass"] = state.get("pass", 0) + 1
    state["pass"] = out["pass"]
    state["asset_cursor"] = asset
    sc = state.setdefault("serve_count", {})
    sc[rid] = sc.get(rid, 0) + 1
    state["last_move"] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "asset": asset, "row": rid, "class": cls, "skill": skill, "tool": tool,
    }
    (eng / STATE_NAME).write_text(json.dumps(state, indent=2))
    if sc[rid] >= 3:
        out["warnings"].append("RE-SERVE %dx: row %s served %d times with no "
                               "disposition - redteamlead / done --dead / change "
                               "one variable" % (sc[rid], rid, sc[rid]))
    if out["autonomy"] in ("L0", "L1") and cls.lower() in EXPLOIT_CLASSES:
        out["warnings"].append("AUTONOMY %s advisory: exploit-class row under a "
                               "restricted scope" % out["autonomy"])
    if not (row.get("arsenal") or "").strip():
        out["gates_remaining"].append("arsenal")
        return out
    if skill and not _skill_fired(eng, skill, _row_since(state, asset, cls)):
        if _events(eng) is None:
            out["warnings"].append("G2 advisory: .events.jsonl absent, skill-fired "
                                   "unverifiable")
        else:
            out["gates_remaining"].append("skill")
            return out
    out["invocation"] = ((index.get("tools") or {}).get(tool, {})
                         .get("invocation") or (tool + " <target>"))
    return out


def cmd_next(args):
    vault = Path(args.vault) if args.vault else DEFAULT_VAULT
    eng = _resolve_eng(args.eng)
    if eng is None or not eng.is_dir():
        print("error: --eng <name|path> required for `next`")
        return 2
    state = _load_state(eng)
    if state is None:
        return 2
    if getattr(args, "json", False):
        # machine-readable cursor+gate payload (brain lanes / steering). Same
        # walk + state writes as the human path below - keep the two in sync;
        # tests/test_next.py pins the field contract. stale-index exits 2 to
        # match the text path's _die (a wrapper branching on the exit code
        # must not silently proceed on a broken index).
        payload = _next_json_payload(eng, state, vault)
        print(json.dumps(payload, ensure_ascii=False))
        return 2 if payload.get("terminal") == "stale-index" else 0

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
    # G4 on the SERVE path too: a hand-edited status cell ([!] -> [ ]) resurrects a
    # dead (asset, class) pair the derivation path would suppress. Drop any open
    # row whose pair sits in Deadends.md, naming it, so the edit is visible instead
    # of silently re-serving a vector that was already exhausted.
    dead = _deadend_pairs(eng)
    if dead:
        _low = lambda r: ((r.get("asset") or "").strip().lower(),
                          (r.get("vuln class") or "").strip().lower())
        zombie = [r for r in rows if _status_of(r) in ("[ ]", "[~]") and _low(r) in dead]
        if zombie:
            print("G4: %d open row(s) match a Deadends.md pair (status cell hand-edited "
                  "back?) - suppressed: %s" % (len(zombie),
                  ", ".join((r.get("id") or "?") for r in zombie)))
        rows = [r for r in rows if _low(r) not in dead]
    for w in _drain_board_warnings():
        print("BOARD (parsed best-effort): %s" % w)
    asset = _cursor_asset(rows, state)
    row = _active_row(rows, asset) if asset else None
    if not asset or not row:
        # G7: terminal state, never a question. Differentiate a SOLVED board
        # (closeout is right) from a WALLED one (all parked/dead, zero finds) --
        # the closeout chain on an unsolved board is the wrong instruction.
        closed = sum(1 for r in rows if _status_of(r) == "[x]")
        stuck = sum(1 for r in rows if _status_of(r) in ("[?]", "[!]"))
        if closed == 0 and stuck:
            print("board exhausted with NO closed rows: %d parked/dead, 0 finds. Run "
                  "Skill(redteamlead) for a ranked re-plan or `coverage` for untested "
                  "classes; closeout is for a SOLVED board." % stuck)
        else:
            print("board exhausted: no open rows. run the closeout chain.")
        return 0

    rid = (row.get("id") or "").strip()
    cls = (row.get("vuln class") or "").strip()
    skill = (row.get("skill") or "").strip()
    state["asset_cursor"] = asset
    # Serve accounting (driver audit, 2026-09-10). `pass` = serves this engagement:
    # drift-guard arms its off-board enforcement at pass >= 5, and the banner had
    # read 0 forever because nothing incremented it. serve_count per row catches the
    # sticky-[~] loop drift-guard's ring cannot see -- a `next` between identical
    # tool fires launders the ring, but the driver knows the same row was re-served.
    state["pass"] = state.get("pass", 0) + 1
    sc = state.setdefault("serve_count", {})
    sc[rid] = sc.get(rid, 0) + 1
    # Compact-boundary discipline (pass 4): the printed plan used to live only in
    # context. Persist the served move so pre-compact steering has a durable source
    # and engagement-init's source=="compact" restore re-injects it verbatim.
    state["last_move"] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "asset": asset, "row": rid, "class": cls, "skill": skill,
        "tool": (row.get("tool") or "").strip(),
    }
    (eng / STATE_NAME).write_text(json.dumps(state, indent=2))
    lvl, _lvl_note = autonomy_of(eng)
    print("PASS %s | ASSET %s | ROW %s %s | AUTONOMY %s"
          % (state.get("pass", 0), asset, rid, cls, lvl))
    if sc[rid] >= 3:
        print("RE-SERVE %dx: row %s has now been served %d times with no disposition - "
              "the tool is not landing. Run Skill(redteamlead) for a ranked re-plan, "
              "close the row (`done %s --dead '<why>'` or `--park`), or change one "
              "variable in the invocation." % (sc[rid], rid, sc[rid], rid))

    # Autonomy envelope (advisory, never a gate): an exploit-class row served
    # under an L0/L1 scope -> say so in one line; the operator/agent decides.
    if lvl in ("L0", "L1") and cls.lower() in EXPLOIT_CLASSES:
        print("AUTONOMY %s advisory: %s is an exploit-class row but scope.md sets "
              "%s (%s) - advisory only, not a gate; park the row or raise the "
              "envelope" % (lvl, cls, lvl, AUTONOMY_DESC[lvl]))

    # Default posture (2026-09-08): 2+ open assets -> run the loop under Skill(brain)
    # (main = strategy/board/triage, execution in 2-3 concurrent disjoint lanes).
    # Below 2 open assets the serial single-agent loop stays correct.
    if len(_open_assets(rows)) >= 2:
        print("PARALLEL  %d open assets - default posture is Skill(brain): keep the "
              "driver/board/triage in the main session, dispatch 2-3 concurrent "
              "disjoint-lane subagents for execution (lane contract: delegate slots a-h)"
              % len(_open_assets(rows)))

    # Post-foothold: route load-bearing tool commands through the recorded shell
    # so the operator keeps visibility (CLAUDE.md Burp-first / post-foothold).
    if state.get("foothold"):
        win = (state.get("footholds") or {}).get(asset)
        # bb has no 4b board (derive_privesc_rows returns [] for it) -> the "see the
        # ### 4b rows" pointer would dangle at nothing, so drop it for bb only.
        board_hint = "" if state.get("type") == "bb" else "  (see the ### 4b rows)"
        if win:
            print("POST-EX   route tool cmds for %s through: bash scripts/vm-rsh.sh "
                  "--win %s '<cmd>'%s" % (asset, win, board_hint))
        else:
            print("POST-EX   foothold established; route post-ex cmds through the "
                  "recorded vm-rsh shell%s" % board_hint)
        # G-cost-control: the row's tool is mechanical/wait-heavy (pspy/linpeas/winpeas,
        # a compile-and-run exploit) -> surface Skill(delegate) here, the one place the
        # driver otherwise never mentions it. Judgment-heavy rows (e.g. bloodhound) get no nudge.
        if (row.get("tool") or "").strip().lower() in MECHANICAL_4B_TOOLS:
            print("  (mechanical/wait-heavy? consider Skill(delegate) to run this on the cheap tier)")

    # method block for the row's class (parse_hunt_method result, keyed by skill).
    # Fields may be empty on real skills; print what's present.
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

    # G2 skill-first: mapped hunt skill unfired SINCE THIS ROW OPENED -> run it,
    # withhold the tool. Anchored to the row's own open time (not engagement
    # start), so a skill fired once at minute 1 doesn't silently cover an
    # unrelated row discovered hours later -- see _row_since/_stamp_row_opened.
    # Fail-open when telemetry is absent (mirrors cmd_done ~:1079), else the
    # tool step is never reached and `next` livelocks on Skill(<skill>) forever.
    if skill and not _skill_fired(eng, skill, _row_since(state, asset, cls)):
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
    tl = tool.lower()
    if tl in SCAN_CLASS:
        print("  %d. run: bash scripts/vm-scan.sh --win %s %s %s '%s'        [G8: "
              "tool-first, tmux-default; output stays in the named tab, autocard "
              "cards it]" % (n, tl, eng.name, asset, inv))
        print("     (cmd: %s)" % inv)
    elif tl in OUTPUT_CLASS or tl in MECHANICAL_4B_TOOLS:
        print("  %d. run: bash scripts/vm-bg.sh %s %s-%s '%s'        [G8: tool-first, "
              "tmux-default; long run stays alive over the bridge]"
              % (n, eng.name, tl, asset, inv))
        print("     read: bash scripts/vm-bg.sh --read %s %s-%s" % (eng.name, tl, asset))
        print("     (cmd: %s)" % inv)
    else:
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
# fired) + G3 (exactly one typed disposition). Gate refusals are hard (_die,
# non-zero); status transitions mutate the board in place. `next` recomputes
# the cursor each run, so parking/killing
# a row advances the loop with no state write here (G7 no-ask).


def _load_state(eng):
    """Shared .offensive.json load with clean failure. A truncated write (crash
    mid-write on /mnt/c) used to surface as a raw JSONDecodeError traceback; a
    wrong-typed file as AttributeError - both now name the fix, including the
    shadow-git recovery path (_ckpt keeps one commit per driver mutation)."""
    try:
        state = json.loads((eng / STATE_NAME).read_text())
    except FileNotFoundError:
        print("error: %s missing - run `init` first" % STATE_NAME)
        return None
    except ValueError as e:
        print("error: %s corrupt (%s) - restore the last checkpoint: "
              "git -C %s log --oneline (pick the pre-corruption commit), then "
              "git -C %s checkout <commit> -- %s" % (STATE_NAME, e, eng, eng, STATE_NAME))
        return None
    if not isinstance(state, dict):
        print("error: %s is a %s, expected a JSON object (the driver state map) - "
              "restore as above" % (STATE_NAME, type(state).__name__))
        return None
    return state


def _eng_state(args, cmd):
    """(eng, state) or (None, None) after printing an error. Shared preamble."""
    eng = _resolve_eng(args.eng)
    if eng is None or not eng.is_dir():
        print("error: --eng <name|path> required for `%s`" % cmd)
        return None, None
    state = _load_state(eng)
    if state is None:
        return None, None
    return eng, state


def _ckpt(eng, msg):
    """Shadow-git checkpoint of the engagement dir: one commit per driver
    mutation (note/done/park) so a post-compaction / post-mistake restore point
    always exists (the board, state, deadends at EVERY step - clone mining pass
    8: compaction + a bad re-entry otherwise lose the pre-drift board). The
    nested repo sits under gitignored targets/, so the vault repo never sees it
    (client-data boundary holds: engagement data stays inside targets/<eng>/).
    Fail-open silent; no-op when nothing changed."""
    import subprocess
    if "tests" in eng.parts:   # fixtures: never shadow-init repos inside the tracked tree
        return
    try:
        def git(*a):
            return subprocess.run(["git", "-C", str(eng), *a],
                                  capture_output=True, text=True, timeout=15)
        if not (eng / ".git").exists():
            if git("init", "-q").returncode != 0:
                return
        git("add", "-A")
        if git("diff", "--cached", "--quiet").returncode == 0:
            return   # nothing changed since the last checkpoint
        git("-c", "user.name=ztorch", "-c", "user.email=ztorch@local",
            "commit", "-q", "-m", msg)
    except Exception:
        pass


def cmd_note(args):
    """G1 release: set the row's arsenal cell (the consulted wiki-arsenal card
    slug) and write the board. Flips a fresh [ ] row to [~] (in-progress).
    No card-file validation - the board carries the slug; the operator ran
    Skill(wiki-arsenal) to get it."""
    eng, state = _eng_state(args, "note")
    if eng is None:
        return 2
    rows, row, writer = _find_row_any(eng, args.row)
    if not row:
        _die("no such row: %s" % args.row)
    # RE-SERVE enforcement (driver audit, 2026-09-10): the RE-SERVE banner says
    # "change one variable"; this makes that checkable at the one boundary the
    # driver owns. After 3+ serves, re-arming the SAME arsenal slug is the
    # byte-identical retry the clone never issues (withRetry mutates context
    # before every retry). Refuse it: different slug, or dispose of the row.
    prev = (row.get("arsenal") or "").strip()
    rid = (row.get("id") or args.row).strip()
    sc = (state.get("serve_count") or {}).get(rid, 0)
    if prev and args.arsenal.strip() == prev and sc >= 3:
        _die("RE-SERVE %dx on %s: re-arming the same arsenal '%s' unchanged. Change "
             "one variable (a different --arsenal slug) or dispose of the row "
             "(`done %s --dead '<why>'` or `--park '<why>'`)" % (sc, rid, prev, rid))
    row["arsenal"] = args.arsenal
    if _status_of(row) == "[ ]":
        row["status"] = "[~]"
        # Re-stamp the row's open time: a hand-revived ([!] -> [ ]) row keeps its
        # original stamp, so a weeks-old Skill(x) fire would satisfy G2 for the
        # reopened vector. The [ ] -> [~] flip is when work on this row really
        # starts (driver audit, 2026-09-10).
        _stamp_row_opened(state, row.get("asset"), row.get("vuln class"))
        (eng / STATE_NAME).write_text(json.dumps(state, indent=2))
    writer(eng, rows)
    print("note: %s arsenal=%s (G1 released; row [~])" % (args.row, args.arsenal))
    _ckpt(eng, "note %s" % args.row)
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
    # A park is a no-find outcome: feed the WALL-BREAK streak exactly like --dead
    # does, else a park-everything loop empties the board without ever triggering
    # the redteamlead redirection (driver audit, 2026-09-10).
    state["dry_streak"] = state.get("dry_streak", 0) + 1
    (eng / STATE_NAME).write_text(json.dumps(state, indent=2))
    print("done: %s parked (status set for later revisit) -> decisions.md; "
          "loop advances with no operator prompt (dry_streak=%d)"
          % ((row.get("id") or "").strip(), state["dry_streak"]))
    _ckpt(eng, "park %s" % (row.get("id") or "").strip())
    return 0


def _set_state_access(eng, asset, win, access="foothold"):
    """Flip the state.md inventory row whose first cell == `asset` to
    access=`access` and append a `tmux:<win>` note. Line-based rewrite of one
    cell. Returns True if a row matched; fail-soft on IO/absent columns."""
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
        _ckpt(eng, "dead %s" % args.row)
        return 0

    # --poc: the evidence path, behind all three gates.
    # G1 arsenal-first: no consulted arsenal card -> refuse (note --arsenal first).
    if not (row.get("arsenal") or "").strip():
        _die("cannot close %s: arsenal cell empty - run "
             "`note %s --arsenal <slug>` first [G1 arsenal-first]"
             % (args.row, args.row))
    # G3 typed evidence: --poc needs a kind; `web` only for visual classes; the
    # file itself must exist (a nonexistent path is not evidence).
    if not args.kind:
        _die("--poc requires --kind req|burp|web|cli [G3]")
    if args.kind == "web" and cls not in VISUAL_CLASSES:
        _die("a 'web' render is not evidence for class '%s' - it is "
             "indistinguishable from any visitor's screenshot. Use --kind cli "
             "(capture.sh cli) for a command-execution class, or --kind req "
             "(capture.sh req) for a request/response one [G3]" % cls)
    if not (Path(eng) / args.poc).is_file():
        _die("--poc %s does not exist under %s [G3: a row never closes on a "
             "path that isn't a real captured evidence file]" % (args.poc, eng))
    # G2 skill-first: the mapped hunt skill must have fired since THIS ROW
    # opened (not engagement start -- see _row_since/_stamp_row_opened). A
    # `--skill <name>` override lets a CORRECTLY-fired skill satisfy G2 when the
    # board mapped the wrong class->skill; the override must itself have fired.
    since = _row_since(state, row.get("asset"), cls)
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
    _ckpt(eng, "done %s poc" % args.row)
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
    # re-init guard: a dir that already holds DRIVER state (.offensive.json) is a live
    # engagement -- re-init on it historically re-scaffolded and lost live rows/blocks
    # (observed live: a re-init cost the first state row + log block + 4b seed). A dir with
    # only scaffolded .md files (setup/new-engagement.sh output) is the intended add-driver-
    # state flow and stays allowed. --rebase is the explicit escape (rotated IP / repair):
    # proceed without touching the existing state file, but DO repoint targets/active.md.
    live_state = (eng / STATE_NAME).is_file()
    if eng.exists() and live_state and not getattr(args, "rebase", False):
        print("init: targets/%s already holds driver state (%s). Re-init on a live engagement "
              "re-scaffolds over it -- refusing. To rebase (rotated IP / repair / repoint "
              "active.md), pass --rebase." % (args.name, STATE_NAME), file=sys.stderr)
        return 1
    eng.mkdir(parents=True, exist_ok=True)

    for name in TEMPLATE_FILES:
        dst = eng / name
        if not dst.exists():
            shutil.copyfile(TEMPLATE_DIR / name, dst)

    state_path = eng / STATE_NAME
    if state_path.exists():
        # only reachable via --rebase (the guard above refused the plain re-init): keep the
        # live state file, still repoint active.md so telemetry lands on THIS engagement.
        active = vault / "targets" / "active.md"
        prev = active.read_text().strip() if active.exists() else ""
        if prev != args.name:
            active.write_text(args.name + "\n")
            print("init: targets/active.md -> %s (was: %s)" % (args.name, prev or "<none>"))
        print("init: %s rebased (%s untouched)" % (args.name, STATE_NAME))
        return 0

    state = {
        "type": args.type,
        "pass": 0,
        "asset_cursor": None,
        "dry_streak": 0,
        "foothold": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    state_path.write_text(json.dumps(state, indent=2))
    # repoint targets/active.md so hook telemetry (.events.jsonl) lands in THIS engagement;
    # a stale pointer silently breaks G2 (skill fires recorded under the old engagement)
    active = vault / "targets" / "active.md"
    prev = active.read_text().strip() if active.exists() else ""
    if prev != args.name:
        active.write_text(args.name + "\n")
        print("init: targets/active.md -> %s (was: %s)" % (args.name, prev or "<none>"))
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
    p_init.add_argument("--rebase", action="store_true",
                        help="allow init over a dir holding live engagement files")
    p_init.set_defaults(fn=cmd_init)

    sub.add_parser("board", help="write the Approach.md 4a coverage matrix from the index").set_defaults(fn=cmd_board)
    p_next = sub.add_parser("next", help="print the next action (cursor + gate walk)")
    p_next.add_argument("--json", action="store_true",
                        help="machine-readable cursor+gate payload (brain lanes / steering)")
    p_next.set_defaults(fn=cmd_next)
    sub.add_parser("coverage", help="per-asset untested vuln-class gaps (no [x] row)").set_defaults(fn=cmd_coverage)
    sub.add_parser("closeout", help="print the per-type close-out Skill chain").set_defaults(fn=cmd_closeout)

    p_note = sub.add_parser("note", help="set a row's arsenal cell (G1 release)")
    p_note.add_argument("row", help="board row id, e.g. 4a:3")
    p_note.add_argument("--arsenal", required=True, help="consulted wiki-arsenal card slug")
    p_note.set_defaults(fn=cmd_note)

    p_done = sub.add_parser("done", help="close a row (G1/G2/G3 gates) or --dead / --park")
    p_done.add_argument("row", help="board row id, e.g. 4a:3")
    p_done.add_argument("--poc", help="evidence image path (closes [x])")
    p_done.add_argument("--kind", choices=("req", "burp", "web", "cli"), help="evidence kind for --poc")
    p_done.add_argument("--dead", nargs="?", const="exhausted",
                        help="mark the row [!] exhausted (optional reason)")
    p_done.add_argument("--park", help="defer the row [?] with a decision note (G7 no-ask)")
    p_done.add_argument("--skill", help="G2 override: the skill that actually fired")
    p_done.add_argument("--win", help="tmux window: also record a foothold on this "
                        "row's asset + seed the 4b post-ex board")
    p_done.set_defaults(fn=cmd_done)

    p_auto = sub.add_parser("autonomy", help="change the advisory autonomy envelope (scope.md + audit event)")
    p_auto.add_argument("level", help="L0|L1|L2|L3")
    p_auto.add_argument("--reason", help="one-line why (recorded in the audit event)")
    p_auto.set_defaults(fn=cmd_autonomy)
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
