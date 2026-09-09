#!/usr/bin/env python3
"""bench.py - score a COMPLETED engagement dir against an expected-coverage manifest.

Reads targets/<eng>/ (the Approach.md 4a coverage table, state.md, poc/) and
scores each manifest scenario 0/1/2:
  2  covered: every expected class tested (4a row [x], or named in state.md)
             AND backed by a poc/evidence artifact on disk
  1  partial: class tested but no evidence artifact
  0  untested

Class names come from scripts/coverage-classes.json -- the same vocabulary the
4a board and hunt routing use. The manifest (scripts/bench-labs.json by default)
maps scenario id -> {name, source, expected_classes}.

Usage:
  python3 scripts/bench.py --eng targets/<name> [--manifest scripts/bench-labs.json] [--json]

score_engagement(eng_dir, manifest) -> dict is the single import point for later
tooling (e.g. scripts/eval_metrics.py could aggregate it per engagement).
"""
import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VAULT = SCRIPT_DIR.parent
DEFAULT_MANIFEST = SCRIPT_DIR / "bench-labs.json"


def _known_classes():
    """Set of class names from scripts/coverage-classes.json, or None if it
    cannot be read (the unknown-class warning then fails open)."""
    try:
        data = json.loads((SCRIPT_DIR / "coverage-classes.json").read_text(encoding="utf-8"))
        return {c for classes in data.values() if isinstance(classes, list) for c in classes}
    except Exception:
        return None


def _board_rows(eng_dir):
    """Row dicts (lowercased headers) from every markdown table in Approach.md
    whose header carries a `vuln class` + `status` column (the 4a coverage
    matrix; Approach.md may hold other tables). [] if absent."""
    p = Path(eng_dir) / "Approach.md"
    if not p.is_file():
        return []
    rows, header, body = [], None, []

    def flush():
        if header and "vuln class" in header and "status" in header:
            rows.extend(dict(zip(header, r)) for r in body)

    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            flush()
            header, body = None, []
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue                       # markdown separator row
        if header is None:
            header = [c.lower() for c in cells]
        else:
            body.append(cells + [""] * (len(header) - len(cells)))
    flush()
    return rows


def score_engagement(eng_dir, manifest):
    """Score one engagement dir against a manifest dict (id -> {name, source,
    expected_classes}). Per scenario the score is the minimum across its
    expected classes (2/1/0 as above). Returns the result dict; also the
    --json payload. Keys starting with "_" (manifest comments) are skipped."""
    eng = Path(eng_dir)
    board = _board_rows(eng)
    sp = eng / "state.md"
    state_txt = sp.read_text(encoding="utf-8", errors="ignore").lower() if sp.is_file() else ""
    poc_dir = eng / "poc"
    # Word-boundary match on purpose: "rce" must not hit "sources", "auth" not
    # "authorization". ponytail: whole-token match only; per-file class tagging
    # if ambiguity ever shows up on a real board.
    poc_names = ([p.name.lower().replace("_", "-") for p in poc_dir.iterdir()]
                 if poc_dir.is_dir() else [])

    def _names(cls):
        pat = re.compile(r"\b" + re.escape(cls) + r"\b")
        if pat.search(state_txt):
            return True
        return any(pat.search(n) for n in poc_names)

    known = _known_classes()
    for sid, spec in manifest.items():
        if sid.startswith("_") or not isinstance(spec, dict):
            continue
        for cls in (spec.get("expected_classes") or []):
            if known is not None and cls not in known:
                print("bench: warn: class '%s' (scenario %s) is not in "
                      "scripts/coverage-classes.json" % (cls, sid), file=sys.stderr)

    def class_score(cls):
        cls = cls.lower()
        # tested = an [x] 4a row (coverage-classes.json's own definition) or the
        # class named in state.md findings/loot.
        closed = [r for r in board
                  if (r.get("vuln class") or "").strip().lower() == cls
                  and (r.get("status") or "").strip() == "[x]"]
        if not closed and not _names(cls):
            return 0
        for r in closed:
            poc = (r.get("poc") or "").strip()
            if poc and (eng / poc).is_file():
                return 2                   # board cites an evidence file that exists
        if any(re.search(r"\b" + re.escape(cls) + r"\b", n) for n in poc_names):
            return 2                       # a poc/ artifact names the class
        return 1                           # tested, nothing on disk

    scenarios, total, max_total = [], 0, 0
    counts = {"covered": 0, "partial": 0, "untested": 0}
    for sid, spec in manifest.items():
        if sid.startswith("_") or not isinstance(spec, dict):
            continue
        cls_scores = {c: class_score(c) for c in (spec.get("expected_classes") or [])}
        score = min(cls_scores.values()) if cls_scores else 0
        counts["covered" if score == 2 else "partial" if score == 1 else "untested"] += 1
        total += score
        max_total += 2
        scenarios.append({"id": sid, "name": spec.get("name", ""),
                          "score": score, "classes": cls_scores})
    return {"engagement": str(eng), "scenarios": scenarios,
            "total": total, "max_total": max_total,
            "coverage_pct": round(total * 100.0 / max_total, 1) if max_total else 0.0,
            "counts": counts}


def _render(res):
    w = max([len(s["id"]) for s in res["scenarios"]] + [len("scenario")])
    out = ["%-*s  %5s  %s" % (w, "scenario", "score", "detail"),
           "-" * (w + 18)]
    for s in res["scenarios"]:
        detail = " ".join("%s=%d" % kv for kv in s["classes"].items())
        out.append("%-*s  %5d  %s" % (w, s["id"], s["score"], detail))
    c = res["counts"]
    out.append("coverage: %.1f%% (%d/%d)  covered=%d partial=%d untested=%d"
               % (res["coverage_pct"], res["total"], res["max_total"],
                  c["covered"], c["partial"], c["untested"]))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bench.py")
    ap.add_argument("--eng", required=True,
                    help="engagement dir (targets/<name> or a path)")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST),
                    help="expected-coverage manifest (default: scripts/bench-labs.json)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args(argv)

    eng = Path(a.eng)
    if not eng.is_dir():
        cand = VAULT / "targets" / a.eng
        if cand.is_dir():
            eng = cand
    if not eng.is_dir():
        print("bench: no such engagement dir: %s" % a.eng, file=sys.stderr)
        return 2
    mp = Path(a.manifest)
    if not mp.is_file():
        print("bench: no such manifest: %s" % a.manifest, file=sys.stderr)
        return 2
    try:
        manifest = json.loads(mp.read_text(encoding="utf-8"))
    except ValueError as e:
        print("bench: bad manifest JSON (%s): %s" % (mp, e), file=sys.stderr)
        return 2
    if not isinstance(manifest, dict):
        print("bench: manifest must be a JSON object mapping scenario id -> spec", file=sys.stderr)
        return 2

    res = score_engagement(eng, manifest)
    print(json.dumps(res, indent=2) if a.json else _render(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
