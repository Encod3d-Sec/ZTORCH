#!/usr/bin/env python3
"""completion-gate.py - per-run checklist ledger + artifact verification.

The Armada hackbot talk (docs/hackbot-port.md, mined 2026-10-11) measured the
harness's single biggest win: markdown checklists as completion ledgers plus a
review pass that verifies every declared output artifact exists and is
non-zero bytes took collection accuracy from ~0.4% to near-full. The failure
it fixes: a lane reports success, the run "completes", and 13 of 22 output
dirs turn out empty. Self-reports are not completion; artifacts are.

House style: a lens by default (exit 0; verdict lines go into the engagement
log and the brain decides). `check --strict` turns it into a hard gate that
exits 1 on any failure.

Usage:
  python3 scripts/completion-gate.py init <dir> --title "<run name>" [--steps steps.txt]
      Writes <dir>/run-ledger.md. Steps come from --steps (one per line) or a
      6-step generic lane skeleton. A step line may declare its artifact
      inline: `- probe httpx sweep @ out/httpx.txt`.

  python3 scripts/completion-gate.py check <dir-or-ledger.md> [--capture <dir>] [--strict]
      Verdicts per checklist box: OK, UNCHECKED (box not ticked), MISSING
      (declared artifact path does not exist), EMPTY (artifact is 0 bytes).
      --capture additionally flags an empty or absent lane capture dir.
      On any failure, prints the GENERIC NUDGE to re-dispatch the lane with
      (verbatim, per the talk: generic beats specific because you do not know
      where it failed). Default exits 0 (lens); --strict exits 1 on any
      failure (hard gate).

Steps file format: one step per line, `#` comments ignored. Inline artifact
after ` @ ` (a path containing `/` or a dot-suffixed name).
"""
import argparse
import os
import sys

LEDGER = "run-ledger.md"

GENERIC_SKELETON = [
    "read engagement state + scope before first action",
    "execute the lane's specified window/commands in full",
    "write raw outputs to the capture dir before any post-processing",
    "record the SUCCESS observable verbatim in the envelope",
    "REVERT any target state the run changed",
    "confirm every declared artifact is non-zero and in the capture dir",
]

NUDGE = (
    "GENERIC NUDGE (re-dispatch verbatim): your work was just reviewed and "
    "either a step of the checklist was missed or an artifact of sufficient "
    "proof was not generated. Read run-ledger.md and the output for each step, "
    "find what you missed, and complete it. Do not re-run steps that already "
    "have their artifact; do not report a verdict without the raw observable."
)

RULE_VOCAB = frozenset((
    "sha256_pass", "table_min_rows", "no_cell_contains", "md_table_headers",
    "md_table_or_explicit_empty", "dir_count_matches", "all_exist",
    "contains_lane_id",
))

import hashlib
import re

_RULE_RE = re.compile(r"\[rule:\s*([^\]]+)\]")

_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")


def _md_tables(path):
    """Markdown file -> list of tables, each a list of rows (list of stripped cells).
    Divider rows (---) are dropped."""
    tables, cur = [], []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                m = _ROW_RE.match(raw)
                if not m:
                    if cur:
                        tables.append(cur)
                        cur = []
                    continue
                cells = [c.strip() for c in m.group(1).split("|")]
                if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if cells):
                    continue
                cur.append(cells)
        if cur:
            tables.append(cur)
    except OSError:
        pass
    return tables


def _rules_of(step_text):
    """`@ path [rule:name=arg] [rule:name2]` -> [(name, arg), ...]."""
    out = []
    for m in _RULE_RE.finditer(step_text):
        clause = m.group(1).strip()
        name, _, arg = clause.partition("=")
        name = name.strip()
        arg = arg.strip().strip('"').strip("'")
        out.append((name, arg))
    return out


