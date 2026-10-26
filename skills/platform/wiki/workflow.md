# wiki workflow

Primary knowledge layer (~90% of lookups, qmd ~0.5s):

1. Query shape content -> `mcp__wiki-search__query` (lex for keywords, vec
   for meaning, hyde for nuanced). Relations/multi-hop -> graphify instead.
2. Read the winning page(s) with `get`/`multi_get`; never read `index.md` to
   browse.
3. Queries stay English even when target content is not.
4. New reusable knowledge at close-out -> `wiki-stage.py` -> `wiki-promote.py`
   via `Skill(learn)`.

## N/A escapes

- `N/A: empty vault (fresh install, no pages ingested yet)`
