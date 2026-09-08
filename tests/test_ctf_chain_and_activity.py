"""ctf chain draft synthesis + cmdlog-only activity synthesis (the webserver-lab gap).

A ctf keeps its live chain in state.md's own ## Chain PROSE list (stage: what -> opens), not a
Killchain.md table -- so the batch-3/4 Killchain auto-draft never fired for ctf, and the table
row counter never saw real prose chain lines either. And a lab-style engagement whose work lives
entirely in poc/cmdlog (state files still template-blank) synthesized nothing at all."""
import importlib.util
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "hooks"))
_spec = importlib.util.spec_from_file_location(
    "_engagement", ROOT / "skills" / "hooks" / "_engagement.py")
_engagement = importlib.util.module_from_spec(_spec)
sys.modules["_engagement"] = _engagement
_spec.loader.exec_module(_engagement)

CTF_CHAIN_TMPL = """---
engagement_type: ctf
---
# State

## Chain

Ordered attack-path hops, operator-maintained live. One line per hop:

`stage: what happened -> what it opens up`

-
"""


def _mk_ctf(tmp_path, loot_rows=0, chain_lines=0):
    d = tmp_path / "ctfbox"
    d.mkdir(exist_ok=True)
    state = CTF_CHAIN_TMPL
    if chain_lines:
        state += "\n".join("foothold: cred found %d -> user shell" % i
                           for i in range(chain_lines)) + "\n"
    (d / "state.md").write_text(state, encoding="utf-8")
    if loot_rows:
        (d / "loot.md").write_text(
            "| type | value | source | notes |\n|---|---|---|---|\n"
            + "".join("| cred | user%d:pw | login form | reused |\n" % (i + 1)
                      for i in range(loot_rows)), encoding="utf-8")
    return str(d)


def test_ctf_drafts_land_in_state_chain_not_killchain(tmp_path):
    d = _mk_ctf(tmp_path, loot_rows=2)
    added = _engagement.append_draft_chain_rows(d)
    assert added == 2
    state = open(pathlib.Path(d) / "state.md", encoding="utf-8").read()
    assert "draft (auto)" in state and "user1:pw" in state
    assert not (pathlib.Path(d) / "Killchain.md").exists(), "ctf must never gain a Killchain.md"


def test_ctf_drafts_idempotent_on_value(tmp_path):
    d = _mk_ctf(tmp_path, loot_rows=1)
    assert _engagement.append_draft_chain_rows(d) == 1
    assert _engagement.append_draft_chain_rows(d) == 0


def test_ctf_prose_chain_lines_count_as_substance(tmp_path):
    # the REAL ctf chain shape is prose lines, not a table; the unmarked-close gap must see them
    d = _mk_ctf(tmp_path, chain_lines=2)
    ts = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    (pathlib.Path(d) / ".events.jsonl").write_text(
        json.dumps({"ts": ts, "kind": "tool"}) + "\n", encoding="utf-8")
    assert _engagement.unmarked_close_gap(d) >= 1


def test_pentest_drafts_still_go_to_killchain(tmp_path):
    d = tmp_path / "ptbox"
    d.mkdir()
    (d / "state.md").write_text(
        "---\nengagement_type: pentest\n---\n# State\n", encoding="utf-8")
    (d / "loot.md").write_text(
        "| type | value | source | notes |\n|---|---|---|---|\n| cred | pw1 | x | y |\n",
        encoding="utf-8")
    (d / "Killchain.md").write_text("| path | stage | status | blocker | next-move |\n"
                                    "|---|---|---|---|---|\n", encoding="utf-8")
    assert _engagement.append_draft_chain_rows(d) == 1
    assert "draft (auto)" in (d / "Killchain.md").read_text()


def test_ctf_paths_gap_counts_state_chain(tmp_path):
    # paths_write_gap returned 0 for ctf across the board; now loot vs state ## Chain substance
    d = _mk_ctf(tmp_path, loot_rows=1)
    assert _engagement.paths_write_gap(d) == 1
    # once the chain carries a real line, the gap closes
    d2 = _mk_ctf(tmp_path, loot_rows=1, chain_lines=1)
    assert _engagement.paths_write_gap(d2) == 0


# --- cmdlog-only activity synthesis (the webserver-lab shape) ---

def _mk_lab(tmp_path, entries, loot_rows=0):
    d = tmp_path / "lab"
    d.mkdir(exist_ok=True)
    (d / "state.md").write_text("---\nengagement_type: pentest\n---\n# State\n"
                                "\n| target | service | port | access | notes |\n"
                                "|---|---|---|---|---|\n", encoding="utf-8")
    (d / "loot.md").write_text("| type | value | source | notes |\n|---|---|---|---|\n",
                               encoding="utf-8")
    (d / "Killchain.md").write_text("| path | stage | status | blocker | next-move |\n"
                                    "|---|---|---|---|---|\n", encoding="utf-8")
    cdir = d / "poc" / "cmdlog"
    cdir.mkdir(parents=True)
    (cdir / "curl.md").write_text(
        "\n## 2026-09-01 10:00:00\n\n```\ncurl -s http://10.0.0.5/api\n```\n\n```\nok\n```\n"
        * entries, encoding="utf-8")
    (cdir / "nmap.md").write_text(
        "\n## 2026-09-01 10:00:00\n\n```\nnmap 10.0.0.5\n```\n\n```\n22 open\n```\n"
        * max(1, entries // 2), encoding="utf-8")
    if loot_rows:
        (d / "loot.md").write_text(
            "| type | value | source | notes |\n|---|---|---|---|\n| cred | pw | x | y |\n",
            encoding="utf-8")
    return str(d)


def test_activity_draft_synthesizes_from_cmdlog_only(tmp_path):
    d = _mk_lab(tmp_path, entries=12)
    n = _engagement.append_activity_draft(d)
    assert n >= 1, "blank state + rich cmdlog must synthesize an activity block"
    state = open(pathlib.Path(d) / "state.md", encoding="utf-8").read()
    assert "## Activity" in state and "curl" in state and "10.0.0.5" in state


def test_activity_draft_idempotent(tmp_path):
    d = _mk_lab(tmp_path, entries=12)
    assert _engagement.append_activity_draft(d) >= 1
    assert _engagement.append_activity_draft(d) == 0


def test_activity_draft_skipped_when_state_has_substance(tmp_path):
    # loot rows exist -> the chain/loot synthesis owns state; no activity block
    d = _mk_lab(tmp_path, entries=12, loot_rows=1)
    assert _engagement.append_activity_draft(d) == 0


def test_activity_draft_needs_min_entries(tmp_path):
    d = _mk_lab(tmp_path, entries=3)
    assert _engagement.append_activity_draft(d) == 0


def test_cmdlog_counts_as_unmarked_close_substance(tmp_path):
    # webserver-lab: all state files blank, work only in cmdlog -> the box still closed unmeasured
    d = _mk_lab(tmp_path, entries=12)
    ts = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    (pathlib.Path(d) / ".events.jsonl").write_text(
        json.dumps({"ts": ts, "kind": "tool"}) + "\n", encoding="utf-8")
    assert _engagement.unmarked_close_gap(d) >= 1


def test_closeout_wires_activity_draft():
    src = (ROOT / "skills" / "hooks" / "close-out.py").read_text(encoding="utf-8")
    assert "append_activity_draft" in src
