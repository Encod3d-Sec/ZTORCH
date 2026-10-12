#!/usr/bin/env python3
"""PreToolUse(Bash) hook: lane-guard -- hermes' two-tier terminal-command safety
(docs/port-specs/sandbox-tooling.md, from tools/approval_detection.py) ported
onto the vault hook architecture (scope-guard's deny wire, sleep-guard's
advisory wire).

Tiers (matched AFTER de-obfuscation, on the text; this is a pattern matcher,
not a shell parser):
  - HARDLINE -> DENY, never auto-upgraded: rm -rf on / or a system dir, mkfs,
    dd/raw write to a block device, fork bomb, kill -1 / broad killall,
    shutdown/reboot/init level change, chmod -R 777 on /, curl/wget to a cloud
    metadata endpoint (169.254.169.254 / metadata.google.internal).
  - DANGEROUS -> ADVISORY one-liner: curl|wget piped into a shell (+ base64/
    xxd/openssl decode variants), chmod 777, SQL DROP / TRUNCATE /
    DELETE-no-WHERE, git reset --hard / push --force / branch -D, writes onto
    .env / ssh config / authorized_keys / crontab, invisible/bidi unicode.
    Operator pre-approval (ZT_ROE_OK=1 env prefix on the command, or the active
    engagement's .roe-ok marker -- same policy as scope-guard's RoE gate)
    upgrades THIS tier only, to allow-with-note; it never lifts a hardline.

SAFETY (this hook can block, so it must never trap the operator):
  - Fail-OPEN: any exception -> exit 0, allow. A hook bug never blocks a command.
  - Escape hatch: skills/hooks/.enforce-off (== this dir) downgrades the
    hardline deny to an advisory, exactly as in scope-guard.
  - Textual matching fails TOWARD caution: a destructive pattern quoted in
    prose (echo/grep) can match. .enforce-off is the relief valve.
"""
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# --- normalization: defeat the cheap obfuscation classes before matching ---
_ANSI = re.compile(r"\x1b(?:\[[0-9;?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))")
_IFS = re.compile(r"\"?\$\{?IFS\}?\"?")


def normalize(cmd):
    """ANSI-strip -> NFKC fold -> join backslash-newline continuations -> $IFS
    to separator.
    # ponytail: not a shell parser; hermes also deobfuscates r\\m, $(echo rm)
    # and variable-indirection shapes -- out of scope here. Upgrade path: a
    # dedicated deobfuscator pass if those evasion shapes show up in the wild."""
    s = _ANSI.sub(" ", cmd)
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\\\r\n", "").replace("\\\n", "")
    return _IFS.sub(" ", s)


def _invisible(cmd):
    """True if the command carries a Cf-format char (zero-width, bidi controls
    U+202A-E / U+2066-9, soft hyphen...) -- hermes' invisible-unicode tell.
    ANSI (Cc) is normalize()'s job, not this check's."""
    return any(unicodedata.category(ch) == "Cf" for ch in cmd)


_DIR = r"/(?:bin|boot|dev|etc|home|lib|lib32|lib64|proc|root|run|sbin|sys|usr|var)?"
_BLK = r"/dev/(?:sd[a-z]|nvme|hd[a-z]|vd[a-z]|mmcblk|xvd|disk)"
_SENS = r"(?:\.env|\.ssh/(?:config|authorized_keys))"

HARDLINE = [
    ("rm -rf on / or a system dir", re.compile(
        r"\brm\s+(?=[^|;&]*-[a-zA-Z]*[rR])(?=[^|;&]*-[a-zA-Z]*[fF])"
        r"[^|;&]*\s" + _DIR + r"/?\s*(?:[;|&]|$)", re.I)),
    ("mkfs (filesystem format)", re.compile(r"\bmkfs(?:\.[a-z0-9]+)?\b|\bmke2fs\b", re.I)),
    ("raw write to a block device (dd/redirect)", re.compile(
        r"\bdd\b[^|;&]*\bof=" + _BLK + r"|>{1,2}\s*" + _BLK, re.I)),
    ("fork bomb", re.compile(r"\(\s*\)\s*\{[^}]*\|[^}]*&[^}]*\}")),
    ("kill -1 / broad killall (all processes)", re.compile(
        r"\bkill\b(?:\s+-\w+)*\s+-1\b|\bkillall5\b|\bkillall\b[^|;&]*\s-(?:9|kill|1)\b", re.I)),
    ("shutdown/reboot/init level change", re.compile(
        r"(?<!@)\b(?:shutdown|poweroff|halt|reboot|telinit)\b|\binit\s+[0-6]\b", re.I)),
    ("chmod -R 777 on /", re.compile(
        r"\bchmod\b(?=[^|;&]*\s-[a-zA-Z-]*[rR])(?=[^|;&]*\s777\b)[^|;&]*\s/\s*(?:[;|&]|$)", re.I)),
    ("cloud metadata endpoint fetch (curl/wget)", re.compile(
        r"\b(?:curl|wget)\b[^|;&]*\b(?:169\.254\.169\.254|metadata\.google\.internal)\b", re.I)),
]

