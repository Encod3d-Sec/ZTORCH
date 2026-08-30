"""Local-only retrieval regression gate. Skips on CI (wiki/ content, qmd, and the embedding
model are not present there), and additionally requires an explicit PYTEST_WIKI_EVAL=1 opt-in.
The live --check runs all 51 gold queries through ONE warm `qmd bench` process (model loads
once; ~20 min wall on this CPU-only WSL seat), while the per-query CLI fallback costs ~1-2
min PER QUERY - an unqualified run inside `pytest tests/` used to take 40+ min and made the
full suite effectively unrunnable. Run the gate deliberately: `PYTEST_WIKI_EVAL=1 python3 -m
pytest tests/test_wiki_eval.py -q` (or `python3 scripts/wiki-eval.py --check`) before/after
any index change. The paired visibility test xfails rather than silently passing so an
un-exercised gate is loud. (Note: the PyPI package named `qmd` is an unrelated project; the
fast path drives the bun-installed @tobilu/qmd dist directly, and absolute hit@3 sits lower
than the old CLI-captured baseline because bench lacks the CLI's query auto-expansion -
the baseline is recaptured per runner change, which is what the gate compares against.)"""
import glob
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL = os.path.join(ROOT, "scripts", "wiki-eval.py")
BASELINE = os.path.join(ROOT, "scripts", "wiki-eval-baseline.json")
QMD_PKG = os.environ.get("QMD_PKG", "/root/.bun/install/global/node_modules/@tobilu/qmd")

_WIKI_PRESENT = bool(glob.glob(os.path.join(ROOT, "wiki", "techniques", "**", "*.md"), recursive=True))
_BENCH_PRESENT = shutil.which("bun") is not None and os.path.isdir(os.path.join(QMD_PKG, "dist"))
_QMD_PRESENT = _BENCH_PRESENT or shutil.which("qmd") is not None
_BASELINE_PRESENT = os.path.isfile(BASELINE)
_OPTED_IN = os.environ.get("PYTEST_WIKI_EVAL") == "1"
_CAN_RUN = _WIKI_PRESENT and _QMD_PRESENT and _BASELINE_PRESENT and _OPTED_IN

_needs_index = pytest.mark.skipif(
    not _CAN_RUN,
    reason="retrieval eval needs wiki/ + qmd (bun fast path or CLI) + a captured baseline "
           "+ PYTEST_WIKI_EVAL=1; local-only gate, minutes per run",
)


def test_wiki_eval_gate_visible():
    if not _CAN_RUN:
        pytest.xfail("retrieval eval gate NOT exercised this run (missing wiki/, qmd, or "
                     "baseline, or PYTEST_WIKI_EVAL=1 not set) - this is not a pass. Run "
                     "`PYTEST_WIKI_EVAL=1 python3 -m pytest tests/test_wiki_eval.py -q`.")
    assert True


@_needs_index
def test_verify_gold_paths_exist():
    r = subprocess.run([sys.executable, EVAL, "--verify-gold"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, f"gold set points at a missing page:\n{r.stdout}"


@_needs_index
def test_retrieval_no_regression_vs_baseline():
    r = subprocess.run([sys.executable, EVAL, "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, f"retrieval regressed vs baseline:\n{r.stdout}"
