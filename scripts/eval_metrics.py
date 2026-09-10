#!/usr/bin/env python3
"""Aggregate per-box AGENT metrics from hook telemetry + the session transcript.

Answers, with REAL data (no self-estimation):
  - how many skill / hook / tool calls  (from targets/<eng>/.events.jsonl)
  - how many drift signals + what triggered them  (.events.jsonl kind="drift")
  - tokens used per box  (session transcripts, windowed to the box's active period)
  - start -> finish time delta + idle-filtered active time  (.metrics.json + event span)

The hooks (tool-telemetry PostToolUse + the guards) APPEND cheap events; this script does the
aggregation offline. Counts and time are exact; per-box token attribution is windowed by
started_at/finished_at (approximate only when one session interleaves several boxes).

Usage:
  python3 scripts/eval_metrics.py [<engagement>] [--write] [--transcript PATH]
    (no engagement -> targets/active.md; --write injects a "## Metrics (auto)" block into eval.md;
     --transcript adds a transcript path not yet recorded in .metrics.json, e.g. for a back-fill.)
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDLE_GAP = timedelta(minutes=15)   # event gaps longer than this = idle, excluded from active-time
AUTO_BEGIN = "<!-- eval-metrics:auto BEGIN -->"
AUTO_END = "<!-- eval-metrics:auto END -->"


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def read_events(d):
    out = []
    p = os.path.join(d, ".events.jsonl")
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def read_metrics(d):
    try:
        return json.load(open(os.path.join(d, ".metrics.json"), encoding="utf-8"))
    except Exception:
        return {}


# $/Mtok, 4-term cache-aware (clone pattern: cache_read is 0.1x input, cache_creation
# 1.25x - collapsing the three input flavors into one number misprices ~10x). Keyed by
# model substring; anything unrecognized prices at the default tier and the rendered
# row names which tier was used, so the number is checkable, never silently wrong.
USD_PER_MTOK = {
    "default": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_creation": 3.75},
    "sonnet":  {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_creation": 3.75},
    "opus":    {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_creation": 18.75},
    "haiku":   {"input": 1.0, "output": 5.0, "cache_read": 0.10, "cache_creation": 1.25},
}


def _rates(model):
    m = (model or "").lower()
    for k in USD_PER_MTOK:
        if k != "default" and k in m:
            return USD_PER_MTOK[k], k
    return USD_PER_MTOK["default"], "default"


def _rate_label(tier_str):
    """Rendered rate string DERIVED from USD_PER_MTOK (never a hardcoded literal that
    goes stale the next time a tier is added - opus transcripts under-priced ~5x before
    the tier existed). Mixed-tier boxes are already priced per-turn; the label names the
    first tier's table so the total stays checkable."""
    t = (tier_str or "default").split("+")[0]
    r = USD_PER_MTOK.get(t, USD_PER_MTOK["default"])
    return "$%g/$%g/$%g/$%g" % (r["input"], r["output"], r["cache_read"], r["cache_creation"])


