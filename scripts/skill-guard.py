#!/usr/bin/env python3
"""skill-guard.py scan [--file X] [--root DIR] - advisory threat scanner over skills/.

Curated port of the hermes tools/skills_guard.py battery
(docs/port-specs/proposals-aux-eval-guards.md, PORT #2). This vault IS an offensive
knowledge base, so the hermes battery is cut to the classes that would subvert the
AGENT or exfiltrate the OPERATOR (never the target); exploit payloads, attack-technique
prose and offensive tooling syntax are deliberately NOT scanned:

  exfiltration   curl/wget pipe-to-shell and secret-interpolating fetches (loopback
                 destinations exempt: they cannot leave the machine), `cat` of a
                 credential file, DNS-exfil dig/nslookup/host interpolation shapes
  injection      ignore-previous-instructions, role hijack, hidden HTML-comment
                 instructions aimed at an AI, invisible/bidi unicode
  destructive    rm -rf on a root path (temp roots exempt), recursive $HOME/~ delete
  persistence    crontab, shell rc files, authorized_keys, sudoers/visudo, and the
                 agent-config attack class (instructions to modify AGENTS.md /
                 CLAUDE.md / .zcode/config.json / .claude/settings*), prose and
                 shell-write tiers
  obfuscation    base64 decoded straight into a shell/interpreter
  credentials    ghp_ / sk- / AKIA literal token shapes

Markdown is scanned fence-aware (code blocks verbatim, prose link destinations masked),
the hermes porting lesson. ADVISORY ONLY: exit 0 always; findings are a triage prompt,
never a gate. Fails open on any error. Wired into offensive-doctor as a manual advisory.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)

# ---- shared regex fragments (ported from hermes tools/skills_guard.py) ----
_SHELL_NAMES = r'(?:bash|sh|zsh|ksh|dash)\b'
_SUDO_PREFIX = r'(?:sudo\s+(?:-\S+\s+)*)?'
# Loopback exemption: a same-line literal scheme-anchored loopback destination cannot
# move data off the machine, so a secret-shaped fetch there is a local session token.
_LOOPBACK_OK = r'(?![^\n]*https?://(?:localhost|127\.0\.0\.1|\[::1\]))'
_CRED_FILE = (r'(?:\.ssh[/\\]id_(?:rsa|ed25519|ecdsa|dsa)(?!\.pub)|\.env\b|credentials\b'
              r'|\.netrc\b|\.pgpass\b|\.npmrc\b|\.pypirc\b)')

MODIFY_VERB_RE = (
    r'(?:\bwrit(?:e|es|ing)\b|\bwritten\b|\bedit(?:s|ed|ing)?\b'
    r'|\bmodif(?:y|ies|ied|ying|ication)s?\b|\bupdat(?:e|es|ed|ing)\b'
    r'|\bappend(?:s|ed|ing)?\b|\bprepend(?:s|ed|ing)?\b'
    r'|\binject(?:s|ed|ing)?\b|\boverwrit(?:e|es|ing)\b|\boverwritten\b'
    r'|\breplac(?:e|es|ed|ing)\b|\balter(?:s|ed|ing)?\b|\badd(?:s|ed|ing)?\b)')

# The agent-config attack class: instructions that persist into what future sessions
# auto-load or enforce. `.claude/settings[\w.]*` consumes the trailing filename so
# settings.json / settings.local.json both match.
_AGENT_CONFIG_FILES = (r'(?:AGENTS\.md|CLAUDE\.md|\.cursorrules|\.clinerules'
                       r'|\.zcode/config\.json|\.claude/settings[\w.]*)')


def _shell_write_re(file_alt):
    """Mechanical shell write into file_alt: >/>>, sed -i, tee, cp/mv destination."""
    return (
        rf'(?:>>|[\w"\'`)\]]\s*>)\s*[~\w./-]*{file_alt}(?!\.?\w)'
        rf'|\bsed\b[^\n]*\s(?:-[A-Za-z]*i[A-Za-z]*|--in-place)\b[^\n]*{file_alt}(?!\.?\w)'
        rf'|\btee\s+(?:-a\s+)?[~\w./"\'-]*{file_alt}(?!\.?\w)'
        rf'|\b(?:cp|mv)\s+[^\s|;&]+\s+[^\n|;&]{{0,40}}?{file_alt}(?!\.?\w)')


def _prose_modify_re(file_alt):
    """Prose instructing modification of file_alt: imperative-position verb, or a
    mid-line verb with a directive marker. Descriptive prose misses by design."""
    return (
        rf'^\s*(?:[-*+]\s+|\d+[.)]\s+)?{MODIFY_VERB_RE}[^\n,]{{0,80}}?{file_alt}\b'
        rf'|(?:\byou\s+(?:must|should|need\s+to)\s+|\bplease\s+'
        rf'|\bmake\s+sure\s+(?:to\s+|you\s+)|\bbe\s+sure\s+to\s+)'
        rf'{MODIFY_VERB_RE}[^\n,]{{0,80}}?{file_alt}\b')


# ---- curated battery: (regex, pattern_id, severity, category, description) ----
THREAT_PATTERNS = [
    # exfiltration / supply chain: download-and-execute (loopback exempt)
    (r'curl\s+' + _LOOPBACK_OK + r'[^|\s][^\n]*\|\s*' + _SUDO_PREFIX + _SHELL_NAMES,
     "curl_pipe_shell", "critical", "supply_chain",
     "curl piped to shell (download-and-execute; loopback exempt)"),
    (r'wget\s+' + _LOOPBACK_OK + r'[^\n]*\|\s*' + _SUDO_PREFIX + _SHELL_NAMES,
     "wget_pipe_shell", "critical", "supply_chain",
     "wget piped to shell (download-and-execute; loopback exempt)"),
    # exfiltration: operator secrets interpolated into an outbound fetch
    (r'curl\s+' + _LOOPBACK_OK + r'[^\n]*\$\{?\w*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)S?\b',
     "env_exfil_curl", "critical", "exfiltration",
     "curl command interpolating a secret environment variable"),
    (r'wget\s+' + _LOOPBACK_OK + r'[^\n]*\$\{?\w*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)S?\b',
     "env_exfil_wget", "critical", "exfiltration",
     "wget command interpolating a secret environment variable"),
    # exfiltration: reading credential stores (`cat >` writes one, so (?!>))
    (r'cat\s+(?!>)[^\n]*' + _CRED_FILE,
     "read_secrets_file", "critical", "exfiltration", "cat of a known credential file"),
    # exfiltration: DNS tunneling shape (data in the queried NAME)
    (r'(?<![-/])\b(?:dig|nslookup)\s+(?:[-+@]\S*(?:\s+[^\s$"\'-][^\s$]*)?\s+)*["\']?[^\s"\'$()]*'
     r'\$(?:\{[^}\s]*\}|\([^\n]*?\)+|\w+)[\w-]*["\']?\.[a-z]'
     r'|(?<![-/])\bhost\s+(?:[-+@]\S*(?:\s+[^\s$"\'-][^\s$]*)?\s+)*["\']?[^\s"\'$()]*'
     r'\$(?:\{[^}\s]*\}|\([^\n]*?\)+|\w+)[\w-]*\.[a-z]'
     r'|(?:^|[;&|]|\$\(|\b(?:do|then|else)\b)\s*host\s+(?:[-+@]\S*(?:\s+[^\s$"\'-][^\s$]*)?\s+)*["\']?\$',
     "dns_exfil", "critical", "exfiltration",
     "DNS lookup with variable interpolation (possible DNS exfiltration)"),
    # prompt injection
    (r'ignore\s+(?:\w+\s+)*(previous|all|above|prior)\s+instructions',
     "prompt_injection_ignore", "critical", "injection",
     "prompt injection: ignore previous instructions"),
    (r'you\s+are\s+(?:\w+\s+)*now\s+',
     "role_hijack", "high", "injection", "attempts to override the agent's role"),
    (r'<!--[^>]*(?:\b(?:ignore|forget|disregard|override)\s+(?:\w+\s+)*?'
     r'(?:previous|prior|above|earlier|all|any|your|the)\s+(?:\w+\s+)*?'
     r'(?:instructions?|rules|prompts?|guidelines|directions|restrictions)'
     r'|\bsystem\s*(?:prompt|message|instructions?|override)|\b(?:override|secret|hidden|system)\s*:'
     r'|\b(?:ignore|override|bypass|disable)\s+(?:\w+\s+)*?(?:safety|security|guardrails|filters)\b'
     r'|\b(?:secret|hidden|new)\s+(?:instructions?|commands?|directives?|tasks?)\b|\byou\s+are\s+now\b'
     r'|\bdo\s+not\s+(?:tell|reveal|show|mention|inform)\b'
     r'|\b(?:note|message)\s+(?:to|for)\s+(?:the\s+)?(?:ai|agent|assistant|model|llm)\b)[^>]*-->',
     "html_comment_injection", "high", "injection", "hidden instructions in HTML comments"),
    # destructive host patterns (temp-root cleanup exempt inside the root_rm shape)
    (r'rm\s+-rf\s+((?:[^\s;&|<>#][^\s;&|<>]*\s+)+?)?/(?(1)(?!/(?:\s|$)))(?:'
     r'(?!(?:tmp|var/tmp|dev/shm|run|var/lib/apt/lists|var/cache/(?:apt|apk|yum|dnf))(?:\b|/))'
     r'|(?:tmp|var/tmp|dev/shm|run|var/lib/apt/lists|var/cache/(?:apt|apk|yum|dnf))/(?:[^/\s]*/)*\.\.(?=/|[\s;&|]|$))',
     "destructive_root_rm", "critical", "destructive", "recursive delete from root"),
    (r'(?<![A-Za-z0-9])rm\s+(-[^\s]*)?r.*(?:\$HOME|~[/\s*]|~$)',
     "destructive_home_rm", "critical", "destructive",
     "recursive delete targeting the home directory"),
    # persistence on the OPERATOR host
    (r'\bcrontab\b', "persistence_cron", "medium", "persistence", "modifies cron jobs"),
    (r'\.(?:bashrc|zshrc|bash_profile|bash_login|zprofile|zlogin)\b'
     r'|(?<![\w)\]?])\.profile\b',
     "shell_rc_mod", "medium", "persistence", "references a shell startup file"),
    (r'authorized_keys', "ssh_backdoor", "critical", "persistence",
     "modifies SSH authorized keys"),
    (r'/etc/sudoers|visudo', "sudoers_mod", "critical", "persistence",
     "modifies sudoers (privilege escalation)"),
    # agent-config attack class: instructions persisting into harness config
    (_prose_modify_re(_AGENT_CONFIG_FILES),
     "agent_config_mod", "critical", "persistence",
     "instructs modification of agent config files (cross-session instruction persistence)"),
    (_shell_write_re(_AGENT_CONFIG_FILES),
     "agent_config_mod_shell", "critical", "persistence",
     "shell write targeting agent config files (persistence mechanism)"),
    # obfuscation: base64 decoded into an interpreter
    (r'(?:\bbase64\s+(?:-[^\s|]+\s+)*?(?:-[a-z]*d[a-z]*|--decode)\b|\bopenssl\s+(?:base64|enc)\b[^|;&\n]*?\s-d\b)'
     r'[^\n]*?(?:\||;|&&)\s*(?:\w+=\S*\s+)*(?:\S*/)?'
     r'(?:sh|bash|zsh|ksh|dash|fish|python[\d.]*|perl|ruby|node|nodejs|php|eval|source|exec|xargs|env|sudo'
     r'|iex|pwsh|powershell|tar|bsdtar|unzip|cpio|gunzip|gzip|zcat|xz|unxz|bunzip2|\.(?=\s))(?![\w.-])'
     r'|\b(?:eval|source|iex|exec)\b[^\n]*\bbase64\s+(?:-[^\s|]+\s+)*?(?:-[a-z]*d[a-z]*|--decode)\b',
     "base64_decode_pipe", "high", "obfuscation", "base64 decodes and pipes to execution"),
    # credential literals (case-fixed provider shapes)
    (r'(?-i:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{80,})',
     "github_token_leaked", "critical", "credential_exposure",
     "GitHub personal access token literal"),
    (r'(?-i:sk-[A-Za-z0-9]{20,})', "openai_key_leaked", "critical", "credential_exposure",
     "possible OpenAI API key literal"),
    (r'(?-i:AKIA[0-9A-Z]{16})', "aws_access_key_leaked", "critical", "credential_exposure",
     "AWS access key ID literal"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), pid, sev, cat, desc)
             for p, pid, sev, cat, desc in THREAT_PATTERNS]

# Invisible / directional unicode used for text hiding (one finding per line).
_INVISIBLE_CHAR_NAMES = {
    '\u200b': "zero-width space",
    '\u200c': "zero-width non-joiner",
    '\u200d': "zero-width joiner",
    '\u202a': "LTR embedding",
    '\u202b': "RTL embedding",
    '\u202c': "pop directional",
    '\u202d': "LTR override",
    '\u202e': "RTL override",
    '\u2060': "word joiner",
    '\u2062': "invisible times",
    '\u2063': "invisible separator",
    '\u2064': "invisible plus",
    '\u2066': "LTR isolate",
    '\u2067': "RTL isolate",
    '\u2068': "first strong isolate",
    '\u2069': "pop directional isolate",
    '\ufeff': "BOM/zero-width no-break space",
}
INVISIBLE_CHARS = set(_INVISIBLE_CHAR_NAMES)

SCANNABLE_SUFFIXES = {".md", ".txt", ".py", ".sh", ".bash", ".js", ".ts", ".rb",
                      ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini", ".conf",
                      ".html", ".css", ".xml", ".tex", ".r", ".jl", ".pl", ".php"}
MAX_FILE = 1024 * 1024      # ponytail: skip >1MB blobs; a skill file that size is raw log noise

# ---- markdown fence-aware scanning (ported from hermes skills_guard :661-691) ----
_FENCE_LINE = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
_CONTAINER_PREFIX = re.compile(r"^(?: {0,3}(?:>|(?:[-*+]|\d{1,9}[.)]) {1,4}))+")


def _mask_link_dest(line):
    """Blank balanced inline-link destinations, preserving line offsets."""
    masked = list(line)
    pos = 0
    while (start := line.find("](", pos)) != -1:
        depth, esc, cur = 1, False, start + 2
        while cur < len(line):
            ch = line[cur]
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    masked[start + 2:cur] = " " * (cur - start - 2)
                    pos = cur + 1
                    break
            cur += 1
        else:
            break
    return "".join(masked)


def _mask_prose(lines):
    """Mask link destinations only in Markdown prose: fenced/indented code blocks
    stay verbatim (an argument, not a hyperlink); fence state is (marker, length)
    so a mismatched fence line cannot drop the scanner back into prose mode; an
    unclosed fence stays code to EOF (fail-safe)."""
    out, fence = [], None
    for line in lines:
        m = _FENCE_LINE.match(_CONTAINER_PREFIX.sub("", line))
        if fence is not None:
            if (m and m["marker"][0] == fence[0] and len(m["marker"]) >= fence[1]
                    and not m["info"].strip()):
                fence = None
            code = True
        else:
            if m and not (m["marker"][0] == "`" and "`" in m["info"]):
                fence = (m["marker"][0], len(m["marker"]))
            code = fence is not None or line.startswith(("\t", "    "))
        out.append(line if code else _mask_link_dest(line))
    return out


class Finding(tuple):
    """(rel_path, line, pattern_id, severity, category, snippet)."""

    def __new__(cls, rel, line, pid, sev, cat, snippet):
        return super().__new__(cls, (rel, line, pid, sev, cat, snippet))


def scan_text(text, rel):
    """Findings for one file's text: battery scan per line + invisible unicode."""
    lines = text.split("\n")
    scan_lines = _mask_prose(lines) if rel.lower().endswith(".md") else lines
    findings = []
    for pat, pid, sev, cat, _desc in _COMPILED:
        for i, line in enumerate(scan_lines, start=1):
            if pat.search(line):
                snippet = lines[i - 1].strip()
                findings.append(Finding(rel, i, pid, sev, cat,
                                        snippet if len(snippet) <= 100 else snippet[:97] + "..."))
    for i, line in enumerate(lines, start=1):
        hit = next((c for c in INVISIBLE_CHARS if c in line), None)
        if hit is not None:
            name = _INVISIBLE_CHAR_NAMES.get(hit, "U+%04X" % ord(hit))
            findings.append(Finding(rel, i, "invisible_unicode", "high", "injection",
                                    "U+%04X (%s)" % (ord(hit), name)))
    return findings


