"""Wave 7 W7-4: _scanner_cap's 2nd-heavy-scanner-within-window advisory was gated to
st.get("type") == "ctf" only. The corpus shows the same self-inflicted-ban pattern on non-ctf
targets too (thm_SeaSurfer, thm_royalrouter both recurred despite a documented throttle note) -
widen the check to all engagement types by dropping the unused `st` param entirely."""
import importlib.util
import inspect
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "drift_guard", os.path.join(VAULT, "skills", "hooks", "drift-guard.py"))
drift_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drift_guard)


def test_scanner_cap_fires_on_second_heavy_scanner(tmp_path):
    d = str(tmp_path)
    first = drift_guard._scanner_cap(d, "ffuf -u https://target/FUZZ")
    assert first is None   # first heavy scanner: allowed, recorded
    second = drift_guard._scanner_cap(d, "feroxbuster -u https://target/")
    assert second is not None
    assert "serialize" in second


def test_scanner_cap_signature_no_longer_takes_state():
    params = list(inspect.signature(drift_guard._scanner_cap).parameters)
    assert params == ["d", "cmd"]


def test_scanner_cap_returns_none_for_non_heavy_command(tmp_path):
    assert drift_guard._scanner_cap(str(tmp_path), "curl https://target/") is None
