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
    """Poll-on-condition: a while/until loop exempts the sleep inside it. (The
    exemption now lives inside blind_sleeps() itself -- see has_poll_loop -- rather
    than only in main(), so blind_sleeps() alone reflects the real decision.)"""
    assert sleep_guard.blind_sleeps("until grep -q Ready app.log; do sleep 20; done") == []


def test_quoted_until_no_longer_falsely_exempts_a_real_blind_sleep():
    """Regression: the while/until exemption checked the RAW command, not quote-blanked,
    so any command containing the WORD "until"/"while" anywhere -- even inside an
    unrelated quoted echo -- disabled the guard for a genuinely blind sleep elsewhere in
    the same command."""
    assert sleep_guard.blind_sleeps('echo "run until ready"; sleep 300') == ["300"]


def test_for_loop_poll_now_exempt():
    """A bounded for-retry loop with a sleep beat between attempts is a legitimate poll,
    same as while/until -- previously only while/until were recognized."""
    assert sleep_guard.blind_sleeps(
        'for i in $(seq 1 5); do curl -s http://10.10.10.5/ && break; sleep 30; done') == []


def test_loop_does_not_exempt_trailing_sibling_sleep():
    """Regression (host-internals pass 1): the poll-loop exemption was whole-command, so
    `for ...; do true; done; sleep 300` passed fully exempt -- the loop exempted a blind
    sleep AFTER it. Exemption is per-segment (with opener->done depth) now: it covers the
    loop's own body only."""
    assert sleep_guard.blind_sleeps("for i in $(seq 1 5); do true; done; sleep 300") == ["300"]
    assert sleep_guard.blind_sleeps("until nc -z h 443; do sleep 5; done; sleep 120") == ["120"]


def test_multiline_loop_body_still_exempt():
    """A loop written across lines (opener / do / body / done on separate lines) keeps its
    body exempt: the depth counter tracks opener -> done across segments, so the bare
    `sleep 30` body line is NOT a new blind sleep."""
    assert sleep_guard.blind_sleeps("while true\ndo\n  sleep 30\ndone\n") == []

