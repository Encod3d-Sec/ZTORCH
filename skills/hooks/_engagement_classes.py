"""Vuln-class / coverage helpers for engagement-state hooks.

Split out of _engagement.py (Wave 4): this cluster's only outward dependencies are
_parse_table/entity/_frontmatter/VAULT, imported below. Every symbol here is re-exported from
_engagement.py so existing callers (next_move.py, status.py) that use the _engagement.<name>
dotted form are unaffected -- import from THIS module directly only in new code.
"""
import json
import os
import re

from _engagement import VAULT, _parse_table, entity, _frontmatter


# vuln-class synonyms: phrases (beyond the literal class token) that credit a class
# as TESTED when they appear in a finding title/slug or a Deadends.md line. Keep
# additions specific -- a false positive silences a coverage-gap reminder early.
CLASS_ALIASES = {
    "sqli": ["sql injection", "sql-injection", "sqlmap", "union select", "blind sql"],
    "xss": ["cross-site scripting", "cross site scripting", "stored xss", "reflected xss", "dom xss"],
    "ssrf": ["server-side request forgery", "server side request forgery"],
    "idor": ["insecure direct object", "bola", "broken object level", "object-level auth"],
    "rce": ["remote code execution", "command injection", "os command", "code execution", "webshell"],
    "ssti": ["template injection", "server-side template"],
    "xxe": ["xml external entity", "xml entity"],
    "csrf": ["cross-site request forgery", "cross site request forgery"],
    "oauth-saml": ["oauth", "saml", "openid", "single sign-on", "federation"],
    "auth": ["authentication bypass", "auth bypass", "broken authentication", "login bypass"],
    "file-upload": ["file upload", "unrestricted upload", "arbitrary file upload"],
    "open-redirect": ["open redirect"],
    "request-smuggling": ["request smuggling", "desync"],
    "deserialization": ["insecure deserialization", "deserialisation", "object injection"],
    "prototype-pollution": ["prototype pollution"],
    "subdomain-takeover": ["subdomain takeover"],
    "web-cache": ["cache poisoning", "cache deception", "web cache"],
    "host-header": ["host header"],
    "jwt": ["json web token"],
    "graphql": ["graph ql"],
    "cors": ["cross-origin resource", "cross origin resource"],
    "race-condition": ["race condition", "toctou"],
    "business-logic": ["business logic", "logic flaw"],
    "default-creds": ["default credential", "default password", "default login", "weak credential"],
    "kerberoast": ["kerberoasting"],
    "asreproast": ["asrep roast", "as-rep roast", "asreproasting"],
    "adcs": ["esc1", "esc2", "esc3", "esc4", "esc8", "certifried", "certipy", "certificate template"],
    "privesc": ["privilege escalation", "local privilege"],
    "signing-relay": ["ntlm relay", "smb relay", "smb signing", "ldap relay", "coerce"],
    "lateral": ["lateral movement", "pass-the-hash", "pass the hash", "pass-the-ticket"],
    "shares": ["smb share", "open share", "anonymous share", "readable share"],
    "enum": ["enumeration"],
    "recon": ["reconnaissance"],
    "mcp": ["model context protocol"],
    "cicd": ["ci/cd", "pipeline injection", "github actions", "runner takeover"],
}


def _match_classes(text, classes):
    """Subset of `classes` whose bare token (word-boundaried, so 'rce' does not match
    'source') or a CLASS_ALIASES phrase (substring) appears in `text`. Case-insensitive."""
    if not text:
        return set()
    t = text.lower()
    hits = set()
    for c in classes:
        cl = c.lower()
        if re.search(r"\b" + re.escape(cl) + r"\b", t):
            hits.add(c)
            continue
        for phrase in CLASS_ALIASES.get(cl, ()):
            if phrase in t:
                hits.add(c)
                break
    return hits


