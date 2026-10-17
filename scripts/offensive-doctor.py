#!/usr/bin/env python3
"""offensive-doctor.py [--verbose] - health check for the /offensive driver subsystem.

Verifies a machine has the /offensive driver correctly set up so every machine runs the
same driver, then runs a live init->index->board->next smoke test on a throwaway fixture
engagement. Modelled on the retired campaign-doctor lineage.

Checks (each a PASS/WARN/FAIL line; exit 1 if any FAIL):
  1. scripts/offensive.py present + importable.
  2. scripts/routing.json parses (non-empty) + every hunt-skill cell names a real
     skills/exploit/hunt/hunt-* dir (dangling-skill-ref).
  3. every wiki/tools/*.md carries phase: + a runnable ## Core usage fence (tool index resolves).
  4. skills/orchestrate/offensive/SKILL.md present with `name: offensive`.
  5. tool-telemetry.py hook present (G2 depends on it) - WARN if absent (G2 fails open).
  6. 4b privesc not hollow: each OS route (windows/macos/ad) has its class with a non-empty
     arsenal - WARN if missing.
  7. live smoke test: init->index->board->next on a throwaway copy of tests/fixtures/offensive,
     including the scope.md `autonomy:` envelope parse (WARN when absent/invalid).

WARN never fails the run. Exit 0 = all green (warns allowed); 1 = at least one FAIL.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
FIX = os.path.join(VAULT, "tests", "fixtures", "offensive")

RESULTS = []


def check(name, ok, detail="", warn=False):
    RESULTS.append((name, "WARN" if (warn and not ok) else ("PASS" if ok else "FAIL"), detail))
    return ok


# --------------------------------------------------------------------------- 1. offensive.py

def _import_offensive():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if not check("scripts/offensive.py present", os.path.isfile(os.path.join(HERE, "offensive.py"))):
        return None
    try:
        import offensive  # noqa
        check("offensive.py importable", True)
        return offensive
    except Exception as e:
        check("offensive.py importable", False, str(e)[:80])
        return None


# --------------------------------------------------------------------------- 2. routing table

# OS -> (routing class, expected hunt-skill) for the 4b privesc-hollow check.
OS_ROUTES = [("windows", "hunt-windows"), ("macos", "hunt-macos"), ("ad", "hunt-ad")]


def _routing(off):
    try:
        routing = off.parse_routing_table(VAULT)
    except Exception as e:
        check("routing table parses", False, str(e)[:80])
        return
    if not check("routing table parses (non-empty)", bool(routing),
                 "no rows in scripts/routing.json"):
        return

    # dangling-skill-ref: every hunt-skill cell must name a real skills/exploit/hunt/hunt-* dir.
    dangling = sorted({row.get("skill") for row in routing.values()
                       if row.get("skill") and not (
                           row["skill"].startswith("hunt-")
                           and os.path.isdir(os.path.join(VAULT, "skills", "exploit", "hunt", row["skill"])))})
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

def _tools(off):
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
    sk = os.path.join(VAULT, "skills", "orchestrate", "offensive", "SKILL.md")
    if check("skills/orchestrate/offensive/SKILL.md present", os.path.isfile(sk)):
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

def _smoke(off):
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


def main(argv):
    verbose = "--verbose" in argv or "-v" in argv
    off = _import_offensive()
    if off is not None:
        _routing(off)
        _tools(off)
    _skill_and_hook()
    _bench()
    _zg()
    _caido()
    _skill_scan()
    _smoke(off)

    fails = [r for r in RESULTS if r[1] == "FAIL"]
    warns = [r for r in RESULTS if r[1] == "WARN"]
    for name, status, detail in RESULTS:
        if status == "PASS" and not verbose:
            continue
        print("%-5s %s%s" % (status, name, ("  - " + detail) if (detail and status != "PASS") else ""))
    print("\noffensive-doctor: %d checks, %d PASS, %d WARN, %d FAIL"
          % (len(RESULTS), sum(1 for r in RESULTS if r[1] == "PASS"), len(warns), len(fails)))
    if fails:
        print("FAIL -> the /offensive driver will not run correctly here. Fix the above.")
    elif warns:
        print("OK with warnings (see the WARN lines).")
    else:
        print("ALL GREEN - the /offensive subsystem is consistent and wired on this machine.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
