"""watcher.py + pmonitor.py (hermes port designs 4 and 5): the engagement digest
watcher (grammar-event diffing of log.md/oob.md, claim-once delivery, dry mode
without telegram env vars, heartbeat-with-error sidecar) and the watch-pattern
process monitor (tail regex watch-hits into log.md, dead-pid pruning, registry
checkpoint round-trip). Synthetic tempdir engagement dirs; send_telegram is
monkeypatched so no test touches the network."""
import importlib.util
import json
import os
import subprocess

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(VAULT, "scripts", name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


w = _load("watcher")
pm = _load("pmonitor")

OOB_WAITING = ("| token | sink | class | planted | status | source |\n"
               "|---|---|---|---|---|---|\n"
               "| abc123 | burp | ssrf | 2026-10-12 | waiting | |\n")


def _eng(tmp_path, log="# log\n\nbaseline prose, no grammar tokens\n"):
    d = tmp_path / "eng"
    d.mkdir()
    (d / "log.md").write_text(log, encoding="utf-8")
    (d / "oob.md").write_text(OOB_WAITING, encoding="utf-8")
    return d


def _once(d):
    return w.main(["--eng-dir", str(d), "--once"])


def test_once_no_new_lines_sends_nothing(tmp_path, monkeypatch):
    d = _eng(tmp_path)
    sent = []
    monkeypatch.setattr(w, "send_telegram", lambda *a: sent.append(a) or True)
    monkeypatch.setenv("ZT_WATCH_TELEGRAM_TOKEN", "t")
    monkeypatch.setenv("ZT_WATCH_CHAT_ID", "c")
    assert _once(d) == 0
    assert sent == []
    hb = json.loads((d / ".watcher-heartbeat.json").read_text(encoding="utf-8"))
    assert hb["last_error"] is None and hb["deliveries"] == 0


def test_grammar_lines_digest_once_claim_once(tmp_path, monkeypatch):
    d = _eng(tmp_path)
    monkeypatch.setenv("ZT_WATCH_TELEGRAM_TOKEN", "t")
    monkeypatch.setenv("ZT_WATCH_CHAT_ID", "c")
    sent = []
    monkeypatch.setattr(w, "send_telegram", lambda tok, chat, text: sent.append(text) or True)
    assert _once(d) == 0                        # baseline tick
    with open(d / "log.md", "a", encoding="utf-8") as f:
        f.write("- 2026-10-12 | lane | exec | -> VERIFIED | cred works\n"
                "noise line with no grammar token\n"
                "- FIND-003 sql injection recorded\n")
    oob = (d / "oob.md").read_text(encoding="utf-8").replace("| waiting |", "| HIT |")
    (d / "oob.md").write_text(oob, encoding="utf-8")
    assert _once(d) == 0
    assert len(sent) == 1                       # one digest, entries joined
    assert "VERIFIED" in sent[0] and "FIND-003" in sent[0] and "HIT" in sent[0]
    st = json.loads((d / ".watcher-state.json").read_text(encoding="utf-8"))
    assert len(st["sent"]) == 3                 # 2 log lines + 1 oob row claimed
    hb = json.loads((d / ".watcher-heartbeat.json").read_text(encoding="utf-8"))
    assert hb["last_error"] is None and hb["deliveries"] == 3
    assert _once(d) == 0                        # claim-once: same lines, no resend
    assert len(sent) == 1


def test_dry_mode_without_env_prints_and_marks_delivered(tmp_path, monkeypatch, capsys):
    d = _eng(tmp_path)
    monkeypatch.delenv("ZT_WATCH_TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("ZT_WATCH_CHAT_ID", raising=False)
    assert _once(d) == 0
    with open(d / "log.md", "a", encoding="utf-8") as f:
        f.write("- FIND-001 xss reflected\n")
    capsys.readouterr()
    assert _once(d) == 0
    out = capsys.readouterr().out
    assert "FIND-001" in out
    st = json.loads((d / ".watcher-state.json").read_text(encoding="utf-8"))
    assert len(st["sent"]) == 1                 # marked delivered in dry mode
    capsys.readouterr()
    assert _once(d) == 0
    assert capsys.readouterr().out == ""        # nothing reprinted on re-run


def test_failed_send_records_error_and_never_retries(tmp_path, monkeypatch):
    d = _eng(tmp_path)
    monkeypatch.setenv("ZT_WATCH_TELEGRAM_TOKEN", "t")
    monkeypatch.setenv("ZT_WATCH_CHAT_ID", "c")
    monkeypatch.setattr(w, "send_telegram", lambda *a: False)
    with open(d / "log.md", "a", encoding="utf-8") as f:
        f.write("- 2026 | oob | cb | OOB HIT | token landed\n")
    assert _once(d) == 1
    hb = json.loads((d / ".watcher-heartbeat.json").read_text(encoding="utf-8"))
    assert "telegram" in hb["last_error"]
    st = json.loads((d / ".watcher-state.json").read_text(encoding="utf-8"))
    assert len(st["sent"]) == 1                 # claimed before send: never retried


def test_pmon_add_tick_watch_hit_and_roundtrip(tmp_path):
    d = _eng(tmp_path)
    lf = tmp_path / "scan.out"
    lf.write_text("starting up\n", encoding="utf-8")
    assert pm.main(["add", "--eng-dir", str(d), "fuzz1", "--pid", str(os.getpid()),
                    "--watch", "ROOT", "--logfile", str(lf)]) == 0
    reg = json.loads((d / ".pmon.json").read_text(encoding="utf-8"))
    assert reg["procs"]["fuzz1"]["pid"] == os.getpid()
    assert reg["procs"]["fuzz1"]["watch"] == ["ROOT"]
    assert reg["procs"]["fuzz1"]["offset"] == len(b"starting up\n")   # future-only tail
    assert pm.main(["tick", "--eng-dir", str(d)]) == 0
    assert "watch-hit" not in (d / "log.md").read_text(encoding="utf-8")
    with open(lf, "a", encoding="utf-8") as f:
        f.write("we got ROOT shell\n")
    assert pm.main(["tick", "--eng-dir", str(d)]) == 0
    log = (d / "log.md").read_text(encoding="utf-8")
    assert "| pmon | fuzz1 | watch-hit | `ROOT`" in log
    # checkpoint round-trip: offset advanced, heartbeat recorded, fields intact
    reg = json.loads((d / ".pmon.json").read_text(encoding="utf-8"))
    assert reg["procs"]["fuzz1"]["offset"] == os.path.getsize(str(lf))
    assert reg["procs"]["fuzz1"]["last_tick"] and reg["procs"]["fuzz1"]["alive"] is True


def test_pmon_dead_pid_pruned_to_dead_list(tmp_path):
    d = _eng(tmp_path)
    p = subprocess.Popen(["sleep", "30"])
    p.terminate()
    p.wait()
    assert pm.main(["add", "--eng-dir", str(d), "gone", "--pid", str(p.pid)]) == 0
    assert pm.main(["tick", "--eng-dir", str(d)]) == 0
    reg = json.loads((d / ".pmon.json").read_text(encoding="utf-8"))
    assert "gone" not in reg["procs"]
    dead = json.loads((d / ".pmon.dead.json").read_text(encoding="utf-8"))
    assert dead and dead[0]["pid"] == p.pid
    assert "| pmon | gone | dead |" in (d / "log.md").read_text(encoding="utf-8")


def test_pmon_rm_and_list(tmp_path, capsys):
    d = _eng(tmp_path)
    assert pm.main(["add", "--eng-dir", str(d), "a1", "--pid", str(os.getpid())]) == 0
    capsys.readouterr()
    assert pm.main(["list", "--eng-dir", str(d)]) == 0
    assert "a1" in capsys.readouterr().out
    assert pm.main(["rm", "a1", "--eng-dir", str(d)]) == 0
    assert "a1" not in json.loads(
        (d / ".pmon.json").read_text(encoding="utf-8"))["procs"]
