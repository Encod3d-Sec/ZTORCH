#!/usr/bin/env python3
"""memory-review.py - the hermes background memory reviewer, as a real process.

The v1 port failed in the field: the trigger was a printed reminder the model
could ignore, so real sessions wrote no memory. Hermes' mechanism is a separate
fork with its own LLM pass that reads the conversation and writes memory itself
(agent/background_review.py). This is that fork:

  transcript tail (last N turns, tool noise stripped, older turns digested
  hermes-style) -> ONE glm-5.3-flash call to the box's gateway carrying
  hermes' two-store routing prompt VERBATIM -> JSON ops -> written through
  the memory.py store (budgets, dedupe, atomicity enforced).

Skill-worthy observations are QUEUED to session/skill-ideas.md for the brain;
skills are never auto-created. Unattended writes are ADD-ONLY (hermes rule:
replace/remove staged for human approval - not offered here at all).
Fail-open: any error -> exit 0 silently.

Usage (normally fired by the close-out Stop hook every 10 turns):
  memory-review.py --transcript <path> [--session <id>] [--dry-run]
                    [--response-file <canned.json>]   # test mode, no gateway
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import urllib.request

VAULT = os.environ.get("ZT_COST_VAULT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_MSGS = 30            # verbatim tail turns (hermes routed-path keeps 24)
MAX_CHARS = 24000        # hard input cap for the flash call
MAX_OPS = 5
FACT_MAX = 400           # chars per fact

ROUTING_BLOCK = """TWO distinct stores - pick the right one for each fact:
  - Operator (who the user is): persona, preferences, communication and work style, personal details they revealed, and expectations about how you should behave.
  - Environment (facts about the ENVIRONMENT you operate in): tool quirks, project conventions, config gotchas, paths and endpoints that matter.

One fact goes to ONE store, never both - writing it to both bloats both files until they hit their size limits and crowds out the facts that matter; misrouting it puts it where the next session won't look."""


def _text_of(entry):
    """USER:/ASSISTANT: text lines from one transcript entry; tool noise dropped."""
    typ = entry.get("type")
    if typ not in ("user", "assistant"):
        return None
    c = (entry.get("message") or {}).get("content")
    texts = []
    if isinstance(c, str):
        texts.append(c)
    elif isinstance(c, list):
        for part in c:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
    txt = " ".join(t for t in texts if t).strip()
    if not txt:
        return None
    return ("USER:" if typ == "user" else "ASSISTANT:") + " " + re.sub(r"\s+", " ", txt)[:1000]


def extract_conversation(path, max_msgs=MAX_MSGS, max_chars=MAX_CHARS):
    """Hermes routed-path shape: old turns -> digest lines, last N verbatim."""
    lines = []
    try:
        for raw in open(path, encoding="utf-8", errors="ignore"):
            try:
                e = json.loads(raw)
            except json.JSONDecodeError:
                continue
            t = _text_of(e)
            if t:
                lines.append(t)
    except OSError:
        return []
    if len(lines) <= max_msgs:
        keep, digest = lines, []
    else:
        keep = lines[-max_msgs:]
        digest = ["[Earlier conversation digest - older turns summarised to bound the review's cost. Recent turns follow verbatim below.]"]
        for l in lines[:-max_msgs]:
            digest.append("[digest] " + l[:160])
    out = digest + keep
    total = 0
    final = []
    for l in reversed(out):                     # spend the cap on the newest
        if total + len(l) > max_chars and final:
            break
        final.append(l)
        total += len(l)
    return list(reversed(final))


def build_prompt(conv_lines):
    convo = "\n".join(conv_lines)
    return (
        "Review the conversation below and consider saving to memory if appropriate.\n\n"
        "Memory has " + ROUTING_BLOCK + """

Save ONLY facts that apply to EVERY future session regardless of task. SKIP: trivial or
easily re-discovered facts, raw data dumps, task progress, completed-work logs, temporary
state, and anything that was merely an INSTRUCTION given to the agent in its task (rules,
prefixes, constraints from a brief) - record only facts you observed about the machine,
tools, or environment itself, not rules the agent was told to follow. Reusable procedures belong in skills, not memory - if you see one, put its name in
the skills list instead of memory. Facts are declarative ("User prefers X"), never
instructions to yourself.

Reply with ONLY a JSON object, no prose:
{"ops": [{"store": "operator"|"environment", "new": "<one declarative fact>"}],
 "skills": ["<procedure name worth recording as a skill, or empty>"],
 "note": "Nothing to save." | ""}

If nothing is worth saving, use empty ops and the note. Keep each fact under 60 words.

Conversation:
""" + convo)