DANGEROUS = [
    ("curl|wget piped into a shell", re.compile(
        r"\b(?:curl|wget)\b[^|;&]*\|\s*(?:sudo\s+)?(?:ba|z|fi|da|k)?sh\b", re.I)),
    ("decoded payload piped into a shell", re.compile(
        r"\b(?:base64|openssl|xxd|uudecode)\b[^|;&]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b", re.I)),
    ("chmod 777", re.compile(r"\bchmod\b[^|;&]*\s777\b", re.I)),
    ("SQL destructive statement (DROP/TRUNCATE/DELETE-no-WHERE)", re.compile(
        r"\bdrop\s+(?:table|database|schema)\b|\btruncate\s+(?:table\s+)?\w+"
        r"|\bdelete\s+from\b(?:(?!\bwhere\b|;).)*(?:;|$)", re.I | re.S)),
    ("git destructive op (reset --hard / force push / branch -D)", re.compile(
        r"\bgit\s+reset\s+--hard\b|\bgit\s+push\s+(?:[^|;&]*\s)?(?:-f\b|--force(?!-with-lease))"
        # `(?-i:-D)`: only capital -D (force-delete unmerged) is dangerous; lowercase -d
        # refuses to delete unmerged branches on its own.
        r"|\bgit\s+branch\s+(?:[^|;&]*\s)?(?-i:-D)\b", re.I)),
    ("write onto sensitive file (.env / ssh config / authorized_keys / crontab)", re.compile(
        r">{1,2}\s*[\w./~'-]*" + _SENS + r"\b|\btee\b[^|;&]*" + _SENS + r"\b"
        r"|\|\s*crontab\b|\bcrontab\s+(?!-)[\w./-]+\b"
        r"|\bsed\b[^|;&]*-i[^|;&]*" + _SENS + r"\b", re.I)),
]


def _enforcing():
    """Enforcement ON unless the escape-hatch marker sits in the hooks dir (the
    scope-guard hatch: downgrades the hardline deny to an advisory).
    ENFORCE_OFF_MARKER lets parallel tests point at their own absent path."""
    marker = os.environ.get("ENFORCE_OFF_MARKER") or os.path.join(HERE, ".enforce-off")
    return not os.path.exists(marker)


def _engagement_dir():
    try:
        import _engagement
        return _engagement.active_dir()
    except Exception:
        return None


_ROE_OK_ENV = re.compile(r"(?<![\w-])ZT_ROE_OK=\S")


def _roe_approved(cmd, d=None):
    """Operator pre-approval for the dangerous tier (same policy as scope-guard's
    RoE gate): a ZT_ROE_OK=<val> env prefix on THIS command, or the engagement's
    .roe-ok marker. Never consulted for hardline patterns."""
    if _ROE_OK_ENV.search(cmd):
        return True
    if d is None:
        d = _engagement_dir()
    try:
        return bool(d) and os.path.isfile(os.path.join(d, ".roe-ok"))
    except Exception:
        return False


def classify(cmd):
    """(hardline names, dangerous names) the command matches, post-normalize."""
    n = normalize(cmd)
    hard = [name for name, rx in HARDLINE if rx.search(n)]
    danger = [name for name, rx in DANGEROUS if rx.search(n)]
    if _invisible(cmd):
        danger.append("invisible/bidi unicode in command")
    return hard, danger


def _emit(**fields):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **fields}}))


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        return
    if data.get("tool_name") != "Bash":
        return
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not cmd:
        return
    hard, danger = classify(cmd)
    if not hard and not danger:
        return
    try:
        import _telemetry
        if hard:
            action = "deny" if _enforcing() else "advise"
            _telemetry.drift("lane-guard", action + " hardline: " + ", ".join(hard))
        else:
            action = "allow" if _roe_approved(cmd) else "advise"
            _telemetry.drift("lane-guard", action + " dangerous: " + ", ".join(danger))
        _telemetry.hook("lane-guard", action=action)
    except Exception:
        pass
    if hard:
        if not _enforcing():
            _emit(additionalContext="LANE-GUARD (advisory; enforcement OFF via .enforce-off): "
                  "hardline pattern(s): " + ", ".join(hard))
            return
        _emit(permissionDecision="deny",
              permissionDecisionReason=(
                  "BLOCKED by harness enforcement (lane-guard hardline):\n- "
                  + "\n- ".join(hard)
                  + "\n\nDestructive-tier pattern, never auto-approved. Fix the command and "
                    "re-run. (False block? ask the OPERATOR to create skills/hooks/.enforce-off "
                    "to downgrade enforcement to advisory.)"))
        return
    if _roe_approved(cmd):
        _emit(additionalContext="LANE-GUARD (allowed): dangerous-tier pattern(s): "
              + ", ".join(danger) + " pre-approved by operator (ZT_ROE_OK=1 / .roe-ok).")
        return
    _emit(additionalContext="LANE-GUARD (advisory): dangerous-tier pattern(s): "
          + ", ".join(danger)
          + ". Destructive-shape command - confirm intent before running; the operator can "
            "pre-approve via ZT_ROE_OK=1 or the engagement's .roe-ok marker.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
