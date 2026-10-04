import importlib.util
import json
import os

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "skills", "hooks", "tool-telemetry.py")


def _mod():
    spec = importlib.util.spec_from_file_location("tt", str(HOOK))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_same_tool_five_times_fires_once_then_resets(tmp_path):
    tt = _mod()
    d = str(tmp_path)
    open(os.path.join(d, ".metrics.json"), "w").write("{}")
    fired = [tt._mentor_check(d, "Bash", ["nmap"]) for _ in range(5)]
    assert sum(x is not None for x in fired) == 1
    assert "nmap" in fired[-1] and "5" in fired[-1]
    # reset-on-fire: the next 4 calls are silent, the 5th fires again
    fired2 = [tt._mentor_check(d, "Bash", ["nmap"]) for _ in range(5)]
    assert sum(x is not None for x in fired2) == 1


def test_open_lane_gets_its_own_bucket(tmp_path):
    tt = _mod()
    d = str(tmp_path)
    open(os.path.join(d, ".metrics.json"), "w").write("{}")
    open(os.path.join(d, "log.md"), "a").write(
        "- lane lf1 (host1) in flight @23:59: SUCCESS = x | tmux win - | capture c | handle h1\n")
    for _ in range(4):
        assert tt._mentor_check(d, "Bash", ["ffuf"]) is None
    m = json.load(open(os.path.join(d, ".metrics.json")))
    assert m["mentor"]["lane"]["ffuf"] == 4      # counted under the lane bucket, not brain


def test_no_lane_counts_under_brain_and_never_raises(tmp_path):
    tt = _mod()
    assert tt._mentor_check(str(tmp_path), "Read", None) is None   # brain bucket, no crash
    assert tt._mentor_check(str(tmp_path / "gone"), "Bash", ["nmap"]) is None  # fail-open
