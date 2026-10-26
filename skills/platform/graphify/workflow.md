# graphify workflow

Exactly two roles (measured split; wiki/qmd covers the rest):

1. Multi-hop chaining: `python3 scripts/wiki-graph.py path "<primitive>"
   "<impact>"` when planning how low-severity findings chain to impact.
2. Large recovered source-map AST graphs: `graphify extract --code-only` on
   multi-file trees BEFORE reading, to map modules and pick read order.

Anything else (page lookup, tool syntax, tech behavior) goes to wiki/qmd.

## N/A escapes

- `N/A: no multi-hop question and no sourcemap tree this lane`
