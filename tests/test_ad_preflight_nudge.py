"""Wave 7 W7-6: the first Kerberos/impacket command of an engagement nudges checking for a stale
/etc/hosts realm entry or /etc/krb5.conf line left by a prior ('sister') box - confirmed root cause
of repeated impacket timeouts across multiple past boxes. Fire-once per engagement."""
import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "recon_capture", os.path.join(VAULT, "skills", "hooks", "recon-capture.py"))
recon_capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recon_capture)


def test_fires_on_secretsdump(tmp_path):
    msg = recon_capture._ad_preflight_nudge(str(tmp_path), "secretsdump.py domain/user:pass@10.1.1.5")
    assert msg is not None
    assert "krb5.conf" in msg and "/etc/hosts" in msg


def test_fires_on_getuserspns(tmp_path):
    msg = recon_capture._ad_preflight_nudge(str(tmp_path), "GetUserSPNs.py -request domain/user")
    assert msg is not None


def test_fires_on_bare_kinit(tmp_path):
    msg = recon_capture._ad_preflight_nudge(str(tmp_path), "kinit user@DOMAIN.LOCAL")
    assert msg is not None


def test_does_not_fire_on_unrelated_command(tmp_path):
    assert recon_capture._ad_preflight_nudge(str(tmp_path), "nmap -sV 10.1.1.5") is None


def test_fires_only_once_per_engagement(tmp_path):
    first = recon_capture._ad_preflight_nudge(str(tmp_path), "kerbrute userenum -d domain users.txt")
    second = recon_capture._ad_preflight_nudge(str(tmp_path), "secretsdump.py domain/user:pass@10.1.1.5")
    assert first is not None
    assert second is None
    assert os.path.exists(os.path.join(str(tmp_path), ".ad-preflight-nudged"))
