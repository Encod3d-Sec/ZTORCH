"""W2-7: sleep-guard.py's SLEEP_RE had no quote-awareness, so a command whose TEXT merely
CONTAINS "sleep N" inside a quoted string (an echo, a grep pattern) was falsely flagged as a
blind-sleep violation even though no `sleep` command was actually invoked."""
import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "sleep_guard", os.path.join(VAULT, "skills", "hooks", "sleep-guard.py"))
sleep_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sleep_guard)


def test_real_sleep_command_still_flagged():
    assert sleep_guard.blind_sleeps("sleep 15") == ["15"]
    assert sleep_guard.blind_sleeps("sleep 15 && echo done") == ["15"]


def test_short_sleep_not_flagged():
    assert sleep_guard.blind_sleeps("sleep 5") == []


def test_quoted_mention_not_flagged():
    """The exact false-positive class W2-7 names."""
    assert sleep_guard.blind_sleeps('echo "we need to sleep 15 before retry"') == []
    assert sleep_guard.blind_sleeps('grep -n "sleep 15" script.py') == []


def test_while_loop_sleep_still_exempt():
    """Pre-existing behavior (poll-on-condition): unaffected by this fix."""
    assert sleep_guard.blind_sleeps("until grep -q Ready app.log; do sleep 20; done") == ["20"]
