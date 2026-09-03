---
name: vector-workflow
description: Documents the vector-workflow board-seeding pipeline in scripts/offensive.py's derive_rows() - the OSINT pre-pass plus per-asset web/ad_windows/linux vector-baseline classes (VECTOR_PRIORITY order) with narrow fingerprint-gated exceptions, that seeds the 4a coverage board. Not manually invoked - `board` runs this automatically. Use for "vector workflow", "osint to web pipeline", "board seeding order", "which vector applies", "why is this row on the board", "vector baseline classes", "VECTOR_PRIORITY".
---

# vector-workflow

Reference doc for the row-seeding logic inside `scripts/offensive.py`'s `derive_rows()`, called by
`offensive.py board`. You do not run this skill as a step in the loop - it explains what already
happens automatically each time `board` writes the Approach.md 4a matrix, the same relationship a
"how the fingerprint router works" doc has to the router itself.

## The pipeline, in order

`derive_rows(eng, index, etype)` builds the desired 4a rows in this fixed sequence:

1. **OSINT pre-pass (once, target-level).** Before any host/IP exists, `VECTOR_CLASSES["osint"]` =
   `osint-subdomain`, `osint-leaks`, `subdomain-takeover` are emitted keyed to the engagement name
   itself (`Path(eng).name` stands in for "asset" since no asset row exists yet at this phase).
   `subdomain-takeover` lives here (not the `web` vector) because it's a subdomain-enumeration-time
   check against every discovered subdomain, not gated on a per-asset web fingerprint.
2. **Per asset, once `state.md` has assets** (from rustscan+nmap etc.), for each asset row:
   a. **Fingerprint-implied classes first.** Every routing-table fingerprint whose `\b<fp>\b` regex
      matches the asset's `hay` text (built from `tech`/`services`/`service`/`os`/`notes` columns)
      contributes its mapped `class`, in routing-table order. These rank above vector/base rows.
   b. **Vector baseline, in `VECTOR_PRIORITY` order** (`["web", "ad_windows", "linux"]`): for each
      vector whose `VECTOR_INDICATOR[vector]` regex matches `hay`, emit every class in
      `VECTOR_CLASSES[vector]`, then check `VECTOR_EXCEPTION` for that vector and emit the extra
      class if its fingerprint substring also appears in `hay`.
   c. **`BASE_CLASSES[etype]` fallback** fills in any base class not already in the implied list
      (rows already `seen` from steps a/b are deduped regardless).

An asset can match more than one vector - a host running both SMB and a web app gets both the
`ad_windows` and `web` baseline rows. G4 (`Deadends.md`) suppression applies at every step: a
`(asset, class)` pair already deadended is never re-emitted. `next`/`done`/G1-G9 treat every
vector-seeded row exactly like any other 4a row - no new gate, no new command.

## Vector indicators and baseline classes

```python
VECTOR_PRIORITY = ["web", "ad_windows", "linux"]
VECTOR_INDICATOR = {
    "web":        r"\b(https?|nginx|apache|iis|tomcat)\b",
    "ad_windows": r"\b(smb|ldap|kerberos|winrm|rdp|445|389|88|3389|5985)\b",
    "linux":      r"\b(ssh|22|linux|nfs|rsync)\b",
}
VECTOR_CLASSES = {
    "osint":      ["osint-subdomain", "osint-leaks", "subdomain-takeover"],
    "web":        ["content-discovery", "js-extract", "recon-nuclei", "recon-nikto"],
    "ad_windows": ["ad", "windows"],
    "linux":      ["linux-svc-enum"],
}
VECTOR_EXCEPTION = {
    ("web", "wordpress"): "wpscan-scan",   # only fires when "wordpress" is also in hay
}
```

## The pseudo-classes and their real hunt-skill mapping

Every class above resolves through the hunt-core routing table (`skills/hunt/hunt-core/SKILL.md`)
to a real skill/wiki/arsenal, same as any fingerprint-implied class - `_class_info()` reads it
straight from the compiled index, no special-casing for vector rows. Current mapping (grep
`skills/hunt/hunt-core/SKILL.md` for the `-baseline` rows if this drifts):

| class | hunt skill | primary wiki | arsenal slug | tool (`CLASS_TOOL`) |
|---|---|---|---|---|
| osint-subdomain | hunt-secrets | web-attack-surface | recon | subfinder |
| osint-leaks | hunt-secrets | secret-hunting | recon-dorks | trufflehog |
| subdomain-takeover | hunt-secrets | subdomain-takeover | recon | nuclei |
| content-discovery | hunt-rce | web-attack-surface | wordlists | ffuf |
| js-extract | hunt-secrets | javascript-source-map-exploitation | recon-dorks | linkfinder |
| recon-nuclei | hunt-rce | web-attack-surface | nuclei-arsenal | nuclei |
| recon-nikto | hunt-rce | web-attack-surface | cve-arsenal | nikto |
| wpscan-scan | hunt-rce | cms-exploitation | cms-exploitation | wpscan |
| ad | hunt-ad | active-directory | netexec | netexec |
| windows | hunt-windows | windows-privesc | privesc-exploit-arsenal | winpeas |
| linux-svc-enum | hunt-rce | vuln-assessment | service-enumeration | searchsploit |

`ad` and `windows` are real hunt-core classes reused as the `ad_windows` vector baseline, not
vector-only pseudo-classes - they also fire directly off `ad`/`windows` fingerprint matches.
`content-discovery`/`js-extract`/`recon-nuclei`/`recon-nikto`/`wpscan-scan`/`osint-subdomain`/
`osint-leaks`/`subdomain-takeover`/`linux-svc-enum` are the nine pseudo-classes that exist only to
give the vector pipeline (and OSINT pre-pass) a routable row.

## When this matters

You don't invoke this skill manually - a fresh engagement's `board` command runs `derive_rows()`
automatically and the resulting OSINT + vector rows just appear on the Approach.md 4a matrix
already populated with arsenal/skill/tool. Read this skill when:

- You need to explain *why* a particular row is on the board (which vector matched, or which
  fingerprint implied it).
- You're extending `offensive.py` conceptually (not editing it here) and need the exact seeding
  order without re-deriving it from `derive_rows()`.
- A vector row's skill/arsenal looks wrong and you need the real mapping to check against
  `skills/hunt/hunt-core/SKILL.md` rather than guessing.

Full loop mechanics (gates, `next`/`note`/`done`, close-out) live in `Skill(offensive)`; this skill
is scoped to the board-seeding pipeline only.
