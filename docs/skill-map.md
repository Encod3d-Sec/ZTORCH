# Skill map: task -> skill/tool

Moved out of AGENTS.md (per-turn context budget): consult on demand. The `/` skill
picker lists every skill with its description and stays the discovery mechanism;
this table is the judgment layer (which skill for which kind of task). Vault-local
skills load via the Skill tool, discovered by basename, so directory placement is
organizational only.

| Task                                          | Use                                                                                    |
| --------------------------------------------- | -------------------------------------------------------------------------------------- |
| Starting/running any engagement; "which skill next?"    | `engage` skill (orchestrator router: situation -> Skill across the whole library; load first, consult between phases) |
| Multi-step planning                           | ZCode plan mode (built-in); `superpowers:brainstorming` + `superpowers:writing-plans` if that plugin is installed (optional) |
| Execute a plan                                | `superpowers:subagent-driven-development` (optional plugin), else work the plan board directly |
| Debug unexpected behavior                     | `superpowers:systematic-debugging` (optional plugin), else reproduce -> isolate -> fix  |
| About to claim done                           | `superpowers:verification-before-completion` (optional), else re-run the checks you claim pass |
| Write/edit vault `.md`                        | `obsidian:obsidian-markdown` (optional plugin), else follow `docs/page-types.md` conventions |
| Fetch URL for ingest                          | `WebFetch` tool                                                                        |
| Web search / OSINT / vuln research (keyless, cached) | `wigolo` MCP (`search`/`fetch`/`crawl`/`research`); see `wiki/tools/wigolo.md`  |
| Read vault file                               | `Read` tool with machine path (see AGENTS.md / `AGENTS.local.md`)                      |
| Search vault (wiki semantic/keyword)          | `mcp__wiki-search__query` (semantic) or `mcp__wiki-search__query (lex)` (keyword) via `wiki-search` MCP                 |
| Search workspace files (vault, targets/, raw/git) | `zg` first: `zvec_grep_search` MCP or `zg query --human "..."`; grep only inside one file |
| Maintain wiki index (re-index, status)        | `wiki` skill                                                                           |
| Over-engineering review of a framework diff | `ponytail-review` plugin skill (diff-scoped, one-line findings, applies nothing) |
| Repo-wide over-engineering audit | `ponytail-audit` plugin skill (ranked biggest-cut-first) |
| `ponytail:` marker ledger sweep | `ponytail-debt` plugin skill (harvests `ponytail:` comments; the close-out Stop hook nudges this) |
| Relational wiki queries (path between pages, hubs, orphans) | `graphify` skill (`scripts/wiki-graph.py`, live wikilink graph over `wiki/`; graphify CLI for code trees) |
| Load engagement playbook / FIND schema        | Read `targets/TARGETS.md`                                                              |
| Audit AGENTS.md (full review)                 | `agents-md-improver` skill (vault-local offline reviewer)                              |
| Update AGENTS.md (targeted session learnings) | `agents-md-improver` skill, targeted mode                                              |
| Session end / pause work                      | `gsd:pause-work` (optional plugin) or the manual pause-work steps                      |
| Parallel independent tasks                    | Dispatch several Agent tool calls in one message, or `superpowers:dispatching-parallel-agents` (optional) |
| Run a full pentest/bb/ctf engagement autonomously  | `offensive` skill (driver: `scripts/offensive.py --type pentest\|bb\|ctf`; the single source of truth for the execution loop) |
| Run an engagement (or any task) with the main chat as brain and execution in subagents | `brain` skill (haiku = glm-5.3-flash default, sonnet = glm-5.3 for in-run judgement; max 3 concurrent disjoint agents; wraps `offensive` when invoked via /brain) |
| Check the offensive driver is set up on this machine | `offensive-doctor` (`scripts/offensive-doctor.py`)                              |
| Board seeding order / vector workflow (why a row is on the board) | `vector-workflow` skill (OSINT pre-pass -> per-asset vector baseline -> base fallback, `derive_rows()`) |
| About to attack a web endpoint                | `hunt-<type>` skill (see AGENTS.md auto-triggers)                                      |
| Dispatching a lane / verifying a lane returned | completion gate: `python3 scripts/completion-gate.py init <lane-dir> --title "<run>"` at dispatch, `... check <lane-dir> --capture <dir>` on return (hunt-core "Run completion gate"; UNCHECKED/MISSING/EMPTY = not done, re-dispatch with the printed nudge) |
| Driving a web target through Burp (proxy-history triage, Repeater/Intruder/Collaborator) | `hunt-burp` skill (Burp MCP; setup [[burp-mcp]])       |
| Web-audit proxy when Burp/MCP is down, per-engagement isolated proxy project, or Caido-native features (Automate, workflows) | `caido` skill (headless Caido on the VM; caido-mode SDK CLI + `~/caido.sh`; [[wiki/tools/caido]])   |
| Starting recon on any target                  | wiki-recon skill                                                                       |
| Manual login / MFA the agent can't do headlessly (Smart-ID, Mobile-ID, captcha) + drive & observe via CDP | `chrome-devtools-browser` skill (visible chromium on the VM via `scripts/browser-visible.sh` + chrome-devtools MCP) |
| Validating / moving finding to Completed      | triage then evidence skills                                                            |
| Vuln/CVE research on a target (binary/repo/app/firmware) | `research` skill (scaffolds `raw/research/<project>/`)                      |
| Hand a fiddly, fully-specified exploit-compile/escalation run to a sub-agent | `delegate` skill (autonomous sub-agent exploit-run; false-root/hostname guardrail mandatory) |
| Drive msfconsole (recon, exploit search/run, reverse shells, post-ex) | `metasploit` skill (msfconsole framework-driver; cheatsheet [[metasploit]]) |
| Windows LPE shortcut on a CTF/lab box (standard-user foothold, recompiled Nightmare_Eclipse PoCs with recorded Defender verdicts) | `nightmare` skill (authorized CTF/lab targets only; hub [[privesc-exploit-arsenal]]; routed from hunt-windows) |
| Working the VM / WSL seat (vm.sh, tmux-on-VM, seat map) | `kali-seat` skill (Windows seat -> WSL kali -> VMware VM; `/opt/ztorch` in WSL) |
| Stuck / which vector / "should I keep hammering this" | `redteamlead` skill (fresh RTL subagent reads state+evidence+wiki, returns ranked directions + explicit STOP) |
| Content discovery / directory brute / hidden params / which wordlist | `fuzz` skill (adaptive wordlist selection + WAF/throttle handling) |
| `scripts/with_server.py` | Start N servers, poll ports until ready, run a command, guaranteed teardown (blind-sleep alternative) |
| Run the engagement as the vhost-lane brain (loop, board, state, triage) | `workflow-brain` skill (main-session brain from move 0; dispatches osint + active lanes on the locked vhost, never executes lanes itself) |
| Execute per-vhost deep-dive stages (lock+caido, context, JS read, list-fed fuzz, version research, hunts, RTL review) | `active-workflow` skill (stages 0-6 engine, 2-3 passes per vhost before unlock) |
| Passive OSINT on the engagement (historical URLs, infra intel, 3rd-party classification) | `osint-workflow` skill (archive + infra flash-tier lanes parallel to active work; zero packets to in-scope targets) |
| Full-read JS analysis of a harvested corpus | `js-extractor` skill (reads every first-party file end to end; emits the js-lists tables that fuel fuzz, version research, hunt selection) |

