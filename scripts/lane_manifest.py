"""Lane-manifest parsing/validation + docker argv builder for scripts/lane-run.sh.

Spec: docs/port-specs/sandbox-tooling.md (native ZTORCH port). Hard refusals
(ManifestError, rc 2): missing/unreadable/non-JSON manifest, non-bool network,
blocklisted or malformed env names, malformed or sandbox-breaking mounts (host
/etc, /boot, docker.sock), non-positive timeout_s, and unknown keys that look
like docker-arg injection (network config fails closed). Unknown benign keys
(tools/writes are dispatch-side) warn to stderr only; window_m/budget (P4
advisory cells) validate warn-not-fail and print as plan lines the runner
skips. stdout: a line-delimited execution plan ("timeout=N", "envs=A,B",
"window_m=M", "budget=max_iters,child_max", then the `docker run` argv
elements, image last); stderr: warnings and errors.
"""
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_IMAGE = "kalilinux/kali-rolling"  # tool-heavy lanes build/pull their own
DEFAULT_TIMEOUT_S = 600
DEFAULT_WINDOW_M = 45                     # P4 per-lane expected window (minutes)
DEFAULT_MAX_ITERS = 250                   # P4 budget cells (advisory, brain-side)
DEFAULT_CHILD_MAX = 2

# hermes local_env_policy blocklist (static tier): inference keys, messaging
# tokens, CI/cloud tokens, dashboard secrets; AUXILIARY_*_API_KEY dynamic shape.
# env passthrough can never re-allow a blocklisted name. Non-provider keys
# (e.g. SHODAN_API_KEY) stay allowed: recon lanes legitimately need them.
_ENV_PREFIXES = ("OPENAI_", "ANTHROPIC_", "GOOGLE_", "GEMINI_", "XAI_", "GROQ_",
                 "TOGETHER_", "PERPLEXITY_", "COHERE_", "DEEPSEEK_", "MISTRAL_",
                 "OPENROUTER_", "NOUS_", "QWEN_", "SLACK_", "DISCORD_",
                 "TELEGRAM_", "GITHUB_", "MODAL_", "DAYTONA_", "VERCEL_")
_ENV_EXACT = {"GH_TOKEN", "DASHBOARD_SECRET", "HERMES_DASHBOARD_SECRET"}
_ENV_SHAPE = re.compile(r"AUXILIARY_.*_API_KEY\Z")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_KNOWN = ("image", "network", "mounts", "env", "timeout_s", "window_m", "budget")
_UNSAFE_KEY = re.compile(r"docker|network|args", re.I)


class ManifestError(Exception):
    """Hard refusal: the lane must not run with this manifest."""


def parse(text):
    try:
        m = json.loads(text)
    except json.JSONDecodeError as e:
        raise ManifestError("manifest is not valid JSON: %s" % e)
    if not isinstance(m, dict):
        raise ManifestError("manifest must be a JSON object")
    return m


def load(path):
    try:
        with open(path) as f:
            return parse(f.read())
    except FileNotFoundError:
        raise ManifestError("manifest not found: %s" % path)
    except OSError as e:
        raise ManifestError("manifest unreadable: %s" % e)


def env_blocked(name):
    n = name.upper()
    return (n in _ENV_EXACT or n.startswith(_ENV_PREFIXES)
            or _ENV_SHAPE.match(name) is not None)


