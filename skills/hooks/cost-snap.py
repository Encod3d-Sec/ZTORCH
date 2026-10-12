#!/usr/bin/env python3
"""cost-snap.py - Stop hook: log every session's real token usage, always.

Zero token cost (a local script; no model calls) and near-zero CPU: it keeps
per-file byte offsets in session/bench/.offsets.json and only reads NEW
transcript lines each fire, so each session-end costs one small incremental
pass. One JSON line appended to session/bench/auto.jsonl (gitignored):

  ts, tokens_total, input, output, cache_read, cache_write, subagent_tokens,
  turns, tool_calls, agent_launches, bash_commands, skills, eng

One LIVE row per session (keyed by session_id from the hook payload): each
Stop fire adds that turn's delta into the session's single row, so mid-session
the row already shows running totals. Fails open and silent: any error ->
exit 0 with no output. Sources: Claude Code transcripts (usage rows) + the active
engagement's .events.jsonl delta (same offset trick).
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.environ.get("ZT_COST_VAULT") or os.path.abspath(os.path.join(HERE, "..", ".."))
BENCH = os.path.join(VAULT, "session", "bench")
PROJDIR = os.environ.get("ZT_COST_PROJDIR") or os.path.expanduser(
    "~/.claude/projects/-home-zerodaygym-tools-ZTORCH")


def _load_json(path, default):
    try:
        return json.load(open(path))
    except (OSError, json.JSONDecodeError):
        return default


def _session_id():
    try:
        d = json.loads(sys.stdin.read() or "{}")
        return d.get("session_id") or "manual"
    except Exception:
        return "manual"


def main():
    sid = _session_id()
    offs = _load_json(os.path.join(BENCH, ".offsets.json"), {})
    row = {"tokens_total": 0, "input": 0, "output": 0, "cache_read": 0,
           "cache_write": 0, "subagent_tokens": 0, "turns": 0,
           "tool_calls": 0, "agent_launches": 0, "bash_commands": 0,
           "skills": 0, "eng": ""}
    # transcripts: incremental read from stored offset
    for p in glob.glob(os.path.join(PROJDIR, "*.jsonl")):
        key = os.path.basename(p)
        try:
            f = open(p, encoding="utf-8", errors="ignore")
        except OSError:
            continue
        start = min(offs.get(key, 0), os.path.getsize(p))
        f.seek(start)
        for line in f:
            if '"usage"' not in line and "subagent" not in line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            u = (d.get("message") or {}).get("usage") or {}
            if u:
                row["turns"] += 1
                row["input"] += u.get("input_tokens", 0)
                row["output"] += u.get("output_tokens", 0)
                row["cache_read"] += u.get("cache_read_input_tokens", 0)
                row["cache_write"] += u.get("cache_creation_input_tokens", 0)
            st = d.get("subagent_tokens") or (d.get("attachment") or {}).get("subagent_tokens")
            if isinstance(st, int):
                row["subagent_tokens"] += st
        offs[key] = f.tell()
        f.close()
    # engagement events delta
    d = os.path.join(VAULT, "targets")
    try:
        active = open(os.path.join(d, "active.md"), encoding="utf-8").read().strip()
        if active and os.path.isdir(os.path.join(d, active)):
            d = os.path.join(d, active)
        else:
            d = None
    except OSError:
        d = None
    if d:
        row["eng"] = os.path.basename(d.rstrip("/"))
        evp = os.path.join(d, ".events.jsonl")
        try:
            start = min(offs.get("events", 0), os.path.getsize(evp))
            f = open(evp, encoding="utf-8", errors="ignore")
            f.seek(start)
            for line in f:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("kind") != "tool":
                    continue
                row["tool_calls"] += 1
                t = e.get("tool")
                if t == "Agent":
                    row["agent_launches"] += 1
                elif t == "Bash":
                    row["bash_commands"] += 1
                elif t == "Skill":
                    row["skills"] += 1
            offs["events"] = f.tell()
            f.close()
        except OSError:
            pass
    row["tokens_total"] = (row["input"] + row["output"] + row["cache_read"]
                           + row["cache_write"] + row["subagent_tokens"])
    # persist offsets first (claim-before-write: a lost row beats double-count)
    os.makedirs(BENCH, exist_ok=True)
    json.dump(offs, open(os.path.join(BENCH, ".offsets.json"), "w"))
    if row["turns"] == 0 and row["tool_calls"] == 0:
        return 0  # nothing new since the last fire
    import time
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    row["ts"] = now
    row["session_id"] = sid
    row["first_seen"] = now
    auto = os.path.join(BENCH, "auto.jsonl")
    # one LIVE row per session: same session_id updates its row in place
    lines = []
    if os.path.exists(auto):
        lines = [l for l in open(auto, encoding="utf-8").read().splitlines() if l.strip()]
        if lines:
            try:
                last = json.loads(lines[-1])
                if last.get("session_id") == sid:
                    row["first_seen"] = last.get("first_seen", now)
                    for k in ("tokens_total", "input", "output", "cache_read",
                              "cache_write", "subagent_tokens", "turns",
                              "tool_calls", "agent_launches", "bash_commands",
                              "skills"):
                        row[k] += last.get(k, 0)
                    lines[-1] = json.dumps(row)
                else:
                    lines.append(json.dumps(row))
            except json.JSONDecodeError:
                lines.append(json.dumps(row))
        else:
            lines.append(json.dumps(row))
    else:
        lines.append(json.dumps(row))
    tmp = auto + ".tmp"
    open(tmp, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    os.replace(tmp, auto)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail open, silent
