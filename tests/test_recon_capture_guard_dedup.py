"""Wave 4 bonus finding: `if d and _engagement and not _is_framework_meta(cmd):` was repeated
verbatim 7 times (plus one variant with an extra and-clause) across main(). Extracted into a
shared _active_and_not_meta(d, cmd) helper."""
import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "recon_capture", os.path.join(VAULT, "skills", "hooks", "recon-capture.py"))
recon_capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recon_capture)


def test_active_and_not_meta_true_when_active_and_not_meta():
    # `recon_capture` itself stands in for a truthy `eng` (the _engagement module object) --
    # the test has no real _engagement import available, only truthiness is checked.
    assert recon_capture._active_and_not_meta("some/dir", recon_capture, "nmap -sV 10.1.1.5") is True


def test_active_and_not_meta_false_when_no_engagement_dir():
    assert recon_capture._active_and_not_meta(None, recon_capture, "nmap -sV 10.1.1.5") is False


def test_active_and_not_meta_false_when_no_engagement_module():
    assert recon_capture._active_and_not_meta("some/dir", None, "nmap -sV 10.1.1.5") is False


def test_active_and_not_meta_false_when_framework_meta_command():
    assert recon_capture._active_and_not_meta(
        "some/dir", recon_capture, "cat scripts/playbook.json") is False


def test_main_source_uses_the_helper_not_the_inline_guard():
    """The 7 exact-duplicate inline guards must be gone, replaced by calls to the helper."""
    src = open(os.path.join(VAULT, "skills", "hooks", "recon-capture.py")).read()
    assert src.count("if d and _engagement and not _is_framework_meta(cmd):") == 0
    assert src.count("_active_and_not_meta(d, _engagement, cmd)") >= 8
