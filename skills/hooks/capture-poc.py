#!/usr/bin/env python3
"""PostToolUse(Bash): append every meaningful command + its output to
targets/<eng>/poc/cmdlog/<tool>.md, grouped by the primary binary, so the operator has a readable,
per-tool record of exactly what ran and what came back - without any manual capture step.

Example: `bash /root/vm.sh 'nmap -sCV 10.1.1.5'` appends to poc/cmdlog/nmap.md:

    ## 2026-08-10 09:06:12

    ```
    nmap -sCV 10.1.1.5
    ```

    ```
    PORT   STATE SERVICE VERSION
    22/tcp open  ssh     OpenSSH 7.6p1 ...
    ```

Grouped by the INNER binary (via tool-telemetry._binaries), so vm.sh-wrapped scans land under the
real tool. Skips framework/dev commands (pytest, offensive.py, git, editing the vault) and empty
output. Fail-open and silent; capped so one runaway scan can't bloat the file. Records into
`cmdlog/` (not poc/ root) so it never mixes with curated PoC screenshots.
"""
import base64
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MAX_OUT = 40000        # per-entry output cap (chars); a huge scan is truncated, not dropped
try:
    from _meta import _DEV_META as _SHARED_DEV_META
except Exception:
    _SHARED_DEV_META = re.compile(
        r"\bpytest\b|\bpy_compile\b|-m\s+pytest|offensive\.py|offensive-doctor|check-hooks|"
        r"\bgit\b|install-hooks|new-engagement|"
        r"scripts/(?:offensive|check|tool|playbook|wiki|gen_|build_|lint|eval_|status|next_move)|"
        r"tests/|skills/hooks|setup/", re.IGNORECASE)
# This file's own extra exemptions (capture.sh's own invocations, eval_metrics.py -- neither is
# target activity) ORed onto the shared pattern.
_META_RE = re.compile(_SHARED_DEV_META.pattern + r"|capture\.sh|\beval_metrics\b", re.IGNORECASE)

try:
    from tool_telemetry import _binaries
except Exception:
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "tool_telemetry", os.path.join(HERE, "tool-telemetry.py"))
        _tt = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_tt)
        _binaries = _tt._binaries
    except Exception:
        # fail open: no grouping, but the hook lives (an import-time crash here killed
        # capture entirely - hook failure-path audit, 2026-09-10)
        _binaries = lambda *_a, **_k: []


def _response_text(data):
    r = data.get("tool_response")
    if r is None:
        return ""
    if isinstance(r, str):
        return r
    if isinstance(r, dict):
        for k in ("stdout", "output", "content", "stderr"):
            v = r.get(k)
            if isinstance(v, str) and v.strip():
                return v
    try:
        return json.dumps(r)
    except Exception:
        return str(r)


def _unwrap(cmd):
    """The INNER command of a `bash /root/vm.sh '<inner>'` (or vm-rsh/win-rsh) transport, so the
    entry is grouped by the real tool (nmap) not the wrapper (bash)."""
    m = re.search(r"(?:vm\.sh|vm-rsh\.sh|win-rsh\.sh)\b[^'\"]*['\"](.+)['\"]\s*$", cmd or "", re.S)
    return m.group(1) if m else (cmd or "")


# Pure shell/navigation builtins that are never the point of a step -- stripped when they are a
# whole top-level segment (but NOT when they feed a pipeline, e.g. `echo <payload> | nc host port`,
# whose real command is the pipe SINK, not the echo).
_NOISE_BINS = {"cd", "ls", "pwd", "mkdir", "clear", "export", "true", ":", "echo", "printf"}
# a local read of vault/engagement state (not target loot) -> noise. A remote `cat /etc/shadow`
# has no targets//.md/ClaudeBrain marker and survives.
_LOCAL_READ_RE = re.compile(r"^(?:cat|head|tail|less|bat|wc)\b.*(?:targets/|\.md\b|/ClaudeBrain/)")
_B64_PIPE_RE = re.compile(r"^echo\s+([A-Za-z0-9+/=]+)\s*\|\s*base64\s+-d\s*\|\s*(.+)$", re.S)
# a shell compound statement (loop/conditional) is ONE command -- its internal `;` must not be
# split into separate lines. A false positive only makes cleanup MORE conservative (show the whole
# command un-split), which is the safe direction.
_COMPOUND_RE = re.compile(r"\bdone\b|\bthen\b|\bfi\b|\besac\b|;\s*do\b|^\s*(?:for|while|until|if|case)\b")


