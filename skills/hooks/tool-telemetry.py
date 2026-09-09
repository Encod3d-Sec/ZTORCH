#!/usr/bin/env python3
"""PostToolUse(*) hook: per-box telemetry capture.

For every tool call, appends one event to the active engagement's `.events.jsonl` (the tool
name, plus the skill name for `Skill` calls so skill invocations are countable by name), stamps
`started_at` on the very first event, and records the session `transcript_path` (so token usage
can be attributed to this box later, even across several sessions).

Fail-open and silent: emits nothing, never blocks (PostToolUse can't block a completed call
anyway), no active engagement -> no-op. All aggregation is done offline by scripts/eval_metrics.py.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Shell separators that start a new command.
_BIN_SPLIT = re.compile(r"[|;\n]|&&|\|\|")
# Compound-header keywords: `for p in a b c` names no binary at all -- skip the whole segment,
# or the loop VARIABLE gets logged as a tool (the loop body is a separate segment and is kept).
_SKIP_SEGMENT = {"for", "case", "select"}
# Tokens that merely precede the real binary: body keywords and wrappers. `while`/`until`/
# `if`/`elif` are here (not _SKIP_SEGMENT) because, unlike `for`, their header IS a real
# invoked command (`until grep ...; do`, `if grep ...; then`) -- skipping the keyword must fall
# through to it, not skip the segment.
_SKIP_TOKEN = {"do", "then", "else", "done", "fi", "esac", "{", "}", "!", "while", "until",
               "if", "elif",
               "sudo", "env", "time", "nohup", "xargs", "doas", "command", "exec"}
# Quoted spans, e.g. a grep pattern's `'a|b|kerbrute'` -- blanked (not stripped) before
# splitting/tokenizing so neither an inner `|` nor an inner word is read as real shell syntax.
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
# A shell function DEFINITION header, e.g. `q(){`, `try()`, or `q () {` (space before the
# parens is common) -- the function's own name is never a real tool; checked on the RAW token,
# before the `()` gets stripped below.
_FUNC_DEF = re.compile(r"^[A-Za-z_]\w*\(\)\{?$")
# Same, but findall'd across the whole (blanked) command to also catch a LATER bare call of a
# function defined earlier in the same command, e.g. `q(){ curl ...; }; q "x"` -- `q` must not
# be logged from either the def or the call. Optional whitespace before `()` covers `q ()`.
_FUNC_DEF_ANY = re.compile(r"\b([A-Za-z_]\w*)\s*\(\)")


def _blank_quotes(s):
    """Blank single/double-quoted spans (length-preserving) so shell operators and words
    INSIDE quotes are inert -- e.g. a `grep -qiE 'a|b|kerbrute'` pattern must not be split
    on its `|` alternation, nor have `kerbrute` read as an invoked command."""
    return _QUOTED.sub(lambda m: " " * len(m.group(0)), s)


def _binaries(cmd):
    """Program names invoked by a shell command.

    Without this every shell call logs as `tool: Bash`, so nothing can tell `sqlmap` from a
    hand-rolled `curl` loop -- which is why tool-use was unmeasurable across a whole campaign.

    Leak-safe by construction: only program NAMES are kept, never arguments, which are what
    carry target hosts, paths and tokens.
    """
    blanked = _blank_quotes(cmd or "")
    funcs = set(_FUNC_DEF_ANY.findall(blanked))   # names defined anywhere in this command
    out = []
    for seg in _BIN_SPLIT.split(blanked):
        for tok in seg.split():
            if "=" in tok and not tok.startswith("-"):
                continue                      # env-var prefix: FOO=bar cmd
            if _FUNC_DEF.match(tok):
                continue                      # q(){ ... -- function's own name, not a tool
            b = os.path.basename(tok.strip("()`$'\"&"))
            if (not b or b.startswith("-") or b in _SKIP_SEGMENT
                    or "<" in b or ">" in b):     # a flag or a redirect: no binary follows
                break
            if b in funcs:
                break                          # a bare call of a locally-defined function,
                                                 # e.g. `q "x"` -- what follows is its ARG, not
                                                 # a command, so stop (don't log the arg either)
            if b in _SKIP_TOKEN:
                continue                      # do/then/sudo/env <real-binary>
            if b not in out:
                out.append(b)
            break
    return out[:8]


def _out_bytes(data):
    """Response size in bytes (output-economy metric: how much tool output each call
    pulled into context). A number only -- leak-safe by construction."""
    r = data.get("tool_response")
    if isinstance(r, str):
        return len(r)
    if isinstance(r, dict):
        for k in ("stdout", "output", "content", "stderr"):
            v = r.get(k)
            if isinstance(v, str):
                return len(v)
    return None


def _context_low(transcript, d):
    """Percent remaining when the last transcript usage row exceeds 75% of the model
    window, else None (clone formula: input + cache_read + cache_creation + output,
    walked backwards off the transcript tail). The transcript is the store - nothing
    is persisted. Deduped to one advisory per 15 min (.ctx-low-stamp, nudge-hook
    pattern); post-compaction the next usage row is small again, so it self-clears."""
    try:
        import time as _t
        stamp = os.path.join(d, ".ctx-low-stamp")
        if os.path.exists(stamp) and _t.time() - os.path.getmtime(stamp) < 900:
            return None
        window = int(os.environ.get("ZT_CONTEXT_WINDOW", "200000"))
        # ponytail: one env window knob; per-model detection if multi-model seats matter
        with open(transcript, "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 65536))
            tail = fh.read().decode("utf-8", "ignore")
        for line in reversed(tail.splitlines()):
            try:
                u = (json.loads(line).get("message") or {}).get("usage") or {}
            except Exception:
                continue
            if not u:
                continue
            used = (u.get("input_tokens", 0) + (u.get("cache_read_input_tokens") or 0)
                    + (u.get("cache_creation_input_tokens") or 0)
                    + u.get("output_tokens", 0))
            if used > window * 0.75:
                return max(0, round(100 * (1 - used / window)))
            return None
    except Exception:
        return None
    return None


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return
    tool = data.get("tool_name")
    if not tool:
        return
    try:
        import _telemetry
        import _engagement
    except Exception:
        return
    d = _engagement.active_dir()
    if not d:
        return
    ti = data.get("tool_input") or {}
    skill = ti.get("skill") if tool == "Skill" else None
    # Record a wiki-page READ (path relative to wiki/, e.g. "techniques/web/ssrf.md"). This is
    # the only way a hook can tell "the mapped page was actually opened" from "worked from
    # memory" -- Skill calls are already countable by name, reads were not. Leak-safe by
    # construction: only paths INSIDE the vault's own wiki/ are recorded, never a target path.
    wiki = None
    if tool in ("Read", "Grep"):
        try:
            p = os.path.abspath(str(ti.get("file_path") or ti.get("path") or ""))
            root = os.path.join(_engagement.VAULT, "wiki") + os.sep
            if p.startswith(root):
                wiki = p[len(root):]
        except Exception:
            wiki = None
    bins = _binaries(ti.get("command")) if tool == "Bash" else None
    _telemetry.log_event("tool", d=d, tool=tool, skill=skill, wiki=wiki, bins=bins or None,
                         out_bytes=_out_bytes(data))
    _telemetry.stamp_once("started_at", _telemetry.now_iso(), d=d)
    _telemetry.add_transcript(data.get("transcript_path"), d=d)
    # context-remainder advisory (the one thing telemetry is positioned to see: it holds
    # the transcript path every call). Silent on the healthy ~75% of the window.
    low = _context_low(data.get("transcript_path"), d)
    if low is not None:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext":
                "Context low (~%d%% remaining) - prefer narrow reads (offset/limit), let "
                "output_econ stub anything >30KB, and finish the served move before the "
                "next compaction (last_move survives it)." % low,
        }}))
        try:
            open(os.path.join(d, ".ctx-low-stamp"), "w").close()
            _telemetry.drift("context-low", "~%d%% context remaining" % low, d=d)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
