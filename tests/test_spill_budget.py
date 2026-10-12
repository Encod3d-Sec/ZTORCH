"""Hermes port P1/P3: scripts/spill-run.sh size budget (head/tail keep + full spill to
ingest/ with a [ZT-ELIDE:n/M] non-prose marker), tool-telemetry per-turn output budget
(.metrics.json turn_bytes, one kind="budget" event at 150k), and the lane_validate
over-claim guard (capture-file mtime predating the lane's `in flight @HH:MM` open)."""
import importlib.util
import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPILL = ROOT / "scripts" / "spill-run.sh"

_tt = importlib.util.spec_from_file_location(
    "tool_telemetry_spill", ROOT / "skills" / "hooks" / "tool-telemetry.py")
tt = importlib.util.module_from_spec(_tt)
_tt.loader.exec_module(tt)

_lv = importlib.util.spec_from_file_location("lane_validate_spill",
                                             ROOT / "scripts" / "lane_validate.py")
lv = importlib.util.module_from_spec(_lv)
_lv.loader.exec_module(lv)


def _vault(tmp_path):
    """Synthetic vault with one active engagement (no client data)."""
    v = tmp_path / "vault"
    (v / "targets" / "synth-eng" / "ingest").mkdir(parents=True)
    (v / "targets" / "active.md").write_text("synth-eng\n", encoding="utf-8")
    return v


def _spill(vault, cap, cmd, extra_env=None):
    env = dict(os.environ, ZTORCH_VAULT=str(vault), ZT_SPILL_BYTES=str(cap))
    env.pop("OUTPUT_ECON", None)
    env.update(extra_env or {})
    return subprocess.run(["bash", str(SPILL)] + cmd, capture_output=True, text=True, env=env)


# --- 1. spill-run.sh ---------------------------------------------------------------------

def test_under_cap_is_byte_identical_passthrough(tmp_path):
    v = _vault(tmp_path)
    r = _spill(v, 100000, ["printf", "hello\nworld\n"])
    assert r.returncode == 0 and r.stdout == "hello\nworld\n"
    assert list((v / "targets" / "synth-eng" / "ingest").iterdir()) == []


