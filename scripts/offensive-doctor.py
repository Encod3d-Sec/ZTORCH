#!/usr/bin/env python3
"""offensive-doctor.py [--verbose] [--fix] [--ack <n>] - health check for the /offensive driver subsystem.

Verifies a machine has the /offensive driver correctly set up so every machine runs the
same driver, then runs a live init->index->board->next smoke test on a throwaway fixture
engagement. Reworked onto the hermes-doctor Finding pattern (port spec design 3): every
check accumulates into a Finding (issues / manual_issues / fixed), each check prints its
own pass/warn/fail rows, and the run ends with a NUMBERED list of manual-intervention
items.

Row classes and exit code:
  FAIL  issue            real breakage; always gates the exit, numbered, NOT ackable.
  WARN  manual advisory  needs operator action; gates the exit until --ack suppresses
                         it (numbered, ackable, --fix may clear it).
  WARN  advisory-only    legacy seat-tool notes (zg/caido/skill-scan/4b-hollow/wiki
                         lint); printed and counted, never gate.
  SKIP  unchecked        the thing this seat cannot check (no VM creds, no engagement).
  ACKED suppressed       a manual advisory silenced via --ack; rendered, never gates.

--fix applies the safe auto-repairs: missing optional engagement files (scaffolded via
skills/hooks/_engagement.py ensure_optional_file), skills-symlink drift (relink that
skill into ~/.claude/skills), orphaned __pycache__ bytecode (deleted).
--ack <n> persists a numbered advisory's suppression into the ACTIVE engagement's
.doctor-acks.json (id + acked_at); delete the file to un-ack. Exit code =
int(bool(unacked issues or manual advisories)). Fail-open: an error inside a check
becomes a manual_issue note, never a crash.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
FIX = os.path.join(VAULT, "tests", "fixtures", "offensive")

VERBOSE = False
FIX_MODE = False
OFF = None            # imported offensive module (set by _import_offensive)
ENG_DIR = None        # active engagement dir (pointer targets/active.md or --eng)
ACKS = {}             # stable-id -> {"acked_at": ...} from <eng>/.doctor-acks.json
FINDINGS = []         # (check_fn_name, Finding) in run order


class Finding:
    """hermes-doctor accumulator: issues = hard failures (gate the exit, numbered,
    not ackable); manual_issues = manual-intervention advisories (gate until --ack);
    fixed = --fix auto-repairs applied. Rows carry the printed pass/warn/fail markers."""

    def __init__(self, issues=None, manual_issues=None, fixed=0):
        self.issues = issues or []
        self.manual_issues = manual_issues or []
        self.fixed = fixed
        self.rows = []          # (status, name, detail): PASS/WARN/FAIL/SKIP/ACKED

    def ok(self, name, detail=""):
        self.rows.append(("PASS", name, detail))

    def skip(self, name, detail=""):
        self.rows.append(("SKIP", name, detail))

    def advice(self, name, detail=""):           # WARN row, never gates
        self.rows.append(("WARN", name, detail))

    def warn(self, name, detail=""):             # manual advisory: gates until acked
        self.rows.append(("WARN", name, detail))
        self.manual_issues.append((name, detail))

    def fail(self, name, detail=""):             # issue: always gates
        self.rows.append(("FAIL", name, detail))
        self.issues.append((name, detail))


CURRENT = Finding()


def check(name, ok, detail="", warn=False):
    """Legacy row helper: FAIL counts as an issue; warn rows are advisory-only."""
    if ok:
        CURRENT.ok(name)
    elif warn:
        CURRENT.advice(name, detail)
    else:
        CURRENT.fail(name, detail)
    return ok


def _aid(name, detail):
    """Stable advisory id (survives renumbering between runs)."""
    return hashlib.sha1(("%s|%s" % (name, detail)).encode()).hexdigest()[:8]


def run_check(fn):
    """Run one check into a fresh Finding; fail-open (a crashed check becomes a
    manual_issue note); apply acks; print the check's own rows; accumulate."""
    global CURRENT
    CURRENT = Finding()
    ret = None
    try:
        ret = fn()
    except Exception as e:
        CURRENT.warn("%s: check crashed (fail-open)" % fn.__name__, str(e)[:100])
    keep = []
    for item in CURRENT.manual_issues:
        if _aid(*item) in ACKS:
            CURRENT.rows.append(("ACKED", item[0], item[1]))
        else:
            keep.append(item)
    CURRENT.manual_issues = keep
    FINDINGS.append((fn.__name__, CURRENT))
    for status, name, detail in CURRENT.rows:
        if status == "PASS" and not VERBOSE:
            continue
        print("%-5s %s%s" % (status, name, ("  - " + detail) if detail else ""))
    return ret


