---
name: ponytail-debt
description: >
  Sweep the ponytail marker ledger: run when the close-out hook nudges it,
  "/ponytail-debt", or before committing framework changes. Lists every
  `ponytail:` comment (known-ceiling debt) with file:line; refresh the stamp
  once reviewed.
metadata:
  hermes:
    tags: [ponytail, debt-ledger, markers]
    related_skills: [ponytail, ponytail-review]
---

# ponytail-debt

Run the sweep:

```
python3 scripts/ponytail-debt.py
```

Exit 1 with markers listed (file:line + the ceiling named in the comment).
Zero markers = clean. Once every listed marker is either accepted or fixed,
refresh the stamp so the close-out hook stops nudging:

```
python3 scripts/ponytail-debt.py --stamp
```

The stamp (.ponytail-debt-stamp, repo root) uses the .wiki-stamp mtime
pattern: the hook compares framework-file mtimes against it.
