"""tool-telemetry .metrics.json writes must be atomic (_telemetry._save): hook
processes run concurrently per tool call, and the bare open(w)+json.dump sites
lost whole files to interleaved writes (observed live: 8 'baseline reset' events
wiping spend_usd, transcripts and started_at - docs/reviews/2026-10-12-logging.md
D1). Two processes racing read-modify-write cycles may lose an update; they must
never leave a file json cannot parse."""
import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "skills" / "hooks" / "tool-telemetry.py"

# each worker drives both .metrics.json writers (_turn_bytes, _mentor_check)
# through the module, exactly as two concurrent hook invocations would
_WORKER = """
import importlib.util, sys
spec = importlib.util.spec_from_file_location("tt", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for _ in range(50):
    m._turn_bytes(sys.argv[2], 64)
    m._mentor_check(sys.argv[2], "Bash", ["nmap"])
"""


def test_two_processes_50_writes_each_never_corrupt_metrics(tmp_path):
    procs = [subprocess.Popen(
        [sys.executable, "-c", _WORKER, str(HOOK), str(tmp_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(2)]
    for p in procs:
        assert p.wait(timeout=120) == 0
    m = json.loads((tmp_path / ".metrics.json").read_text(encoding="utf-8"))
    # atomicity, not linearizability: racing read-modify-write cycles may LOSE an
    # update (a clobbered counter), but every written file carries turn_bytes (the
    # first write sets it and no write ever drops it), and none is unparseable.
    assert m["turn_bytes"] and len(m["turn_bytes"]) >= 1


def test_no_bare_metrics_json_writes_remain():
    """guard the guard: every .metrics.json write in the hook routes through
    _telemetry._save (tmp + os.replace), never a bare open(path, 'w')."""
    src = HOOK.read_text(encoding="utf-8")
    assert "open(mp, \"w\"" not in src
    assert src.count("_telemetry._save(d, m)") == 3
