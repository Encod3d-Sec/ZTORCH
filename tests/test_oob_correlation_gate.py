"""OOB auto-flip invocation gating: displaying the ledger (or anything quoting its
rows) must not flip a waiting row to HIT; only a non-table output line naming the
token does. Peer-seat incident 2026-09-29: a cat of oob.md auto-flipped 4 rows."""
import importlib.util
import os
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "recon_capture", os.path.join(VAULT, "skills", "hooks", "recon-capture.py"))
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)

TOK = "ssrf-rt1.datfufknbo97rrvo76rgr1r4putru9jqc.oast.pro"


def test_ledger_row_displayed_is_not_a_callback():
    ledger = ("| %s | api.paslaugos.vilnius.lt POST /auth/refresh-jwt refresh_token "
              "| ssrf | 2026-09-29 | waiting | lane-apipl-ssrf |" % TOK)
    assert rc._oob_callback_observed(ledger, TOK) is False


def test_zero_hit_grep_output_is_not_a_callback():
    assert rc._oob_callback_observed("", TOK) is False


def test_listener_json_line_is_a_callback():
    poll = ('{"unique-id":"%s","remote-address":"10.0.0.9:443",'
            '"timestamp":"2026-09-29T03:41:02Z"}' % TOK)
    assert rc._oob_callback_observed(poll, TOK) is True


def test_raw_poll_line_is_a_callback():
    assert rc._oob_callback_observed("DNS %s A 10.0.0.9" % TOK, TOK) is True


def test_mixed_output_with_any_real_line_flips():
    ledger = "| %s | sink | ssrf | 2026-09-29 | waiting | lane |" % TOK
    assert rc._oob_callback_observed(ledger + "\nGET /ssrf-rt1.datfufknbo97rrvo76rgr1r4putru9jqc.oast.pro/ 200", TOK) is True
