#!/usr/bin/env python3
"""cost-log.py - what did running this harness cost, in tokens and activity?

Three sources, one report (branch-independent, works on old and new harness):
  1. Tokens: the Claude Code session transcripts (~/.claude/projects/<proj>/
     *.jsonl) carry per-assistant-turn usage (input/output/cache read/write).
     Summed over a time window. Subagent token rows (when the transcript
     carries them) are summed separately as subagent_tokens.
  2. Activity: the engagement's .events.jsonl (tool-telemetry) - tool calls,
     Agent launches, Bash commands, Skill fires + names, output bytes.
  3. Outcome: state.md - STATUS line, flag captures (THM/HTB/flag/FLAG{...}),
     FIND count.

Usage:
  cost-log.py --eng <name> --since <iso> [--until <iso>] [--json]
"""
import glob
import json
import os
import re
import sys

VAULT = os.environ.get("ZT_COST_VAULT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJDIR = os.path.expanduser("~/.claude/projects/-home-zerodaygym-tools-ZTORCH")


def _in_window(ts, since, until):
    if not ts:
        return False
    if since and ts < since:
        return False
    if until and ts > until:
        return False
    return True


def tokens_since(since, until, projdir=None):
    tot = {"turns": 0, "input": 0, "output": 0, "cache_read": 0,
           "cache_write": 0, "subagent_tokens": 0}
    for p in glob.glob(os.path.join(projdir or PROJDIR, "*.jsonl")):
        for line in open(p, encoding="utf-8", errors="ignore"):
            if '"usage"' not in line and "subagent" not in line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            u = (d.get("message") or {}).get("usage") or {}
            if u and _in_window(d.get("timestamp"), since, until):
                tot["turns"] += 1
                tot["input"] += u.get("input_tokens", 0)
                tot["output"] += u.get("output_tokens", 0)
                tot["cache_read"] += u.get("cache_read_input_tokens", 0)
                tot["cache_write"] += u.get("cache_creation_input_tokens", 0)
            st = d.get("subagent_tokens") or (d.get("attachment") or {}).get("subagent_tokens")
            if isinstance(st, int) and _in_window(d.get("timestamp"), since, until):
                tot["subagent_tokens"] += st
    tot["total"] = (tot["input"] + tot["output"] + tot["cache_read"]
                    + tot["cache_write"] + tot["subagent_tokens"])
    return tot


def activity(eng, vault=None, since=None):
    vault = vault or VAULT
    a = {"tool_calls": 0, "agent_launches": 0, "bash_commands": 0,
         "skills_fired": 0, "skill_names": [], "out_bytes": 0}
    p = os.path.join(vault, "targets", eng, ".events.jsonl")
    seen = set()
    try:
        for line in open(p, encoding="utf-8", errors="ignore"):
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("kind") != "tool":
                continue
            if since and (e.get("ts") or "") < since:
                continue
            t = e.get("tool")
            a["tool_calls"] += 1
            a["out_bytes"] += e.get("out_bytes") or 0
            if t == "Agent":
                a["agent_launches"] += 1
            elif t == "Bash":
                a["bash_commands"] += 1
            elif t == "Skill":
                a["skills_fired"] += 1
                if e.get("skill") and e["skill"] not in seen:
                    seen.add(e["skill"])
                    a["skill_names"].append(e["skill"])
    except OSError:
        pass
    return a


def challenges(eng, vault=None):
    vault = vault or VAULT
    c = {"status": "", "flags": 0, "finds": 0}
    p = os.path.join(vault, "targets", eng, "state.md")
    try:
        txt = open(p, encoding="utf-8", errors="ignore").read()
    except OSError:
        return c
    m = re.search(r"## STATUS: (\w+)", txt)
    c["status"] = m.group(1) if m else ""
    c["flags"] = len(re.findall(r"(?:THM|HTB|flag|FLAG|CTF)\{[^}]{3,}\}", txt))
    c["finds"] = len(re.findall(r"^#{1,3} FIND-\d+", txt, re.M))
    return c


def report(eng, since, until, vault=None, projdir=None):
    t = tokens_since(since, until, projdir)
    a = activity(eng, vault)
    c = challenges(eng, vault)
    L = [f"== harness cost: {eng} ({since} .. {until or 'now'}) =="]
    L.append("tokens:")
    for k in ("turns", "input", "output", "cache_read", "cache_write",
              "subagent_tokens", "total"):
        L.append(f"  {k:>16}: {t[k]:,}")
    if os.environ.get("ZT_PRICE_IN") and os.environ.get("ZT_PRICE_OUT"):
        est = t["input"] / 1e6 * float(os.environ["ZT_PRICE_IN"]) + \
              t["output"] / 1e6 * float(os.environ["ZT_PRICE_OUT"])
        L.append(f"  {'est_cost_usd':>16}: {est:.2f} (ZT_PRICE_IN/OUT per Mtok)")
    L.append("activity:")
    L.append(f"  {'tool_calls':>16}: {a['tool_calls']}")
    L.append(f"  {'Agent launches':>16}: {a['agent_launches']}")
    L.append(f"  {'Bash commands':>16}: {a['bash_commands']}")
    L.append(f"  {'Skill fires':>16}: {a['skills_fired']} ({', '.join(a['skill_names']) or '-'})")
    L.append(f"  {'output bytes':>16}: {a['out_bytes']:,}")
    L.append("outcome:")
    L.append(f"  {'status':>16}: {c['status'] or '-'}")
    L.append(f"  {'flags captured':>16}: {c['flags']}")
    L.append(f"  {'FIND count':>16}: {c['finds']}")
    return "\n".join(L)


def main():
    args = sys.argv[1:]
    eng = since = until = None
    js = "--json" in args
    it = iter(args)
    for x in it:
        if x == "--eng":
            eng = next(it, None)
        elif x == "--since":
            since = next(it, None)
        elif x == "--until":
            until = next(it, None)
    if not eng or not since:
        print(__doc__)
        return 2
    if js:
        print(json.dumps({"tokens": tokens_since(since, until),
                          "activity": activity(eng, since=since), "outcome": challenges(eng)}))
        return 0
    print(report(eng, since, until))
    return 0


if __name__ == "__main__":
    sys.exit(main())
