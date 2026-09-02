#!/usr/bin/env python3
"""offensive-doctor.py [--verbose] - health check for the /offensive driver subsystem.

Verifies a machine has the /offensive driver correctly set up so every machine runs the
same driver, then runs a live init->index->board->next smoke test on a throwaway fixture
engagement. Modelled on the retired campaign-doctor lineage.

Checks (each a PASS/WARN/FAIL line; exit 1 if any FAIL):
  1. scripts/offensive.py present + importable.
  2. hunt-core routing table parses (non-empty) + every hunt-skill cell names a real
     skills/hunt/hunt-* dir (dangling-skill-ref).
  3. every wiki/tools/*.md carries phase: + a runnable ## Core usage fence (tool index resolves).
  4. skills/workflow/offensive/SKILL.md present with `name: offensive`.
  5. tool-telemetry.py hook present (G2 depends on it) - WARN if absent (G2 fails open).
  6. 4b privesc not hollow: each OS route (windows/macos/ad) has its class with a non-empty
     arsenal - WARN if missing.
  7. live smoke test: init->index->board->next on a throwaway copy of tests/fixtures/offensive.

WARN never fails the run. Exit 0 = all green (warns allowed); 1 = at least one FAIL.
"""
import os
import re
import shutil
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
                 "no rows in hunt-core '## Routing table (machine-readable)'"):
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
    sk = os.path.join(VAULT, "skills", "workflow", "offensive", "SKILL.md")
    if check("skills/workflow/offensive/SKILL.md present", os.path.isfile(sk)):
        head = open(sk, encoding="utf-8", errors="ignore").read()
        check("offensive SKILL.md declares name: offensive",
              bool(re.search(r"^name:\s*offensive\s*$", head, re.M)))
    tt = os.path.join(VAULT, "skills", "hooks", "tool-telemetry.py")
    check("tool-telemetry.py hook present (G2 skill-fired telemetry)", os.path.isfile(tt),
          "G2 fails open without it - run setup/install-hooks.sh", warn=True)


# --------------------------------------------------------------------------- 7. live smoke test

def _smoke():
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
        r = O("--eng", eng, "next")
        check("smoke: next prints an action block",
              r.returncode == 0 and "REQUIRED, in order:" in r.stdout,
              (r.stderr or r.stdout).strip()[:80])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    verbose = "--verbose" in argv or "-v" in argv
    off = _import_offensive()
    if off is not None:
        _routing(off)
        _tools(off)
    _skill_and_hook()
    _smoke()

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
