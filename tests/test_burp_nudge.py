"""burp-nudge matcher tests (pure _should_nudge)."""
import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "burp_nudge", os.path.join(VAULT, "skills", "hooks", "burp-nudge.py"))
burp_nudge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(burp_nudge)


def test_fires_on_bodyful_payload_curl():
    assert burp_nudge._should_nudge(
        """curl -s -X POST http://10.10.10.5/api -d '{"u":"a' or '1=1"}'""")


def test_fires_on_authed_bodyful_curl():
    assert burp_nudge._should_nudge(
        "curl -s -X PUT http://10.10.10.5/api -H 'Cookie: sid=x' -d '{\"a\":1}'")


def test_fires_on_curl_loop():
    assert burp_nudge._should_nudge(
        "for i in a b c d; do curl -s http://10.10.10.5/$i; done")


def test_fires_inside_vmsh_wrapper():
    assert burp_nudge._should_nudge(
        """bash /root/vm.sh "curl -s -X POST http://x/api -d '{\\"u\\":\\"sleep(1)\\"}'" """)


def test_silent_on_plain_get():
    assert not burp_nudge._should_nudge("curl -s http://10.10.10.5/")


def test_silent_on_burp_rerouted():
    assert not burp_nudge._should_nudge(
        "bash scripts/burp/burp-hunt.sh eng slug 10.10.10.5 8080 http POST /api body.txt")


def test_silent_on_benign_post():
    # body-ful but no payload signature and no auth header: routine API use
    assert not burp_nudge._should_nudge(
        'curl -s -X POST http://10.10.10.5/api -d \'{"name":"demo"}\'')
