#!/usr/bin/env python3
"""confirm-bench.py - confirmation regression bench (P3 WS4).

Replays recorded confirmation decisions through the DETERMINISTIC gates only
(find-lint's card contract over synthetic cards plus simulated capture files):
file presence, section population, closure status, claim-vs-capture, bundle
sections. No live targets, no network, no advisory screen. A case whose
expected verdict no longer reproduces is an oracle regression.

  python3 scripts/confirm-bench.py                  # tests/bench/confirm-cases
  python3 scripts/confirm-bench.py --cases <dir> -v

Output: confirm-bench: N cases, X pass, Y fail, Z% agreement ; exit 1 on any
fail. True multi-run sampling is deferred (operator cost decision); this
replay catches regressions, not variance.
"""
import argparse
import glob
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
DEFAULT_CASES = os.path.join(os.path.dirname(HERE), "tests", "bench",
                             "confirm-cases")

_spec = importlib.util.spec_from_file_location("find_lint",
                                               os.path.join(HERE, "find-lint.py"))
find_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(find_lint)


def run_case(case, tmp):
    cid = os.path.basename(case["id"])   # id joins the tmp path: no traversal
    d = os.path.join(tmp, cid)
    os.makedirs(d, exist_ok=True)
    for rel, content in case.get("files", {}).items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
    card = os.path.join(d, case.get("file", "FIND-001-HIGH-bench.md"))
    os.makedirs(os.path.dirname(card), exist_ok=True)
    with open(card, "w", encoding="utf-8") as fh:
        fh.write(case["text"])
    issues, _ = find_lint.lint_file(card, d, patterns=[])
    return not issues


def main(argv=None):
    ap = argparse.ArgumentParser(description="Confirmation regression bench.")
    ap.add_argument("--cases", default=DEFAULT_CASES)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    paths = sorted(glob.glob(os.path.join(args.cases, "*.json")))
    if not paths:
        print("confirm-bench: no cases in %s" % args.cases, file=sys.stderr)
        return 2
    ok = fail = 0
    tmp = tempfile.mkdtemp(prefix="confirm-bench-")
    try:
        for p in paths:
            case = json.loads(open(p, encoding="utf-8").read())
            actual = "pass" if run_case(case, tmp) else "fail"
            agree = actual == case.get("expect")
            if agree:
                ok += 1
            else:
                fail += 1
                print("REGRESSION %s: expected %s, gates now say %s"
                      % (case.get("id", p), case.get("expect"), actual))
            if args.verbose:
                print("  %s: %s (expected %s)" % (case.get("id", p), actual,
                                                  case.get("expect")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = ok + fail
    # truncate, not round: 7/8 must read 87% (round-half-to-even prints 88)
    pct = int(100.0 * ok / n) if n else 0
    print("confirm-bench: %d cases, %d pass, %d fail, %d%% agreement"
          % (n, ok, fail, pct))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
