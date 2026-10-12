#!/usr/bin/env python3
"""token-audit.py - where do context tokens go, in one report.

Answers four questions the harness could not answer before (hermes token-
posture port):
  1. What loads into EVERY session for free? (SessionStart injection: hot.md
     + memory snapshot; AGENTS.md rides with the harness itself)
  2. What does each skill cost when it fires? (whole SKILL.md loads; ~chars/4
     is a fair token estimate; OVERSIZED > 24000 chars flagged - hermes'
     own threshold)
  3. How full are the memory budgets?
  4. What did recent turns actually burn? (.metrics.json turn_bytes, from the
     spill/budget port)

Usage: python3 scripts/token-audit.py [--json]
"""
import glob
import json
import os
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERSIZED = 24000          # hermes oversized-body threshold
SECTIONS_HINT = 10000      # above this, a `## Sections` index pays for itself
LIMITS = {"operator": 1375, "environment": 2200}


def skill_sizes(root=None):
    root = root or os.path.join(VAULT, "skills")
    out = {}
    for p in glob.glob(os.path.join(root, "**", "SKILL.md"), recursive=True):
        out[os.path.relpath(p, VAULT)] = os.path.getsize(p)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def memory_usage(path=None):
    path = path or os.path.join(VAULT, "session", "memory.md")
    used = {"operator": 0, "environment": 0}
    cur = None
    if not os.path.exists(path):
        return 0, 0
    for ln in open(path, encoding="utf-8", errors="ignore"):
        if ln.startswith("## Operator"):
            cur = "operator"
        elif ln.startswith("## Environment"):
            cur = "environment"
        elif ln.startswith("- ") and cur:
            used[cur] += len(ln[2:]) + 1
    return used["operator"], used["environment"]


def turn_bytes_summary():
    rows = []
    for m in glob.glob(os.path.join(VAULT, "targets", "*", ".metrics.json")):
        eng = m.split(os.sep)[-2]
        try:
            tb = json.load(open(m)).get("turn_bytes") or []
        except (OSError, json.JSONDecodeError):
            continue
        if tb:
            rows.append((eng, sum(r.get("b", 0) for r in tb), len(tb)))
    if not rows:
        return "no turn_bytes recorded yet (spill/budget port writes them as turns run)"
    return "\n".join(f"  {e}: {b} bytes across {n} turns" for e, b, n in rows)


def report():
    L = []
    hot = os.path.join(VAULT, "session", "hot.md")
    hot_n = os.path.getsize(hot) if os.path.exists(hot) else 0
    op, env = memory_usage()
    mem_n = op + env
    L.append("== SessionStart injection (loads into EVERY session) ==")
    L.append(f"  hot.md: {hot_n} chars (rotation keeps ~3 newest blocks; hard cap 25600)")
    L.append(f"  memory snapshot: {mem_n} chars (budgets: operator {op}/{LIMITS['operator']}, "
             f"environment {env}/{LIMITS['environment']})")
    ag = os.path.join(VAULT, "AGENTS.md")
    if os.path.exists(ag):
        n = os.path.getsize(ag)
        L.append(f"  AGENTS.md (harness-level, not vault-controlled): {n} chars ~{n//4} tokens")
    L.append("")
    L.append("== Skill fire cost (whole file loads; ~chars/4 = tokens) ==")
    sizes = skill_sizes()
    for p, n in list(sizes.items())[:12]:
        flag = " OVERSIZED" if n > OVERSIZED else (" sections-hint" if n > SECTIONS_HINT else "")
        L.append(f"  {p}: {n} chars ~{n//4} tokens{flag}")
    over = [p for p, n in sizes.items() if n > OVERSIZED]
    L.append(f"  total across {len(sizes)} skills: {sum(sizes.values())} chars")
    if over:
        L.append(f"  OVERSIZED (> {OVERSIZED} chars): {len(over)} - split into "
                 "`## Sections` + wiki-section.sh loads, move detail to references/")
    L.append("")
    L.append("== Lane dispatch fixed cost ==")
    bat = os.path.join(VAULT, "skills", "workflow", "exec", "delegate", "SKILL.md")
    if os.path.exists(bat):
        txt = open(bat, encoding="utf-8", errors="ignore").read()
        if "## Lane mandate battery" in txt:
            blk = txt.split("## Lane mandate battery", 1)[1].split("##", 1)[0]
            L.append(f"  mandate battery: ~{len(blk)} chars (frozen prefix; prompt-cached "
                     "across concurrent lanes)")
        else:
            L.append("  mandate battery: MISSING")
    L.append("  brief size is per-dispatch: keep the directive lean, files by path not body")
    L.append("")
    L.append("== Turn bytes recorded (actual output volume) ==")
    L.append(turn_bytes_summary())
    return "\n".join(L)


def main():
    if "--json" in sys.argv:
        sizes = skill_sizes()
        op, env = memory_usage()
        print(json.dumps({"skills": sizes, "oversized": [p for p, n in sizes.items() if n > OVERSIZED],
                          "memory": {"operator": op, "environment": env}}))
        return 0
    print(report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
