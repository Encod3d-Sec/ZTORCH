#!/usr/bin/env python3
"""cost-snap.py - Stop hook: log every session's real token usage, always.

Zero token cost (a local script; no model calls) and near-zero CPU: it keeps
per-file byte offsets in session/bench/.offsets.json and only reads NEW
transcript lines each fire, so each session-end costs one small incremental
pass. One JSON line appended to session/bench/auto.jsonl (gitignored):

  ts, tokens_total, input, output, cache_read, cache_write, subagent_tokens,
  turns, tool_calls, agent_launches, bash_commands, skills, eng

Fails open and silent: any error -> exit 0 with no output (never pollutes the
session end). Sources: Claude Code transcripts (usage rows) + the active
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


def main():
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
        return 0  # nothing new (hook fired twice, or a zero-activity session)
    import time
    row["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(os.path.join(BENCH, "auto.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail open, silent
