"""Wave 4: the vuln-class/coverage cluster (CLASS_ALIASES, _match_classes, tested_classes,
_class_vocab, _vuln_index_confirmed_ids, confirmed_findings) moves from _engagement.py into its
own _engagement_classes.py module, re-exported from _engagement.py so every existing caller
(next_move.py, status.py -- both use the _engagement.<name> dotted form) keeps working unchanged."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "hooks"))

import _engagement  # noqa: E402
import _engagement_classes  # noqa: E402


def test_engagement_classes_module_has_the_six_symbols():
    for name in ("CLASS_ALIASES", "_match_classes", "tested_classes", "_class_vocab",
                 "_vuln_index_confirmed_ids", "confirmed_findings"):
        assert hasattr(_engagement_classes, name), f"_engagement_classes missing {name}"


def test_engagement_reexports_are_the_same_objects():
    """Re-export, not a copy -- _engagement.X must be identically _engagement_classes.X so a
    monkeypatch of one is visible through the other (existing test-fixture behavior depends on
    this if any test ever patches _engagement.tested_classes directly)."""
    for name in ("CLASS_ALIASES", "_match_classes", "tested_classes", "_class_vocab",
                 "_vuln_index_confirmed_ids", "confirmed_findings"):
        assert getattr(_engagement, name) is getattr(_engagement_classes, name), (
            f"_engagement.{name} is not the same object as _engagement_classes.{name}")


def test_match_classes_still_works_through_engagement(tmp_path):
    """A real behavior check, not just an identity check: the re-exported function still runs."""
    hits = _engagement._match_classes("a stored xss finding", {"xss", "sqli"})
    assert hits == {"xss"}


def test_confirmed_findings_still_works_through_engagement(tmp_path):
    """No Vuln-index.md -> [] (error-safe path), reachable through the _engagement re-export."""
    assert _engagement.confirmed_findings(str(tmp_path)) == []


def test_4a_row_spelling_variant_credits_both(tmp_path):
    """D-D2 (pass 15): a 4a row closed under the driver spelling (`upload`) must credit
    the coverage-classes.json spelling (`file-upload`) too - else next_move's [gap] floor
    re-emits the class forever no matter how the row closes."""
    (tmp_path / "Approach.md").write_text(
        "| asset | vuln class | status |\n|---|---|---|\n| web01 | upload | [x] |\n",
        encoding="utf-8")
    per_asset, _ = _engagement.tested_classes(str(tmp_path), "bugbounty", {"file-upload"})
    assert "file-upload" in per_asset.get("web01", set())


def test_4a_row_json_spelling_credits_driver_spelling(tmp_path):
    """Reverse direction: a hand-written row using the JSON spelling must credit the
    driver spelling, so cmd_coverage (BASE_CLASSES, driver spellings) clears too."""
    (tmp_path / "Approach.md").write_text(
        "| asset | vuln class | status |\n|---|---|---|\n| web01 | file-upload | done |\n",
        encoding="utf-8")
    per_asset, _ = _engagement.tested_classes(str(tmp_path), "bugbounty", {"upload"})
    assert "upload" in per_asset.get("web01", set())


def test_negated_deadend_row_credits_nothing(tmp_path):
    """Audit 2026-09-10 negation guard: a Deadends row saying the class was NOT tested
    (`skipped` / `out of scope`) is the opposite of a credit - crediting it would silence
    the gap reminder for a class never touched. The exhausted row beside it still credits."""
    (tmp_path / "Deadends.md").write_text(
        "| asset | class | what was tried | why exhausted | date | reopen-if |\n"
        "|---|---|---|---|---|---|\n"
        "| 10.0.0.5 | sqli | skipped, out of scope this phase | - | 2026-09-10 | |\n"
        "| 10.0.0.5 | ssrf | full param matrix, OOB sink dry | exhausted | 2026-09-10 | |\n",
        encoding="utf-8")
    per_asset, _ = _engagement.tested_classes(str(tmp_path), "pentest", {"sqli", "ssrf"})
    got = per_asset.get("10.0.0.5", set())
    assert "ssrf" in got                 # the real deadend credits
    assert "sqli" not in got             # the negated row does not


def test_negated_deadend_prose_line_credits_nothing(tmp_path):
    """Same guard on hand-written prose lines (`never tested`, `false positive`): the
    negated line must land in no credit set, while the plain exhausted line still does."""
    (tmp_path / "Deadends.md").write_text(
        "ssrf exhausted after the bounded param matrix\n"
        "ssrf never tested on web02 - no route to the proxy\n"
        "xss false positive, parser echo only\n",
        encoding="utf-8")
    _, glob = _engagement.tested_classes(str(tmp_path), "bugbounty", {"ssrf", "xss"})
    assert glob == {"ssrf"}
