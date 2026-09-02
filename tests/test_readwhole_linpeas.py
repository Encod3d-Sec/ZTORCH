"""Wave 7 W7-3: extend the read-whole-not-grep nudge's high-signal set to cover linpeas/pspy
output, not just fixed config paths - thm_SeaSurfer's root cause was grepping linpeas output and
missing the box's actual pam_ssh_agent_auth privesc line (cost the entire engagement)."""
import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "recon_capture", os.path.join(VAULT, "skills", "hooks", "recon-capture.py"))
recon_capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recon_capture)


def test_high_signal_cfg_matches_linpeas_and_pspy():
    assert recon_capture._HIGH_SIGNAL_CFG.search("cat linpeas.log")
    assert recon_capture._HIGH_SIGNAL_CFG.search("pspy64 | tee pspy.log")


def test_readwhole_nudge_fires_on_grepped_linpeas(tmp_path):
    import _engagement
    (tmp_path / "state.md").write_text("| access |\n|---|\n| foothold |\n")
    msg = recon_capture._readwhole_nudge(str(tmp_path), "cat linpeas.log | grep -i pam", _engagement)
    assert msg is not None
    assert "linpeas" in msg.lower() or "linpeas.log" in msg