def _check_rule(name, arg, art_path, ledger_dir, lane_id):
    """None = pass; str = failure detail. Unknown rules fail closed."""
    if name not in RULE_VOCAB:
        return "unknown rule '%s' (closed vocabulary: %s)" % (name, ",".join(sorted(RULE_VOCAB)))
    if name == "all_exist":
        for rel in [p.strip() for p in arg.split(",") if p.strip()]:
            p = _resolve(rel, ledger_dir)
            if not os.path.exists(p):
                return "all_exist: %s absent" % rel
            if os.path.isfile(p) and os.path.getsize(p) == 0:
                return "all_exist: %s empty" % rel
        return None
    if name == "contains_lane_id":
        want = arg or lane_id
        if not want:
            return "contains_lane_id: no id given and no lane id derivable"
        if not art_path:
            return "contains_lane_id: no artifact on the line"
        try:
            with open(art_path, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            return "contains_lane_id: cannot read %s" % art_path
        if want not in body:
            return "contains_lane_id: '%s' not in %s" % (want, os.path.basename(art_path))
        return None
    if name == "sha256_pass":
        try:
            with open(art_path, encoding="utf-8", errors="replace") as fh:
                lines = [l.split() for l in fh if l.split()]
        except OSError:
            return "sha256_pass: cannot read %s" % art_path
        if not lines:
            return "sha256_pass: ledger is empty"
        checked = 0
        for parts in lines:
            if len(parts) >= 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
                f = os.path.join(os.path.dirname(art_path), parts[-1])
                if not os.path.isfile(f):
                    return "sha256_pass: %s missing" % parts[-1]
                h = hashlib.sha256()
                with open(f, "rb") as fh:
                    for chunk in iter(lambda: fh.read(65536), b""):
                        h.update(chunk)
                if h.hexdigest() != parts[0]:
                    return "sha256_pass: hash mismatch for %s" % parts[-1]
                checked += 1
        if checked == 0:
            return "sha256_pass: no `<sha256>  <file>` lines found"
        return None
    if name == "dir_count_matches":
        if not os.path.isdir(art_path):
            return "dir_count_matches: %s is not a directory" % art_path
        n = len(list(os.scandir(art_path)))
        if re.fullmatch(r"\d+", arg):
            want = int(arg)
            if n != want:
                return "dir_count_matches: %d entries, expected %d" % (n, want)
            return None
        other = _resolve(arg, ledger_dir)
        if not os.path.isdir(other):
            return "dir_count_matches: comparison dir %s absent" % arg
        m = len(list(os.scandir(other)))
        if n != m:
            return "dir_count_matches: %d entries vs %d in %s" % (n, m, arg)
        return None
    tables = _md_tables(art_path)
    if name == "md_table_headers":
        want = [w.strip() for w in arg.split(",")]
        if not tables:
            return "md_table_headers: no table in %s" % os.path.basename(art_path)
        hdr = [re.sub(r"\s+", "_", h.lower()) for h in tables[0][0]]
        if hdr != want:
            return "md_table_headers: got '%s', want '%s'" % (",".join(hdr), ",".join(want))
        return None
    if name == "table_min_rows":
        n = max((len(t) - 1 for t in tables), default=0)
        want = 1
        if arg:
            if not re.fullmatch(r"\d+", arg):
                return "table_min_rows: non-numeric arg '%s' (want an integer)" % arg
            want = int(arg)
        if n < want:
            return "table_min_rows: %d data rows, want >= %d" % (n, want)
        return None
    if name == "md_table_or_explicit_empty":
        if any(len(t) > 1 for t in tables):
            return None
        try:
            with open(art_path, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            body = ""
        if "(none found)" in body:
            return None
        return "md_table_or_explicit_empty: no data rows and no '(none found)' line"
    if name == "no_cell_contains":
        for t in tables:
            for row in t:
                for cell in row:
                    if arg and arg in cell:
                        return "no_cell_contains: '%s' found in cell" % arg
        return None
    return "%s: not implemented" % name


def _artifact_of(step_text):
    """Extract the inline artifact path from a step line, or None.

    The path is the single token after ' @ ' (no spaces). Resolved relative to
    the ledger's directory by the caller.
    """
    if " @ " not in step_text:
        return None
    tail = step_text.rsplit(" @ ", 1)[1].strip()
    art = tail.split()[0] if tail.split() else ""
    # path-ish: contains a separator or a dot-suffix; rejects bare words like "done"
    if art and ("/" in art or "\\" in art or ("." in art and not art.endswith("."))):
        return art
    if art and any(n == "dir_count_matches" for n, _ in _rules_of(step_text)):
        return art
    return None


def _resolve(art, ledger_dir):
    """Artifact paths in the ledger are relative to the LEDGER's directory."""
    if os.path.isabs(art):
        return art
    return os.path.join(ledger_dir, art)


def cmd_init(args):
    os.makedirs(args.dir, exist_ok=True)
    path = os.path.join(args.dir, LEDGER)
    if os.path.exists(path):
        sys.stderr.write("completion-gate: %s already exists, leaving it alone\n" % path)
        return False
    steps = []
    if args.steps:
        if args.steps == "-":
            raw = sys.stdin.read()
        elif "\n" in args.steps:
            raw = args.steps
        else:
            with open(args.steps, encoding="utf-8") as fh:
                raw = fh.read()
        steps = [l.strip() for l in raw.splitlines()
                 if l.strip() and not l.strip().startswith("#")]
    if not steps:
        steps = list(GENERIC_SKELETON)
    lines = [
        "# Run ledger - %s" % args.title,
        "",
        "Every box ticked and every artifact non-zero, or the run is not done.",
        "Checked by: `python3 scripts/completion-gate.py check %s`" % args.dir,
        "",
    ]
    for s in steps:
        lines.append("- [ ] %s" % s)
    lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("wrote %s (%d steps)" % (path, len(steps)))
    return False


def cmd_check(args):
    target = args.target
    if os.path.isdir(target):
        target = os.path.join(target, LEDGER)
    if not os.path.isfile(target):
        print("VERDICT: NO LEDGER (%s not found) - run was never given a checklist" % target)
        print(NUDGE)
        return True
    unchecked, missing, empty, stale, rule_failed, na_failed, ok = [], [], [], [], [], [], 0
    ticked = 0
    baseline_ledger = os.path.join(os.path.dirname(os.path.abspath(target)), "run-ledger.md")
    baseline = (os.path.getmtime(baseline_ledger)
                if os.path.isfile(baseline_ledger) else os.path.getmtime(target))
    with open(target, encoding="utf-8", errors="replace") as fh:
        ledger_text = fh.read()
    wf_ref = ""
    for line in ledger_text.splitlines():
        if line.startswith("Workflow-Ref:"):
            wf_ref = line.split(":", 1)[1].strip()
            break
    wf_path = wf_ref if wf_ref and os.path.isfile(wf_ref) else os.path.join(
        os.path.dirname(os.path.abspath(target)), "workflow.md")
    na_tokens = []
    if os.path.isfile(wf_path):
        with open(wf_path, encoding="utf-8", errors="replace") as fh:
            grab = False
            for line in fh:
                if line.startswith("## "):
                    grab = line.strip() == "## N/A escapes"
                    continue
                if grab and line.strip().startswith(("-", "`", "N")):
                    tok = line.strip().strip("-` ").strip()
                    if tok.startswith("N/A:"):
                        tok = tok[len("N/A:"):].strip()
                    if tok:
                        na_tokens.append(tok)
    for raw in ledger_text.splitlines():
        line = raw.rstrip("\n").rstrip("\r")
        if not line.startswith("- ["):
            continue
        text = line[3:].lstrip(" ]").lstrip()
        na = line.startswith("- [-]")
        if na:
            claim = ""
            m = re.search(r"N/A:\s*(.+)$", text)
            if m:
                claim = m.group(1).strip()
            if not claim or not any(t and t in claim for t in na_tokens):
                na_failed.append(text)
            else:
                ok += 1
            continue
        done = line.startswith("- [x]") or line.startswith("- [X]")
        art = _artifact_of(text)
        if not done:
            unchecked.append(text)
            continue
        ticked += 1
        art_path = None
        if art:
            art_path = _resolve(art, os.path.dirname(os.path.abspath(target)))
            if not os.path.exists(art_path):
                missing.append(art)
                continue
            if os.path.isdir(art_path):
                ok += 1
            elif os.path.getsize(art_path) == 0:
                empty.append(art)
                continue
            elif os.path.getmtime(art_path) < baseline - 2:
                # artifact older than the ledger's last edit = residue from a
                # PREVIOUS run; ticking the box does not make it fresh evidence
                stale.append(art)
                continue
            else:
                ok += 1
        lane_id = os.path.basename(os.path.dirname(os.path.abspath(target)))
        for rname, rarg in _rules_of(text):
            if not art_path and rname != "contains_lane_id":
                rule_failed.append("%s: no artifact on the line" % rname)
                continue
            why = _check_rule(rname, rarg, art_path,
                              os.path.dirname(os.path.abspath(target)), lane_id)
            if why:
                rule_failed.append("%s (%s): %s" % (rname, art or "-", why))
            else:
                ok += 1
    # rule annotations legitimately name their arg (no_cell_contains="TBD"):
    # strip them before the placeholder scan or every such rule self-flags
    scan_text = _RULE_RE.sub("", ledger_text)
    placeholders = [tok for tok in ("{{", "}}", "TBD", "<TODO>")
                    if tok in scan_text]
    capture_note = ""
    if args.capture:
        if not os.path.isdir(args.capture):
            capture_note = "CAPTURE MISSING (%s)" % args.capture
        elif not any(os.scandir(args.capture)):
            capture_note = "CAPTURE EMPTY (%s)" % args.capture
        else:
            capture_note = "capture OK"
    if (not unchecked and not missing and not empty and not stale
            and not rule_failed and not na_failed and not placeholders
            and not capture_note.startswith("CAPTURE")):
        if ok == 0:
            # a checklist whose boxes declare no artifacts verifies nothing;
            # COMPLETE with "0 steps verified" was read as a pass in the field
            print("VERDICT: NEEDS-REVIEW (%d boxes ticked, 0 steps verified - "
                  "no box declares a verifiable artifact; spot-read the "
                  "deliverables on disk before merging)" % ticked)
            return True
        print("VERDICT: COMPLETE (%d steps verified%s)" % (ok, ", " + capture_note if capture_note else ""))
        return False
    print("VERDICT: INCOMPLETE run-ledger=%s" % os.path.abspath(target))
    for t in unchecked:
        print("  UNCHECKED: %s" % t)
    for a in missing:
        print("  MISSING (declared, absent): %s" % a)
    for a in empty:
        print("  EMPTY (0 bytes): %s" % a)
    for a in stale:
        print("  STALE (artifact predates the ledger edit - previous run's residue): %s" % a)
    for r in rule_failed:
        print("  RULE_FAILED: %s" % r)
    for t in na_failed:
        print("  NA_FAILED: %s" % t)
    for tok in placeholders:
        print("  PLACEHOLDER: '%s' left in the checklist (lane-init substitution missed or ticked template text)" % tok)
    if capture_note.startswith("CAPTURE"):
        print("  %s" % capture_note)
    print("  verified: %d" % ok)
    print(NUDGE)
    return True


def main():
    ap = argparse.ArgumentParser(description="run checklist ledger + artifact gate (lens, exit 0)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init", help="write a run-ledger.md checklist")
    p_init.add_argument("dir")
    p_init.add_argument("--title", default="lane run")
    p_init.add_argument("--steps", help="steps file (one per line), inline multiline steps text, or '-' for stdin; optional inline artifact after ' @ '")
    p_init.set_defaults(func=cmd_init)
    p_chk = sub.add_parser("check", help="verify a ledger (dir or file)")
    p_chk.add_argument("target", help="engagement/lane dir or run-ledger.md path")
    p_chk.add_argument("--capture", help="lane capture dir to also flag if empty/absent")
    p_chk.add_argument("--strict", action="store_true", help="exit 1 on any failure (hard gate; default is exit-0 lens)")
    p_chk.set_defaults(func=cmd_check)
    args = ap.parse_args()
    failed = args.func(args)
    if getattr(args, "strict", False) and failed:
        sys.exit(1)
    sys.exit(0)  # lens, not gate, unless --strict


if __name__ == "__main__":
    main()
