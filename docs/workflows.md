# Wiki Workflows

## CPTS / PortSwigger module ingest

1. **Check** the destination pages' `sources:` frontmatter -- if the ingest slug is already listed there, that source is done; skip it. (The `sources:` list is the dedup mechanism; there is no separate `ingested.md` tracker.)
2. **Look up** slug in `raw/manifest.md` for exact file path. Read all markdown files in the module. Skip image references.
3. **Write** `wiki/courses/<slug>.md`. For each technique/tool page: read frontmatter only -- skip if slug already in `sources:`, otherwise read and update. Add slug to `sources:` list.
4. **Update** `wiki/overview.md` and regenerate `wiki/index.md` (`scripts/gen_index.py`). Append a one-line entry to `session/log.md`.

## TryHackMe room ingest

When the user asks you to ingest a THM section or room:

1. **Check** the destination pages' `sources:` frontmatter -- if the slug is already listed, that source is done; skip it.
2. **Look up** the slug in `raw/manifest.md` to get file paths and dedup notes. Check for any [warn] skip warnings before reading files.
3. **Read** the markdown files. Strip all `![[...]]` and `![](...)` image references.
4. For each technique/tool page to update: read frontmatter only. Skip if slug already in `sources:`.
5. **Update or create** technique pages directly -- no course page per room. Add slug to `sources:`.
6. **Update or create** tool pages if new tools appear. Add slug to `sources:`.
7. **Update** `wiki/overview.md` and `wiki/index.md`.
8. **Record** the slug in each updated page's `sources:` list (the dedup marker).
9. **Append a single log entry** to `session/log.md` covering all rooms in the slug -- don't log each room individually.

## Research ingest

When the user drops a CVE writeup, blog post, or advisory into `raw/research/`, or provides a URL to ingest:

1. **Fetch** the source. If it's a URL (not a local `.md` file), prefer `defuddle parse <url> --md` for clean markdown output (install: `npm install -g defuddle`). Fall back to WebFetch if defuddle is unavailable.
2. **Update** the relevant technique page(s) -- add the new payload, bypass, or finding.
3. **Update or create** a tool page if a new tool is introduced.
4. **Create** a course page only if the source is course material -- otherwise just update technique/tool pages.
5. Regenerate `wiki/index.md` (`scripts/gen_index.py`) and append a one-line entry to `session/log.md`.

## Learn / knowledge harvest (post-engagement)

At close-out of a completed box/bugbounty/pentest/CTF, harvest the GENERIC knowledge the
engagement produced that the wiki does not already have. This is the mirror image of
research ingest (external source -> wiki): the source here is the finished engagement.
Use `Skill(learn)` at close-out, once the engagement is `SOLVED` and its walkthrough is
assembled.

1. **Inventory** what the engagement taught from `state/loot/Approach/Deadends/
   Vuln-index/walkthrough`; pentest/bugbounty add `Killchain/log`, while ctf keeps its
   chain in `state.md`'s `## Chain` section instead.
2. **Generalize** each lesson (product + technique/cred/endpoint + impact); strip every
   client host/IP/domain/cred value.
3. **Dedup vs wiki** with `mcp__wiki-search__query`/`mcp__wiki-search__query (lex)` -- keep only what the home page does
   not already cover.
4. **Stage** each survivor (`scripts/wiki-stage.py --kind default-cred|api-pattern|
   technique`); a genuinely new class gets a content-free scaffold page first so its
   substance still arrives through the gate.
5. **Promote** through the leak gate (`scripts/wiki-promote.py --promote all`, runs
   `check-leaks.sh`, fails closed, re-indexes), then `lint-wiki.py -q` and, for a new
   page, `gen_index.py` + `build_moc.py` + `qmd update && qmd embed`. If the harvest
   touched routing data (`scripts/playbook.json`, `skills/exploit/hunt/triggers.json`), run
   `python3 scripts/check-routing.py` too (bad regex/enums drop rows silently at load).
6. **Self-clear + log**: `touch targets/<eng>/.learn-done`; one generic line to
   `session/log.md`. Never write client specifics into `session/*` or `wiki/`.

## Git repo ingest

When the user provides a GitHub URL to clone and analyse:

1. **Clone** the repo. Use WSL (`wsl -d kali-linux -u kali -- git clone <url> /home/kali/<reponame>`). **Do not clone directly to the Windows `raw/git/` path** -- `git clone` fails on Windows filesystem mounts due to a `chmod` error on `.git/config.lock`. After cloning, record the WSL path in `raw/manifest.md` (e.g. `/home/kali/<reponame>`).
2. **Read** all relevant source files (code, README, headers).
3. **Register** the slug `git-<reponame>` in `raw/manifest.md` under `## Git Research Repositories` -- include path, file count, and key topics.
4. **Create or update** the relevant technique page(s) with mechanisms, code examples, detection notes, and real-world context drawn from the code.
5. **Update or create** a tool page if the repo is a standalone tool.
6. Regenerate `wiki/index.md` (`scripts/gen_index.py`), update `wiki/overview.md`, append to `session/log.md`, and update **`AGENTS.md`** if the vault structure changed.
7. No `wiki/courses/` page is needed for git repos -- synthesise directly into technique/tool pages.

## Target session

