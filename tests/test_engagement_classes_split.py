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
