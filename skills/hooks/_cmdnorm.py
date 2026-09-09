"""Shared Bash-command normalization for the guard hooks (scope/sleep/drift).

One property: a rule must match what the shell will actually RUN, not what the
string looks like. Commands arrive wrapped (`FOO=bar sudo timeout 30 ...`),
compound (`ok && denied`), and bridged (`bash /root/vm.sh '<inner>'`,
`sshpass ... ssh host '<inner>'`, `bash -c '<body>'`, heredocs). A guard that
matches only the whole string or only segment 0 misses the wrapped or
second-segment command entirely.

segments(cmd) -> every command that will run: quote-aware outer segments split on
;|&&||/newline PLUS unwrapped inner (bridge/-c/heredoc) commands, each with env-var
assignments and sudo/env/timeout-style wrappers peeled to a fixed point
(`nohup FOO=bar timeout 5 curl ...` resolves to `curl`). Segment text is the
ORIGINAL (un-blanked) string; apply your own quote-blanking per segment.

The split/unwrap machinery lives in recon-capture.py and is loaded lazily via
importlib (same pattern as burp-nudge.py/tmux-nudge.py); if that module is ever
unreadable, local best-effort fallbacks keep segments() working (guards fail open
regardless).
"""
import importlib.util
import os
import re

_FALLBACK_ASSIGN = re.compile(r"^\w+=\S*")
_FALLBACK_WRAP = re.compile(
    r"^(sudo|env|time|timeout|nice|nohup|stdbuf|doas|proxychains4?)\b", re.I)

_RC = None
_RC_LOADED = False


def _rc():
    """Lazy-load recon-capture once; None if unreadable (fallbacks apply)."""
    global _RC, _RC_LOADED
    if not _RC_LOADED:
        _RC_LOADED = True
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "recon-capture.py")
            spec = importlib.util.spec_from_file_location("_cmdnorm_rc", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _RC = mod
        except Exception:
            _RC = None
    return _RC


def _outer_segments(cmd):
    rc = _rc()
    if rc is not None:
        return rc._segments(cmd)
    return re.split(r"&&|\|\||[;|\n]", cmd or "")


def _inner_commands(cmd):
    rc = _rc()
    return rc.inner_cmds(cmd) if rc is not None else []


def _normalize(seg):
    """Peel leading env-var assignments and wrapper commands (with their flag/secs
    args) to a fixed point, so rule matching sees the real command token."""
    toks = (seg or "").strip()
    prev = None
    while toks and toks != prev:
        prev = toks
        m = (_rc()._ASSIGN if _rc() is not None else _FALLBACK_ASSIGN).match(toks)
        if m:
            toks = toks[m.end():].lstrip()
            continue
        wrap = (_rc()._WRAP if _rc() is not None else _FALLBACK_WRAP).match(toks)
        if wrap:
            toks = toks[wrap.end():].lstrip()
            toks = re.sub(r"^((-{1,2}\S+|\d+)\s+)*", "", toks)  # wrapper flags / timeout secs
    return toks


def segments(cmd):
    """Normalized original-text command strings for rule matching (see module doc).
    Empty strings dropped."""
    out = [_normalize(s) for s in _outer_segments(cmd)]
    for ic in _inner_commands(cmd):
        out.extend(_normalize(s) for s in _outer_segments(ic))
    return [s for s in out if s]


def inner(cmd):
    """Raw inner command strings unwrapped from vm.sh/ssh/wsl/-c/heredoc wrappers."""
    return _inner_commands(cmd)


if __name__ == "__main__":
    # self-check: the shapes the guards were blind to before this module
    got = segments("nohup FOO=bar timeout 5 curl http://10.0.0.5/")
    assert got and got[0].startswith("curl"), got
    assert any(s.startswith("nmap") for s in
               segments("bash /root/vm.sh 'nmap -sV 10.0.0.5'")), "bridge inner missed"
    assert any("sleep" in s for s in segments("echo ok; sleep 300")), "second segment missed"
    assert "10.0.0.5" not in " ".join(segments("TOKEN=10.0.0.5 nmap localhost")), "env value scanned"
    print("_cmdnorm: OK")