def tested_classes(d, etype, classes):
    """Vuln classes credited as TESTED for the engagement, inferred from the files the
    state-first discipline already produces -- so coverage stays current with no manual
    bookkeeping:
      1. Approach.md 4a table         -> explicit, per-asset ('vuln class' when status done)
      2. Vulns/**/FIND-*.md           -> tested-and-found, per 'affected' asset
      3. Deadends.md lines            -> tested-and-cleared (a named class, bounded-out)
    Returns (per_asset: {asset_lower: set}, glob: set); glob credits apply to every asset
    (un-attributed signals). Best-effort: any missing file is skipped. `classes` is the
    canonical vocabulary to match findings/dead-ends against."""
    per_asset, glob = {}, set()
    if not d or not classes:
        return per_asset, glob

    def credit(hits, asset):
        if not hits:
            return
        if asset:
            per_asset.setdefault(asset.lower(), set()).update(hits)
        else:
            glob.update(hits)

    # 1. explicit Approach.md 4a table: credit a row's 'vuln class' as tested when its
    #    status cell is done ([x] or "done"). Drop dash placeholders.
    try:
        for r in _parse_table(os.path.join(d, "Approach.md")):
            status = (r.get("status", "") or "").strip().lower()
            if "[x]" not in status and "done" not in status:
                continue
            a = (r.get("asset") or r.get("host") or r.get("target") or "").strip().lower()
            cls = (r.get("vuln class", "") or "").strip().lower()
            if cls and not re.fullmatch(r"-+", cls):
                credit({cls}, a)
    except Exception:
        pass

    # 2. written findings -> class proven tested on the affected asset
    vroot = os.path.join(d, "Vulns")
    if os.path.isdir(vroot):
        for root, _dirs, files in os.walk(vroot):
            if os.path.basename(root).lower().startswith(("skip", "false")):
                continue
            for f in files:
                if not (f.startswith("FIND-") and f.endswith(".md")):
                    continue
                try:
                    text = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue
                fm = _frontmatter(text)
                title = fm.get("title", "")
                if isinstance(title, list):
                    title = " ".join(title)
                explicit = (fm.get("class") or "").strip().lower()
                hits = ({explicit} if explicit in {c.lower() for c in classes}
                        else _match_classes(f + " " + title, classes))
                aff = fm.get("affected", "")
                for a in (aff if isinstance(aff, list) else [aff]):   # block-list affected -> per-asset
                    credit(hits, a)

    # 3. Deadends.md -> tested-and-cleared; attribute to a state entity if the line names one
    de = os.path.join(d, "Deadends.md")
    if os.path.isfile(de):
        ents = []
        try:
            for r in _parse_table(os.path.join(d, "state.md")):
                e = entity(r, etype)
                if e and e != "?":
                    ents.append(e)
        except Exception:
            pass
        try:
            raw = open(de, encoding="utf-8", errors="ignore").read()
            body = re.sub(r"^\s*---\s*\n.*?\n---\s*\n", "", raw, count=1, flags=re.S)
            for line in body.splitlines():
                s = line.strip()
                if not s or s.startswith(("#", "<!--", "|", "---")):
                    continue
                asset = next((e for e in ents if e.lower() in s.lower()), "")
                credit(_match_classes(s, classes), asset)
        except OSError:
            pass

    return per_asset, glob


def _class_vocab():
    """Full vuln-class vocabulary: every coverage-classes.json value + CLASS_ALIASES key.
    Lowercased. The canonical set confirmed_findings / chains.json validate against."""
    vocab = set(CLASS_ALIASES.keys())
    try:
        cc = json.load(open(os.path.join(VAULT, "scripts", "coverage-classes.json"),
                            encoding="utf-8"))
        for v in cc.values():
            if isinstance(v, list):
                vocab.update(c.lower() for c in v)
    except Exception:
        pass
    return {c.lower() for c in vocab}


