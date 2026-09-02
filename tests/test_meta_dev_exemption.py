"""W2-4: capture-poc.py and drift-guard.py each hand-rolled their own copy of the same
"framework/dev command" exemption regex. They had already drifted -- drift-guard.py said
`scripts/(?:offensive|...)`, capture-poc.py still said `scripts/(?:campaign|...)` (a dead prefix,
scripts/campaign.py was deleted in Wave 1) -- so capture-poc.py failed to recognize a
scripts/offensive* path not already covered by its separate offensive.py/offensive-doctor
literals. This test locks in ONE shared source so this class of drift can't recur."""
import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(name, os.path.join(VAULT, *relpath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_meta = _load("_meta", ("skills", "hooks", "_meta.py"))
capture_poc = _load("capture_poc", ("skills", "hooks", "capture-poc.py"))
drift_guard = _load("drift_guard", ("skills", "hooks", "drift-guard.py"))


def test_shared_dev_meta_recognizes_offensive_scripts():
    assert _meta._DEV_META.search("cat scripts/offensive-internals.py")


def test_shared_dev_meta_no_longer_says_campaign():
    # the dead prefix must not survive anywhere in the shared pattern's source text
    assert "campaign" not in _meta._DEV_META.pattern.lower()


def test_capture_poc_uses_shared_source_and_recognizes_offensive():
    assert capture_poc._META_RE.search("cat scripts/offensive-internals.py")


def test_drift_guard_uses_shared_source_and_recognizes_offensive():
    assert drift_guard._META_RE.search("cat scripts/offensive-internals.py")


def test_capture_poc_keeps_its_own_extra_exemptions():
    assert capture_poc._META_RE.search("capture.sh req demo login")
    assert capture_poc._META_RE.search("python3 scripts/eval_metrics.py demo")
