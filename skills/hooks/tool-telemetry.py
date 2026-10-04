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


def _spend_update(transcript, d):
    """Accumulate est. USD spend into .metrics.json['spend_usd'] (status.py renders it;
    eval_metrics' auto block carries the full breakdown at close-out). Reads only the
    transcript bytes past the offset recorded last run (spend_state: {path: byte_off}),
    so each call is one tail-read, never a full re-walk. Pricing comes from
    scripts/eval_metrics.py (USD_PER_MTOK via _rates) - imported, never forked, so a
    tier added there prices here too. With ZT_MAX_ENG_USD set, returns one over-budget
    advisory per 15 min (.budget-stamp) for additionalContext; PostToolUse cannot block,
    so the cap is advisory by construction."""
    tp = str(transcript or "")
    if not tp or not os.path.isfile(tp):
        return None
    try:
        size = os.path.getsize(tp)
        mp = os.path.join(d, ".metrics.json")
        try:
            m = json.load(open(mp, encoding="utf-8"))
        except Exception:
            m = {}
        state = m.get("spend_state") or {}
        off = int(state.get(tp, 0) or 0)
        if size < off:
            off = 0                                  # rotated/truncated: re-read whole file
        with open(tp, "rb") as fh:
            fh.seek(off)
            chunk = fh.read()
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "scripts"))
        import eval_metrics as em
        delta = 0.0
        for line in chunk.decode("utf-8", "ignore").splitlines():
            try:
                msg = (json.loads(line).get("message") or {})
            except Exception:
                continue                             # partial first line past a mid-line offset
            u = msg.get("usage") or {}
            if not u:
                continue
            r, _tier = em._rates(msg.get("model"))
            delta += (u.get("input_tokens", 0) * r["input"]
                      + u.get("output_tokens", 0) * r["output"]
                      + (u.get("cache_read_input_tokens") or 0) * r["cache_read"]
                      + (u.get("cache_creation_input_tokens") or 0) * r["cache_creation"]) / 1e6
        m["spend_usd"] = round(float(m.get("spend_usd", 0) or 0) + delta, 4)
        state[tp] = size
        m["spend_state"] = state
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump(m, fh, indent=1)
        cap = 0.0
        try:
            cap = float(os.environ.get("ZT_MAX_ENG_USD", "") or 0)
        except ValueError:
            cap = 0.0
        if cap > 0 and m["spend_usd"] > cap:
            # drift-guard (PreToolUse) already DENIES Bash over this same cap while
            # enforcing; this PostToolUse advisory would only echo the deny's message as
            # extra context noise. Keep the advisory solely when enforcement is off
            # (.enforce-off hatch), where it is the only budget signal left.
            marker = os.environ.get("ENFORCE_OFF_MARKER") or os.path.join(HERE, ".enforce-off")
            if not os.path.exists(marker):
                return None
            import time as _t
            st = os.path.join(d, ".budget-stamp")
            if os.path.exists(st) and _t.time() - os.path.getmtime(st) < 900:
                return None
            try:
                open(st, "w").close()
                import _telemetry
                _telemetry.drift("budget",
                                 "est. $%.2f exceeds cap $%.2f (ZT_MAX_ENG_USD)"
                                 % (m["spend_usd"], cap), d=d)
            except Exception:
                pass
            return ("Engagement spend est. $%.2f is over the $%.2f cap - wrap up: cheap-tier "
                    "lanes (Skill(delegate)), narrow reads, close out open rows."
                    % (m["spend_usd"], cap))
    except Exception:
        return None
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


_MENTOR_SAME_TOOL = 5   # pentagi helpers.go:164-197 threshold; reset-on-fire


def _mentor_check(d, tool, bins):
    """PentAGI Mentor pattern: one tool/binary accumulating _MENTOR_SAME_TOOL calls inside
    one bucket (the freshest OPEN lane line, else the brain) gets one additionalContext
    steer - answer from the output you already have or switch approach - and its counter
    resets. Advisory only, fail-open by construction (PostToolUse cannot block)."""
    try:
        bucket = "brain"
        try:
            sys.path.insert(0, os.path.join(
                os.path.dirname(os.path.dirname(HERE)), "scripts"))
            import lane_validate
            if lane_validate.lane_lines(d):
                bucket = "lane"
        except Exception:
            pass
        keys = [b for b in (bins or []) if b] or [tool]
        mp = os.path.join(d, ".metrics.json")
        try:
            m = json.load(open(mp, encoding="utf-8"))
        except Exception:
            m = {}
        mc = (m.get("mentor") or {}).get(bucket) or {}
        fired = []
        for k in keys[:4]:
            mc[k] = int(mc.get(k, 0) or 0) + 1
            if mc[k] >= _MENTOR_SAME_TOOL:
                fired.append(k)
                mc[k] = 0
        while len(mc) > 16:
            mc.pop(next(iter(mc)))
        m.setdefault("mentor", {})[bucket] = mc
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump(m, fh, indent=1)
        if fired:
            try:
                import _telemetry
                _telemetry.drift("mentor", "same-tool threshold: %s" % ",".join(fired), d=d)
            except Exception:
                pass
            return ("LANE PATTERN (mentor): %s fired %d times in this %s. Answer from the "
                    "output you already have, switch tool or approach, or state what is "
                    "missing before the next call."
                    % (", ".join(fired), _MENTOR_SAME_TOOL, bucket))
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
    mentor = _mentor_check(d, tool, bins)
    if mentor:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse", "additionalContext": mentor,
        }}))
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
    # live spend accumulator (pass 11 L5): status.py's `spend:` line + the opt-in
    # ZT_MAX_ENG_USD over-budget advisory. Silent unless the cap is set and crossed.
    budget = _spend_update(data.get("transcript_path"), d)
    if budget:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": budget,
        }}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
