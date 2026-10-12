#!/usr/bin/env python3
"""lane_envelope.py - schema-validated lane return envelope (P1 port of hermes
output_schema; docs/port-specs/proposals-delegation.md). The lane's LAST write
into its capture dir is `envelope.json`, the machine-readable twin of the
15-line prose return (Scope / Result / Key files / Issues; delegate slot (f)).
A schema miss NEVER discards the run (hermes rationale: a 68-minute audit was
once written off over a stray code fence): it earns exactly ONE same-handle
re-prompt carrying the validation errors verbatim; a second miss files the
lane NOT VERIFIED, raw capture kept.

    python3 scripts/lane_envelope.py init <capture-dir> --lane <name>
    python3 scripts/lane_envelope.py validate <envelope.json | capture-dir>
"""
import json
import os
import sys

# delegate slot (f): tool/arg mechanics | seat/VM/network | wrong vector class
# for this surface | target-side change (WAF rule, patch)
FAILURE_CLASSES = ("technical", "environmental", "conceptual", "external")
_NEGATIVE = ("fail", "negative", "blocked", "abort", "no output", "no finding",
             "no result", "not verified", "no exploitation")

# Exactly the four delegate envelope slots plus optional pending_write (the
# PENDING-WRITE paste-able diff blocks, delegate slot (f) review lanes).
# Unknown extra keys are ignored: the schema is a floor, not a cage.
ENVELOPE_SCHEMA = {
    "scope": "str!",                          # what was attempted
    "result": "dict!",                        # verdict + the raw observable
    "key_files": "list!",                     # capture paths
    "issues": "list!",                        # blockers
    "pending_write": "list",                  # optional paste-able diff blocks
}
_RESULT_SCHEMA = {
    "verdict": "str!",
    "success_observable_raw": "str!",         # the observable, RAW (or the
                                              # explicit `no output captured`)
    "failure_class": "str",                   # REQUIRED when verdict is negative
}
TEMPLATE = {
    "scope": "",
    "result": {"verdict": "", "success_observable_raw": ""},
    "key_files": [],
    "issues": [],
}


def _typ(spec):
    return {"str": str, "dict": dict, "list": list}[spec.rstrip("!")]


def _required(spec):
    return spec.endswith("!")


def _is_strlist(v):
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def is_negative(verdict):
    v = (verdict or "").lower()
    return any(m in v for m in _NEGATIVE)


def validate(data):
    """[] when data matches ENVELOPE_SCHEMA, else human-readable field reasons
    (JSON-pointer-ish paths, hermes validate_output shape)."""
    errs = []
    if not isinstance(data, dict):
        return ["envelope: must be a JSON object"]
    for key, spec in ENVELOPE_SCHEMA.items():
        if key not in data:
            if _required(spec):
                errs.append("%s: missing" % key)
            continue
        v = data[key]
        if key in ("key_files", "issues", "pending_write"):
            if not _is_strlist(v):
                errs.append("%s: must be a list of strings" % key)
        elif not isinstance(v, _typ(spec)):
            errs.append("%s: must be %s" % (key, _typ(spec).__name__))
    if isinstance(data.get("scope"), str) and not data["scope"].strip():
        errs.append("scope: empty (template never filled)")
    res = data.get("result")
    if isinstance(res, dict):                    # missing/wrong type: reported above
        for key, spec in _RESULT_SCHEMA.items():
            if key not in res:
                if _required(spec):
                    errs.append("result.%s: missing" % key)
                continue
            if not isinstance(res[key], str):
                errs.append("result.%s: must be str" % key)
        verdict = res.get("verdict")
        if isinstance(verdict, str):
            if not verdict.strip():
                errs.append("result.verdict: empty (template never filled)")
            elif is_negative(verdict) and not res.get("failure_class"):
                errs.append("result.failure_class: missing on negative verdict "
                            "(technical|environmental|conceptual|external)")
        fc = res.get("failure_class")
        if fc is not None and fc not in FAILURE_CLASSES:
            errs.append("result.failure_class: '%s' not one of %s"
                        % (fc, "|".join(FAILURE_CLASSES)))
        so = res.get("success_observable_raw")
        if isinstance(so, str) and not so.strip():
            errs.append("result.success_observable_raw: empty (a lane that "
                        "produced nothing returns `no output captured`, never silence)")
    return errs


def envelope_path(p):
    return os.path.join(p, "envelope.json") if os.path.isdir(p) else p


def init(capture_dir, lane):
    path = os.path.join(capture_dir, "envelope.json")
    if os.path.exists(path):
        print("lane_envelope: %s already exists; not overwritten" % path)
        return 1
    os.makedirs(capture_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(TEMPLATE, f, indent=2)
        f.write("\n")
    print("lane_envelope: wrote empty envelope template for lane %s at %s "
          "(the lane fills it as its LAST write into the capture dir)" % (lane, path))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) >= 2 and argv[0] == "init":
        lane = ""
        if "--lane" in argv[2:] and argv.index("--lane") + 1 < len(argv):
            lane = argv[argv.index("--lane") + 1]
        return init(argv[1], lane)
    if len(argv) == 2 and argv[0] == "validate":
        p = envelope_path(argv[1])
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            print("INVALID: no envelope.json at %s" % p)
            return 1
        except (json.JSONDecodeError, OSError) as e:
            print("INVALID: envelope.json unreadable (%s)" % e)
            return 1
        errs = validate(data)
        if errs:
            print("INVALID %s" % "; ".join(errs))
            return 1
        print("VALID")
        return 0
    print(__doc__.strip().splitlines()[-2])
    return 2


if __name__ == "__main__":
    sys.exit(main())
