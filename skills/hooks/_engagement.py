"""Shared helpers for engagement-state hooks.

Resolves the active engagement and parses its state/loot/killchain markdown tables.
Everything here is best-effort and never raises to the caller: callers wrap use
in try/except, but these helpers also degrade to empty/None on any problem.
"""
import ipaddress
import json
import os
import re
import time
from datetime import date, datetime, timezone

# Self-locate: realpath resolves the ~/.claude/vault-hooks symlink to the real
# skills/hooks dir inside whichever machine's vault. skills/hooks -> skills -> root.
# Machine-independent: works regardless of user/path/spelling on each device.
HERE = os.path.dirname(os.path.realpath(__file__))
# ZTORCH_VAULT / OBSIDIAN_VAULT override the self-located vault root (used by
# tests to point at a fixture vault). CLAUDEBRAIN_VAULT kept as a legacy alias.
# Unset in normal use -> self-locate via the symlinked path.
_BW = None

VAULT = (os.environ.get("ZTORCH_VAULT") or os.environ.get("OBSIDIAN_VAULT")
         or os.environ.get("CLAUDEBRAIN_VAULT")
         or os.path.dirname(os.path.dirname(HERE)))
TARGETS = os.path.join(VAULT, "targets")
# Templates live OUTSIDE targets/ (which is git-ignored) so they ship with the
# shareable repo. Engagement instances stay private under targets/.
TEMPLATES = os.path.join(VAULT, "setup", "templates")
# Per-type core files: state/loot/Approach come from the type's own template dir for
# every type; Killchain.md (the evolving discovered attack chain) is a pentest/
# bugbounty-only core artifact; a ctf's live chain lives in state.md's own `## Chain`/
# `## Status` sections instead (folded in, never a separate file).
ALL_STATE_FILES = ("state.md", "loot.md", "Killchain.md", "Approach.md")
_STATE_FILES_CTF = ("state.md", "loot.md", "Approach.md")


def state_files(etype):
    """Type-aware core file tuple: ctf omits Killchain.md; pentest/bugbounty keep it.
    engagement_type() itself detects the type from ALL_STATE_FILES (the flat union)
    BEFORE the type is known; a file absent for a given type is simply skipped."""
    return _STATE_FILES_CTF if etype == "ctf" else ALL_STATE_FILES


TYPES = ("pentest", "bugbounty", "ctf")
# entity identifier columns by engagement type. Defined once here; next_move and
# coverage both import it so the mapping cannot drift between the two analyzers.
ENTITY_KEY = {"pentest": ("host", "ip"), "ctf": ("target",), "bugbounty": ("asset", "url")}

# Per-engagement-type heal set. state/loot/Approach (+ Killchain for pentest/bugbounty)
# come from the type's own template dir via state_files() and are healed for every type.
# The shared type-agnostic files split three ways: a lean ctf core (scope + Deadends only;
# log.md/walkthrough.md/eval.md self-create at their own trigger instead of being
# scaffolded upfront: see close-out.py's eval-metrics write, build-walkthrough.py, and
# Skill(learn)), the full pentest/bugbounty core (adds log/walkthrough/eval), and a
# pentest/bugbounty-only extension (Vuln-index/oob). CTF rooms never use the severity/OOB
# machinery (dead across every THM room); oob/vuln-index become opt-in via
# ensure_optional_file() (see below) or new-engagement.sh --with-oob. Per-asset test
# coverage lives in the Approach.md 4a table (Approach.md is in state_files()).
SHARED_CORE_CTF = (("scope.md", "_scope.md"), ("Deadends.md", "_deadends.md"))
SHARED_CORE = (("log.md", "_log.md"), ("scope.md", "_scope.md"),
               ("walkthrough.md", "_walkthrough.md"),
               ("Deadends.md", "_deadends.md"),
               ("eval.md", "_eval.md"))
SHARED_FULL = (("Vuln-index.md", "_vuln-index.md"),
               ("oob.md", "_oob.md"))
# Standard dirs scaffolded for every type. poc/ = curated exploit/PoC/flag shots,
# ingest/ = raw tool output. Vulns/ is intentionally absent: it is created lazily on
# the first FIND (pentest/bugbounty), never at init.
STATE_DIRS = ("ingest", "poc")


def _heal_shared_set(etype):
    """Shared (dest, templatefile) pairs to heal for an engagement type. ctf gets the
    lean core (scope + Deadends) only; pentest/bugbounty get the full core (adds log/
    walkthrough/eval) + the Vuln-index/oob machinery."""
    return SHARED_CORE_CTF if etype == "ctf" else SHARED_CORE + SHARED_FULL


# Opt-in shared files a ctf engagement omits at init. Created on demand: the
# new-engagement.sh --with-oob flag, ensure_optional_file() when a blind bug (oob)
# actually runs, or a manual findings roll-up (vuln-index). vuln-index is type-aware:
# ctf uses a slim findings list.
OPTIONAL_FILES = {"oob": ("oob.md", "_oob.md"),
                  "vuln-index": ("Vuln-index.md", "_vuln-index.md"),
                  "decisions": ("decisions.md", "_decisions.md"),
                  "changelog": ("changelog.md", "_changelog.md")}


def ensure_optional_file(kind, d=None):
    """Back-fill one opt-in shared file (oob/vuln-index/decisions) on demand for the
    active (or given) engagement. Returns the created filename, or '' if it already
    exists / kind is unknown / no engagement / the template is missing. For
    kind='vuln-index' a ctf engagement gets the slim setup/templates/ctf/vuln-index.md;
    every other case uses the shared template. Never overwrites (idempotent)."""
    d = d or active_dir()
    if not d or kind not in OPTIONAL_FILES:
        return ""
    fn, tplname = OPTIONAL_FILES[kind]
    dest = os.path.join(d, fn)
    if os.path.exists(dest):
        return ""
    tpl = ""
    if kind == "vuln-index":
        cand = os.path.join(TEMPLATES, engagement_type(d), "vuln-index.md")
        if os.path.isfile(cand):
            tpl = cand
    if not tpl:
        tpl = os.path.join(TEMPLATES, tplname)
    if not os.path.isfile(tpl):
        return ""
    name = os.path.basename(d)
    today = date.today().isoformat()
    text = open(tpl, encoding="utf-8", errors="ignore").read()
    text = text.replace("{{ENGAGEMENT}}", name).replace("{{DATE}}", today)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(text)
    return fn


def entity(row, etype):
    """Identifier for a state/coverage row by engagement type (host/ip | target |
    asset/url), or '?' if none present."""
    for k in ENTITY_KEY.get(etype, ("host",)):
        if row.get(k):
            return row[k]
    return "?"


def _read_pointer():
    """Engagement name from targets/active.md (syncs via Obsidian, unlike a
    dotfile). First non-empty line that is not a markdown header/comment."""
    p = os.path.join(TARGETS, "active.md")
    if not os.path.isfile(p):
        return ""
    for line in open(p, encoding="utf-8", errors="ignore"):
        s = line.strip()
        if s and not s.startswith(("#", "<!--", "-", "*")):
            return s
    return ""


def active_dir():
    """Return path to the active engagement dir, or None.

    Priority: targets/active.md pointer, else most-recently-modified engagement
    dir (excluding _templates and dotfiles). Returns None if targets/ empty.
    """
    name = _read_pointer()
    if name:
        cand = os.path.join(TARGETS, name)
        if os.path.isdir(cand):
            return cand
    dirs = []
    for n in os.listdir(TARGETS):
        if n.startswith(".") or n == "_templates":
            continue
        p = os.path.join(TARGETS, n)
        if os.path.isdir(p):
            dirs.append(p)
    if not dirs:
        return None
    return max(dirs, key=os.path.getmtime)