For any offensive engagement (pentest, bug bounty, or CTF box), `scripts/offensive.py` via
`Skill(offensive)` owns the loop, the gates, and the plan board -- it is the authority for how a
target session actually runs. Full mechanics (the `init` -> `index` -> `board` -> `next`/`note`/`done`
cycle, the G1-G9 gates, close-out) live there and in `Skill(vector-workflow)` for how the board's 4a
rows get seeded; this doc does not duplicate them (duplicating them here is exactly what let this
section drift the last time the driver changed -- go to the skill, don't re-derive it from memory).
In short: `Skill(offensive)`'s `next` prints the row to work and the exact Skill/tool to run, `note`
records the arsenal card consulted, `done` closes it with typed evidence (or `--dead`/`--park`); repeat.

The state files underneath the driver are still the source of truth it reads and writes, and the
conventions below (full schema in `targets/TARGETS.md`; the file set is self-healed by the
`engagement-init` hook) stay accurate independent of which loop is driving:

- `scope.md` -- in/out-of-scope + RoE flags; read before ANY action
- `state.md` -- hosts/services/access (and owned status)
- `loot.md` -- captured credentials + reuse map
- `Killchain.md` -- the evolving attack chain: open/blocked attack-path rows + the Confirmed-chain header
- `Deadends.md` -- exhausted vectors (do not re-test without new input); a `done --dead` writes this
  automatically and suppresses that (asset, class) pair from ever being re-served
- `Approach.md` -- the plan board: the `### 4a` tested-class table (plus phase checklists) the driver reads and writes
- `Vuln-index.md` -- confirmed findings and chains

Search-wiki-before-attacking and capture-as-you-go still apply -- `Skill(offensive)`'s G1 gate
enforces the wiki-arsenal lookup before any exploit action, and `note`/`done` are how you record it,
but the underlying discipline is the same one this doc has always described: run `qmd query "<service
or technique>"` (or `Skill(wiki-arsenal)`) before attacking a service, read the matching technique and
tool pages, then write results into `state.md`/`loot.md`/`Killchain.md` immediately (prose in chat is
lost; the tables persist) rather than letting them pile up in the conversation. Findings still go to
`Vulns/FIND-NNN-SEVERITY-title.md`, linted with `scripts/find-lint.py` before `/evidence`.

**If the driver is unavailable** (no `scripts/offensive.py`, or working off-campaign): fall back to
`Approach.md` by hand -- take the top open row, run its arsenal lookup then its hunt skill, capture
typed evidence, mark `[x]`; on exhaustion write one `Deadends.md` line and mark `[!]`.

**After the session:** run `gsd:pause-work` -- append a named entry to the engagement `log.md` (audit)
and refresh `hot.md` (rolling cache). Generic/framework learnings (no client specifics) go to
`session/log.md` + `session/hot.md`.

**Feed reusable knowledge back to wiki** -- after a novel bypass, payload, or CVE chain, update the
relevant `wiki/techniques/` page in generic form (no client specifics). Do not create per-finding wiki
pages. At close-out, `Skill(offensive)`'s printed chain includes `Skill(learn)` to sweep the whole
engagement for anything still missing from the wiki.

## Query

When the user asks a question:

1. **Search first** using the `wiki-search` MCP tool (`mcp__wiki-search__query` for semantic search, `mcp__wiki-search__query (lex)` for keyword). This replaces reading `wiki/index.md` manually.
2. Read the pages returned by the search in full.
3. Synthesise an answer with inline `[[wiki links]]` as citations.
4. **Offer to file the answer** as a wiki page if it's a non-trivial synthesis -- e.g. a comparison of techniques, a methodology walkthrough, or a cheatsheet.

If the `wiki-search` MCP is unavailable, fall back to reading `wiki/index.md` to identify relevant pages.

## Re-indexing after ingest

After writing new or updated wiki pages, run `qmd update && qmd embed` via the `Bash` tool to keep the search index current (`update` = text index, `embed` = semantic vectors; skipping `embed` leaves new pages invisible to `qmd query`). Do this once at the end of an ingest session, not after every file.

## Hot cache

`session/hot.md` is a rolling session summary read at startup. At the end of every ingest, query, or target session, append a brief update:

```
## [YYYY-MM-DD] <ingest|query|target>
- <what was ingested or answered>
- <pages created or updated>
- <gaps identified or next steps>
```

Keep only the three most recent entries -- delete older ones when adding a new one.

## Lint

Health check is script-driven. The SessionStart hook surfaces a one-line summary automatically; run the full check on demand (or every ~15 ingests):

1. **`python3 scripts/lint-wiki.py`** (`-v` for every offender) - broken wikilinks (code blocks ignored), dead `scripts/*` references in docs/AGENTS.md/skills, frontmatter gaps, stale `index.md`, and the leanest technique areas. Exits 1 on hard problems.
2. **`python3 scripts/gen_index.py`** - regenerate `wiki/index.md` whenever lint reports it stale (or after adding/renaming any page). It is auto-generated; never hand-edit it.
3. **`python3 scripts/build_moc.py`** - regenerate graph hubs after adding pages so every page stays reachable (replaces the manual orphan scan).
4. **`python3 scripts/wiki-gaps.py -v`** - technique pages referenced by hunt skills / FIND files but missing.
5. Pick the next build-out target from the leanest-areas note in step 1; append a one-line lint entry to `session/log.md`.
6. Re-index search after page changes with `qmd update && qmd embed` (see `### Re-index search`).

### Re-index search

After touching many wiki pages, run **`qmd update && qmd embed`** on the host where the `wiki-search` collection is registered (often WSL Kali for this vault).