def _vuln_index_confirmed_ids(d):
    """{FIND-NNN: host} for Vuln-index.md rows whose Status's first alphabetic word token
    is CONFIRMED or PARTIAL. Multi-table aware (_parse_table only reads the first table):
    rows are credited only under an `id | title | host | status` header, so the
    Severity-Count table is ignored. ID cell may be a bare `FIND-NNN` or a markdown link
    `[FIND-NNN](...)` (re.search, not match). Status may be decorated (emoji/`**`/leading
    whitespace); only the first alphabetic token is compared, so '(emoji/bold-decorated)
    CONFIRMED (Flag 1)' and '**CONFIRMED HIGH**' count, while 'VERSION CONFIRMED / PoC
    pending' (first token VERSION) and 'CLOSED' are excluded. -> {} on any problem."""
    ids = {}
    try:
        lines = open(os.path.join(d, "Vuln-index.md"), encoding="utf-8",
                     errors="ignore").read().splitlines()
    except OSError:
        return ids
    header = None
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue                       # separator row
        low = [c.lower() for c in cells]
        if low[:4] == ["id", "title", "host", "status"]:
            header = "finding"
            continue
        if low and low[0] == "severity":   # Severity-Count table header
            header = "other"
            continue
        if header != "finding" or len(cells) < 4:
            continue
        m = re.search(r"(FIND-\d+)", cells[0])
        tok = re.match(r"[^A-Za-z]*([A-Za-z]+)", cells[3].strip())
        first = tok.group(1).upper() if tok else ""
        if m and first in ("CONFIRMED", "PARTIAL"):
            ids[m.group(1)] = cells[2].strip()
    return ids


def confirmed_findings(d):
    """CONFIRMED/PARTIAL findings as typed records: [{class, asset, severity, status}].
    The Vuln-index Status column is the authoritative gate (a FIND file's own frontmatter
    `status:` stays Research in practice). One record per `affected` asset (comma-split
    when `affected` is a single scalar string, e.g. 'web08a, web08b'). Class = explicit
    frontmatter `class:` (when a known class) else fuzzy _match_classes(title+filename).
    The record's `status` field is always the literal 'confirmed', a gate-provenance
    tag meaning "passed the CONFIRMED/PARTIAL gate", not the original Vuln-index status.
    Error-safe -> []."""
    out = []
    if not d:
        return out
    ok = _vuln_index_confirmed_ids(d)
    if not ok:
        return out
    vocab = _class_vocab()
    vroot = os.path.join(d, "Vulns")
    if not os.path.isdir(vroot):
        return out
    for root, _dirs, files in os.walk(vroot):
        if os.path.basename(root).lower().startswith(("skip", "false")):
            continue
        for f in files:
            if not (f.startswith("FIND-") and f.endswith(".md")):
                continue
            m = re.match(r"(FIND-\d+)", f)
            if not m or m.group(1) not in ok:
                continue
            try:
                text = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            fm = _frontmatter(text)
            title = fm.get("title", "")
            if isinstance(title, list):
                title = " ".join(title)
            explicit = (fm.get("class") or "").strip().lower()
            if explicit in vocab:
                cls = explicit
            else:
                hits = _match_classes(f + " " + title, vocab)
                # multiple fuzzy hits: alphabetical-first is a fallback; explicit
                # frontmatter `class:` is the reliable disambiguator.
                cls = sorted(hits)[0] if hits else ""
            if not cls:
                continue
            sev_m = re.match(r"FIND-\d+-([A-Za-z]+)-", f)
            sev = (sev_m.group(1).upper() if sev_m else str(fm.get("severity", "")).upper())
            aff = fm.get("affected", "")
            raw = aff if isinstance(aff, list) else str(aff).split(",")
            assets = [a.strip() for a in raw if a and a.strip()] or [ok[m.group(1)]]
            for a in assets:
                out.append({"class": cls, "asset": a, "severity": sev, "status": "confirmed"})
    return out