def test_over_cap_keeps_head_tail_spills_full_and_marks(tmp_path):
    v = _vault(tmp_path)
    full = subprocess.run(["seq", "1", "10000"], capture_output=True, text=True).stdout
    r = _spill(v, 1000, ["bash", "-c", "seq 1 10000; exit 3"])
    assert r.returncode == 3                          # wrapped rc propagates
    spills = list((v / "targets" / "synth-eng" / "ingest").glob("spill-*"))
    assert len(spills) == 1
    assert spills[0].read_text(encoding="utf-8") == full      # FULL output on disk
    m = re.search(r"\[ZT-ELIDE:(\d+)/(\d+) bytes elided here; full output \((\d+) B\) at (\S+);"
                  r" not target output; never reproduce or imitate\]", r.stdout)
    assert m, r.stdout                                 # one non-prose marker line, no bare '...'
    total = len(full.encode())
    assert int(m.group(2)) == int(m.group(3)) == total
    assert int(m.group(1)) == total - 2 * (total * 30 // 100)  # omitted = total - head - tail
    assert m.group(4) == str(spills[0])
    assert r.stdout.startswith("1\n2\n3\n")            # first 30% kept inline
    assert r.stdout.rstrip("\n").endswith("10000")     # last 30% kept inline
    assert r.stdout.count("[ZT-ELIDE:") == 1
    assert "..." not in r.stdout.replace(spills[0].name, "")   # no bare-ellipsis truncation


def test_no_engagement_dir_fails_open_to_passthrough(tmp_path):
    nov = tmp_path / "novault"
    nov.mkdir()
    r = _spill(nov, 10, ["printf", "0123456789abcdefghij"])    # way over a 10B cap
    assert r.returncode == 0 and r.stdout == "0123456789abcdefghij"  # plain passthrough


def test_output_econ_0_bypasses(tmp_path):
    v = _vault(tmp_path)
    r = _spill(v, 10, ["printf", "0123456789abcdefghij"], {"OUTPUT_ECON": "0"})
    assert r.stdout == "0123456789abcdefghij"
    assert list((v / "targets" / "synth-eng" / "ingest").iterdir()) == []


# --- 2. tool-telemetry per-turn output budget ---------------------------------------------

def _metrics(tmp_path):
    return json.load(open(tmp_path / ".metrics.json", encoding="utf-8"))


def test_turn_bytes_append_and_cap_at_200(tmp_path):
    d = str(tmp_path)
    for _ in range(205):
        assert tt._turn_bytes(d, 100) is None          # 20k/turn: never crosses
    m = _metrics(tmp_path)
    assert len(m["turn_bytes"]) == 200                 # capped list
    assert all(r["b"] == 100 and "ts" in r for r in m["turn_bytes"][-5:])
    assert not (tmp_path / ".events.jsonl").exists()   # no budget event under the cap


def test_turn_crossing_150k_fires_one_budget_event(tmp_path):
    d = str(tmp_path)
    assert tt._turn_bytes(d, 100_000) is None          # under
    msg = tt._turn_bytes(d, 100_000)                   # crossing
    assert msg and "150k" in msg and "spill-run.sh" in msg
    assert tt._turn_bytes(d, 100_000) is None          # once per turn, not per call
    ev = [json.loads(l) for l in open(os.path.join(d, ".events.jsonl"), encoding="utf-8")]
    assert sum(e["kind"] == "budget" for e in ev) == 1
    assert "spill-run.sh" in ev[-1]["detail"]


def test_turn_gap_rearms_the_advisory(tmp_path):
    d = str(tmp_path)
    tt._turn_bytes(d, 160_000)                         # fires
    assert _metrics(tmp_path)["turn_fired"] is True
    rows = _metrics(tmp_path)["turn_bytes"]
    rows.append({"ts": time.time() - 3600, "b": 0})    # an hour of silence: new turn
    m = _metrics(tmp_path)
    m["turn_bytes"] = rows
    json.dump(m, open(os.path.join(d, ".metrics.json"), "w", encoding="utf-8"))
    assert tt._turn_bytes(d, 160_000) is not None      # re-armed by the turn gap


def test_turn_bytes_fail_open_on_bad_dir(tmp_path):
    assert tt._turn_bytes(str(tmp_path / "gone"), 5000) is None   # no crash, no file


# --- 3. lane_validate over-claim guard (STALE-EVIDENCE) -----------------------------------

CLOSE = ("- lane %s (10.10.10.9) in flight @%s: SUCCESS = battery.txt names uid=33(www-data)"
         " | tmux win w1 | capture poc/%s -> done\n")


def _eng_with_capture(tmp_path, opened_minutes_ago):
    eng = tmp_path / "eng"
    (eng / "poc" / "a").mkdir(parents=True)
    cap = eng / "poc" / "a" / "battery.txt"
    cap.write_text("id\nuid=33(www-data)\n", encoding="utf-8")
    opened = (datetime.now() - timedelta(minutes=opened_minutes_ago)).strftime("%H:%M")
    (eng / "log.md").write_text(CLOSE % ("a", opened, "a"), encoding="utf-8")
    return eng, cap


def test_fresh_capture_verifies_without_stale_flag(tmp_path, capsys):
    eng, _cap = _eng_with_capture(tmp_path, opened_minutes_ago=1)
    lv.main([str(eng)])
    out = capsys.readouterr().out
    assert "lane a: VERIFIED" in out and "STALE-EVIDENCE" not in out


def test_capture_predating_lane_open_is_stale_evidence_but_still_verified(tmp_path, capsys):
    eng, cap = _eng_with_capture(tmp_path, opened_minutes_ago=1)
    old = time.time() - 7200                          # file written 2h before the lane opened
    os.utime(cap, (old, old))
    lv.main([str(eng)])
    out = capsys.readouterr().out
    assert "lane a: VERIFIED" in out                  # advisory: verdict does NOT flip
    assert "NOT VERIFIED" not in out
    assert "STALE-EVIDENCE" in out and "battery.txt" in out
    assert "pre-existing" in out


def test_stale_evidence_unit_cases(tmp_path):
    eng, cap = _eng_with_capture(tmp_path, opened_minutes_ago=1)
    capdir = str(eng / "poc" / "a")
    old = time.time() - 86400                          # written yesterday
    os.utime(cap, (old, old))
    assert lv.stale_evidence(capdir, "battery.txt landed", "(x) in flight @00:01") == \
        ["battery.txt"]                                # yesterday predates any @HH:MM today
    assert lv.stale_evidence(capdir, "battery.txt landed", "no timestamp here") == []
    assert lv.stale_evidence(str(tmp_path / "nope"), "battery.txt landed",
                             "(x) in flight @00:01") == []          # no dir: fail-open


def test_missing_named_file_stays_not_verified_no_stale_suffix(tmp_path, capsys):
    eng = tmp_path / "eng"
    (eng / "poc" / "b").mkdir(parents=True)
    opened = (datetime.now() - timedelta(minutes=1)).strftime("%H:%M")
    (eng / "log.md").write_text(CLOSE % ("b", opened, "b"), encoding="utf-8")
    lv.main([str(eng)])                                # battery.txt never created
    out = capsys.readouterr().out
    assert "lane b: NOT VERIFIED" in out and "STALE-EVIDENCE" not in out