def touch_direction(d=None):
    """Mark a 'direction event' (a board row -> [x], new loot/host/flag, or an RTL call). The file's
    mtime IS the payload; drift-guard reads it for the auto-RTL clock. Fail-open (never raises)."""
    try:
        d = d or active_dir()
        if not d:
            return
        p = os.path.join(d, ".last-direction")
        open(p, "a").close()
        os.utime(p, None)
    except Exception:
        pass


def seconds_since_direction(d=None):
    """Seconds since the last direction event; None if never marked (treated as 'just started')."""
    try:
        d = d or active_dir()
        if not d:
            return None
        return time.time() - os.path.getmtime(os.path.join(d, ".last-direction"))
    except Exception:
        return None


def _parse_table(path):
    """Parse the first markdown table in a file into list-of-dicts keyed by
    lowercased header cell. Returns [] on any problem."""
    if not os.path.isfile(path):
        return []
    rows = []
    header = None
    for line in open(path, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line.startswith("|"):
            if header is not None:
                break  # table ended
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue  # separator row
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if not any(cells):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def append_state_asset(d, target, service="?", port="?", access="port-open", notes=""):
    """Append one inventory row to <d>/state.md's FIRST markdown table, filling cells by the
    header's column order (target/host/asset<-target; service; port; access; notes). Dedups: a
    bare seed (port "?") is skipped if the target already has ANY row; a real port is skipped if
    target+port already exists. Returns True if a row was added. Fail-soft (returns False) on any
    IO/parse problem, so a caller (board auto-seed, the recon hook) never crashes on it.

    This is the plumbing that lets `offensive.py board` auto-populate from recon instead of
    requiring a hand-edited state.md - the friction that made the board easy to bypass."""
    p = os.path.join(d, "state.md")
    tgt = (target or "").strip()
    if not tgt or tgt in ("?", "-"):
        return False

    def _rk(r):
        return (r.get("target") or r.get("host") or r.get("asset") or "").strip().lower()

    existing = _parse_table(p)
    if str(port) in ("?", ""):
        if any(_rk(r) == tgt.lower() for r in existing):
            return False
    elif any(_rk(r) == tgt.lower() and (r.get("port") or "").strip() == str(port) for r in existing):
        return False

    try:
        lines = open(p, encoding="utf-8", errors="ignore").read().split("\n")
    except Exception:
        return False
    header = None
    header_i = None
    last_i = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("|"):
            if header is not None:
                break  # first table ended
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            last_i = i  # separator is part of the table region
            continue
        if header is None:
            header = [c.lower() for c in cells]
            header_i = last_i = i
            continue
        last_i = i
    if header is None:
        return False
    valmap = {"target": tgt, "host": tgt, "asset": tgt, "service": str(service),
              "port": str(port), "access": access, "notes": notes}
    row = "| " + " | ".join(valmap.get(c, "") for c in header) + " |"
    lines.insert((last_i + 1) if last_i is not None else (header_i + 1), row)
    try:
        open(p, "w", encoding="utf-8").write("\n".join(lines))
    except Exception:
        return False
    return True


def _frontmatter(text):
    """key->value dict from a leading --- YAML block, or {}. Scalars become strings;
    a key followed by `- item` lines becomes a list (so block-list `affected:` parses)."""
    m = re.match(r"\s*---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    fm = {}
    key = None
    for line in m.group(1).splitlines():
        li = re.match(r"\s+-\s+(.*)$", line)
        if li and key:                                  # block-list item under the current key
            cur = fm.get(key)
            if not isinstance(cur, list):
                fm[key] = [] if (cur is None or cur == "") else [cur]
            fm[key].append(li.group(1).strip().strip('"').strip("'"))
            continue
        km = re.match(r"([A-Za-z][\w-]*):\s*(.*)$", line)
        if km:
            key = km.group(1).lower()
            fm[key] = km.group(2).strip().strip('"').strip("'")
    return fm


# Vuln-class/coverage helpers moved to _engagement_classes.py (Wave 4); re-exported here so
# existing callers using the _engagement.<name> dotted form are unaffected.
from _engagement_classes import (
    CLASS_ALIASES, _match_classes, tested_classes, _class_vocab,
    _vuln_index_confirmed_ids, confirmed_findings,
)


def summary():
    """One-line-per-fact summary dict for the active engagement."""
    d = active_dir()
    if not d:
        return None
    name = os.path.basename(d)
    state = _parse_table(os.path.join(d, "state.md"))
    paths = _parse_table(os.path.join(d, "Killchain.md"))
    loot = _parse_table(os.path.join(d, "loot.md"))
    owned = sum(1 for r in state if r.get("owned", "").lower() == "yes")
    open_paths = [r for r in paths if r.get("status", "").lower() == "open"]
    creds = sum(1 for r in loot if r.get("status", "").lower() in ("active", "unconfirmed"))
    next_moves = [
        f"{r.get('path', '?')}: {r.get('next-move', '?')}"
        for r in open_paths
        if r.get("next-move")
    ][:3]
    return {
        "name": name,
        "hosts": len(state),
        "owned": owned,
        "creds": creds,
        "open_paths": len(open_paths),
        "next_moves": next_moves,
    }


def summary_text():
    """Compact counts-only summary string, or '' if no engagement. Move ranking
    is owned by scripts/next_move.py (the analyzer), not duplicated here."""
    s = summary()
    if not s:
        return ""
    return (
        f"Active engagement: {s['name']} | hosts {s['hosts']} (owned {s['owned']}) "
        f"| creds {s['creds']} | open paths {s['open_paths']}"
    )


def engagement_type(d=None):
    """Read engagement_type from any existing state/loot/killchain frontmatter.
    Falls back to the driver cache (.offensive.json "type"), which offensive.py
    writes even when the scaffold's frontmatter omits the line. Defaults to
    'pentest' when unknown."""
    d = d or active_dir()
    if not d:
        return "pentest"
    for fn in ALL_STATE_FILES:
        p = os.path.join(d, fn)
        if not os.path.isfile(p):
            continue
        for line in open(p, encoding="utf-8", errors="ignore"):
            if line.startswith("engagement_type:"):
                val = line.split(":", 1)[1].strip().lower()
                if val in TYPES:
                    return val
    try:
        cache = json.load(open(os.path.join(d, ".offensive.json"), encoding="utf-8"))
        val = str(cache.get("type", "")).strip().lower()
        # offensive.py's own CLI/state vocabulary abbreviates bug-bounty as "bb" (--type bb,
        # BASE_CLASSES["bb"], CLOSEOUT_CHAINS["bb"]); normalize to the canonical full word this
        # module and every hook that calls engagement_type() actually uses.
        val = {"bb": "bugbounty"}.get(val, val)
        if val in TYPES:
            return val
    except Exception:
        try:   # shared loader: the one corrupt-state signal every hook routes through here
            if os.path.isfile(os.path.join(d, ".offensive.json")):
                import _telemetry
                _telemetry.log_event("hook", d=d, hook="engagement-type",
                                     error=".offensive.json unparseable - type detection fell back to pentest")
        except Exception:
            pass
    return "pentest"


_SCOPE_SECTIONS = {
    "in scope": "in_scope",
    "out of scope": "out_of_scope",
    "allowed tooling": "allowed_tooling",
    "rules of engagement": "roe",
}


def scope(d=None):
    """Parse scope.md: in/out-of-scope lists, allowed tooling, RoE, and the
    no_bruteforce/no_dos/passive_only flags. Empty defaults if absent."""
    res = {"in_scope": [], "out_of_scope": [], "allowed_tooling": [], "roe": [],
           "no_bruteforce": False, "no_dos": False, "passive_only": False,
           "tunnel_safe": False}
    d = d or active_dir()
    if not d:
        return res
    p = os.path.join(d, "scope.md")
    if not os.path.isfile(p):
        return res
    cur = None
    for line in open(p, encoding="utf-8", errors="ignore"):
        s = line.strip()
        fm = re.match(r"(no_bruteforce|no_dos|passive_only|tunnel_safe):\s*(true|false)", s, re.I)
        if fm:
            res[fm.group(1).lower()] = fm.group(2).lower() == "true"
            continue
        h = re.match(r"##\s+(.*)", s)
        if h:
            cur = _SCOPE_SECTIONS.get(h.group(1).strip().lower())
            continue
        if cur and s.startswith("-"):
            v = s[1:].strip()
            if v and not v.startswith("<!--"):
                res[cur].append(v)
    return res


def phase_explicit(d):
    """The Approach frontmatter `current_phase`, IFF present and its `entered_because`
    names no out-of-scope asset; else None (caller falls back to the heuristic phase scan).
    The citation-scope check keeps a phase transition in scope. Deterministic, no network."""
    if not d:
        return None
    try:
        raw = open(os.path.join(d, "Approach.md"), encoding="utf-8", errors="ignore").read()
    except OSError:
        return None
    fm = _frontmatter(raw)
    cp = (fm.get("current_phase") or "").strip()
    if not cp:
        return None
    cited = fm.get("entered_because") or ""
    if isinstance(cited, list):
        cited = " ".join(cited)
    sc = scope(d)
    for tok in re.findall(r"[A-Za-z0-9._:/-]+", cited):
        if out_of_scope_match(tok.lower(), sc):
            return None                    # citation names an out-of-scope asset -> ignore field
    return cp


def _host_of(s):
    """Reduce a URL / authority string to its bare host: drop scheme, userinfo, any
    path/query/fragment, and a trailing :port. A plain host or IP passes through. A
    single-colon `host:port` / `ipv4:port` is de-ported; IPv6 (>=2 colons) is left
    intact. Lets a URL-form scope entity (a bugbounty asset is a full URL) match a
    bare-host scope entry."""
    s = s.split("://", 1)[-1]      # strip scheme
    s = s.split("/", 1)[0]         # strip path/query/fragment
    s = s.rsplit("@", 1)[-1]       # strip userinfo
    if s.count(":") == 1:          # host:port / ipv4:port -> host; IPv6 keeps its colons
        s = s.split(":", 1)[0]
    return s


def _scope_entry_match(e, o, strict=False):
    """Boundary-aware match of host/ip `e` against scope entry `o`.

    Handles: exact host; `o` as a parent domain (`x.com` -> `api.x.com`, the
    `endswith("." + o)` arm, a genuine-subdomain relationship); `o` as a wildcard
    (`*.x.com` matches `x.com` and any subdomain); `o` as a CIDR/IP containing `e`;
    and URL-form `e`/`o` (each reduced to its bare host first, so a full-URL bugbounty
    asset matches a bare-host scope entry).

    The label-prefix arm (`o` as a bare-label prefix, `prod-db` -> `prod-db.x.com`,
    only when `o` has no dot) is ADVISORY-ONLY and applies only when `strict=False`.
    It is inherently attacker-spoofable: anyone can register `<label>.attacker.tld`,
    so a bare-label prefix does NOT prove `e` is the in-scope host. It is a
    convenience for advisory callers (scope-guard warnings, next_move ranking) but
    must never authorize a security decision that writes data to disk. Strict callers
    (the poc/pages disk-write gate) pass `strict=True` and get exact/parent/wildcard/CIDR
    only. Also avoids the old bidirectional-substring bug (`db` -> `db-staging`) and
    dotted label-prefix confusion (`10.0.0.9` -> `10.0.0.9.evil.com`).
    """
    if not o:
        return False
    e = _host_of(e)
    if o.startswith("*."):
        base = o[2:]   # *.x.com -> matches x.com and any subdomain of it
        return bool(base) and (e == base or e.endswith("." + base))
    if "/" in o:
        # CIDR/IP-network, checked before host-normalizing `o` (which would drop the /prefix).
        # A "/" that is NOT a parseable network is a URL path -> fall through to host match.
        try:
            net = ipaddress.ip_network(o, strict=False)
        except ValueError:
            net = None
        if net is not None:
            try:
                return ipaddress.ip_address(e) in net
            except ValueError:
                return False
    o = _host_of(o)
    if e == o or e.endswith("." + o):
        return True
    if not strict and "." not in o and e.startswith(o + "."):
        # advisory-only convenience: a bare-label entry matches its FQDN forms; NOT
        # trusted for a disk-write gate (a host can spoof <label>.attacker.tld).
        return True
    return False


_MACHINE_ENTRY = re.compile(
    r"^\*?\.[A-Za-z0-9._-]+\.[A-Za-z]{2,}$"   # wildcard domain: *.x.com
    r"|^[A-Za-z0-9._-]+\.[A-Za-z]{2,}$"        # bare domain: x.com / sub.x.com
    r"|^[0-9a-fA-F.:]+/\d{1,3}$"               # CIDR (v4/v6)
    r"|^[0-9a-fA-F.:]+$")                      # bare IP (v4/v6)


def _machine_token(o):
    """The machine-matchable head of an out-of-scope bullet, or None.

    scope.md bullets are written `token - prose` (or bare token). Only a head that
    parses as a wildcard domain / bare domain / CIDR / bare IP is returned; a prose
    sentence bullet ('Infrastructure-level attacks ...') returns None so it can never
    silently half-match. This is what made prose-only out-of-scope lists no-op: the
    matcher received whole sentences.
    """
    o = (o or "").strip().lower()
    if not o:
        return None
    # Style 1: `token` backticked inside the bullet - extract every backticked span
    # and return the first that is a machine token (active-engagement scope style).
    # EXCEPTION-CLAUSE GUARD: a bullet like 'every hostname under `x.com` NOT named above'
    # semantically excludes the in-scope hosts; machine-matching its parent token would deny
    # EVERYTHING under x.com including the in-scope siblings (the matcher has no negation).
    # Such except-clause bullets contribute only their OTHER backticked tokens; the parent
    # is skipped, and the residual risk ('unknown future subdomains') stays advisory prose.
    except_clause = bool(re.search(r"not named|except|other hostname", o, re.I))
    for bt in re.findall(r"`([^`]+)`", o):
        bt = bt.strip()
        if not _MACHINE_ENTRY.match(bt):
            continue
        if except_clause and bt in (
                re.findall(r"under\s+`?([a-z0-9.-]+\.[a-z]{2,})`?", o, re.I) or [None]):
            continue  # this token is the except-clause parent - not a deny entry
        return bt
    # Style 2: bare token head, prose after ' - '
    head = re.split(r"\s+-\s+|\s+--\s+", o, maxsplit=1)[0].strip().strip("`")
    if _MACHINE_ENTRY.match(head):
        return head
    return None


def out_of_scope_match(entity, sc):
    """True if entity (host/ip/asset) matches any out-of-scope entry."""
    e = (entity or "").lower().strip()
    if not e:
        return False
    for raw in sc.get("out_of_scope", []):
        o = (raw or "").lower().strip()
        token = _machine_token(o)
        if token and _scope_entry_match(e, token):
            return True
    return False


def oos_exact_match(entity, sc):
    """True when `entity` matches an out-of-scope entry EXACTLY (bare-host equal after
    normalization, or the entity's IP sits in a listed CIDR). An exact deny beats a
    parent-domain in-scope match (common pattern: apex in scope, but a specific
    staging host is named out-of-scope)."""
    e = (entity or "").lower().strip()
    if not e:
        return False
    for raw in sc.get("out_of_scope", []):
        token = _machine_token(raw)
        if not token:
            continue
        if token == _host_of(e):
            return True
        if "/" in token:
            try:
                if ipaddress.ip_address(e) in ipaddress.ip_network(token, strict=False):
                    return True
            except ValueError:
                pass
    return False


def resolve_scope(entity, sc):
    """Three-way scope resolution with SPECIFICITY precedence.

    1. exact in-scope entry  -> "in"   (operator named this host in scope)
    2. exact out-of-scope    -> "out"  (operator named this host out - beats parent in-scope)
    3. in-scope match (any)  -> "in"   (parent/wildcard in-scope beats parent oos)
    4. out-of-scope match    -> "out"
    5. else                  -> "unknown" (advisory prose only; deny never fires)
    Callers enforcing the deny act on "out" only. "unknown" is UNEXAMINED, never clean.
    """
    e = (entity or "").lower().strip()
    if not e:
        return "unknown"
    e_host = _host_of(e)

    def _tokens(o):
        """All machine tokens in a bullet: the head (after ' - ') plus any backticked
        spans. Handles bare entries, 'token - prose', and prose-wrapped `token` style."""
        o = (o or "").lower().strip()
        if not o:
            return []
        toks = []
        for bt in re.findall(r"`([^`]+)`", o):
            bt = bt.strip()
            if _MACHINE_ENTRY.match(bt):
                toks.append(bt)
        # OUT-of-scope exception bullets ('every hostname under `x.com` NOT named above
        # (incl. `sub.x.com`)') enumerate exceptions under a parent: the parent token there
        # is CONTEXT, not a deny rule - keeping it would deny the in-scope siblings. Drop a
        # token that is a parent of another token from the same bullet. IN-scope bullets
        # keep parents (an apex entry legitimately covers apex+www forms).
        if len(toks) > 1 and "not named" in o:
            toks = [t for t in toks
                    if not any(o2 != t and o2.endswith("." + t) for o2 in toks)]
        head = re.split(r"\s+-\s+|\s+--\s+", o.strip("`"), maxsplit=1)[0].strip("`").strip()
        if _MACHINE_ENTRY.match(head):
            toks.append(head)
        return list(dict.fromkeys(toks))

    def _exact_tok(o):
        return any(t == e_host for t in _tokens(o))

    def _any_tok(o):
        return any(_scope_entry_match(e, t, strict=True) for t in _tokens(o))

    in_exact = any(_exact_tok(i) for i in sc.get("in_scope", []))
    out_exact = any(_exact_tok(o) for o in sc.get("out_of_scope", []))
    if in_exact:
        return "in"
    if out_exact:
        return "out"
    out_any = any(_any_tok(o) for o in sc.get("out_of_scope", []))
    if out_any:
        return "out"
    in_any = any(_any_tok(i) for i in sc.get("in_scope", []))
    if in_any:
        return "in"
    return "unknown"


def in_scope_override(entity, sc):
    """True when `entity` matches an IN-SCOPE entry (strict machine match). An explicit
    in-scope host beats a parent-domain out-of-scope entry (common pattern: one named host
    in scope while all sibling subdomains under the parent domain are denied). Callers
    enforcing the deny (scope-guard) check this BEFORE out_of_scope_match."""
    e = (entity or "").lower().strip()
    if not e:
        return False
    for raw in sc.get("in_scope", []):
        i = (raw or "").lower().strip()
        # whole-bullet strict match first (bare-token in-scope entries)
        if _scope_entry_match(e, i, strict=True):
            return True
        # prose-wrapped entries: any backticked machine token inside counts
        # (common style: '- `host.example` (HTTPS 443) - the web application ...')
        for bt in re.findall(r"`([^`]+)`", i):
            bt = bt.strip()
            if _MACHINE_ENTRY.match(bt) and _scope_entry_match(e, bt, strict=True):
                return True
    return False


def scope_text():
    """Compact scope/RoE summary for injection, or ''."""
    s = scope()
    parts = []
    if s["in_scope"]:
        parts.append(f"in-scope {len(s['in_scope'])}")
    if s["out_of_scope"]:
        parts.append(f"out-of-scope {len(s['out_of_scope'])}")
    flags = [k for k in ("no_bruteforce", "no_dos", "passive_only") if s[k]]
    if flags:
        parts.append("RoE: " + ", ".join(flags))
    return "Scope: " + " | ".join(parts) if parts else ""


def recent_log(maxlines=12):
    """Newest block of the active engagement's log.md, or ''. Lets the client
    narrative load from targets/<eng>/log.md instead of session/hot.md."""
    d = active_dir()
    if not d:
        return ""
    p = os.path.join(d, "log.md")
    if not os.path.isfile(p):
        return ""
    lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
    seps = [i for i, l in enumerate(lines) if l.strip() == "---"]
    start = (seps[2] + 1) if len(seps) >= 3 else (seps[1] + 1 if len(seps) >= 2 else 0)
    body = [l for l in lines[start:] if l.strip()]
    return "\n".join(body[:maxlines])


def oob_rows(d=None):
    """Rows of the active engagement's oob.md ledger (list of dicts), or []."""
    d = d or active_dir()
    if not d:
        return []
    return _parse_table(os.path.join(d, "oob.md"))


def oob_hits(d=None):
    """OOB ledger rows whose callback landed (status HIT) but are not yet actioned."""
    return [r for r in oob_rows(d) if r.get("status", "").strip().lower() == "hit"]


def flip_oob_status(d, token, new_status, source=""):
    """Flip the status (and optionally source) of the oob.md row whose token cell
    contains `token`, but only if it is still open (waiting/blank). Line-based edit
    so the rest of the table is untouched. Returns True if a row changed.
    Best-effort: never raises."""
    if not d or not token or len(token) < 4:
        return False
    p = os.path.join(d, "oob.md")
    try:
        lines = open(p, encoding="utf-8", errors="ignore").read().splitlines(keepends=True)
    except OSError:
        return False
    changed = False
    for i, line in enumerate(lines):
        if token not in line or not line.lstrip().startswith("|"):
            continue
        nl = "\n" if line.endswith("\n") else ""
        cells = line[:len(line) - len(nl)].split("|")
        # "| token | sink | class | planted | status | source |" -> 8 parts (lead/trail empty)
        if len(cells) < 8 or token not in cells[1]:
            continue
        if cells[5].strip().lower() not in ("waiting", ""):
            continue  # only flip an open row, never overwrite HIT/actioned/expired
        cells[5] = " " + new_status + " "
        if source:
            cells[6] = " " + source + " "
        lines[i] = "|".join(cells) + nl
        changed = True
    if changed:
        try:
            open(p, "w", encoding="utf-8").write("".join(lines))
        except OSError:
            return False
    return changed


_STATUS_RE = re.compile(r"^##\s*STATUS:\s*(SOLVED|OWNED|ROOTED|COMPLETE)\b",
                        re.IGNORECASE | re.MULTILINE)
# a parked-not-solved close-out: the box is measured (eval metrics) but its
# walkthrough/learn chain stays dormant until it is reopened and actually solved
_SUSPENDED_RE = re.compile(r"^##\s*STATUS:\s*(SUSPEND(?:ED)?)\b",
                           re.IGNORECASE | re.MULTILINE)
# ANY status heading at all -- an unmarked box closes unmeasured (see unmarked_close_gap)
_STATUS_ANY_RE = re.compile(r"^##\s*STATUS\s*:", re.IGNORECASE | re.MULTILINE)


def is_solved(d):
    """True iff <d>/state.md carries a '## STATUS: SOLVED' (or OWNED/ROOTED/COMPLETE)
    heading, case-insensitive -- the explicit close-out marker the walkthrough
    auto-assembly gate watches for. Missing file / any error -> False (fail-open:
    never nag on a detection error)."""
    if not d:
        return False
    p = os.path.join(d, "state.md")
    try:
        text = open(p, encoding="utf-8", errors="ignore").read()
        return bool(_STATUS_RE.search(text))
    except Exception:
        return False


def is_suspended(d):
    """True iff <d>/state.md carries a '## STATUS: SUSPEND' (or SUSPENDED) heading -- a
    deliberate park. Shares is_solved's fail-open posture."""
    if not d:
        return False
    p = os.path.join(d, "state.md")
    try:
        text = open(p, encoding="utf-8", errors="ignore").read()
        return bool(_SUSPENDED_RE.search(text))
    except Exception:
        return False


def _chain_substance_rows(text):
    """Substance lines of a chain section. pentest/bugbounty chains are TABLES (counted by
    _table_data_rows); a ctf's live chain in state.md is a PROSE list (`stage: what -> opens`
    bullets), which the table counter never saw. Count real content bullets / stage lines,
    skipping the template's guidance prose and its bare '-' placeholder."""
    n = 0
    for ln in text.splitlines():
        s = ln.strip()
        if re.match(r"^-\s+\S.{7,}$", s):                       # a real bullet with content
            n += 1
        elif re.match(r"^[A-Za-z][\w /-]{2,}:\s+\S", s):        # a 'stage: what happened' line
            n += 1
    return n


def _append_to_section(text, heading, line):
    """Insert `line` at the END of the `## <heading>` section (before the next `## ` heading
    or EOF), so a draft does not land below a later section. Returns the new text."""
    lines = text.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().lower().startswith("## " + heading.lower()):
            start = i
            break
    if start is None:
        return text + "\n" + line
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    lines.insert(end, line)
    return "\n".join(lines)


def append_draft_chain_rows(d):
    """State auto-synthesis: loot.md holds captured rows but the chain has zero rows ->
    append one DRAFT chain row per un-reflected loot value. The standing nudge to "write the
    chain NOW" fired and was ignored on every engagement to date, so the write now happens
    automatically and the operator polishes the cells instead of authoring from a blank file.
    Routing is type-aware: pentest/bugbounty rows go to Killchain.md's table
    (path '<type>->?' | draft (auto) | open); a ctf's live chain is state.md's own ## Chain
    PROSE list, so its drafts go there as '- draft (auto): ...' lines (never a Killchain.md,
    which ctf does not have). Rows quoting an already-chained loot VALUE are skipped
    (idempotent). Returns the number of rows appended. Fail-open (0)."""
    if not d:
        return 0
    try:
        loot_p = os.path.join(d, "loot.md")
        if not os.path.isfile(loot_p):
            return 0
        loot = open(loot_p, encoding="utf-8", errors="ignore").read()
        rows = _table_data_lines(loot)
        if not rows:
            return 0
        if engagement_type(d) == "ctf":
            state_p = os.path.join(d, "state.md")
            if not os.path.isfile(state_p):
                return 0
            state = open(state_p, encoding="utf-8", errors="ignore").read()
            if "## Chain" not in state:
                return 0
            added = 0
            for row in rows:
                cells = [c.strip() for c in row.strip().strip("|").split("|")]
                value = cells[1] if len(cells) >= 2 else ""
                if not value or value in state:
                    continue                  # already reflected in the chain
                kind = (cells[0] if cells else "loot") or "loot"
                state = _append_to_section(
                    state, "Chain",
                    "- draft (auto): %s %s captured -> trace where it reaches (fill stage + impact)"
                    % (kind, value[:60]))
                added += 1
            if added:
                open(state_p, "w", encoding="utf-8").write(state)
            return added
        chain_p = os.path.join(d, "Killchain.md")
        if not os.path.isfile(chain_p):
            return 0
        chain = open(chain_p, encoding="utf-8", errors="ignore").read()
        added = 0
        for row in rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            value = cells[1] if len(cells) >= 2 else ""
            if not value or value in chain:
                continue                      # already reflected in the chain
            kind = (cells[0] if cells else "loot") or "loot"
            chain += "| %s->? | draft (auto) | open | fill stage + impact | trace where %s reaches |\n" \
                % (kind, value[:60])
            added += 1
        if added:
            open(chain_p, "w", encoding="utf-8").write(chain)
        return added
    except Exception:
        return 0


def cmdlog_entry_count(d):
    """Captured entries across poc/cmdlog/*.md (the '## ts' blocks capture-poc appends). The
    work record that exists even when every state file is still blank."""
    cdir = os.path.join(d, "poc", "cmdlog")
    n = 0
    try:
        for fn in os.listdir(cdir):
            if fn.endswith(".md"):
                try:
                    with open(os.path.join(cdir, fn), encoding="utf-8", errors="ignore") as fh:
                        n += fh.read().count("\n## ")
                except OSError:
                    pass
    except OSError:
        pass
    return n


_HOST_TELL_RE = re.compile(r"https?://([^/\s:'\"]+)|\b(\d{1,3}(?:\.\d{1,3}){3})\b")


def append_activity_draft(d, minimum=10):
    """Activity auto-synthesis for the webserver-lab shape: poc/cmdlog holds the whole work
    record but every state file is still template-blank (loot rows 0, chain rows 0), so the
    engagement carries NOTHING forward and closes unmeasured. Drafts an '## Activity
    (auto-draft)' block into state.md: date, per-tool entry counts, hosts touched. Skipped
    when loot/chain substance exists (those syntheses own state). Idempotent on the heading.
    Returns 1 when drafted, 0 otherwise. Fail-open (0)."""
    if not d:
        return 0
    try:
        state_p = os.path.join(d, "state.md")
        if not os.path.isfile(state_p):
            return 0
        state = open(state_p, encoding="utf-8", errors="ignore").read()
        if "## Activity" in state:
            return 0
        loot_rows = 0
        loot_p = os.path.join(d, "loot.md")
        if os.path.isfile(loot_p):
            loot_rows = _table_data_rows(open(loot_p, encoding="utf-8", errors="ignore").read())
        chain_rows = 0
        if "## Chain" in state:
            tail = state.split("## Chain", 1)[1]
            chain_rows = max(_table_data_rows(tail), _chain_substance_rows(tail))
        kc_p = os.path.join(d, "Killchain.md")
        kc_rows = _table_data_rows(open(kc_p, encoding="utf-8", errors="ignore").read()) \
            if os.path.isfile(kc_p) else 0
        if loot_rows >= 1 or chain_rows >= 1 or kc_rows >= 1:
            return 0
        cdir = os.path.join(d, "poc", "cmdlog")
        tools, hosts, total = [], set(), 0
        try:
            names = sorted(fn for fn in os.listdir(cdir) if fn.endswith(".md"))
        except OSError:
            names = []
        for fn in names:
            try:
                with open(os.path.join(cdir, fn), encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            except OSError:
                continue
            n = text.count("\n## ")
            if n:
                total += n
                tools.append("%s x%d" % (fn[:-3], n))
            for m in _HOST_TELL_RE.finditer(text):
                hosts.add((m.group(1) or m.group(2)).lower())
        if total < minimum:
            return 0
        host_line = ", ".join(sorted(hosts)[:8]) or "?"
        block = ("\n## Activity (auto-draft %s)\n\n%d captured command(s) live in poc/cmdlog/ "
                 "while the state files above stayed blank. Tools: %s. Hosts touched: %s.\n"
                 "Polish into real state rows (assets, loot, chain) or close the box:\n"
                 "`python3 scripts/eng-close.py SOLVED|SUSPEND`.\n"
                 % (date.today().isoformat(), total, "; ".join(tools[:10]), host_line))
        if not state.endswith("\n"):
            state += "\n"
        open(state_p, "w", encoding="utf-8").write(state + block)
        return 1
    except Exception:
        return 0


# placeholder 'why exhausted' cells that carry no reusable signal (machine-read by G4)
_PLACEHOLDER_WHY = {"", "-", "n/a", "na", "none", "no", "x", "?", "tbd", "dead", "failed",
                    "exhausted", "nothing", "no luck", "not working", "didn't work"}


def deadends_placeholder_rows(d):
    """Count Deadends.md rows that pass the anti-loop gate on shape but carry no signal: a
    placeholder 'why exhausted' cell (empty / 'exhausted' / 'failed' ...) or an exact
    duplicate of an earlier asset x class pair. The table is machine-read (offensive.py G4
    suppression); a row without a WHY gets re-tested later and a duplicate bloats the lookup.
    Fail-open (0)."""
    if not d:
        return 0
    try:
        rows = _parse_table(os.path.join(d, "Deadends.md"))
    except Exception:
        return 0
    bad, seen = 0, set()
    for r in rows:
        why = (r.get("why exhausted") or "").strip().lower()
        if why in _PLACEHOLDER_WHY:
            bad += 1
            continue
        key = ((r.get("asset") or "").strip().lower(), (r.get("class") or "").strip().lower())
        if key != ("", "") and key in seen:
            bad += 1                                  # exact duplicate asset x class pair
            continue
        seen.add(key)
    return bad


def deadends_uncontrolled_rows(d):
    """Rows whose `why exhausted` makes a SAFETY claim (not vulnerable / safe / clean /
    not exploitable) without naming the control that makes it safe. A safety claim with
    no control is an unproven negative: name the encoder/sanitizer/block and WHERE it
    was observed ("safe because output is HTML-encoded at the render helper, verified
    on /search"). Fail-open (0)."""
    if not d:
        return 0
    try:
        rows = _parse_table(os.path.join(d, "Deadends.md"))
    except Exception:
        return 0
    claim = re.compile(r"not vulnerable|not exploitable|\bsafe\b|no exposure|\bclean\b")
    bad = 0
    for r in rows:
        why = (r.get("why exhausted") or "").strip()
        if claim.search(why.lower()) and not re.search(r"because\s+\S.{10,}", why, re.I):
            bad += 1
    return bad


def deadends_unclassed_rows(d):
    """Rows appended after the fail-class deploy that left the class cell empty.
    Legacy tables (header lacks fail-class) are exempt - only new rows carry the duty.
    Fail-open (0)."""
    if not d:
        return 0
    try:
        rows = _parse_table(os.path.join(d, "Deadends.md"))
    except Exception:
        return 0
    # dict keys come from the header, so a row carrying the key proves the header
    # has the column; no row carrying it = legacy header -> exempt.
    # ponytail: a 7-col header whose EVERY row was hand-truncated to 6 cells reads
    # as legacy; the appender always pads to 7 cells, so only that path is missed.
    if not any("fail-class" in r for r in rows):
        return 0
    six = ("asset", "class", "what was tried", "why exhausted", "date", "reopen-if")
    n = 0
    for r in rows:
        if not (r.get("fail-class") or "").strip() and any(
                (r.get(k) or "").strip() for k in six):
            n += 1
    return n


def _last_event_age_hours(d):
    """Age in hours of the newest .events.jsonl record, or None when there is no telemetry
    (treated as idle by the caller: work predates telemetry or was copied in)."""
    ev = os.path.join(d, ".events.jsonl")
    last = ""
    with open(ev, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.strip():
                last = line
    if not last:
        return None
    ts = (json.loads(last) or {}).get("ts", "")
    if not ts:
        return None
    t = datetime.fromisoformat(ts)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600.0


def unmarked_close_gap(d):
    """Close-out ROOT-CAUSE reflex: the engagement holds CAPTURED SUBSTANCE (loot.md data
    rows, or a ctf's live '## Chain' rows inside state.md) but state.md carries NO
    '## STATUS:' heading at all, and the last telemetry event is > 12h old (the box was
    left across a session gap -- not mid-box). Every step of the close-out chain (the
    eval-metrics write, the walkthrough build, the learn harvest) keys on that marker, so
    an unmarked box closes UNMEASURED: every closed engagement to date has an empty
    eval.md for exactly this reason. Returns the substance row count when the gap exists,
    else 0. Fail-open (0 on any error)."""
    if not d:
        return 0
    try:
        state_p = os.path.join(d, "state.md")
        if not os.path.isfile(state_p):
            return 0
        state = open(state_p, encoding="utf-8", errors="ignore").read()
        if _STATUS_ANY_RE.search(state):
            return 0                       # marked; solved/suspend chains own it from here
        loot_rows = 0
        loot_p = os.path.join(d, "loot.md")
        if os.path.isfile(loot_p):
            loot_rows = _table_data_rows(open(loot_p, encoding="utf-8", errors="ignore").read())
        chain_rows = 0
        if "## Chain" in state:
            tail = state.split("## Chain", 1)[1]
            chain_rows = max(_table_data_rows(tail), _chain_substance_rows(tail))
        sub = max(loot_rows, chain_rows)
        if sub < 1 and cmdlog_entry_count(d) >= 10:
            sub = 1                # webserver-lab shape: work only in cmdlog, state files blank
        if sub < 1:
            return 0
        age = _last_event_age_hours(d)
        if age is not None and age < 12:
            return 0                        # live session: mid-box, do not nag
        return sub
    except Exception:
        return 0


# unfilled-template markers a scaffolded-but-untouched walkthrough.md still carries
_WALKTHROUGH_STUB_MARKERS = ("<entrypoint>", "<foothold")
_WALKTHROUGH_STUB_LINES = ("- target:", "- reach:")


def walkthrough_stale(d):
    """True (needs assembling) iff <d>/walkthrough.md is absent/empty/whitespace, OR
    still carries an unfilled-template marker (<entrypoint>, <foothold, or a bare
    '- target:'/'- reach:' stub line), OR its '## Evidence' section has no image row
    (![](...)). False once the narrative is filled in and the gallery has a shot.
    Any error -> False (fail-open: do NOT nag on a detection error)."""
    if not d:
        return False
    p = os.path.join(d, "walkthrough.md")
    try:
        if not os.path.isfile(p):
            return True
        text = open(p, encoding="utf-8", errors="ignore").read()
        if not text.strip():
            return True
        if any(m in text for m in _WALKTHROUGH_STUB_MARKERS):
            return True
        if any(line.strip() in _WALKTHROUGH_STUB_LINES for line in text.splitlines()):
            return True
        m = re.search(r"^##\s+Evidence\s*$(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL)
        section = m.group(1) if m else ""
        if not re.search(r"!\[[^\]]*\]\([^)]+\)", section):
            return True  # no markdown image row at all (any alt text counts; a bare '![](' check missed real galleries like '![auto laneFF](x.png)')
        # repro-command floor (pass 13): stubs cleared + one image can still be an
        # images-only gallery that cannot reproduce the box. Reuse build-walkthrough's
        # own counter (the check its WARNING prints, previously swallowed under DEVNULL
        # in the hook path). Cached module-level; any import error -> skipped (fail-open).
        global _BW
        try:
            if _BW is None:
                import importlib.util as _ilu
                _sp = _ilu.spec_from_file_location("bw", os.path.join(VAULT, "scripts", "build-walkthrough.py"))
                _BW = _ilu.module_from_spec(_sp)
                _sp.loader.exec_module(_BW)
            if _BW.reproduction_command_count(text) == 0:
                return True
        except Exception:
            pass
        return False
    except Exception:
        return False


def learn_pending(d):
    """True (a knowledge-harvest pass is due) iff <d> is SOLVED, its walkthrough is
    already assembled (walkthrough_stale False), AND no fresh <d>/.learn-done marker
    exists. Skill(learn) writes .learn-done at the end of a harvest pass to self-clear
    this gate. A marker OLDER than state.md's mtime is stale (the operator changed
    close-out state since the last pass) and re-arms the gate. Placed strictly AFTER
    the walkthrough gate so it never nags while the walkthrough is still unassembled.
    Any error / missing file -> False (fail-open: never nag on a detection error)."""
    if not d:
        return False
    try:
        if not is_solved(d):
            return False
        if walkthrough_stale(d):
            return False                       # walkthrough gate owns this Stop first
        marker = os.path.join(d, ".learn-done")
        if not os.path.isfile(marker):
            return True
        try:
            state = os.path.join(d, "state.md")
            return os.path.getmtime(marker) < os.path.getmtime(state)
        except OSError:
            return False
    except Exception:
        return False


_WEB_PORT_RE = re.compile(r"(?:\b|:)(80|443|8080|8443|8000)\b|https?://|\bhttps?\b", re.I)


def web_evidence_gaps(d):
    """For a SOLVED WEB engagement, the evidence the operator expects before close-out is
    complete. Returns a list of missing categories (empty = complete, or not a web box).
    A web box = state.md shows an http port (80/443/8080/...) or an http(s) service.
    Checks, all reliably read from disk:
      - recon cards: recon/*.png  (EVERY scan tab carded - the thing skipped under momentum)
      - saved page source: poc/*source* or poc/*.html  (the raw site source, per operator ask)
    `capture.sh web` now auto-saves source next to each render, so a missing source file also
    means a site was never rendered. Fail-open: any error -> [] (never blocks a Stop)."""
    if not d:
        return []
    try:
        st = open(os.path.join(d, "state.md"), encoding="utf-8", errors="ignore").read()
        if not _WEB_PORT_RE.search(st):
            return []                                  # not a web box -> gate is silent
        import glob
        gaps = []
        if not glob.glob(os.path.join(d, "recon", "*.png")):
            gaps.append("recon cards (scripts/capture.sh recon <eng> <slug> <tab> for EACH scan tab)")
        poc = os.path.join(d, "poc")
        # recursive: captures live in per-lane subdirs (poc/<slug>/...), not poc/ root;
        # a depth-0 glob reported "evidence missing" on a fully-captured box.
        if not (glob.glob(os.path.join(poc, "**", "*source*"), recursive=True)
                + glob.glob(os.path.join(poc, "**", "*.html"), recursive=True)):
            gaps.append("website render + source (scripts/capture.sh web <eng> <slug> <url>)")
        return gaps
    except Exception:
        return []


def _table_data_rows(text):
    """Count real markdown-table DATA rows (skip header, `---` separators, and empty
    placeholder rows). A data row = a `|`-line whose first cell has content and is not a
    known column label. Lets a caller tell 'this table has real findings' from 'still stub'."""
    rows = 0
    for ln in text.splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            continue
        first = s.strip("|").split("|", 1)[0].strip()
        if not first or set(first) <= set("-: "):          # empty leading cell or a --- separator
            continue
        if first.lower() in ("item", "path", "target", "host", "asset", "flag", "scope", "type", "what", "kind"):
            continue                                        # header row
        rows += 1
    return rows


def _table_data_lines(text):
    """The DATA rows _table_data_rows counts, as their line text (same skip rules)."""
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            continue
        first = s.strip("|").split("|", 1)[0].strip()
        if not first or set(first) <= set("-: "):
            continue
        if first.lower() in ("item", "path", "target", "host", "asset", "flag", "scope", "type", "what", "kind"):
            continue
        out.append(s)
    return out


def paths_write_gap(d):
    """Live state-discipline reflex: LOOT was captured (a cred/key/flag/technique row in
    loot.md) but the chain has ZERO rows -- a finding landed and the attack path was never
    written down (the drift where the chain is filled only at close-out). Type-aware: a
    pentest/bugbounty chain is Killchain.md's table; a ctf's live chain is state.md's own
    ## Chain section (prose lines count). Returns the loot data-row count when a gap exists,
    else 0. Fail-open (0 on any error)."""
    if not d:
        return 0
    try:
        loot = open(os.path.join(d, "loot.md"), encoding="utf-8", errors="ignore").read()
        loot_rows = _table_data_rows(loot)
        if loot_rows < 1:
            return 0
        if engagement_type(d) == "ctf":
            state = open(os.path.join(d, "state.md"), encoding="utf-8", errors="ignore").read()
            if "## Chain" not in state:
                return loot_rows
            tail = state.split("## Chain", 1)[1]
            if max(_table_data_rows(tail), _chain_substance_rows(tail)) == 0:
                return loot_rows
            return 0
        paths = open(os.path.join(d, "Killchain.md"), encoding="utf-8", errors="ignore").read()
        if _table_data_rows(paths) == 0:
            return loot_rows
        return 0
    except Exception:
        return 0


def unsprayed_cred_gap(d):
    """Live cred-reuse reflex: we hold MULTIPLE distinct credentials in loot.md, the box is
    still short of root, and Deadends.md records no cred-reuse/spray attempt -- the drift where
    a newly captured password is written down and then never tried against the auth surfaces
    while a new privesc vector is hunted instead. (Observed live: the app's real DB password sat
    in loot.md while filesystem privesc was ground for ~25min; that password's sibling was the
    root password.) Returns the loot cred-row count when a gap exists, else 0. Counts only rows
    that look like a credential, so a flag/technique row never triggers it. Fail-open (0)."""
    if not d:
        return 0
    try:
        if is_solved(d):
            return 0
        loot = open(os.path.join(d, "loot.md"), encoding="utf-8", errors="ignore").read()
        creds = 0
        for ln in loot.splitlines():
            s = ln.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not cells or not cells[0] or set(cells[0]) <= set("-: "):
                continue
            if cells[0].lower() in ("item", "cred", "credential", "type", "user", "scope"):
                continue                                    # header row
            row = " ".join(cells).lower()
            # " / " (spaced) catches the `user / password` loot form; a bare "/" would match
            # incidental cells like "n/a" or a path and count a flag row as a credential.
            if any(k in row for k in ("pass", "cred", "secret", "token", "key", "hash", " / ")):
                creds += 1
        if creds < 2:
            return 0
        try:
            de = open(os.path.join(d, "Deadends.md"), encoding="utf-8",
                      errors="ignore").read().lower()
        except Exception:
            de = ""
        if any(k in de for k in ("spray", "reuse", "cred-reuse", "password reuse")):
            return 0
        return creds
    except Exception:
        return 0


# a flag token in a loot.md item cell: PREFIX{...}. Excludes placeholder rows ("Base Flag")
# whose item is prose, so an un-captured flag never counts toward the total.
_FLAG_STR_RE = re.compile(r"[A-Za-z0-9_]{2,}\{[^}]+\}")


def captured_flags(d):
    """Distinct SCORED flag strings recorded in loot.md (any cell containing a PREFIX{...}
    token). De-duplicated by value so a copied flag file (e.g. /tmp/rootflag.txt ==
    /root/root.txt) counts once. A row labelled `decoy` (case-insensitive) is skipped, so a
    troll/decoy flag file does not inflate the count and mask a genuinely missing scored flag.
    Fail-open -> set() on any error."""
    out = set()
    if not d:
        return out
    try:
        loot = open(os.path.join(d, "loot.md"), encoding="utf-8", errors="ignore").read()
        for ln in loot.splitlines():
            if "decoy" in ln.lower():
                continue
            for m in _FLAG_STR_RE.finditer(ln):
                out.add(m.group(0))
    except Exception:
        pass
    return out


def flag_accounting_gap(d):
    """Close-out reflex for a SOLVED ctf box: returns a nudge string when the flags recorded
    in loot.md are fewer than state.md's `flags_expected`, OR flags_expected is unset/empty
    (can't verify -> still remind to set it + run the full-FS sweep). Returns "" when
    satisfied, not SOLVED, or not a ctf box. Fail-open ("" on any error).

    This is the guard a CTF flag-accounting retro exposed: a box was declared done with a
    mislabeled decoy user flag and a scored flag missed entirely, nothing checked completeness."""
    if not d:
        return ""
    try:
        if not is_solved(d):
            return ""
        if (engagement_type(d) or "").lower() != "ctf":
            return ""
        st = open(os.path.join(d, "state.md"), encoding="utf-8", errors="ignore").read()
        raw = (_frontmatter(st).get("flags_expected") or "").strip()
        flags = captured_flags(d)
        n = len(flags)
        fmt = next((f.split("{", 1)[0] for f in flags), "flag")   # infer sweep prefix
        sweep = ("`grep -RIn '%s{' / --exclude-dir={proc,sys,dev,run}`" % fmt)
        try:
            expected = int(raw)
        except (TypeError, ValueError):
            expected = None
        common = ("The first home-dir flag may be a DECOY and the scored user flag may belong "
                  "to a LATER user; verify each captured flag matches the room's answer format. "
                  "A scored flag that is nowhere on disk (a THM 'Base Flag') may live in the "
                  "ROOM-PAGE source (view-source), not the box.")
        if expected is None:
            return ("flags_expected is unset in state.md and %d flag(s) are recorded. Set "
                    "flags_expected from the room's answer boxes, then run %s to enumerate ALL "
                    "flags. %s" % (n, sweep, common))
        if n < expected:
            return ("SOLVED but only %d/%d flags recorded. Run %s to enumerate ALL flags. %s"
                    % (n, expected, sweep, common))
        return ""
    except Exception:
        return ""


_MIGRATE_TYPE = {"Approach.md": "engagement-approach", "Killchain.md": "engagement-killchain"}


def _rewrite_type(path, newtype):
    try:
        txt = open(path, encoding="utf-8", errors="ignore").read()
        new = re.sub(r"(?m)^type:.*$", "type: " + newtype, txt, count=1)
        if new != txt:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)
    except OSError:
        pass


def _migrate_schema_names(d):
    """Rename the pre-swap files in an EXISTING engagement dir. killchain.md (old plan board) ->
    Approach.md; paths.md (old chain) -> Killchain.md. Case-insensitive FS: rename killchain.md
    FIRST (Killchain.md aliases it), then paths.md. Idempotent + non-destructive."""
    for old, new in (("killchain.md", "Approach.md"), ("paths.md", "Killchain.md")):
        op, np = os.path.join(d, old), os.path.join(d, new)
        if os.path.exists(op) and not os.path.exists(np):
            os.rename(op, np)
            _rewrite_type(np, _MIGRATE_TYPE[new])


def ensure_state_files():
    """Create any missing per-engagement files (from the type's template) and the
    standard dirs in the active engagement. Both the core set (state_files()) and the
    shared set (_heal_shared_set()) are type-aware: a ctf engagement heals only the lean
    set (state/loot/Approach/scope/Deadends), skipping Killchain.md (its live chain lives
    in state.md's own ## Chain/## Status sections), log.md/walkthrough.md/eval.md (self-
    create at their own trigger), and the Vuln-index/oob severity machinery (dead across
    CTF rooms); pentest/bugbounty heal the full set. poc/ is scaffolded for every type;
    Vulns/ is created lazily on the first FIND, never here. Returns the created names.
    Idempotent: never overwrites an existing file."""
    d = active_dir()
    if not d:
        return []
    name = os.path.basename(d)
    today = date.today().isoformat()
    etype = engagement_type(d)
    tpldir = os.path.join(TEMPLATES, etype)
    if not os.path.isdir(tpldir):
        tpldir = os.path.join(TEMPLATES, "pentest")
    created = []
    _migrate_schema_names(d)   # rename pre-swap killchain.md/paths.md before self-heal recreates them

    def _emit(dest, tpl):
        if os.path.exists(dest) or not os.path.isfile(tpl):
            return None
        text = open(tpl, encoding="utf-8", errors="ignore").read()
        text = text.replace("{{ENGAGEMENT}}", name).replace("{{DATE}}", today)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text)
        return os.path.basename(dest)

    # 1. state/loot/Approach (+ Killchain for pentest/bugbounty) from the type's own
    # template dir (per-type columns); ctf's live chain lives in state.md's ## Chain
    # instead, so it never gets a Killchain.md.
    for fn in state_files(etype):
        c = _emit(os.path.join(d, fn), os.path.join(tpldir, fn))
        if c:
            created.append(c)
    # 2. shared type-agnostic files, type-aware set (ctf omits Vuln-index/oob)
    for fn, tplname in _heal_shared_set(etype):
        c = _emit(os.path.join(d, fn), os.path.join(TEMPLATES, tplname))
        if c:
            created.append(c)
    # 3. standard dirs for every type (see STATE_DIRS). Vulns/ stays lazy (first FIND).
    for sub in STATE_DIRS:
        p = os.path.join(d, sub)
        if not os.path.isdir(p):
            os.makedirs(p, exist_ok=True)
            created.append(sub + "/")
    return created