def _iter_files(root):
    for dirpath, dirs, files in os.walk(root):
        # node_modules = vendored deps (legitimate ZWNJ locale text, huge), not skill
        # instructions; __pycache__/.git are never scannable content
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules")]
        for fn in sorted(files):
            path = os.path.join(dirpath, fn)
            if fn == "SKILL.md" or os.path.splitext(fn)[1].lower() in SCANNABLE_SUFFIXES:
                yield path


def scan_root(root):
    """(findings, files_scanned) for every scannable file under root. Fails open."""
    findings, n = [], 0
    for path in _iter_files(root):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        try:
            if os.path.getsize(path) > MAX_FILE:
                continue
            with open(path, encoding="utf-8-sig", errors="strict") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        n += 1
        findings.extend(scan_text(text, rel))
    return findings, n


def verdict(findings):
    sevs = {f[3] for f in findings}
    return "dangerous" if "critical" in sevs else "caution" if "high" in sevs else "safe"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description="advisory agent-subversion scanner over skills/")
    ap.add_argument("cmd", nargs="?", default="scan", choices=["scan"], help="scan (default)")
    ap.add_argument("--file", help="scan a single file instead of a tree")
    ap.add_argument("--root", help="tree to scan (default: <vault>/skills/)")
    args = ap.parse_args(argv)
    try:
        if args.file:
            try:
                text = open(args.file, encoding="utf-8-sig").read()
            except (OSError, UnicodeDecodeError) as e:
                print("skill-guard: cannot read %s (%s)" % (args.file, e))
                return 0
            findings = scan_text(text, os.path.basename(args.file))
            n = 1
        else:
            findings, n = scan_root(args.root or os.path.join(VAULT, "skills"))
    except Exception as e:                       # fail open: advisory tool never breaks
        print("skill-guard: scan failed (fail-open): %s" % e)
        return 0
    for f in sorted(findings):
        print("%s:%d  [%s] %s  %s" % (f[0], f[1], f[3], f[2], f[5]))
    counts = {}
    for f in findings:
        counts[f[2]] = counts.get(f[2], 0) + 1
    print("skill-guard: %d file(s) scanned, %d finding(s), verdict %s%s"
          % (n, len(findings), verdict(findings),
             (" (" + ", ".join("%s=%d" % kv for kv in sorted(counts.items())) + ")") if counts else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