def _split_top_level(cmd):
    """Split on top-level `;` `&&` `||` that are NOT inside single/double quotes. A `|` pipe is
    kept intact inside a segment. Fail-soft: on any confusion the worst case is one un-split
    segment, which is still logged (never dropped)."""
    segs, buf, quote, i, n = [], [], None, 0, len(cmd or "")
    while i < n:
        c = cmd[i]
        if quote:
            buf.append(c)
            if c == quote:
                quote = None
            i += 1
        elif c in ("'", '"'):
            quote = c
            buf.append(c)
            i += 1
        elif c == ";":
            segs.append("".join(buf)); buf = []; i += 1
        elif c in "&|" and i + 1 < n and cmd[i + 1] == c:      # && or ||
            segs.append("".join(buf)); buf = []; i += 2
        else:
            buf.append(c); i += 1
    segs.append("".join(buf))
    return [s.strip() for s in segs if s.strip()]


def _effective_bin(seg):
    """The leading word of a pipeline's SINK (last `|` stage) -- the command that actually does the
    work. `echo X | base64 -d | nc h p` -> `nc`. Naive `|` split is fine here: a mis-split only
    keeps a segment (the safe direction)."""
    stage = (seg.rsplit("|", 1)[-1]).strip()
    return (stage.split() or [""])[0].strip("(){}").lower()


def _decode_b64_pipe(seg):
    """`echo <literal-b64> | base64 -d | bash|sh` -> the decoded shell command (the common
    download/IEX cradle), so the real command shows instead of an opaque blob. A `$VAR`-based b64
    is not a literal -> left untouched (undecodable by design; the value isn't in the string)."""
    m = _B64_PIPE_RE.match(seg.strip())
    if not m:
        return seg
    b64, rest = m.group(1), m.group(2).strip()
    if (rest.split() or [""])[0] not in ("bash", "sh"):
        return seg
    try:
        dec = base64.b64decode(b64).decode("utf-8", "replace").strip()
    except Exception:
        return seg
    return dec or seg


def _clean_for_display(cmd):
    """Turn the raw issued command into the REAL command(s) for the cmdlog: strip the vm.sh/rsh
    transport, decode literal base64 cradles, and drop top-level noise segments (cd/echo banners,
    local state reads). Returns '' when nothing meaningful remains (all transport/noise) so the
    caller skips the entry entirely. Fail-soft: any parse trouble falls back to the unwrapped
    command rather than dropping it."""
    try:
        inner = _unwrap(cmd).strip()
        if _COMPOUND_RE.search(inner):        # a for/while/if/case block is one command -> keep whole
            return inner
        kept = []
        for s in _split_top_level(inner):
            s = _decode_b64_pipe(s)
            if _effective_bin(s) in _NOISE_BINS or _LOCAL_READ_RE.match(s):
                continue
            kept.append(s)
        return "\n".join(kept).strip()
    except Exception:
        return _unwrap(cmd).strip()


def _slug(binary):
    s = re.sub(r"[^A-Za-z0-9_.-]", "-", binary or "misc").strip("-.") or "misc"
    return s[:40]