def validate(m):
    """Normalize + validate a parsed manifest; unknown benign keys warn only."""
    for k in m:
        if k in _KNOWN:
            continue
        if _UNSAFE_KEY.search(k):
            raise ManifestError("manifest key '%s' looks like docker-arg "
                                "injection; docker/network args fail closed" % k)
        print("lane_manifest: warning: unknown manifest key '%s' ignored "
              "(runner honors: %s)" % (k, ", ".join(_KNOWN)), file=sys.stderr)

    image = m.get("image", DEFAULT_IMAGE)
    if not isinstance(image, str) or not image.strip():
        raise ManifestError("image must be a non-empty string")

    network = m.get("network", False)
    if not isinstance(network, bool):
        raise ManifestError("network must be a boolean (true opts into egress)")

    mounts = m.get("mounts", [])
    if not isinstance(mounts, list):
        raise ManifestError("mounts must be a list of 'src:dst[:ro]' strings")
    for spec in mounts:
        parts = str(spec).split(":")
        if len(parts) not in (2, 3) or not parts[0] or not parts[1]:
            raise ManifestError("bad mount '%s' (want src:dst[:ro])" % spec)
        if not parts[1].startswith("/"):
            raise ManifestError("mount dst must be absolute in '%s'" % spec)
        if parts[1] == "/var/run/docker.sock" or parts[1].startswith(("/etc", "/boot")):
            raise ManifestError("refusing unsafe mount dst '%s'" % parts[1])
        if len(parts) == 3 and parts[2] not in ("ro", "rw"):
            raise ManifestError("bad mount mode in '%s' (ro|rw)" % spec)

    names = m.get("env", [])
    if not isinstance(names, list):
        raise ManifestError("env must be a list of variable NAMES to pass through")
    for n in names:
        if not isinstance(n, str) or not _NAME.match(n):
            raise ManifestError("bad env name '%s'" % n)
        if env_blocked(n):
            raise ManifestError("blocklisted env name '%s' refused (provider/CI "
                                "secrets never pass through)" % n)

    timeout_s = m.get("timeout_s", DEFAULT_TIMEOUT_S)
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, int) or timeout_s <= 0:
        raise ManifestError("timeout_s must be a positive integer")

    # P4 advisory cells (docs/port-specs/proposals-delegation.md): the lane's
    # expected window (minutes; brain ages + 80% wrap-up nudge off it) and its
    # iteration budget. The runner ignores both; they are plan lines for the
    # brain. Bad types WARN and fall back to the default - never fail a lane
    # over an advisory cell.
    window_m = m.get("window_m", DEFAULT_WINDOW_M)
    if isinstance(window_m, bool) or not isinstance(window_m, int):
        print("lane_manifest: warning: window_m must be an int (minutes); "
              "using default %d" % DEFAULT_WINDOW_M, file=sys.stderr)
        window_m = DEFAULT_WINDOW_M
    budget = m.get("budget", {})
    if not isinstance(budget, dict):
        print("lane_manifest: warning: budget must be an object "
              "{max_iters, child_max}; using defaults", file=sys.stderr)
        budget = {}
    max_iters = budget.get("max_iters", DEFAULT_MAX_ITERS)
    child_max = budget.get("child_max", DEFAULT_CHILD_MAX)
    for k, v in (("max_iters", max_iters), ("child_max", child_max)):
        if isinstance(v, bool) or not isinstance(v, int):
            print("lane_manifest: warning: budget.%s must be an int; "
                  "using default" % k, file=sys.stderr)
            if k == "max_iters":
                max_iters = DEFAULT_MAX_ITERS
            else:
                child_max = DEFAULT_CHILD_MAX

    return {"image": image, "network": network, "mounts": [str(x) for x in mounts],
            "env": names, "timeout_s": timeout_s, "window_m": window_m,
            "budget": {"max_iters": max_iters, "child_max": child_max}}


def build_argv(cfg, cwd, wiki):
    """Full `docker run` argv (flags + mounts + env + image); cmd appended by caller."""
    argv = ["--cap-drop", "ALL", "--cap-add", "DAC_OVERRIDE", "--cap-add", "CHOWN",
            "--cap-add", "FOWNER", "--security-opt", "no-new-privileges",
            "--pids-limit", "512", "--cpus", "2", "--memory", "4g",
            "--shm-size", "1g",
            "--tmpfs", "/tmp:rw,nosuid,size=512m",
            "--tmpfs", "/var/tmp:rw,nosuid,noexec,size=512m",
            "--tmpfs", "/run:rw,nosuid,noexec,size=64m",
            "--init", "--rm", "-i"]
    if not cfg["network"]:
        argv += ["--network", "none"]
    if wiki and os.path.isdir(wiki):
        argv += ["-v", "%s:/ztorch/wiki:ro" % wiki]
    else:
        print("lane_manifest: warning: wiki dir '%s' not found; /ztorch/wiki "
              "not mounted" % wiki, file=sys.stderr)
    argv += ["-v", "%s:/eng" % cwd, "-w", "/eng"]
    for spec in cfg["mounts"]:
        parts = spec.split(":")
        src = parts[0] if parts[0].startswith("/") else os.path.join(cwd, parts[0])
        argv += ["-v", ":".join([src] + parts[1:])]
    for n in cfg["env"]:
        argv += ["-e", n]  # name only: the value is read from the env at run time
    argv.append(cfg["image"])
    return argv


def main(argv):
    if len(argv) not in (2, 4):
        print("usage: lane_manifest.py <manifest.json> [cwd wikiDir]", file=sys.stderr)
        return 2
    cwd = argv[2] if len(argv) == 4 else os.getcwd()
    wiki = argv[3] if len(argv) == 4 else str(Path(__file__).resolve().parent.parent / "wiki")
    try:
        cfg = validate(load(argv[1]))
        plan = build_argv(cfg, cwd, wiki)
    except ManifestError as e:
        print("lane_manifest: %s" % e, file=sys.stderr)
        return 2
    # ponytail: line-delimited plan; manifest paths containing newlines unsupported
    print("timeout=%d" % cfg["timeout_s"])
    print("envs=%s" % ",".join(cfg["env"]))
    # advisory plan cells (P4): lane-run.sh's parser skips them; the brain reads
    # them for window aging, the 80% wrap-up nudge, and iteration budgeting
    print("window_m=%d" % cfg["window_m"])
    print("budget=%d,%d" % (cfg["budget"]["max_iters"], cfg["budget"]["child_max"]))
    for a in plan:
        print(a)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