## Vault-local skill layout

`skills/` groups the library by role (nesting is organizational only -- the Skill tool
discovers every skill by basename regardless of depth): `exploit/` holds `hunt/` (the
`hunt-*` vuln-class skills plus the shared `hunt-core` spine and `triggers.json`) and
`exec/` (`delegate`, `metasploit`, `redteamlead`); `orchestrate/` holds the engagement
entry points `offensive` (the driver) and `engage` (the router), plus `brain`
(subagent dispatch mode over the driver) and `kali-seat`; `platform/` holds the
process utilities (`caveman`, `graphify`, `ponytail` + `ponytail-debt`/`ponytail-review`,
`obsidian-lint`, `wiki`, and `agents-md-improver`, the offline instruction-file
reviewer); `research/` holds `research`, `nday`, `searchsploit`, `wiki-arsenal`,
`wiki-recon`; `surface/` holds the by-surface tooling: `vector-workflow` (the
board-seeding pipeline reference, not a loop step), `browser/`
(`chrome-devtools-browser`, `screenshot`), `burp/` (`hunt-burp` the MCP driver +
`screenshot-burp` Repeater-PoC capture; driver scripts in `scripts/burp/`, host setup
in `setup/burp/`), `caido` (headless Caido driver; caido-mode SDK CLI vendored +
helper `scripts/caido.sh`), `fuzz`, `interceptor`, `js-discover`, `js-parser`;
`report/` holds `disclosure` and `walkthrough`; `workflow/` holds `bb-workflow`,
`nightmare`, `closeout/` (`engagement-retro`, `evidence`, `learn`, `triage`),
`ctf/` (`ctf-box`, `ctf-category`), and `recon/` (`ingest`, `research-ingest`).
Plus `hooks/` (hook scripts) and `skills-setup.md` at the root.
MCP/hook/plugin troubleshooting: `skills/skills-setup.md`.

## SKILL.md frontmatter (authoring reference)

Semantics verified against the host skill loader (2026-09-09, host-internals pass 5):

- `name` -- display only; the directory basename is the real invocation name. Keep them equal.
- `description` -- the listing/discovery gate (what the `/` picker and trigger routing weigh).
  Keep it under ~240 chars with trigger phrases front-loaded: the host truncates listing
  entries at ~250.
- `allowed-tools` -- absent means NONE are pre-allowed (not "all"); list what the skill needs.
- `user-invocable` -- defaults true; `false` hides it from the picker.
- `paths` -- NOT USED here, deliberately: a `paths:` skill is parked OUT of the command list
  until a matching file is touched (file-read activation). Our skills are prompt-routed
  (triggers.json -> `Skill(<name>)`), not file-triggered, so parking would break routing.
- `context: fork` -- NOT USED here: heavy skills (brain, wiki-arsenal deep) already manage
  their own subagent fleets; a fork-wrapped skill that also dispatches double-forks.

Editorial rule (compaction): an invoked SKILL.md re-attaches after a compact HEAD-TRUNCATED
at ~5k tokens (with a "read the path for full text" marker). Load-bearing rules -- gates,
guardrails, the output contract -- must live in the FIRST 5k tokens of the file body;
put worked examples and background after.

Editorial rule (prompt cache): the skill list is part of the cached prefix; editing a live
skill's description or AGENTS.md mid-session invalidates a ~20-70k-token cache write.
Batch those edits between sessions.