def tokens_in_window(transcripts, start, end):
    """Sum usage (and est. USD) across assistant turns whose timestamp falls in
    [start, end]."""
    tot = Counter()
    tiers = set()
    for tp in transcripts:
        if not tp or not os.path.isfile(tp):
            continue
        for line in open(tp, encoding="utf-8", errors="ignore"):
            try:
                e = json.loads(line)
            except Exception:
                continue
            msg = e.get("message") or {}
            u = msg.get("usage") or {}
            if not u:
                continue
            t = parse_ts(e.get("timestamp"))
            if start and t and t < start:
                continue
            if end and t and t > end:
                continue
            r, tier = _rates(msg.get("model"))
            tiers.add(tier)
            tot["output"] += u.get("output_tokens", 0) or 0
            tot["input"] += u.get("input_tokens", 0) or 0
            tot["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
            tot["cache_creation"] += u.get("cache_creation_input_tokens", 0) or 0
            tot["cost"] += (u.get("input_tokens", 0) * r["input"]
                            + u.get("output_tokens", 0) * r["output"]
                            + u.get("cache_read_input_tokens", 0) * r["cache_read"]
                            + u.get("cache_creation_input_tokens", 0) * r["cache_creation"]) / 1e6
            tot["turns"] += 1
    tot["tiers"] = "+".join(sorted(tiers))
    return tot


def bench_lines(d):
    """Expected-coverage line for practice engagements: the engagement is NAMED after
    its scenario id in scripts/bench-labs.json (that naming convention IS the link,
    no extra state), so the close-out auto block carries the bench score for free.
    [] when the engagement name matches no scenario -- client engagements never do."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import bench
        manifest = json.loads(bench.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        name = os.path.basename(os.path.normpath(d))
        spec = manifest.get(name)
        if not isinstance(spec, dict):
            return []
        res = bench.score_engagement(d, {name: spec})
        classes = res["scenarios"][0]["classes"] if res["scenarios"] else {}
        det = ", ".join("%s=%d" % kv for kv in classes.items()) or "no expected classes"
        return ["**Bench vs expected (%s):** coverage %.1f%% -- %s"
                % (name, res["coverage_pct"], det)]
    except Exception:
        return []          # bench is an add-on; never break the metrics write


def active_time(events):
    ts = sorted(t for t in (parse_ts(e.get("ts")) for e in events) if t)
    total = timedelta(0)
    for a, b in zip(ts, ts[1:]):
        gap = b - a
        if gap <= IDLE_GAP:
            total += gap
    return total


def collect(d, extra_transcript=None):
    events = read_events(d)
    m = read_metrics(d)
    start = parse_ts(m.get("started_at"))
    end = parse_ts(m.get("finished_at"))
    ev_ts = sorted(t for t in (parse_ts(e.get("ts")) for e in events) if t)
    if not start and ev_ts:
        start = ev_ts[0]
    if not end and ev_ts:
        end = ev_ts[-1]
    transcripts = list(m.get("transcripts", []))
    if extra_transcript and extra_transcript not in transcripts:
        transcripts.append(extra_transcript)
    tools = Counter(e.get("tool") for e in events if e.get("kind") == "tool" and e.get("tool"))
    skills = Counter(e.get("skill") for e in events if e.get("kind") == "tool" and e.get("skill"))
    hooks = Counter(e.get("hook") for e in events if e.get("kind") == "hook" and e.get("hook"))
    drifts = [e for e in events if e.get("kind") == "drift"]
    # hunt-firing drift: a fingerprint routed a hunt-* skill that was never invoked this session
    # (recon-capture logs kind="route"; tool-telemetry logs kind="tool" skill=<name> on invocation).
    _routed = {e.get("routed") for e in events
               if e.get("kind") == "route" and str(e.get("routed", "")).startswith("hunt-")}
    _invoked = {e.get("skill") for e in events if e.get("kind") == "tool" and e.get("skill")}
    for _h in sorted(h for h in _routed if h and h not in _invoked):
        drifts.append({"kind": "drift", "source": "hunt-not-fired",
                       "reason": "fingerprint routed %s but it was never invoked "
                                 "(worked from memory / hand-rolled)" % _h})
    return {
        "start": start, "end": end,
        "wall": (end - start) if (start and end) else None,
        "active": active_time(events),
        "tokens": tokens_in_window(transcripts, start, end),
        "tool_calls": sum(tools.values()), "tools": tools,
        "skill_calls": sum(skills.values()), "skills": skills,
        "hook_fires": sum(hooks.values()), "hooks": hooks,
        "drift_count": len(drifts), "drifts": drifts,
        "tool_out": sum(e.get("out_bytes") or 0 for e in events if e.get("kind") == "tool"),
        "bench": bench_lines(d),
        "transcripts": [t for t in transcripts if os.path.isfile(t)],
    }


def _fmt_td(td):
    if td is None:
        return "n/a"
    s = int(td.total_seconds())
    return "%dh%02dm" % (s // 3600, (s % 3600) // 60)


def render(name, c):
    tk = c["tokens"]
    hr = 100.0 * tk.get("cache_read", 0) / max(1, tk.get("input", 0)
                                               + tk.get("cache_read", 0)
                                               + tk.get("cache_creation", 0))
    L = [AUTO_BEGIN, "## Metrics (auto)", "",
         "_Generated by `scripts/eval_metrics.py %s` from hook telemetry + the session "
         "transcript. Counts and time are exact; per-box tokens are the box's active window "
         "(approximate when one session interleaves boxes)._" % name, "",
         "| metric | value |", "|--------|-------|",
         "| started | %s |" % (c["start"].isoformat() if c["start"] else "n/a"),
         "| finished | %s |" % (c["end"].isoformat() if c["end"] else "(open)"),
         "| wall-clock (start->finish) | %s |" % _fmt_td(c["wall"]),
         "| active time (idle-filtered) | %s |" % _fmt_td(c["active"]),
         "| output tokens | {:,} |".format(tk.get("output", 0)),
         "| input tokens | {:,} |".format(tk.get("input", 0)),
         "| cache-read tokens | {:,} |".format(tk.get("cache_read", 0)),
         "| cache-creation tokens | {:,} |".format(tk.get("cache_creation", 0)),
         "| assistant turns | {:,} |".format(tk.get("turns", 0)),
         # est. cost, 4-term cache-aware (collapsing input flavors misprices ~10x).
         # The tier names the rate table used - "default" prices unknown models.
         "| est. cost | ${:.2f} ({} tier: {} per Mtok in/out/cache-r/cache-w) |".format(
             tk.get("cost", 0.0), tk.get("tiers", "default"),
             _rate_label(tk.get("tiers", "default"))),
         # cache hit-rate: share of input served from cache. Low (<~70%) across a long
         # box = context churn (compactions / re-reading fresh context every turn).
         "| cache hit-rate | {:.0f}% |".format(hr),
         "| tool output into context | {:,} KB |".format(c.get("tool_out", 0) // 1024),
         "| tool calls | {:,} |".format(c["tool_calls"]),
         "| skill calls | %d |" % c["skill_calls"],
         "| hook fires | %d |" % c["hook_fires"],
         "| drift signals | %d |" % c["drift_count"],
         ""]
    # cache-churn advisory (pass 11): the hit-rate row alone does not force the read; a
    # long box under 70% is context churn (compactions / fresh-context re-reads) and the
    # one lever that fixes it is output economy (narrower tool output), so say so here.
    if tk.get("turns", 0) >= 20 and hr < 70:
        L += ["**Advisory:** cache hit-rate {:.0f}% across {:,} turns - context churn "
              "(compactions or re-reading fresh context). Tighten tool output "
              "(output economy / vm-bg reads) before the next long box.".format(hr, tk["turns"]),
              ""]
    if c.get("bench"):
        L += c["bench"] + [""]
    if c["skills"]:
        L += ["**Skills:** " + ", ".join("%s x%d" % kv for kv in c["skills"].most_common()), ""]
    if c["hooks"]:
        L += ["**Hooks:** " + ", ".join("%s x%d" % kv for kv in c["hooks"].most_common()), ""]
    if c["tools"]:
        L += ["**Tools:** " + ", ".join("%s x%d" % kv for kv in c["tools"].most_common()), ""]
    if c["drifts"]:
        L += ["**Drift signals (auto-detected; the model narrates the cause in Drift moments above):**"]
        for e in c["drifts"][:15]:
            L.append("- [%s] %s" % (e.get("source", "?"), e.get("reason", "")))
        L += [""]
    L.append(AUTO_END)
    return "\n".join(L)


def inject(eval_path, block):
    """Replace the AUTO block in eval.md (or append it) idempotently."""
    if os.path.isfile(eval_path):
        text = open(eval_path, encoding="utf-8").read()
    else:
        text = "# Agent Eval\n"
    if AUTO_BEGIN in text and AUTO_END in text:
        pre = text[:text.index(AUTO_BEGIN)]
        post = text[text.index(AUTO_END) + len(AUTO_END):]
        text = pre + block + post
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    with open(eval_path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _active_name():
    try:
        for line in open(os.path.join(REPO, "targets", "active.md"), encoding="utf-8"):
            s = line.strip()
            if s and not s.startswith(("#", "<!--", "-", "*")):
                return s
    except Exception:
        pass
    return None


def judgement_filled(eval_text):
    """True when eval.md's human JUDGEMENT half is filled, not just the auto block + template stubs.
    The auto block (`--write`) is machine-written; the judgement half (Drift moments / What went
    right / Score) is the part only the agent can write, and `Skill(learn)` has self-cleared with it
    left blank. The tell: the 'one thing to change next box:' line carries real content after its
    colon (the required takeaway), OR a non-stub Drift-moments bullet exists."""
    if not eval_text:
        return False
    # The judgement sections sit BEFORE the auto block in the scaffold layout, so search the
    # whole text: the template's own "- one thing to change next box:" stub has nothing after
    # the colon, so a real fill still matches and a bare template still fails.
    if re.search(r"one thing to change next box:\s*\S", eval_text):
        return True
    # fallback: a real Drift-moments bullet (a "- " line with >10 chars of content, not the "-" stub)
    m = re.search(r"##\s*Drift moments.*?\n(.*?)(?:\n##\s|\Z)", eval_text, re.S | re.I)
    if m:
        for line in m.group(1).splitlines():
            s = line.strip()
            if s.startswith("-") and len(s.lstrip("- ").strip()) > 10 and not s.startswith("<!--"):
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("engagement", nargs="?")
    ap.add_argument("--write", action="store_true", help="inject a Metrics (auto) block into eval.md")
    ap.add_argument("--transcript", help="add a transcript path not yet in .metrics.json")
    ap.add_argument("--check-judgement", action="store_true",
                    help="exit 1 if eval.md's judgement half (Drift moments / Score) is unfilled")
    a = ap.parse_args()
    name = a.engagement or _active_name()
    if not name:
        print("eval_metrics: no engagement given and targets/active.md is empty")
        return 2
    d = os.path.join(REPO, "targets", name)
    if not os.path.isdir(d):
        print("eval_metrics: no such engagement dir: %s" % d)
        return 2
    if a.check_judgement:
        ep = os.path.join(d, "eval.md")
        txt = open(ep, encoding="utf-8").read() if os.path.isfile(ep) else ""
        if judgement_filled(txt):
            print("eval judgement half: filled")
            return 0
        print("eval_metrics: eval.md JUDGEMENT half is unfilled (Drift moments / What went right / "
              "Score / 'one thing to change next box'). Fill it before `touch .learn-done` "
              "(Skill(learn) Phase 0d/7) -- learn must not self-clear with it blank.")
        return 1
    c = collect(d, a.transcript)
    block = render(name, c)
    if a.write:
        inject(os.path.join(d, "eval.md"), block)
        print("eval_metrics: wrote Metrics (auto) block into targets/%s/eval.md" % name)
    else:
        print(block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
