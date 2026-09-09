"""bench.py: scores a completed engagement dir against an expected-coverage
manifest -- full credit (2) = class tested AND a poc artifact on disk, partial
(1) = tested with no evidence, zero (0) = untested; missing dir/manifest exits 2.
Fixture: tests/fixtures/bench-eng + tests/fixtures/bench-manifest.json
(example.test data only). Standalone assert-based; run: python3 tests/test_bench.py
"""
import contextlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import bench  # noqa: E402

FIX_ENG = ROOT / "tests" / "fixtures" / "bench-eng"
FIX_MANIFEST = ROOT / "tests" / "fixtures" / "bench-manifest.json"


def _score():
    return bench.score_engagement(FIX_ENG, json.loads(FIX_MANIFEST.read_text()))


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = bench.main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_full_partial_and_zero_scenarios():
    res = _score()
    by_id = {s["id"]: s["score"] for s in res["scenarios"]}
    assert by_id["lab-sqli-full"] == 2          # [x] row + poc/sqli-union.png exists
    assert by_id["lab-ssrf-no-evidence"] == 1   # [x] row, empty poc cell, no artifact
    assert by_id["lab-xss-untouched"] == 0      # never tested
    assert by_id["lab-auth-state-only"] == 1    # named in state.md findings, no poc
    assert by_id["lab-rce-substring-trap"] == 0  # "sources" in frontmatter is not "rce"
    assert res["total"] == 4 and res["max_total"] == 10
    assert res["coverage_pct"] == 40.0
    assert res["counts"] == {"covered": 1, "partial": 2, "untested": 2}


def test_missing_engagement_dir_exits_two():
    rc, out, err = _run(["--eng", str(ROOT / "tests" / "fixtures" / "no-such-eng-xyz"),
                         "--manifest", str(FIX_MANIFEST)])
    assert rc == 2 and "no such engagement dir" in err


def test_missing_manifest_exits_two():
    rc, out, err = _run(["--eng", str(FIX_ENG), "--manifest", "no-such-manifest.json"])
    assert rc == 2 and "no such manifest" in err


def test_json_output_shape():
    rc, out, _err = _run(["--eng", str(FIX_ENG), "--manifest", str(FIX_MANIFEST), "--json"])
    assert rc == 0
    data = json.loads(out)
    assert data["total"] == 4 and data["counts"]["covered"] == 1
    assert data["coverage_pct"] == 40.0


def test_table_output_has_coverage_line():
    rc, out, _err = _run(["--eng", str(FIX_ENG), "--manifest", str(FIX_MANIFEST)])
    assert rc == 0
    assert "coverage: 40.0% (4/10)  covered=1 partial=2 untested=2" in out


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for n, f in fns:
        f()
        print("PASS %s" % n)
    print("all %d bench tests passed" % len(fns))
