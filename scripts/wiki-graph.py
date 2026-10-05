#!/usr/bin/env python3
"""Structural wikilink graph over wiki/: path, hubs, orphans, neighbors.

Zero dependencies (stdlib only); reads wiki/ live on every run, so there is
no cache to rebuild after promote. Resolves [[target]], [[target|alias]],
[[target#anchor]] by exact relative path, then unique basename. Code fences
are skipped so quoted link syntax adds no edges.
"""
import re
import sys
from collections import deque
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
WIKI = VAULT / "wiki"
LINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")


def build(root=WIKI):
    """{page -> set(link_pages)} over every .md under root."""
    files = sorted(root.rglob("*.md"))
    pages = {p.relative_to(root).as_posix()[:-3]: p for p in files}
    graph = {rel: set() for rel in pages}
    for rel, p in pages.items():
        in_fence = False
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for m in LINK_RE.finditer(line):
                t = m.group(1).strip().lstrip("/")
                if t.endswith(".md"):
                    t = t[:-3]
                if t in pages:
                    graph[rel].add(t)
                    continue
                hits = [r for r in pages
                        if r.rsplit("/", 1)[-1].lower() == t.rsplit("/", 1)[-1].lower()]
                if len(hits) == 1:
                    graph[rel].add(hits[0])
    return graph


def resolve(name, pages):
    n = name.strip().lstrip("/").removesuffix(".md")
    if n in pages:
        return n
    hits = [r for r in pages if r.rsplit("/", 1)[-1].lower() == n.lower()]
    if not hits:
        hits = [r for r in pages if n.lower() in r.lower()]
    if len(hits) == 1:
        return hits[0]
    sys.exit("unknown or ambiguous page %r -> %s" % (name, hits[:6] or "no match"))


def _undirected(graph):
    nbrs = {r: set() for r in graph}
    for src, dsts in graph.items():
        for d in dsts:
            nbrs[src].add(d)
            nbrs[d].add(src)
    return nbrs


def shortest(graph, a, b):
    """BFS shortest hop chain a..b (undirected) as a list, or None."""
    nbrs = _undirected(graph)
    prev = {a: None}
    q = deque([a])
    while q:
        cur = q.popleft()
        if cur == b:
            chain = [b]
            while prev[chain[-1]] is not None:
                chain.append(prev[chain[-1]])
            return chain[::-1]
        for n in sorted(nbrs.get(cur, ())):
            if n not in prev:
                prev[n] = cur
                q.append(n)
    return None


def in_degrees(graph):
    ind = {r: 0 for r in graph}
    for dsts in graph.values():
        for d in dsts:
            ind[d] += 1
    return ind


def cmd_path(graph, a, b):
    chain = shortest(graph, a, b)
    if chain is None:
        print("no path: %s -> %s" % (a, b))
        return 1
    print(" -> ".join(chain) + "  (%d hops)" % (len(chain) - 1))
    return 0


def cmd_hubs(graph, top=10):
    ind = in_degrees(graph)
    ranked = sorted(((len(graph[r]) + ind[r], ind[r], len(graph[r]), r)
                     for r in graph), reverse=True)
    print("degree  in  out  page")
    for deg, i, o, r in ranked[:top]:
        print("%6d  %3d  %3d  %s" % (deg, i, o, r))
    return 0


def cmd_orphans(graph):
    ind = in_degrees(graph)
    hits = [(r, bool(graph[r])) for r in graph if ind[r] == 0]
    if not hits:
        print("no orphans: every page is linked from at least one other")
        return 0
    for r, has_out in sorted(hits):
        print("%s%s" % (r, "" if has_out else "  (isolated: no links either way)"))
    print("%d page(s) with zero in-links" % len(hits))
    return 0


def cmd_neighbors(graph, page):
    incoming = sorted(r for r in graph if page in graph[r])
    print("out:")
    for d in sorted(graph[page]):
        print("  " + d)
    print("in:")
    for s in incoming:
        print("  " + s)
    return 0


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("usage: wiki-graph.py path A B | hubs [N] | orphans | neighbors PAGE")
        return 0
    graph = build()
    cmd = argv[1]
    if cmd == "path" and len(argv) == 4:
        return cmd_path(graph, resolve(argv[2], graph), resolve(argv[3], graph))
    if cmd == "hubs":
        return cmd_hubs(graph, int(argv[2]) if len(argv) > 2 else 10)
    if cmd == "orphans":
        return cmd_orphans(graph)
    if cmd == "neighbors" and len(argv) == 3:
        return cmd_neighbors(graph, resolve(argv[2], graph))
    print("bad args; usage: wiki-graph.py path A B | hubs [N] | orphans | neighbors PAGE")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