# Finding-grade signals (batch 6, late-evidence drift ~17x): a captured pair that holds a
# CONFIRMED finding. Precision beats recall -- this ACTS (writes a poc card), so only signals
# that are never ordinary output: a flag token, a root-shell banner, a hashcat run that
# cracked something. Reflections/error strings deliberately do NOT qualify (the confirmation
# gate owns those; auto-carding every echo would be noise).
_FLAG_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_]{1,}\{[A-Za-z0-9_!@#$%&*+.-]{4,}\}")
_ROOT_RE = re.compile(r"uid=0\(root\)|NT AUTHORITY\\SYSTEM", re.IGNORECASE)
_CRACKED_RE = re.compile(r"Recovered\s*\.*\s*:?\s*[1-9]\d*\s*/")


def _finding_signal(cmd, out):
    """(kind, token) for a finding-grade signal in the captured pair, else None."""
    m = _FLAG_RE.search(out or "")
    if m:
        return ("flag", m.group(0))
    if _ROOT_RE.search(out or ""):
        return ("root-shell", "")
    if _CRACKED_RE.search(out or ""):
        return ("cracked", "")
    return None


def _auto_card(d, tool, display, body, kind, token):
    """Persist a finding-grade pair as poc/<N>-<kind>-auto.md (deduped on the token) and
    return the printed advisory line, or '' when the signal was already carded. Never
    re-executes anything: the raw pair is already in hand (full response, uncut)."""
    import glob
    pocdir = os.path.join(d, "poc")
    os.makedirs(pocdir, exist_ok=True)
    key = token or kind
    for f in glob.glob(os.path.join(pocdir, "*-auto.md")):
        try:
            if key in open(f, encoding="utf-8", errors="ignore").read():
                return ""                                # already carded
        except OSError:
            pass
    n = len(glob.glob(os.path.join(pocdir, "*-auto.md"))) + 1
    fname = "%02d-%s-auto.md" % (n, _slug(kind))
    card = ("<!-- auto-captured finding pair (%s, %s); polish into a proper card -->\n\n"
            "# %s (auto-captured)\n\nCommand:\n\n```\n%s\n```\n\nResponse:\n\n```\n%s\n```\n"
            % (kind, tool, kind, display, body.rstrip()))
    try:
        with open(os.path.join(pocdir, fname), "w", encoding="utf-8") as fh:
            fh.write(card)
    except OSError:
        return ""
    return ("FINDING-GRADE (%s): pair auto-saved to poc/%s. Make the operator-facing card NOW "
            "while the pane is live: `bash scripts/capture.sh cli <eng> <slug> <cmdfile>` "
            "(or `capture.sh req ...` / `capture.sh burp ...` for the Repeater grab), and log "
            "the finding per hunt-core FIND output." % (kind, fname))


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return
    if data.get("tool_name") != "Bash":
        return
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not cmd or _META_RE.search(cmd):
        return
    out = _response_text(data)
    if not out.strip():
        # Empty tool output is SIGNAL, not noise (docs/shell-interaction.md:43-58):
        # count the streak; >= 2 in a row -> whoami-probe advisory. Never a cmdlog
        # entry (nothing to show), just the counter + one-shot nudge.
        import _engagement as _e
        d_empty = _e.active_dir()
        if d_empty and not _META_RE.search(cmd):
            m = os.path.join(d_empty, ".empty-streak")
            try:
                n = int(open(m).read().strip() or 0) + 1
            except OSError:
                n = 1
            if n >= 2:
                print("EMPTY OUTPUT x%d: probe with a bare `whoami` before anything else - "
                      "a username = the shell is alive and the empty result was real; "
                      "nothing = stuck; a non-username = the shell died back to your own "
                      "prompt (false-RCE trap, re-pop it). See docs/shell-interaction.md."
                      % n)
                n = 0            # advisory fired; start a fresh streak
            try:
                open(m, "w").write(str(n))
            except OSError:
                pass
        return

    # Show the REAL command, not the raw issued line: unwrap the vm.sh/rsh transport, decode
    # literal base64 cradles, drop cd/echo-banner/local-read noise. Empty -> the command was pure
    # transport/navigation, nothing worth a cmdlog entry.
    display = _clean_for_display(cmd)
    if not display.strip():
        return

    import _engagement
    d = _engagement.active_dir()
    if not d:
        return
    try:                          # a real output resets the empty-output streak
        open(os.path.join(d, ".empty-streak"), "w").write("0")
    except OSError:
        pass

    bins = _binaries(display.replace("\n", " ; ")) or []
    # first binary that is not a pure wrapper/transport is the meaningful tool
    tool = next((b for b in bins if b not in ("bash", "sh", "sudo", "env", "time")), None) \
        or (bins[0] if bins else "misc")

    pdir = os.path.join(d, "poc", "cmdlog")
    try:
        os.makedirs(pdir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = out if len(out) <= MAX_OUT else out[:MAX_OUT] + "\n...[truncated]"
        entry = "\n## %s\n\n```\n%s\n```\n\n```\n%s\n```\n" % (ts, display, body.rstrip())
        with open(os.path.join(pdir, _slug(tool) + ".md"), "a", encoding="utf-8") as fh:
            fh.write(entry)

        # Finding-grade auto-capture: persist the pair as a poc card the MOMENT the finding
        # lands (no re-execution; the curated card was skipped under momentum on every
        # engagement to date). Deduped on the signal token.
        sig = _finding_signal(display, out)
        if sig:
            line = _auto_card(d, tool, display, body, sig[0], sig[1])
            if line:
                print(line)

        # Mechanical wrong-vector tells, injected at decision time: after any scan/probe/
        # crack capture lands, run the stall battery over the WHOLE cmdlog (consecutive
        # failures against one host = target starvation, any connectivity tool; repeated
        # Exhausted-with-0-cracked = stop cracking; scanner zero-yield; frozen vm-bg log).
        # The prose version of these rules sat in hunt-core and was ignored under momentum.
        # Deduped to one verdict per 30 min so a starved loop surfaces, not spams.
        if tool in ("curl", "hashcat", "nmap", "nc", "nxc", "netexec", "ssh",
                    "hydra", "nuclei", "ffuf", "feroxbuster", "vm-bg"):
            import subprocess, time
            smarker = os.path.join(d, ".stall-nudged")
            fresh = True
            try:
                if time.time() - os.path.getmtime(smarker) < 1800:
                    fresh = False
            except OSError:
                pass                     # no marker yet
            if fresh:
                sc = os.path.join(_engagement.VAULT, "scripts", "stallcheck.py")
                try:
                    r = subprocess.run(["python3", sc, d], capture_output=True, text=True,
                                       timeout=5, stdin=subprocess.DEVNULL)
                    if r.stdout.strip():
                        print(r.stdout.strip())
                        open(smarker, "w").close()
                        # A starvation/zero-yield verdict on the row the driver last
                        # served is doom-loop closure: the driver itself said try this;
                        # the data says it can never land. Close it --dead so the cursor
                        # advances (G4 suppression) instead of the row re-serializing.
                        # (done --dead skips G1/G2 by design: a dead-end needs no
                        # evidence, so this close can never be gate-blocked.)
                        state_p = os.path.join(d, ".offensive.json")
                        try:
                            st = json.loads(open(state_p, encoding="utf-8").read())
                            rid = ((st.get("last_move") or {}).get("row") or "").strip()
                        except Exception:
                            rid = ""
                        # host-match guard: the verdict may name a DIFFERENT host than
                        # the row the driver last served - closing that row would kill
                        # an unrelated vector. Only auto-close when the verdict's host
                        # token appears in the served row's target/notes (or the verdict
                        # names no host at all, e.g. hash exhaustion).
                        row_ok = True
                        host_m = re.search(r"against (\S+)", r.stdout)
                        if rid and host_m:
                            host = host_m.group(1).strip("'\".,")
                            row_ok = False
                            try:
                                sys.path.insert(0, os.path.join(_engagement.VAULT, "scripts"))
                                import offensive as _off
                                for rw in (_off.read_board(d)
                                           + (_off.read_board_4b(d)
                                              if st.get("foothold") else [])):
                                    if (rw.get("id") or "").strip() == rid:
                                        hay = " ".join(str(rw.get(k) or "")
                                                       for k in ("asset", "notes", "target"))
                                        row_ok = host.lower() in hay.lower()
                                        break
                            except Exception:
                                row_ok = True    # board unreadable -> old behavior
                        if rid and row_ok and "STALL SIGNAL" in r.stdout:
                            try:
                                subprocess.run(
                                    ["python3", os.path.join(_engagement.VAULT, "scripts",
                                     "offensive.py"), "--eng", d, "done", rid,
                                     "--dead", "auto-stall: cmdlog stall verdict"],
                                    capture_output=True, timeout=10,
                                    stdin=subprocess.DEVNULL)
                            except Exception:
                                pass
                except Exception:
                    pass
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
