# Skill map: task -> skill/tool

Moved out of AGENTS.md (per-turn context budget): consult on demand. The `/` skill
picker lists every skill with its description and stays the discovery mechanism;
this table is the judgment layer (which skill for which kind of task). Vault-local
skills load via the Skill tool, discovered by basename, so directory placement is
organizational only.

| Task                                          | Use                                                                                    |
| --------------------------------------------- | -------------------------------------------------------------------------------------- |
| Multi-step planning                           | ZCode plan mode (built-in); `superpowers:brainstorming` + `superpowers:writing-plans` if that plugin is installed (optional) |
| Execute a plan                                | `superpowers:subagent-driven-development` (optional plugin), else work the plan board directly |
| Debug unexpected behavior                     | `superpowers:systematic-debugging` (optional plugin), else reproduce -> isolate -> fix  |
| About to claim done                           | `superpowers:verification-before-completion` (optional), else re-run the checks you claim pass |
| Write/edit vault `.md`                        | `obsidian:obsidian-markdown` (optional plugin), else follow `docs/page-types.md` conventions |
| Fetch URL for ingest                          | `WebFetch` tool                                                                        |
| Read vault file                               | `Read` tool with machine path (see AGENTS.md / `AGENTS.local.md`)                      |
| Search vault                                  | `qmd_query` (semantic) or `qmd_search` (keyword) via `wiki-search` MCP                 |
| Maintain wiki index (re-index, status)        | `wiki` skill                                                                           |
| Load engagement playbook / FIND schema        | Read `targets/TARGETS.md`                                                              |
| Audit AGENTS.md (full review)                 | `agents-md-improver` skill (vault-local offline reviewer)                              |
| Update AGENTS.md (targeted session learnings) | `agents-md-improver` skill, targeted mode                                              |
| Session end / pause work                      | `gsd:pause-work` (optional plugin) or the manual pause-work steps                      |
| Parallel independent tasks                    | Dispatch several Agent tool calls in one message, or `superpowers:dispatching-parallel-agents` (optional) |
| Run a full bb/pt/ctf engagement autonomously  | `bb-workflow` / `pt-workflow` / `ctf-workflow` skill (driver: `scripts/campaign.py`; the single source of truth for the execution loop) |
| Check the workflow driver is set up on this machine | `campaign-health` skill (`scripts/campaign-doctor.py`)                           |
| About to attack a web endpoint                | `hunt-<type>` skill (see AGENTS.md auto-triggers)                                      |
| Driving a web target through Burp (proxy-history triage, Repeater/Intruder/Collaborator) | `hunt-burp` skill (Burp MCP; setup [[burp-mcp]])       |
| Starting recon on any target                  | wiki-recon skill                                                                       |
| Manual login / MFA the agent can't do headlessly (Smart-ID, Mobile-ID, captcha) + drive & observe via CDP | `chrome-devtools-browser` skill (visible chromium on the VM via `scripts/browser-visible.sh` + chrome-devtools MCP) |
| Validating / moving finding to Completed      | triage then evidence skills                                                            |
| Vuln/CVE research on a target (binary/repo/app/firmware) | `research` skill (scaffolds `raw/research/<project>/`)                      |
| Hand a fiddly, fully-specified exploit-compile/escalation run to a sub-agent | `delegate` skill (autonomous sub-agent exploit-run; false-root/hostname guardrail mandatory) |
| Drive msfconsole (recon, exploit search/run, reverse shells, post-ex) | `metasploit` skill (msfconsole framework-driver; cheatsheet [[metasploit]]) |
| Working the VM / WSL seat (vm.sh, tmux-on-VM, seat map) | `kali-seat` skill (Windows seat -> WSL kali -> VMware VM; `/opt/ztorch` in WSL) |

## Vault-local skill layout

`skills/hunt/` holds the `hunt-*` vuln-class skills plus the shared `hunt-core` spine
every hunt assumes. `skills/workflow/` holds the engagement PROCESS skills: `arsenal`/
`wiki-arsenal`, `triage`, `evidence`, `coverage`, `ingest`, `next-move`, `wiki-recon`,
`nday`, `research-ingest`, `delegate`, `metasploit`, `ctf-box`, `ctf-category`,
`screenshot`, `chrome-devtools-browser`, `learn`, `walkthrough`. `skills/burp/` holds
`hunt-burp` + `screenshot-burp` (the Burp MCP driver + Repeater-PoC capture; driver
scripts in `scripts/burp/`, host setup in `setup/burp/`). Standalone: `wiki/`,
`research/`, `disclosure/`, `code-review/`. `agents-md-improver/` is the offline
instruction-file reviewer (the ZCode counterpart of the old `claude-md-improver`).
MCP/hook/plugin troubleshooting: `skills/skills-setup.md`.
