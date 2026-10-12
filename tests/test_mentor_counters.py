import importlib.util
import json
import os
import time

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "skills", "hooks", "tool-telemetry.py")


def _mod():
    spec = importlib.util.spec_from_file_location("tt", str(HOOK))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _unstamp(d):
    # the mentor advisory is 15-min deduped; tests exercising repeat fires drop the stamp
    try:
        os.remove(os.path.join(d, ".mentor-stamp"))
    except FileNotFoundError:
        pass


def test_same_tool_five_times_fires_once_then_resets(tmp_path):
    tt = _mod()
    d = str(tmp_path)
    open(os.path.join(d, ".metrics.json"), "w").write("{}")
    fired = [tt._mentor_check(d, "Bash", ["nmap"]) for _ in range(5)]
    assert sum(x is not None for x in fired) == 1
    assert "nmap" in fired[-1] and "5" in fired[-1]
    # reset-on-fire: the next 4 calls are silent, the 5th fires again (stamp dropped:
    # the real advisor fires at most once per 15 min)
    _unstamp(d)
    fired2 = [tt._mentor_check(d, "Bash", ["nmap"]) for _ in range(5)]
    assert sum(x is not None for x in fired2) == 1
    # stamp written at fire time -> an immediate second grind is silent
    assert tt._mentor_check(d, "Bash", ["nmap"]) is None


def test_mentor_scoped_to_probe_bins_not_read_tier(tmp_path):
    """tokens review issue 1: 5 sequential Reads/greps/python3 runs are the analysis
    workflow, not a grind loop - read-tier names must never count or fire."""
    tt = _mod()
    d = str(tmp_path)
    open(os.path.join(d, ".metrics.json"), "w").write("{}")
    for _ in range(12):
        assert tt._mentor_check(d, "Read", None) is None
        assert tt._mentor_check(d, "Bash", ["grep"]) is None
        assert tt._mentor_check(d, "Bash", ["python3", "find", "head"]) is None
    m = json.load(open(os.path.join(d, ".metrics.json")))
    assert not m.get("mentor", {}).get("brain")   # nothing counted, nothing fired
    # probe/enum class still steers
    fired = [tt._mentor_check(d, "Bash", ["gobuster"]) for _ in range(5)]
    assert sum(x is not None for x in fired) == 1


def test_mentor_stamp_caps_fire_rate(tmp_path):
    """the stamp file holds the fire epoch: within 15 min the advisory stays silent
    (~4/hour ceiling), counters re-arming only after it goes stale."""
    tt = _mod()
    d = str(tmp_path)
    open(os.path.join(d, ".metrics.json"), "w").write("{}")
    for _ in range(5):
        tt._mentor_check(d, "Bash", ["ffuf"])              # fires, stamps
    assert os.path.isfile(os.path.join(d, ".mentor-stamp"))
    assert float(open(os.path.join(d, ".mentor-stamp")).read()) <= time.time() + 1
    for _ in range(10):                                    # within the window: silent
        assert tt._mentor_check(d, "Bash", ["ffuf"]) is None
    open(os.path.join(d, ".mentor-stamp"), "w").write(str(time.time() - 901))
    fired = [tt._mentor_check(d, "Bash", ["ffuf"]) for _ in range(5)]
    assert sum(x is not None for x in fired) == 1          # stale stamp re-arms


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
