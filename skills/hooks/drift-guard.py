#!/usr/bin/env python3
"""PreToolUse(Bash) hook: nudge the offensive driver back into view (anti-drift, advisory-only).

The proven failure: the deterministic driver (scripts/offensive.py) is advisory BY
INVOCATION - it only enforces its gates on turns the agent chooses to run it, so under
momentum the agent walked away from `offensive.py next` in 90 seconds and free-handed a whole
box via 85 raw `bash /root/vm.sh` exploit calls. This hook pulls the agent back: on an
exploit-shaped Bash command during an active campaign, if the agent is OFF-BOARD (running an
exploit/scan binary the driver never emitted, and the board is NOT empty), it ESCALATES a
counter and ADVISES the agent back to the driver.

ESCALATE-TO-DENY (approach B, board-bypass drift ~17x across 2 months): advice alone was
ignored for whole boxes, so a REPEAT PATTERN now denies. Streak 1-3 (then every 25th) stays
advisory - a probe is not a pattern - but streak >= _DENY_STREAK exploit-shaped calls with
ZERO driver contact is no longer a judgement call, it DENIES naming the driver step that
clears it. Post-foothold boxes never deny (the board is a pre-foothold planning aid), and the
shared escape hatch applies: skills/hooks/.enforce-off downgrades the deny to advisory.

Policy:
  - off_board_streak N -> INJECT an advisory warning ("run offensive.py next; N calls since")
    for streak 1,2,3 then every 25th (the counter is kept and reported every time)
  - off_board_streak >= _DENY_STREAK (and not post-foothold, and enforcing) -> DENY
  - identical off-board command re-run >= _RETRY_DENY times (retry ring, reset by driver
    contact) -> DENY (loop-break): change one variable / close the row dead / run the driver
  - every _DENY_TOTAL_ESCALATE cumulative denies the deny message grows a Skill(redteamlead)
    escalation (repeating the same lane that keeps denying is the doom loop)
  - `offensive.py next|board|done|note|init|foothold` seen in the command -> reset the streak to 0
  - an OPEN lane line (`in flight`, delegate contract) in log.md is driver contact too:
    calls during lane flight (the lane's own + brain support probes) never count as
    drift; the identical-retry ring still accumulates mid-lane

ON-BOARD (allowed, never counted) when EITHER:
  - the command's exploit/scan binary is in .offensive.json emitted bins (the driver told them to
    run it), OR
  - the board is empty/uncounted (generic tech -> the index yields 0 rows -> the driver
    has nothing to serve, so there is nothing to hold the agent to). Fail-open by design.

EXPLOIT-SHAPED = handroll.classify() fires (a substitutable hand-rolled request loop) OR the
command mentions a network/scan/exploit binary (NET_BINS). NET_BINS is word-searched over the
WHOLE command string, not just the leading token, so `bash /root/vm.sh 'nmap ...'` - the exact
wrapper the reference failure used - is caught by the inner binary.

SAFETY (this hook only advises, but stays fail-open anyway - never let a hook bug break a turn):
  - Fail-OPEN everywhere: no engagement / no .offensive.json / pass < 5 / unparseable / any
    exception -> exit 0, allow. A hook bug never blocks a command.
  - pass >= 5 gate: only fires once the board is actually driving (passes 0-4 are pre-board recon
    where free exploration is expected).
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

# Network/scan/exploit binary set = the driver's own NET_BINS (drift pre-filter). Import the shared
# _netbins module so this PreToolUse hook never parses the driver per call;
# fall back to a literal mirror if the module can't be imported.
try:
    from _netbins import NET_BINS
except Exception:
    NET_BINS = {"curl", "wget", "nmap", "rustscan", "dnsx", "httpx", "nc", "ncat", "ffuf",
                "feroxbuster", "gobuster", "sqlmap", "nuclei", "nxc", "netexec", "katana",
                "gau", "subfinder", "amass", "nikto", "wpscan", "dig", "openssl", "hydra"}
try:
    from handroll import classify as _handroll_classify
except Exception:
    def _handroll_classify(_cmd):
        return False, None, ""

HEAVY_SCANNERS = {"ffuf", "feroxbuster", "gobuster", "wpscan", "nuclei", "dirb", "katana", "nikto"}
_SCAN_WINDOW = 180          # seconds: a 2nd heavy scanner launched within this is "concurrent"
_DENY_STREAK = 6            # off-board calls with zero driver contact before the deny fires
_RETRY_DENY = 3             # identical off-board command re-runs before the loop-break deny
_DENY_TOTAL_ESCALATE = 20   # cumulative denies before the message names a way out (RTL)


def _save_state(sp, st):
    """Atomic save (tmp + os.replace): the old truncate-then-write, killed mid-write
    on /mnt/c, left .offensive.json unparseable -- which silently disabled this guard
    (every later run exits at the json.load) for the rest of the engagement."""
    tmp = sp + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(st, fh, indent=1)
        os.replace(tmp, sp)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _enforcing():
    """Same escape hatch as scope-guard: skills/hooks/.enforce-off downgrades the deny to
    advisory. ENFORCE_OFF_MARKER lets parallel test workers point at a tmp file."""
    marker = os.environ.get("ENFORCE_OFF_MARKER") or os.path.join(HERE, ".enforce-off")
    return not os.path.exists(marker)
# Own regex, independent of NET_BINS: dirb (and any future HEAVY_SCANNERS entry not in NET_BINS)
# must still be caught even when it's the ONLY thing in the command (not otherwise exploit-shaped).
_HEAVY_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, HEAVY_SCANNERS), key=len, reverse=True)) + r")\b")

_BIN_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, NET_BINS), key=len, reverse=True)) + r")\b")
_DRIVER_RE = re.compile(
    r"offensive\.py\s+(?:-{1,2}[\w-]+(?:\s+[^\s-][^\s]*)?\s+)*"
    r"(?:next|board|done|note|init|foothold)\b")
# A HAND-WRITTEN exploit run as a script/interpreter, or an interactive reverse-shell driver:
# exploit-shaped even though it touches no NET_BIN (the exact gap the post-mortem free-handed
# through - `bash /root/vm.sh 'python3 exp.py'`). Deliberately does NOT match the `bash /root/vm.sh`
# transport wrapper itself (that is how EVERY VM command runs); it matches the INNER interpreter.
_INTERP_RE = re.compile(
    r"\bpython3?\s+(?:-c\b|\S+\.py\b)|\bphp\s+(?:-r\b|\S+\.php\b)|\bruby\s+-e\b|\bperl\s+-e\b"
    r"|\bvm-rsh\.sh\b|\bwin-rsh\.sh\b|(?:^|\s)\./\S+\.(?:py|sh|elf)\b")


# Framework/dev commands are NOT engagement drift: running tests, the driver itself, or editing the
# vault's own trees while an engagement happens to be active must never fire the guard (observed:
# `pytest` misfiring during harness development). Mirrors recon-capture.py's framework-meta guard.
try:
    from _meta import _DEV_META as _META_RE
except Exception:
    _META_RE = re.compile(
        r"\bpytest\b|\bpy_compile\b|-m\s+pytest|offensive\.py|offensive-doctor|check-hooks|"
        r"\bgit\b|install-hooks|new-engagement|"
        r"scripts/(?:offensive|check|tool|playbook|wiki|gen_|build_|lint|eval_|status|next_move)|"
        r"tests/|skills/hooks|setup/", re.IGNORECASE)

try:
    import _cmdnorm
except Exception:
    _cmdnorm = None

# Command-position lead-in for the driver: `<path>/offensive.py ...` itself or its
# python interpreter (`python3 scripts/offensive.py next`). A command merely MENTIONING
# the driver (`echo run offensive.py next`) starts with echo/... and is not driver contact.
_DRV_LEAD = re.compile(r"^(?:(?:sudo|env|time|nice|nohup)\s+)*(?:.*/)?(?:offensive\.py|python3?)\b")


def _retry_key(active):
    """Stable hash of the whitespace-squeezed normalized command (segment order kept).
    Feeds the identical-retry detector: same key 3x = the model is re-firing one
    command, which no amount of advice fixes - it needs the loop-break deny."""
    norm = " ".join(" ".join(active.split()).split())
    if _cmdnorm is not None:
        try:
            norm = " ".join(_cmdnorm.segments(active))
        except Exception:
            pass
    # strip quote chars: the model re-fires the SAME command with cosmetic quoting
    # variance (`curl host` vs `curl 'host'`) and the ring never accumulates toward
    # the 3x deny. Digits/ports stay (iterating a port list is a real new attempt).
    norm = norm.replace("'", "").replace('"', "")
    return hashlib.sha1(norm.encode("utf-8", "ignore")).hexdigest()[:12]


def _driver_called(cmd):
    """True when a normalized SEGMENT invokes the driver in command position. The old
    whole-string `_DRIVER_RE.search(cmd)` let an echo/grep string mentioning
    `offensive.py next` reset the off-board streak without any real driver contact."""
    if _cmdnorm is None:
        return bool(_DRIVER_RE.search(cmd))
    return any(_DRV_LEAD.match(s) and _DRIVER_RE.search(s)
               for s in _cmdnorm.segments(cmd))


def _active_segs(cmd):
    """Segments that are NOT framework-meta. The old whole-string `_META_RE` early-return
    exempted MIXED commands entirely (`git status && nmap <target>` never counted the
    nmap); per-segment, only the meta part is exempt and engagement work still counts.
    Returns None on _cmdnorm absence (caller falls back to whole-string behavior)."""
    if _cmdnorm is None:
        return None
    return [s for s in _cmdnorm.segments(cmd) if not _META_RE.search(s)]


# B5 (pass 14): reader-lead segments (cat/grep/rg/... ) are file READS, not invocations --
# their arguments are filenames whose text must not count as a fired binary (observed: 22 false
# flags off `cat nmap-notes.md` alone). Exec-capable walkers (find -exec, xargs, awk system(),
# sed e) are deliberately NOT readers: their arguments can still execute.
_READER_LEAD = re.compile(
    r"^(?:sudo\s+)?(?:cat|grep|rg|ls|head|tail|echo|less|more|wc|sort|uniq|file|jq|strings|zcat|bat)\b")


def _bins_in(cmd):
    """Exploit/scan binaries mentioned anywhere in the command string (whole-string search, so a
    binary inside a `bash vm.sh '<inner>'` wrapper is still seen -- the unwrapped inner command
    is its own segment). Reader segments are skipped (see _READER_LEAD); a WRAPPER segment whose
    inner command was already unwrapped is skipped too (its quoted text is a filename to the
    wrapper, scanned once as the inner segment). Falls back to the whole-string scan when the
    segmenter is absent. Wrappers the segmenter does NOT unwrap (vm-ssh.sh) keep their whole-
    segment scan, unchanged."""
    if _cmdnorm is None:
        return set(_BIN_RE.findall(cmd or ""))
    inners = [i.strip() for i in _cmdnorm.inner(cmd or "") if i.strip()]
    found = set()
    for seg in _cmdnorm.segments(cmd or ""):
        s = seg.strip()
        # skip the WRAPPER segment (carries the inner as quoted text); an unwrapped
        # inner segment IS the inner (`i in s` matched it too and zeroed the whole
        # scan -- vm.sh-wrapped scans counted no bins at all, audit 2026-09-10)
        if _READER_LEAD.match(s) or any(i != s and i in s for i in inners):
            continue
        found |= set(_BIN_RE.findall(s))
    return found


def _scanner_cap(d, cmd):
    """Advise on a 2nd HEAVY scanner within _SCAN_WINDOW on ANY engagement type -- a fragile/
    rate-limited target is not ctf-exclusive (W7-4: the corpus shows the same self-inflicted-ban
    pattern on pentest/bb targets too, including one where a scope.md-documented throttle note
    still didn't prevent a recurring ban without a live check). Records each heavy-scanner launch
    to .scan-launches.jsonl; if a prior launch is < _SCAN_WINDOW old, returns a reason string (the
    caller always advises, never denies, on it). Records this launch and returns None (allow) only
    when there is no prior in-window launch."""
    import time
    heavy = set(_HEAVY_RE.findall(cmd or ""))
    if not heavy:
        return None
    p = os.path.join(d, ".scan-launches.jsonl")
    now = time.time()
    prior = None
    try:
        for ln in open(p, encoding="utf-8"):
            try:
                e = json.loads(ln)
            except Exception:
                continue
            if now - float(e.get("ts", 0)) < _SCAN_WINDOW:
                prior = e
    except Exception:
        pass
    if prior:
        age = int(now - float(prior["ts"]))
        return ("a scan is already running (`%s` launched %ds ago) - serialize on this target, "
                "or drop threads to -t<=20. Wait for it or kill it first." % (prior.get("tool", "?"), age))
    try:                                              # record this launch, then allow
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now, "tool": sorted(heavy)[0]}) + "\n")
    except Exception:
        pass
    return None


# T5.2 self-kill footgun: `pkill -f bash` / `killall nc` / `pkill python` matches the operator's OWN
# reverse shell or session and kills it (a recurring shell-loss drift across several boxes). Advisory only
# (never deny - the operator may genuinely want it), fires on a shell/reverse-shell process name in a
# pkill/killall. The sibling footgun (Ctrl-C on an unstabilized shell) is a terminal signal no hook
# sees, so it stays CLAUDE.md prose. Word-list kept to actual shell/relay binaries -> low false-fire.
_SELFKILL_RE = re.compile(
    r"\b(pkill|killall)\b[^|;&\n]*\b(ba?sh|nc|ncat|netcat|socat|python\d?|perl|php|rlwrap|/dev/tcp)\b",
    re.IGNORECASE)


def _selfkill_advisory(cmd):
    """Advisory string when a pkill/killall could self-match the operator's own shell, else None."""
    if not _SELFKILL_RE.search(cmd or ""):
        return None
    return ("SELF-KILL RISK: `pkill`/`killall` on a shell/relay name (bash/sh/nc/python/socat...) "
            "will also match your OWN reverse shell or session and kill it (recurring footgun). Kill "
            "by PID (`kill <PID>`, get it from `ps`) or bracket the pattern to exclude your shell. If "
            "the next command hangs or drops to the attacker prompt, the shell died - re-pop it.")


# P15 (clone pattern: reservedShortcuts.ts DOA table): commands the transport structurally
# kills, checked BEFORE the fire instead of discovered after a timeout. A long foreground
# scan through the direct vm.sh/vm-ssh.sh bridge is dropped at ~2min (exit 255, no output),
# burning the call and reading as a dead target. Detached forms (vm-scan.sh tmux tab /
# nohup / background &) are the sanctioned paths and never fire.
_BRIDGE_RE = re.compile(r"(?<![\w-])(?:vm|vm-ssh|win-vm)\.sh\b")
_DETACHED_RE = re.compile(r"\b(?:nohup|tmux|disown|vm-scan\.sh|vm-rsh\.sh|win-rsh\.sh)\b")
# single `&` that is a background OPERATOR: at least one flank is whitespace/edge (an `&`
# glued between non-space chars is data: `?a=1&b=2` in a URL, quoted or not), never part
# of `&&`, and never fd plumbing (`2>&1`, `&>`). Quote-blanking cannot work here: the
# transport wrapper's OWN quotes carry the operator (`vm.sh 'longcmd ... &'`).
_BG_RE = re.compile(r"(?<!\S)&(?![>&\d])|(?<![&>\d])&(?!\S)")
# nmap only counts with a slow-shape marker (a `nmap -sV -p 80` finishes in seconds); the
# rest are slow essentially always on real wordlists/rules.
_SLOW_RE = re.compile(
    r"\b(?:feroxbuster|ffuf|nuclei|hashcat|john|sqlmap|gobuster|dirb|wpscan|nikto|amass|"
    r"subfinder|masscan|crackmapexec|nxc)\b"
    r"|nmap[^|;&\n]*?(?:-p-|-p\s*\d+-|-sU|--min-rate|-T5)")


_DOA_MSG = ("TRANSPORT DOA (advisory): a long foreground command through the direct "
            "vm.sh/vm-ssh.sh bridge is dropped at ~2min (exit 255, no output) - the scan "
            "never completes and the empty output reads as a dead target. Run it detached: "
            "`bash scripts/vm-scan.sh <eng> <target> '<cmd>'` (named tmux tab, gets a recon "
            "card) or `nohup <cmd> >/tmp/out 2>&1 &` + poll for the DONE marker.")


def _bridge_doa_advisory(cmd):
    """Advisory string when a long FOREGROUND command goes through the direct VM bridge
    (the transport drops it at ~2min), else None. Advisory-only: a deliberate foreground
    run of a fast-enough scan is the operator's call.
    Per-SEGMENT (audit 2026-09-10): the bridge marker and the slow-shape marker must
    co-occur in ONE executable segment -- the old whole-string pair let an echo/grep
    text mentioning vm.sh plus an nmap word elsewhere false-fire. Reader segments are
    skipped; a vm.sh wrapper segment carries its quoted inner command, so a real bridge
    run pairs inside the wrapper segment itself. Detached/background markers are still
    checked whole-string (backgrounding is a property of the whole command)."""
    c = cmd or ""
    if _DETACHED_RE.search(c) or _BG_RE.search(c):
        return None
    if _cmdnorm is None:
        segs = [c]
    else:
        segs = [s.strip() for s in _cmdnorm.segments(c)
                if s.strip() and not _READER_LEAD.match(s.strip())]
    if not any(_BRIDGE_RE.search(s) and _SLOW_RE.search(s) for s in segs):
        return None
    return _DOA_MSG


# --- advisory throttle (A1/A2/A3): a legitimately off-board run (writeup-driven, or post-foothold
#     manual exploitation the driver can't plan) was getting the SAME nudge injected on every call
#     (observed: 184 identical fires in one box = pure token noise). The streak is still COUNTED
#     every time (telemetry/eval-metrics accuracy); only the context INJECTION is gated.
_STATUS_RE = re.compile(r"^##\s*status:\s*(solved|owned|rooted|complete)\b", re.I | re.M)
_FOOTHOLD = {"foothold", "user", "root", "owned", "system", "domain-admin", "da"}


def _state_text(d):
    try:
        return open(os.path.join(d, "state.md"), encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""


def _post_foothold(d):
    """True once state.md's host table shows an access cell at foothold-or-better. The board is a
    PRE-foothold planning aid; post-foothold manual exploitation should not be nagged repeatedly."""
    try:
        import _engagement                       # imported here: main()'s import is local-scoped
        for r in _engagement._parse_table(os.path.join(d, "state.md")):
            if (r.get("access") or "").strip().lower() in _FOOTHOLD:
                return True
    except Exception:
        pass
    return False


def _lane_in_flight(d):
    """True when log.md still holds an OPEN `in flight` lane line (delegate's lane-line
    contract). lane_validate owns the parse (status.py + close-out share it) so every
    consumer agrees on what 'open' means; fail-open False on any error."""
    try:
        import lane_validate
        return bool(lane_validate.lane_lines(d))
    except Exception:
        return False


def _should_advise(streak, post_foothold):
    """Gate the context injection (never the count). Post-foothold: one reminder then silent. Else:
    streak 1,2,3 then every 25th - keeps the early signal, kills the ~180x repeat that was noise."""
    if post_foothold:
        return streak == 1
    return streak in (1, 2, 3) or streak % 25 == 0


def _advise_probe(cmd):
    """Executable, non-framework text for the always-on advisories: joined segments that
    are neither framework-meta (in a MIXED command only the meta part is exempt; the old
    whole-string check exempted `git status && pkill -f bash` entirely) nor reader-leads
    (an echo/grep string MENTIONING pkill or vm.sh is not an invocation). Whole string
    when the segmenter is absent; '' = nothing to check."""
    if _cmdnorm is None:
        return "" if _META_RE.search(cmd or "") else (cmd or "")
    return "\n".join(s.strip() for s in _cmdnorm.segments(cmd or "")
                     if s.strip() and not _META_RE.search(s)
                     and not _READER_LEAD.match(s.strip()))


_STAMP_TTL = 900     # one advisory injection per 15 min per kind (audit 2026-09-10): the
                     # DOA/selfkill advisories returned early and re-fired on EVERY
                     # matching call -- a retry loop over a DOA shape flooded context AND
                     # skipped the off-board streak below (a loop the ring never saw).


def _stamp_fresh(d, name):
    """True (and touches the stamp) when an advisory of this kind may inject now; False
    while a fresh stamp stands. Per-engagement; no engagement -> always True (no stamp
    file to write). Pattern = tool-telemetry's .ctx-low-stamp."""
    if not d:
        return True
    p = os.path.join(d, name)
    import time
    try:
        if time.time() - os.path.getmtime(p) < _STAMP_TTL:
            return False
    except OSError:
        pass
    try:
        open(p, "w").close()
    except OSError:
        pass
    return True


def _budget_deny(d):
    """Engagement budget hard-stop (opt-in via ZT_MAX_ENG_USD): spend_usd over cap in
    .metrics.json (written by tool-telemetry) -> deny further Bash calls. Bash-only
    ceiling: other tools still run; the full budget picture lives in the transcript.
    Returns True when it printed the deny."""
    try:
        cap = float(os.environ.get("ZT_MAX_ENG_USD", "") or 0)
    except ValueError:
        cap = 0.0
    if cap <= 0 or not _enforcing():
        return False
    try:
        spent = float(json.load(open(os.path.join(d, ".metrics.json"),
                                     encoding="utf-8")).get("spend_usd", 0) or 0)
        if spent > cap:
            try:
                import _telemetry
                _telemetry.hook("drift-guard", action="deny")
            except Exception:
                pass
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason":
                    ("BLOCKED by harness enforcement: engagement spend $%.2f exceeds "
                     "ZT_MAX_ENG_USD=$%.2f. Stop and report to the operator; raise "
                     "ZT_MAX_ENG_USD to continue." % (spent, cap)),
            }}))
            return True
    except Exception:
        pass                                       # no metrics file / bad json -> no stop
    return False


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return
    if data.get("tool_name") != "Bash":
        return
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not cmd:
        return

    import _engagement
    d = _engagement.active_dir()

    # Budget deny FIRST, above the advisory block: an advisory that returns early
    # bypassed the deny for exactly the long DOA-shaped commands that burn spend
    # (audit 2026-09-10).
    if d and _budget_deny(d):
        return

    # self-kill / transport-DOA advisories (any time, before the campaign gates). The probe
    # is per-segment (mixed commands: only the meta part exempt); injection is stamp-gated
    # (15 min per kind) and a stamped-out advisory FALLS THROUGH to the campaign logic
    # below so the off-board streak / retry ring still counts the call.
    _probe = _advise_probe(cmd)
    if _probe:
        _sk = _selfkill_advisory(_probe)
        _msg = _sk or _bridge_doa_advisory(cmd)
        if _msg:
            _stamp = ".selfkill-stamp" if _sk else ".doa-stamp"
            if _stamp_fresh(d, _stamp):
                try:
                    import _telemetry
                    _telemetry.drift("drift-guard", "advisory " + _stamp.lstrip("."))
                except Exception:
                    pass
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                      "additionalContext": _msg}}))
                return

    if not d:
        return
    sp = os.path.join(d, ".offensive.json")
    if not os.path.isfile(sp):
        return                                    # no driver state -> nothing to enforce
    try:
        st = json.load(open(sp, encoding="utf-8"))
    except Exception:
        try:      # corrupt state silently disabled this guard for whole boxes; record it
            import _telemetry
            _telemetry.log_event("hook", d=d, hook="drift-guard",
                                 error=".offensive.json unparseable - drift-guard disabled")
        except Exception:
            pass
        return

    # A driver call resets the streak (the agent came back to the board). Command-position
    # only (_driver_called): an echo/grep string mentioning the driver is not contact.
    # The retry RING is only cleared when the driver moved the board (a different row
    # served than last contact): `tool -> next(same row) -> tool` launders the ring on
    # every serve cycle, so an identical grind never accumulates to the 3x deny
    # (driver audit, 2026-09-10).
    if _driver_called(cmd):
        new_row = (st.get("last_move") or {}).get("row")
        same_row = new_row is not None and new_row == st.get("_driver_row")
        complied = bool(st.get("off_board_streak")) or bool(st.get("retry_counts"))
        changed = complied or (st.get("_driver_row") or "") != (new_row or "")
        if changed:
            st["off_board_streak"] = 0
            if not same_row:
                st["retry_counts"] = {}            # board advanced = a re-plan; identical
                                                   # re-runs after it are new attempts
            st["_driver_row"] = new_row
            _save_state(sp, st)
            if complied:
                # advice was outstanding and the agent came back to the driver: the one
                # "advisories acted on" signal eval_metrics reports (audit rec 3).
                try:
                    import _telemetry
                    _telemetry.log_event("advice", hook="drift-guard", action="complied")
                except Exception:
                    pass
        return

    # Framework/dev commands are not engagement drift -- but only per-SEGMENT: in a mixed
    # command (`git status && nmap <target>`) the nmap segment still counts.
    act = _active_segs(cmd)
    if act is not None:
        if not act:
            return                                # every segment is framework-meta
        active = "\n".join(act)
    else:
        if _META_RE.search(cmd):
            return                                # framework/dev command, not engagement drift
        active = cmd
    if st.get("pass", 0) < 5:
        return                                    # pre-board recon: free exploration expected

    if _STATUS_RE.search(_state_text(d)):
        return                                    # A2: engagement SOLVED -> board is moot, stay silent

    cmd_bins = _bins_in(active)
    exploit_shaped = bool(cmd_bins) or _handroll_classify(active)[0] or bool(_INTERP_RE.search(active))

    # Scanner-cap runs on ANY heavy-scanner mention, independent of exploit_shaped/NET_BINS, so a
    # bare `dirb ...` (not in NET_BINS, and not otherwise exploit-shaped) still hits it.
    if _HEAVY_RE.search(cmd):
        _deny = _scanner_cap(d, cmd)
        if _deny:
            try:
                import _telemetry
                _telemetry.hook("drift-guard", action="advise-scanner")
            except Exception:
                pass
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                  "additionalContext": "SCANNER-CAP (advisory): " + _deny}}))
            return

    if not exploit_shaped:
        return                                    # not an exploit/scan/interpreter call -> ignore

    # ON-BOARD escape 1: no OPEN ([ ]/[~]) rows -> empty board (generic tech) OR end-of-board.
    # Either way the driver has nothing to hold the agent to, so allow (fail-open). Checking OPEN
    # status (not mere presence) stops end-of-board verification probes from being false-blocked.
    # B6 (pass 14): parse the `### 4a` board SLICE, not the file's first table -- an
    # agent-added table above the board (a recon-finding matrix) otherwise becomes "the
    # board": its rows neither hold the cursor nor whitelist the driver's real tools.
    # offensive.read_board is the same tested reader `next` uses; fail back to the old
    # whole-file parse if the import is unavailable.
    try:
        _sc = os.path.join(os.path.dirname(os.path.dirname(HERE)), "scripts")
        if _sc not in sys.path:                  # the scripts/ that ships with this hook
            sys.path.insert(0, _sc)
        import offensive
        rows = offensive.read_board(d) \
            or _engagement._parse_table(os.path.join(d, "Approach.md"))
    except Exception:
        rows = _engagement._parse_table(os.path.join(d, "Approach.md"))
    open_rows = [r for r in rows if (r.get("status") or "[ ]").strip() in ("[ ]", "[~]", "")]
    if not open_rows:
        return
    # ON-BOARD escape 2: the binary is a tool of a currently-OPEN row, or one the driver emitted.
    # Deriving the whitelist from OPEN-row tools (not only the append-only emitted_bins) stops the
    # guard eroding as a long campaign appends every tool to emitted_bins.
    onboard = set(st.get("emitted_bins") or [])
    for r in open_rows:
        t = (r.get("tool") or "").strip().lower()
        if t:
            onboard.add(t)
    if cmd_bins & onboard:
        return

    # OFF-BOARD: escalate. An OPEN lane (delegate's `in flight` line in log.md) is
    # driver contact: the lane's checklist was authored from `next`, so calls during
    # flight (the lane's own and the brain's support probes) are planned work, not
    # streak drift (observed: a lane denied pre-flight on streak inherited from earlier
    # lanes' calls). A STALE open line keeps the exemption until closed; status.py ages
    # it and close-out sweeps it. The retry ring below STILL counts: a lane re-firing
    # one identical command is the same doom loop whoever ran the first one.
    lane_open = _lane_in_flight(d)
    if lane_open and st.get("off_board_streak"):
        st["off_board_streak"] = 0
    streak = int(st.get("off_board_streak", 0) or 0) + (0 if lane_open else 1)
    st["off_board_streak"] = streak

    # Identical-retry ring (doom-loop break): re-firing the SAME unchanged command is a loop,
    # not exploration, and no advisory fixes it. Count per normalized key (MRU-ordered dict,
    # pruned to 32); >= _RETRY_DENY identical fires -> the loop-break deny below.
    rk = _retry_key(active)
    ring = st.get("retry_counts") or {}
    ring[rk] = ring.pop(rk, 0) + 1
    while len(ring) > 32:
        ring.pop(next(iter(ring)))
    st["retry_counts"] = ring
    _save_state(sp, st)

    off = ", ".join(sorted(cmd_bins)) or "hand-rolled request loop"
    if not lane_open:
        try:
            import _telemetry
            _telemetry.drift("drift-guard", "off-board streak %d (%s)" % (streak, off))
        except Exception:
            pass

    # ESCALATE-TO-DENY, most specific trigger first:
    #   1. IDENTICAL-RETRY (loop-break): the same unchanged command fired >= _RETRY_DENY
    #      times. Names the exact loop and the three ways out.
    #   2. REPEAT PATTERN: streak >= _DENY_STREAK exploit-shaped calls, zero driver contact,
    #      board has open rows.
    # Post-foothold never denies (see module docstring). With enforcement off a would-be
    # block prints as an UN-THROTTLED advisory (the operator must see what would have been
    # blocked), instead of being swallowed by the throttle below.
    post_fh = _post_foothold(d)
    retries = int(ring.get(rk, 0) or 0)
    # The retry deny fires regardless of lane state (a lane re-firing one command is the
    # same doom loop); the STREAK deny only when no lane is open (lane flight = contact).
    deny_wanted = not post_fh and (retries >= _RETRY_DENY
                                   or (streak >= _DENY_STREAK and not lane_open))

    def _deny(reason):
        st["deny_total"] = int(st.get("deny_total", 0) or 0) + 1
        _save_state(sp, st)
        try:
            import _telemetry
            _telemetry.hook("drift-guard", action="deny")
        except Exception:
            pass
        if st["deny_total"] % _DENY_TOTAL_ESCALATE == 0:
            reason += ("\n\nThis is deny %d with no lane change - stop iterating solo: call "
                       "`Skill(redteamlead)` for a ranked re-plan." % st["deny_total"])
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))

    if deny_wanted and _enforcing():
        if retries >= _RETRY_DENY:
            _deny(
                "BLOCKED by harness enforcement (doom-loop break):\n"
                "- this exact command has now been run %d times unchanged. Re-running it "
                "identically cannot produce a different result.\n"
                "- do NOT re-attempt the exact same call. Change one variable, close the row "
                "dead (`Deadends.md` line + `python3 scripts/offensive.py done <row> --dead`), "
                "or run `python3 scripts/offensive.py next` to switch vector.\n\n"
                "(False block? ask the OPERATOR to create skills/hooks/.enforce-off to "
                "downgrade enforcement to "
                "advisory.)" % retries)
        else:
            _deny(
                "BLOCKED by harness enforcement:\n- off-board: %d exploit-shaped calls since "
                "the last driver step (%s not emitted by the board). The offensive driver is "
                "authoritative. Run `python3 scripts/offensive.py next` to get the required "
                "row + tool (this also resets the counter), or `offensive.py note` if this is "
                "a legitimate off-board lane, then re-run the command.\n\n"
                "(False block? ask the OPERATOR to create skills/hooks/.enforce-off to "
                "downgrade enforcement to "
                "advisory.)" % (streak, off))
        return

    if lane_open:
        return

    # THROTTLE the context injection (the count above still fired for eval accuracy).
    if not deny_wanted and not _should_advise(streak, post_fh):
        return
    if deny_wanted:
        # not enforcing (.enforce-off): the would-be deny prints as an UN-THROTTLED
        # advisory so the operator sees what would have blocked -- capped at 5 fires so
        # a long off-board run under the hatch cannot flood context either.
        st["soft_deny_total"] = int(st.get("soft_deny_total", 0) or 0) + 1
        _save_state(sp, st)
        if st["soft_deny_total"] > 5:
            return

    try:
        import _telemetry
        _telemetry.hook("drift-guard", action="advise")
    except Exception:
        pass

    warn = (" This exact command has been run %d times; one more identical run is BLOCKED - "
            "change a variable or close the row dead." % retries
            ) if retries == _RETRY_DENY - 1 else ""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": (
            "DRIFT (off-board, streak %d): %d exploit-shaped call(s) since the last driver step "
            "(%s not emitted by the board). The offensive driver is authoritative - run "
            "`python3 scripts/offensive.py next` to get the required row + tool before "
            "continuing, and `done` each row as it lands.%s" % (streak, streak, off, warn)),
    }}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