def _strip_fences(s):
    s = s.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.S)
    if m:
        return m.group(1)
    return s


def call_gateway(prompt, model="glm-5.3-flash"):
    base = os.environ.get("ZT_MEMORY_REVIEW_URL") or os.environ.get("ANTHROPIC_BASE_URL", "")
    key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    if not base or not key:
        return None, "no gateway env (ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN)"
    req = urllib.request.Request(
        base.rstrip("/") + "/v1/messages",
        data=json.dumps({"model": model, "max_tokens": 4000,
                         "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"content-type": "application/json",
                 "authorization": "Bearer " + key,
                 "anthropic-version": "2023-06-01"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read())
        txt = "".join(p.get("text", "") for p in d.get("content", [])
                      if isinstance(p, dict) and p.get("type") == "text")
        return txt, None
    except Exception as e:  # fail-open
        return None, str(e)[:200]


def review(transcript, response_file=None, write=True, dry_run=False):
    conv = extract_conversation(transcript)
    if not conv:
        return {"written": 0, "nothing_to_save": True, "error": "empty conversation"}
    if response_file:
        raw = open(response_file).read()
    else:
        raw, err = call_gateway(build_prompt(conv))
        if raw is None:
            return {"written": 0, "error": err}
    try:
        verdict = json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        return {"written": 0, "error": "model reply not JSON"}

    ops = [o for o in (verdict.get("ops") or [])
           if isinstance(o, dict) and o.get("store") in ("operator", "environment")
           and isinstance(o.get("new"), str) and 3 < len(o["new"].strip()) <= FACT_MAX][:MAX_OPS]
    out = {"written": 0, "duplicates": 0, "nothing_to_save": not ops,
           "skills": [s for s in (verdict.get("skills") or []) if isinstance(s, str)][:3]}
    if not ops and not out["skills"]:
        return out

    # write through the memory store (budgets, dedupe, atomic write)
    spec = importlib.util.spec_from_file_location(
        "zt_memory", os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.py"))
    mem = importlib.util.module_from_spec(spec)
    mem.VAULT = VAULT
    spec.loader.exec_module(mem)
    mem.VAULT = VAULT
    mem.MEMFILE = os.path.join(VAULT, "session", "memory.md")  # module binds it at import
    stores, _ = mem.parse()
    msgs = []
    for o in ops:
        m = mem.op_add(stores, o)
        if m and "duplicate" in m:
            out["duplicates"] += 1
        elif not m:
            out["written"] += 1
    for key in ("operator", "environment"):
        if mem.used(stores, key) > mem.LIMITS[key]:
            return {"written": 0, "error": "over budget after ops; needs consolidation (brain-side)"}
    if write and not dry_run and out["written"]:
        mem.atomic_write(mem.render(stores))
    if out["skills"]:
        ideas = os.path.join(VAULT, "session", "skill-ideas.md")
        with open(ideas, "a", encoding="utf-8") as f:
            for s in out["skills"]:
                f.write("- %s (queued by memory-review %s)\n"
                        % (s, __import__("time").strftime("%Y-%m-%d")))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--transcript")
    ap.add_argument("--session")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--response-file")
    args = ap.parse_args()
    t = args.transcript
    if not t and args.session:
        p = os.path.expanduser("~/.claude/projects/-home-zerodaygym-tools-ZTORCH")
        c = os.path.join(p, args.session + ".jsonl")
        t = c if os.path.exists(c) else None
    if not t:
        print("no transcript", file=sys.stderr)
        return 0
    out = review(t, response_file=args.response_file, dry_run=args.dry_run)
    if out.get("error"):
        print("memory-review: skipped (%s)" % out["error"], file=sys.stderr)
    elif out.get("written"):
        print("memory-review: wrote %d fact(s) to memory%s"
              % (out["written"], "; skill ideas queued" if out.get("skills") else ""))
    elif out.get("duplicates"):
        print("memory-review: %d fact(s) already known, nothing new" % out["duplicates"])
    else:
        print("memory-review: nothing to save")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open, silent
