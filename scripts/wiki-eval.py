#!/usr/bin/env python3
"""wiki-eval.py - retrieval quality harness for the qmd-indexed wiki.

Reads a tracked gold set (scripts/wiki-eval-gold.json) of representative pentest queries,
each mapped to the canonical wiki page(s) that MUST rank. For each query it runs the qmd
CLI (semantic `qmd query`, or keyword `qmd keyword` when mode="keyword") and computes
hit@3, hit@5, and MRR, per-query and aggregate. Result paths are wiki-relative (e.g.
techniques/web/ssrf.md); a query hits if ANY of its expected paths is in the top-k (either
twin counts).

Read-only against the live index. Fast path: ALL queries go through ONE warm `qmd bench`
process (via scripts/qmd-bench-runner.js under bun - the embedding model + reranker load
once, then per-query cost is ms-to-seconds; the CLI `bench --json` flag is dead upstream,
hence the runner). Falls back to a fresh `qmd query` CLI process per query (~1-2 min each
on this seat - the reason the pytest gate is opt-in). The in-process `import qmd` path is
kept for a hypothetical python binding of the SAME index; the PyPI package named `qmd` is
an unrelated project (chengzhag/qmd-py) and cannot read this index. QMD_VAULT is set
automatically. Exit 0 for reports; exit 1 for the gate modes (--verify-gold with a missing
page, --check with a regression).

  python3 scripts/wiki-eval.py                 # human report (per-query + aggregate)
  python3 scripts/wiki-eval.py --json          # metrics as JSON (subagent/CI consumption)
  python3 scripts/wiki-eval.py --verify-gold   # assert every expected page exists on disk (exit 1 if not)
  python3 scripts/wiki-eval.py --baseline      # write scripts/wiki-eval-baseline.json from the current index
  python3 scripts/wiki-eval.py --check         # compare live eval to the baseline; exit 1 on regression
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
WIKI = os.path.join(VAULT, "wiki")
GOLD = os.path.join(VAULT, "scripts", "wiki-eval-gold.json")
BASELINE = os.path.join(VAULT, "scripts", "wiki-eval-baseline.json")
QMD_PKG = os.environ.get("QMD_PKG", "/root/.bun/install/global/node_modules/@tobilu/qmd")
RUNNER = os.path.join(VAULT, "scripts", "qmd-bench-runner.js")
BENCH_TIMEOUT = 5400  # one warm process for all queries; generous, but never silent-fallback
TOPN = 5
EPSILON = 0.001  # aggregate must not drop by more than this vs baseline

_SCORE = re.compile(r"^\[[0-9.]+\]\s+(.*)$")


def _blocks(stdout):
    """qmd prints, per result: a blank line, a result line, then up to ~300 chars of chunk
    text. Split on blank lines; the first line of each block is the candidate result line."""
    blocks, cur = [], []
    for ln in stdout.splitlines():
        if ln.strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    return blocks


def parse_results(stdout):
    """Ranked wiki-relative paths from `qmd query` / `qmd keyword` stdout. Strips the
    [score] prefix (semantic) and accepts only path-shaped heads (ends .md, no spaces), so a
    prose text block is never mistaken for a result."""
    out = []
    for b in _blocks(stdout):
        head = b[0].strip()
        m = _SCORE.match(head)
        cand = (m.group(1) if m else head).strip()
        if cand.endswith(".md") and " " not in cand:
            out.append(cand)
    return out


_QMD = None  # lazy in-process handle: dict of callables, or False if qmd is not importable


def _qmd_inproc():
    """Load qmd's own query functions once (model stays warm across queries). Returns a dict of
    callables, or False if qmd cannot be imported (caller falls back to the CLI)."""
    global _QMD
    if _QMD is None:
        os.environ.setdefault("QMD_VAULT", VAULT)
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        try:
            from qmd.embedder import embed_one
            from qmd.store import query_keyword, query_semantic
            _QMD = {"embed_one": embed_one, "semantic": query_semantic, "keyword": query_keyword}
        except Exception:
            _QMD = False
    return _QMD


def _dedupe(paths):
    """Order-preserving dedupe so hit@k is page-level (semantic results repeat a file across
    chunks)."""
    seen, out = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _run_inproc(query, mode, window):
    q = _qmd_inproc()
    if not q:
        return None
    try:
        if mode == "keyword":
            res = q["keyword"](query, window)
        else:
            res = q["semantic"](q["embed_one"](query), window)
        return [m["file"] for m in res["metadatas"][0]]
    except Exception:
        return None


def _run_subprocess(query, mode, window):
    cmd = "keyword" if mode == "keyword" else "query"
    env = dict(os.environ, QMD_VAULT=VAULT, HF_HUB_DISABLE_PROGRESS_BARS="1")
    try:
        out = subprocess.check_output(["qmd", cmd, query, "-n", str(window)], text=True, env=env,
                                      stderr=subprocess.DEVNULL, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return []
    return parse_results(out)


def run_query(query, mode, n=TOPN):
    """Ranked, page-level (deduped) wiki-relative paths for one query. Prefers qmd in-process
    (model loaded once, warm across queries); falls back to the `qmd` CLI. Fetches a wider
    window than n so dedupe still yields n distinct pages."""
    window = max(n * 3, 12)
    paths = _run_inproc(query, mode, window)
    if paths is None:
        paths = _run_subprocess(query, mode, window)
    return _dedupe(paths)


def _bench_rows(gold):
    """Project the gold set onto qmd's bench fixture schema (keyword rows score against the
    bm25 backend, semantic rows against `full` = the hybrid + rerank pipeline behind
    `qmd query`). expected_in_top_k is 10 because bench caps top_files at 10 anyway."""
    return {"description": "wiki-eval gold set projection", "version": 1, "queries": [
        {
            "id": f"q{i}",
            "query": row["query"],
            "type": "exact" if row.get("mode") == "keyword" else "semantic",
            "description": row["query"],
            "expected_files": row["expected"],
            "expected_in_top_k": 10,
        }
        for i, row in enumerate(gold)
    ]}


def _wiki_rel(p):
    """Normalize a bench result path (absolute, vault- or wiki-relative) to wiki-relative."""
    return p.replace("\\", "/").split("/wiki/", 1)[-1]


def _run_bench(gold):
    """Fast path: every query through ONE warm `qmd bench` process (model + reranker load
    once). Returns {query: {backend: {top_files: [...]}}} on success, or None when the
    runner is not installed (caller falls back to the per-query CLI path). When the runner
    IS installed but fails or times out, exit loudly instead: the CLI fallback costs
    ~1-2 min per query on this seat and a silent degradation is how a gate turns into a
    multi-hour hang."""
    if not (shutil.which("bun") and os.path.isfile(RUNNER)
            and os.path.isdir(os.path.join(QMD_PKG, "dist"))):
        return None
    tmp = tempfile.mkdtemp(prefix="wiki-eval-")
    fx, out = os.path.join(tmp, "fixture.json"), os.path.join(tmp, "bench.json")
    with open(fx, "w", encoding="utf-8") as fh:
        json.dump(_bench_rows(gold), fh)
    env = dict(os.environ, QMD_VAULT=VAULT, HF_HUB_DISABLE_PROGRESS_BARS="1")
    try:
        subprocess.run(["bun", RUNNER, QMD_PKG, fx, out], env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=BENCH_TIMEOUT)
        with open(out, encoding="utf-8") as fh:
            res = json.load(fh)
    except subprocess.TimeoutExpired:
        sys.exit(f"wiki-eval: bench runner timed out after {BENCH_TIMEOUT}s; refusing to "
                 "fall back to hours of per-query CLI queries. Check the index/model or "
                 "raise BENCH_TIMEOUT.")
    except (subprocess.CalledProcessError, OSError, ValueError) as e:
        sys.exit(f"wiki-eval: bench runner failed ({e}); refusing to fall back to hours of "
                 "per-query CLI queries. Run scripts/qmd-bench-runner.js manually to see the "
                 "error.")
    return {r["query"]: r.get("backends", {}) for r in res.get("results", [])}


def hit_at(ranked, expected, k):
    return any(e in ranked[:k] for e in expected)


def reciprocal_rank(ranked, expected):
    for i, r in enumerate(ranked, 1):
        if r in expected:
            return 1.0 / i
    return 0.0


def load_gold():
    with open(GOLD, encoding="utf-8") as fh:
        return json.load(fh)["queries"]


def verify_gold(gold):
    """Return the list of expected paths that do not exist on disk."""
    missing = []
    for row in gold:
        for p in row["expected"]:
            if not os.path.isfile(os.path.join(WIKI, p)):
                missing.append(f'{p}  (query: "{row["query"]}")')
    return missing


def evaluate(gold, n=TOPN, warm=None):
    """warm = {query: backends} from one `_run_bench` pass; rows missing from it (or
    warm=None) fall back to the per-query CLI path."""
    per = []
    for row in gold:
        ranked = None
        if warm is not None:
            b = warm.get(row["query"], {})
            br = (b.get("bm25" if row.get("mode") == "keyword" else "full")
                  or b.get("hybrid"))
            if br:
                ranked = _dedupe([_wiki_rel(p) for p in br.get("top_files", [])])
        if ranked is None:
            ranked = run_query(row["query"], row.get("mode", "semantic"), n)
        per.append({
            "query": row["query"],
            "expected": row["expected"],
            "hit@3": hit_at(ranked, row["expected"], 3),
            "hit@5": hit_at(ranked, row["expected"], 5),
            "rr": reciprocal_rank(ranked, row["expected"]),
            "top": ranked[:n],
        })
    q = len(per) or 1
    agg = {
        "hit@3": round(sum(p["hit@3"] for p in per) / q, 4),
        "hit@5": round(sum(p["hit@5"] for p in per) / q, 4),
        "mrr": round(sum(p["rr"] for p in per) / q, 4),
        "n_queries": len(per),
    }
    return {"aggregate": agg, "per_query": per}


def main():
    args = sys.argv[1:]

    gold = load_gold()

    if "--verify-gold" in args:
        missing = verify_gold(gold)
        if missing:
            print(f"wiki-eval: {len(missing)} gold expected-path(s) missing on disk:")
            for m in missing:
                print(f"  {m}")
            return 1
        print(f"wiki-eval: gold set OK ({len(gold)} queries, all expected pages exist).")
        return 0

    warm = _run_bench(gold)
    if warm is None and not shutil.which("qmd") and not _qmd_inproc():
        print("wiki-eval: no bench runner (bun + qmd dist), no `qmd` on PATH and no in-process "
              "qmd; cannot run retrieval eval. (--verify-gold works without qmd.)",
              file=sys.stderr)
        return 1

    res = evaluate(gold, warm=warm)

    if "--baseline" in args:
        base = {
            "_comment": "Baseline metrics for scripts/wiki-eval.py --check, captured from the "
                        "clean index via the warm qmd-bench fast path (backend rankings differ "
                        "slightly from the per-query CLI fallback - recapture after any change "
                        "to the runner or backends). Regenerate with: python3 "
                        "scripts/wiki-eval.py --baseline. The pytest gate fails if a live eval "
                        "drops aggregate hit@3 below baseline (minus epsilon) or flips a "
                        "per-query hit@3 from true to false.",
            "captured": datetime.date.today().isoformat(),
            "aggregate": res["aggregate"],
            "per_query_hit3": {p["query"]: p["hit@3"] for p in res["per_query"]},
        }
        with open(BASELINE, "w", encoding="utf-8") as fh:
            json.dump(base, fh, indent=2)
            fh.write("\n")
        print(f"wiki-eval: wrote {os.path.relpath(BASELINE, VAULT)} "
              f"(hit@3={res['aggregate']['hit@3']}, mrr={res['aggregate']['mrr']}, "
              f"n={res['aggregate']['n_queries']}).")
        return 0

    if "--check" in args:
        if not os.path.isfile(BASELINE):
            print("wiki-eval: no baseline; run `python3 scripts/wiki-eval.py --baseline` first.",
                  file=sys.stderr)
            return 1
        with open(BASELINE, encoding="utf-8") as fh:
            base = json.load(fh)
        regressions = []
        if res["aggregate"]["hit@3"] < base["aggregate"]["hit@3"] - EPSILON:
            regressions.append(f'aggregate hit@3 {res["aggregate"]["hit@3"]} < baseline '
                               f'{base["aggregate"]["hit@3"]}')
        live = {p["query"]: p["hit@3"] for p in res["per_query"]}
        for query, was in base.get("per_query_hit3", {}).items():
            if was and not live.get(query, False):
                regressions.append(f'per-query regressed to miss: "{query}"')
        if regressions:
            print(f"wiki-eval CHECK FAIL: {len(regressions)} regression(s):")
            for r in regressions:
                print(f"  {r}")
            return 1
        print(f"wiki-eval CHECK OK: hit@3={res['aggregate']['hit@3']} "
              f">= baseline {base['aggregate']['hit@3']}; no per-query regressions.")
        return 0

    if "--json" in args:
        print(json.dumps(res, indent=2))
        return 0

    agg = res["aggregate"]
    print(f"Wiki retrieval eval  ({agg['n_queries']} queries)")
    print(f"  hit@3 = {agg['hit@3']}   hit@5 = {agg['hit@5']}   MRR = {agg['mrr']}")
    print("-" * 70)
    for p in res["per_query"]:
        mark = "ok " if p["hit@3"] else "MISS"
        print(f"  [{mark}] rr={p['rr']:.2f}  {p['query']}")
        if not p["hit@3"]:
            print(f"         expected {p['expected']}")
            print(f"         got      {p['top']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