# ------------------------------------------------------------- acks ledger

def _acks_path():
    return os.path.join(ENG_DIR, ".doctor-acks.json") if ENG_DIR else None


def _load_acks():
    try:
        with open(_acks_path(), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


# ------------------------------------------------------------- engagement

def _resolve_eng(name=None):
    """Active engagement dir: --eng <name|path>, else the targets/active.md pointer."""
    if not name:
        p = os.path.join(VAULT, "targets", "active.md")
        if not os.path.isfile(p):
            return None
        for line in open(p, encoding="utf-8", errors="ignore"):
            s = line.strip()
            if s and not s.startswith(("#", "<!--", "-", "*")):
                name = s
                break
        if not name:
            return None
    cand = name if os.path.isdir(name) else os.path.join(VAULT, "targets", name)
    return cand if os.path.isdir(cand) else None


def _load_mod(fname, modname):
    import importlib.util
    spec = importlib.util.spec_from_file_location(modname, os.path.join(HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CH = None


def _check_hooks_mod():
    global _CH
    if _CH is None:
        _CH = _load_mod("check-hooks.py", "check_hooks")
    return _CH


_ENGMOD = False


def _engagement_mod():
    """skills/hooks/_engagement.py (ensure_optional_file / engagement_type), or None."""
    global _ENGMOD
    if _ENGMOD is False:
        _ENGMOD = None
        sys.path.insert(0, os.path.join(VAULT, "skills", "hooks"))
        try:
            import _engagement  # noqa
            _ENGMOD = _engagement
        except Exception:
            _ENGMOD = None
    return _ENGMOD


_TYPES = ("pentest", "bugbounty", "ctf")


def _eng_type(d):
    m = _engagement_mod()
    if m is not None:
        try:
            return m.engagement_type(d)
        except Exception:
            pass
    for fn in ("state.md", "loot.md", "Approach.md", "Killchain.md"):   # lightweight fallback
        p = os.path.join(d, fn)
        if not os.path.isfile(p):
            continue
        for line in open(p, encoding="utf-8", errors="ignore"):
            if line.startswith("engagement_type:"):
                v = line.split(":", 1)[1].strip().lower()
                if v in _TYPES:
                    return v
    try:
        v = json.load(open(os.path.join(d, ".offensive.json"), encoding="utf-8"))["type"]
        return {"bb": "bugbounty"}.get(v, v)
    except Exception:
        return "pentest"


# --------------------------------------------------------------------------- 1. offensive.py

def _import_offensive():
    global OFF
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if not check("scripts/offensive.py present", os.path.isfile(os.path.join(HERE, "offensive.py"))):
        return None
    try:
        import offensive  # noqa
        check("offensive.py importable", True)
        OFF = offensive
        return offensive
    except Exception as e:
        check("offensive.py importable", False, str(e)[:80])
        return None


# --------------------------------------------------------------------------- 2. routing table

# OS -> (routing class, expected hunt-skill) for the 4b privesc-hollow check.
OS_ROUTES = [("windows", "hunt-windows"), ("macos", "hunt-macos"), ("ad", "hunt-ad")]


def _routing():
    off = OFF
    if off is None:
        CURRENT.skip("routing table", "offensive.py not importable - skipped")
        return
    try:
        routing = off.parse_routing_table(VAULT)
    except Exception as e:
        check("routing table parses", False, str(e)[:80])
        return
    if not check("routing table parses (non-empty)", bool(routing),
                 "no rows in scripts/routing.json"):
        return

    # dangling-skill-ref: every hunt-skill cell must name a real skills/hunt/hunt-* dir.
    dangling = sorted({row.get("skill") for row in routing.values()
                       if row.get("skill") and not (
                           row["skill"].startswith("hunt-")
                           and os.path.isdir(os.path.join(VAULT, "skills", "hunt", row["skill"])))})
    check("every hunt-skill cell resolves to a real dir", not dangling,
          "dangling: " + ", ".join(dangling))

    # 4b privesc-hollow: a class is routable if ANY of its rows carries a
    # non-empty arsenal, not just the first one (a class has multiple
    # fingerprint rows and only needs one live arsenal to not be hollow).
    has_arsenal = {}
    for row in routing.values():
        cls = (row.get("class") or "").strip()
        has_arsenal[cls] = has_arsenal.get(cls, False) or bool((row.get("arsenal") or "").strip())
    for cls, _skill in OS_ROUTES:
        check("4b OS route not hollow: %s" % cls, has_arsenal.get(cls, False),
              "no '%s' class with a non-empty arsenal (4b hollow for that OS)" % cls, warn=True)


# --------------------------------------------------------------------------- 3. tool index

def _tools():
    off = OFF
    if off is None:
        CURRENT.skip("tool index", "offensive.py not importable - skipped")
        return
    tdir = os.path.join(VAULT, "wiki", "tools")
    if not check("wiki/tools/ present", os.path.isdir(tdir)):
        return
    # tool index resolves: every page yields a runnable ## Core usage invocation
    try:
        idx = off.parse_tool_index(VAULT)
    except Exception as e:
        check("tool index resolves", False, str(e)[:80])
        return
    # every page carries phase: in its FRONTMATTER (idx["phase"] comes from
    # off._frontmatter(), scoped to the leading --- block - not a body match).
    nopf = sorted(s for s, m in idx.items() if not m.get("phase"))
    check("all wiki/tools pages carry phase:", not nopf, "missing: " + ", ".join(nopf))
    noinv = sorted(s for s, m in idx.items() if not m.get("invocation"))
    check("tool index resolves (every page has a ## Core usage command)", not noinv,
          "no usage command: " + ", ".join(noinv))


# --------------------------------------------------------------------------- 4. skill + 5. hook

def _skill_and_hook():
    sk = os.path.join(VAULT, "skills", "workflow", "offensive", "SKILL.md")
    if check("skills/workflow/offensive/SKILL.md present", os.path.isfile(sk)):
        head = open(sk, encoding="utf-8", errors="ignore").read()
        check("offensive SKILL.md declares name: offensive",
              bool(re.search(r"^name:\s*offensive\s*$", head, re.M)))
    tt = os.path.join(VAULT, "skills", "hooks", "tool-telemetry.py")
    check("tool-telemetry.py hook present (G2 skill-fired telemetry)", os.path.isfile(tt),
          "G2 fails open without it - run setup/install-hooks.sh", warn=True)
    # pass 11 L6 wiring (warn-level, static): the background-tab residuals are pure shell;
    # a missing marker string is the earliest signal the wiring got reverted or drift-merged.
    ac = os.path.join(VAULT, "scripts", "autocard.sh")
    if os.path.isfile(ac):
        body = open(ac, encoding="utf-8", errors="ignore").read()
        check("autocard.sh open-tabs ledger + RUNNING line wired",
              ".open-tabs" in body and "RUNNING >45m" in body,
              "un-carded VM tabs would age invisibly (no wedged-scan signal)", warn=True)
    vs = os.path.join(VAULT, "scripts", "vm-scan.sh")
    if os.path.isfile(vs):
        body = open(vs, encoding="utf-8", errors="ignore").read()
        check("vm-scan.sh same-name reuse prompt-gated",
              "capture-pane" in body and "-2" in body,
              "keystrokes could re-enter a LIVE pane and clobber a running scan", warn=True)


# ------------------------------------------------- 5b. eval_metrics -> bench seam

def _bench():
    """close-out's auto Metrics block imports bench for lab scoring under a bare
    `except: return []` (eval_metrics.py bench_lines) - a broken seam loses practice-lab
    scores with zero signal anywhere, and nothing tests the eval->bench direction. Check
    it in-process against the TEST fixture pair (no client data; doctor never globs
    targets/), plus the manifest's dangling class refs (bench warns these only when run
    by hand)."""
    fx = os.path.join(VAULT, "tests", "fixtures")
    if not (os.path.isfile(os.path.join(fx, "bench-manifest.json"))
            and os.path.isdir(os.path.join(fx, "bench-eng"))):
        check("bench fixture pair present (in-process score)", False,
              "tests/fixtures/bench-manifest.json + bench-eng/ missing")
        return
    try:
        sys.path.insert(0, os.path.join(VAULT, "scripts"))
        import bench
        man = json.load(open(os.path.join(fx, "bench-manifest.json"), encoding="utf-8"))
        d = bench.score_engagement(os.path.join(fx, "bench-eng"), man)
        check("bench.score_engagement scores (eval_metrics seam live)",
              isinstance(d.get("total"), int) and "coverage_pct" in d,
              "the close-out auto Metrics block would silently lose lab scores")
    except Exception as e:
        check("bench.score_engagement scores (eval_metrics seam live)", False, str(e)[:80])
        return
    try:
        labs = json.load(open(os.path.join(VAULT, "scripts", "bench-labs.json"),
                              encoding="utf-8"))
        known = bench._known_classes() or set()
        dangling = sorted({c for k, v in labs.items()
                           if not k.startswith("_") and isinstance(v, dict)
                           for c in (v.get("expected_classes") or []) if c not in known})
        check("bench-labs.json expected_classes all resolve (coverage-classes.json)",
              not dangling, "dangling: " + ", ".join(dangling))
    except Exception as e:
        check("bench-labs.json expected_classes all resolve (coverage-classes.json)",
              False, str(e)[:80])


# --------------------------------------------------------------------------- 6. zg (zvec-grep) search layer

def _zg():
    """zg integration health: warn-level, fail-open - the harness works without zg,
    doctrine just prefers it. Each check prints its own fix command."""
    zg = shutil.which("zg")
    if check("zg CLI on PATH", bool(zg),
             "npm install -g @zvec/zvec-grep (Node 22+)", warn=True):
        idx = os.path.join(VAULT, ".zvec-grep")
        check("zg standing index present (vault root)", os.path.isdir(idx),
              "cd %s && zg index --no-ignore -g '!.obsidian/**' -g '!**/poc/cmdlog/**' "
              "--embedding local/potion-retrieval-32m "
              "(full exclude set: wiki/tools/zvec-grep.md)" % VAULT, warn=True)
        reg = False
        try:
            with open(os.path.expanduser("~/.claude.json"), encoding="utf-8") as fh:
                reg = "zvec-grep" in (json.load(fh).get("mcpServers") or {})
        except Exception:
            pass
        check("zg MCP server registered (user scope)", reg,
              "claude mcp add -s user -t http zvec-grep http://127.0.0.1:7999/mcp", warn=True)
        daemon = False
        try:
            with socket.create_connection(("127.0.0.1", 7999), timeout=1):
                daemon = True
        except OSError:
            pass
        check("zg daemon reachable (loopback 7999)", daemon, "zg server on", warn=True)


# --------------------------------------------------------------------------- 7. live smoke test

def _smoke():
    off = OFF
    if not check("fixture present for smoke test", os.path.isdir(FIX)):
        return
    tmp = tempfile.mkdtemp(prefix="offensive-doctor-")
    try:
        vault = os.path.join(tmp, "vault")
        shutil.copytree(FIX, vault)
        eng = os.path.join(vault, "targets", "demo")

        def O(*a):
            return subprocess.run([sys.executable, os.path.join(HERE, "offensive.py"),
                                   "--vault", vault, *a], capture_output=True, text=True)

        r = O("init", "demo", "--type", "bb")
        check("smoke: init", r.returncode == 0, r.stderr.strip()[:80])
        r = O("--eng", eng, "index")
        check("smoke: index compiles", r.returncode == 0 and "index built" in r.stdout,
              (r.stderr or r.stdout).strip()[:80])
        r = O("--eng", eng, "board")
        m = re.search(r"board:\s*(\d+)\s*rows", r.stdout)
        check("smoke: board writes rows", r.returncode == 0 and bool(m) and int(m.group(1)) > 0,
              (r.stderr or r.stdout).strip()[:80])
        if off is not None:
            lvl, note = off.autonomy_of(eng)
            check("smoke: scope.md autonomy parses (%s)" % lvl,
                  lvl in off.AUTONOMY_LEVELS and not note, note, warn=True)
        r = O("--eng", eng, "next")
        check("smoke: next prints an action block",
              r.returncode == 0 and "REQUIRED, in order:" in r.stdout,
              (r.stderr or r.stdout).strip()[:80])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _caido():
    # Advisory only: Burp stays the primary proxy lane; Caido being down never fails the doctor.
    bridge = next((b for b in ("/root/vm.sh", os.path.join(VAULT, "scripts", "win-vm.sh"))
                   if os.path.isfile(b)), None)
    if bridge is None:
        check("caido: VM bridge present (advisory)", False,
              "no /root/vm.sh or scripts/win-vm.sh on this seat", warn=True)
        return
    try:
        r = subprocess.run(["bash", bridge, "~/caido.sh status"],
                           capture_output=True, text=True, timeout=40)
    except Exception as e:
        check("caido: instance status (advisory)", False, str(e)[:80], warn=True)
        return
    out = (r.stdout or "").strip()
    check("caido: instance up + token valid (advisory)",
          r.returncode == 0 and "token-valid:yes" in out,
          (out.splitlines() or ["no output"])[0][:80], warn=True)


def _skill_scan():
    # Advisory only: skillspector sweep vs baseline; new findings are a triage prompt,
    # not a broken driver. Incremental, so cheap after the first full run.
    script = os.path.join(VAULT, "scripts", "skill-scan.sh")
    if not os.path.isfile(script):
        check("skill-scan: wrapper present (advisory)", False, "scripts/skill-scan.sh missing", warn=True)
        return
    if shutil.which("skillspector") is None:
        check("skill-scan: skillspector installed (advisory)", False,
              "uv tool install 'git+https://github.com/NVIDIA/skillspector.git'", warn=True)
        return
    try:
        r = subprocess.run(["bash", script], capture_output=True, text=True, timeout=180)
    except Exception as e:
        check("skill-scan: sweep ran (advisory)", False, str(e)[:80], warn=True)
        return
    summary = (r.stdout or "").strip().splitlines()
    check("skill-scan: no new findings vs baseline (advisory)", r.returncode == 0,
          (summary[-1] if summary else "no output")[:80], warn=True)


def _skill_guard():
    """Curated advisory battery over skills/ for agent-subversion patterns (hermes
    skills_guard port, docs/port-specs/proposals-aux-eval-guards.md #2). The vault
    IS an offensive knowledge base, so only subvert-the-AGENT / exfil-the-OPERATOR
    shapes are scanned; findings are a manual advisory (triage prompt), never a FAIL."""
    try:
        sg = _load_mod("skill-guard.py", "skill_guard")
        findings, n = sg.scan_root(os.path.join(VAULT, "skills"))
    except Exception as e:
        CURRENT.warn("skill-guard battery runs over skills/", str(e)[:80])
        return
    if not findings:
        CURRENT.ok("skill-guard: skills/ clean (%d file(s) scanned)" % n)
        return
    counts = {}
    for f in findings:
        counts[f[2]] = counts.get(f[2], 0) + 1
    # the ack id keys on the pattern-CLASS set (no counts), so count churn never
    # invalidates an ack; a genuinely NEW class re-trips the advisory
    classes = ", ".join(sorted(counts))
    CURRENT.rows.append(("WARN", "skills/ agent-subversion scan (skill-guard)",
                         "%d finding(s) in %d file(s) (advisory; triage: python3 "
                         "scripts/skill-guard.py scan)" % (len(findings), n)))
    CURRENT.manual_issues.append(("skills/ agent-subversion scan (skill-guard)",
                                  "pattern classes present: " + classes))


# ----------------------------------------------- 8. hook registration (canonical set)

def _hooks():
    """Registration matches the canonical EXPECTED_HOOKS set. Reuses check-hooks.py
    via import (single source of truth); its advisory classes stay advisory."""
    ch = _check_hooks_mod()
    miss = ch.missing_hooks()
    if miss:
        CURRENT.fail("all canonical vault hooks registered",
                     "missing/mis-registered: %s (run: bash setup/install-hooks.sh)"
                     % ", ".join(miss))
    else:
        CURRENT.ok("all canonical vault hooks registered (%d)" % len(ch.EXPECTED_HOOKS))
    stale = ch.stale_hooks()
    if stale:
        CURRENT.fail("no stale vault hooks (script deleted upstream)",
                     "still registered: %s (run: bash setup/install-hooks.sh)" % ", ".join(stale))
    else:
        CURRENT.ok("no stale vault hooks")
    unreg = ch.unregistered_scripts()
    if unreg:
        CURRENT.advice("no unregistered skills/hooks scripts",
                       "advisory: %s (intentional library, or missing .zcode/config.json row)"
                       % ", ".join(unreg))
    else:
        CURRENT.ok("no unregistered skills/hooks scripts")


# ----------------------------------------------- 9. skills symlink drift + --fix

def _relink_skill(name):
    """Re-run the install-skills link for ONE skill; False when it must stay manual."""
    src = None
    for dirpath, _d, files in os.walk(os.path.join(VAULT, "skills")):
        if os.path.basename(dirpath) == name and "SKILL.md" in files:
            src = dirpath
            break
    if not src:
        return False
    dest = os.path.join(os.path.expanduser("~/.claude/skills"), name)
    if os.path.lexists(dest):
        if not os.path.islink(dest):
            return False          # a real copy: the installer replaces it, doctor never rm -rf's
        os.remove(dest)
    os.symlink(src, dest)
    return True


def _symlinks():
    """Vault skills vs ~/.claude/skills drift: missing links (check-hooks) and
    dangling ones. --fix relinks each drifted skill."""
    ch = _check_hooks_mod()
    miss = ch.missing_skills(skills_root=os.path.join(VAULT, "skills"))
    dangling = []
    dest = os.path.expanduser("~/.claude/skills")
    try:
        for n in os.listdir(dest):
            p = os.path.join(dest, n)
            if os.path.islink(p) and not os.path.exists(p):
                dangling.append(n)
    except OSError:
        pass
    miss, dangling = sorted(miss), sorted(dangling)
    if not miss and not dangling:
        CURRENT.ok("vault skills symlinked into ~/.claude/skills (no drift)")
        return
    names = sorted(set(miss + dangling))
    if FIX_MODE:
        fixed = sum(1 for n in names if _relink_skill(n))
        CURRENT.fixed = fixed
        if fixed == len(names):
            CURRENT.ok("skills symlinks relinked (--fix): %s" % ", ".join(names))
            return
    CURRENT.warn("skills symlink drift (vault vs ~/.claude/skills)",
                 "%s (run: bash setup/install-skills.sh, or --fix)" % ", ".join(names))


# ----------------------------------------------- 10. orphaned __pycache__ + --fix

def _orphan_pyc():
    out = []
    for root in (os.path.join(VAULT, "skills", "hooks"), os.path.join(VAULT, "scripts")):
        for dirpath, _d, files in os.walk(root):
            if os.path.basename(dirpath) != "__pycache__":
                continue
            src_dir = os.path.dirname(dirpath)
            for fn in files:
                if not fn.endswith(".pyc"):
                    continue
                stem = fn[:-4].split(".cpython-")[0]
                if stem and not os.path.exists(os.path.join(src_dir, stem + ".py")):
                    out.append(os.path.join(dirpath, fn))
    return out


def _pycache():
    orphans = _orphan_pyc()
    if not orphans:
        CURRENT.ok("no orphaned __pycache__ bytecode")
        return
    if FIX_MODE:
        n = 0
        for p in orphans:
            try:
                os.remove(p)
                n += 1
            except OSError:
                pass
        CURRENT.fixed = n
        if n == len(orphans):
            CURRENT.ok("orphaned __pycache__ deleted (--fix): %d .pyc" % n)
            return
    CURRENT.warn("orphaned __pycache__ bytecode",
                 "%d orphaned .pyc (source .py gone); --fix deletes them" % len(orphans))


# ----------------------------------------------- 11. qmd index health

def _qmd():
    """qmd (wiki-search) index health. The MCP server is not probeable from a plain
    script context, so shell out to `qmd status` (bounded)."""
    qmd = shutil.which("qmd")
    if not qmd:
        CURRENT.warn("qmd index health", "qmd CLI not on PATH (wiki-search MCP + `qmd status` need it)")
        return
    try:
        r = subprocess.run([qmd, "status"], capture_output=True, text=True, timeout=15)
    except Exception as e:
        CURRENT.warn("qmd index health", "qmd status failed: %s" % str(e)[:60])
        return
    if r.returncode == 0:
        CURRENT.ok("qmd index health (qmd status ok)")
    else:
        CURRENT.warn("qmd index health",
                     "qmd status rc=%d: %s" % (r.returncode, (r.stdout or r.stderr or "").strip()[:60]))


# ----------------------------------------------- 12. active-engagement files + --fix

ENG_CORE = ("scope.md", "state.md", "loot.md", "Approach.md")
ENG_OPT = (("oob", "oob.md"), ("vuln-index", "Vuln-index.md"))


def _engfiles():
    """Active engagement carries its per-type core files (scope/state/loot/Approach,
    + Killchain for non-ctf); optional oob/Vuln-index are advisories a non-ctf
    engagement should have (--fix scaffolds them). File NAMES only in output."""
    if ENG_DIR is None:
        CURRENT.skip("active-engagement files", "no active engagement on this vault - unchecked")
        return
    etype = _eng_type(ENG_DIR)
    core = list(ENG_CORE) + ([] if etype == "ctf" else ["Killchain.md"])
    missing = [fn for fn in core if not os.path.isfile(os.path.join(ENG_DIR, fn))]
    if missing:
        CURRENT.fail("active engagement core files present (%s)" % etype,
                     "missing: %s (SessionStart self-heals these; restart the session)"
                     % ", ".join(missing))
    else:
        CURRENT.ok("active engagement core files present (%s)" % etype)
    if etype == "ctf":
        return
    for kind, fn in ENG_OPT:
        if os.path.isfile(os.path.join(ENG_DIR, fn)):
            CURRENT.ok("optional file %s present" % fn)
            continue
        if FIX_MODE:
            m = _engagement_mod()
            created = ""
            if m is not None:
                try:
                    created = m.ensure_optional_file(kind, d=ENG_DIR)
                except Exception:
                    created = ""
            if created:
                CURRENT.fixed += 1
                CURRENT.ok("optional file %s scaffolded (--fix)" % fn)
                continue
        CURRENT.warn("optional engagement file %s" % fn,
                     "missing for a %s engagement; --fix scaffolds it from setup/templates"
                     % etype)


# ----------------------------------------------- 13. VM SSH reachability

def _vmssh():
    """vm-ssh.sh round-trip; SKIP-with-note when this seat has no VM creds. Never
    hangs: the whole probe is capped at 5s."""
    script = os.path.join(HERE, "vm-ssh.sh")
    if not os.path.isfile(script):
        CURRENT.skip("VM SSH reachability", "scripts/vm-ssh.sh absent - unchecked")
        return
    if not (os.path.isfile("/root/.ssh/ztorch_vm") or os.path.isfile("/root/vm.sh")):
        CURRENT.skip("VM SSH reachability",
                     "no VM creds on this seat (/root/.ssh/ztorch_vm + /root/creds.txt unreadable) - unchecked")
        return
    try:
        r = subprocess.run(["bash", script, "echo doctor-vm-ok"],
                           capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired:
        CURRENT.warn("VM SSH reachability", "vm-ssh.sh timed out after 5s (VM down or wedged?)")
        return
    except Exception as e:
        CURRENT.warn("VM SSH reachability", str(e)[:60])
        return
    if r.returncode == 0 and "doctor-vm-ok" in (r.stdout or ""):
        CURRENT.ok("VM SSH reachability (vm-ssh.sh round-trip)")
    else:
        CURRENT.warn("VM SSH reachability",
                     "vm-ssh.sh rc=%d: %s" % (r.returncode, (r.stdout or r.stderr or "").strip()[:60]))


# ----------------------------------------------- 14. wiki lint

def _wikilint():
    """scripts/lint-wiki.py when present (advisory count, never a gate: the wiki is
    agent-owned and carries known refs), else the skill-lint advisory count."""
    lint = os.path.join(HERE, "lint-wiki.py")
    if os.path.isfile(lint) and os.path.isdir(os.path.join(VAULT, "wiki")):
        try:
            r = subprocess.run([sys.executable, lint, "-q"],
                               capture_output=True, text=True, timeout=120)
        except Exception as e:
            CURRENT.advice("wiki lint", "lint-wiki.py failed to run: %s" % str(e)[:60])
            return
        if r.returncode == 0:
            CURRENT.ok("wiki lint clean (lint-wiki.py -q)")
        else:
            lines = [l for l in (r.stdout or r.stderr or "").strip().splitlines() if l.strip()]
            CURRENT.advice("wiki lint", "%s (run: python3 scripts/lint-wiki.py -v)"
                           % (lines[-1] if lines else "rc=%d" % r.returncode)[:120])
        return
    try:
        m = _load_mod("skill-lint.py", "skill_lint")
        n = len(m.lint_all(VAULT))
        if n:
            CURRENT.advice("skill lint", "%d advisory issue(s) (skill-lint)" % n)
        else:
            CURRENT.ok("skill lint clean")
    except Exception as e:
        CURRENT.skip("wiki lint", "lint-wiki.py/skill-lint.py not runnable: %s" % str(e)[:60])


# ------------------------------------------------------------- ordered checks tuple

CHECKS = (
    _import_offensive,
    _routing,
    _tools,
    _skill_and_hook,
    _bench,
    _zg,
    _caido,
    _skill_scan,
    _smoke,
    _skill_guard,
    _hooks,
    _symlinks,
    _pycache,
    _qmd,
    _engfiles,
    _vmssh,
    _wikilint,
)


def _numbered_items():
    """FAIL rows + open manual advisories, in emission order = the numbered list."""
    out = []
    for _title, f in FINDINGS:
        for status, name, detail in f.rows:
            if status == "FAIL":
                out.append(("FAIL", name, detail))
            elif status == "WARN" and (name, detail) in f.manual_issues:
                out.append(("WARN", name, detail))
    return out


def main(argv):
    global VERBOSE, FIX_MODE, ENG_DIR, ACKS
    ap = argparse.ArgumentParser(description="offensive driver subsystem health check")
    ap.add_argument("--verbose", "-v", action="store_true", help="also print PASS rows")
    ap.add_argument("--fix", action="store_true",
                    help="apply safe auto-repairs (optional engagement files, skill symlinks, orphaned __pycache__)")
    ap.add_argument("--ack", metavar="N",
                    help="suppress numbered advisory N (persists into the active engagement's .doctor-acks.json)")
    ap.add_argument("--eng", help="engagement name (targets/<name>) or path the engagement checks target")
    args = ap.parse_args(argv)
    VERBOSE, FIX_MODE = args.verbose, args.fix
    ENG_DIR = _resolve_eng(args.eng)
    if args.eng and ENG_DIR is None:
        print("warning: --eng %s not found under targets/; engagement checks skip" % args.eng)
    ACKS = _load_acks()

    for fn in CHECKS:
        run_check(fn)

    rows = [row for _t, f in FINDINGS for row in f.rows]
    issues = [i for _t, f in FINDINGS for i in f.issues]
    manual = [m for _t, f in FINDINGS for m in f.manual_issues]
    fixed = sum(f.fixed for _t, f in FINDINGS)
    counts = {s: sum(1 for r in rows if r[0] == s) for s in ("PASS", "WARN", "FAIL", "SKIP", "ACKED")}
    print("\noffensive-doctor: %d checks, %d PASS, %d WARN, %d FAIL"
          % (len(rows), counts["PASS"], counts["WARN"], counts["FAIL"]))
    if counts["SKIP"] or counts["ACKED"]:
        print("offensive-doctor: %d SKIP, %d ACKED" % (counts["SKIP"], counts["ACKED"]))
    if fixed:
        print("offensive-doctor: --fix applied %d auto-repair(s)" % fixed)

    numbered = _numbered_items()
    if numbered:
        print("\nManual items (fix, or suppress an advisory with --ack <n>):")
        for i, (sev, name, detail) in enumerate(numbered, 1):
            print("  %d. [%s] %s%s  (ack id: %s)"
                  % (i, sev, name, ("  - " + detail) if detail else "", _aid(name, detail)))
    else:
        print("\nNo manual-intervention items.")

    if args.ack is not None:
        key = args.ack.strip()
        sel = None
        if key.isdigit():
            idx = int(key) - 1
            if 0 <= idx < len(numbered):
                sel = numbered[idx]
        else:
            sel = next((r for r in numbered if _aid(r[1], r[2]) == key), None)
        if sel is None:
            print("error: --ack %s matches no numbered item (run without --ack to list them)" % args.ack)
            return 1
        sev, name, detail = sel
        if sev == "FAIL":
            print("error: item %s is a FAIL (real breakage) - fix it; acks are for advisories only" % args.ack)
            return 1
        p = _acks_path()
        if not p:
            print("error: no active engagement dir to persist the ack into")
            return 1
        acks = _load_acks()
        acks[_aid(name, detail)] = {"acked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(acks, fh, indent=1)
        print("acked: [%s] %s -> %s" % (sev, name, p))
        return 0

    if issues:
        print("FAIL -> the /offensive driver will not run correctly here. Fix the above.")
    elif manual:
        print("ADVISORIES open -> fix them or suppress with --ack <n>.")
    elif counts["WARN"]:
        print("OK with warnings (see the WARN lines).")
    else:
        print("ALL GREEN - the /offensive subsystem is consistent and wired on this machine.")
    return int(bool(issues or manual))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
