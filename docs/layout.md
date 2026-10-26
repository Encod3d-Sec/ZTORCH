# Directory layout (full annotated tree)

`AGENTS.md` carries the compact top-level tree; this is the detailed per-file reference.

```
ZTORCH/
├── AGENTS.md                    <- agent instructions (+ README.md, LICENSE)
├── .zcode/config.json           <- ZCode hook registration (committed)
├── targets/                     <- engagements (PRIVATE; client data only here, git-ignored)
│   ├── active.md                <- pointer: current engagement dir name
│   ├── scrub-terms.txt          <- private leak-check extras (not shipped)
│   └── <eng>/                   <- pentest/bugbounty self-healed set (state,loot,Killchain,Approach,log,scope,walkthrough,eval,oob,Vuln-index,Deadends) + ingest/ + poc/ (curated PoC shots) + Vulns/ (pentest); ctf: lean upfront set (state,loot,Approach,scope,Deadends); Killchain/log stay pentest/bugbounty-only, walkthrough/eval/decisions self-create on demand; flow-scope scaffolding: lists/ + osint/ + ledgers/ + .paths.json (new engagements create them; lanes write run-state there)
├── wiki/
│   ├── index.md                 <- catalog of all wiki pages
│   ├── moc.md                   <- graph map-of-content (domain hubs; navigate here)
│   ├── overview.md              <- methodology map and coverage status
│   ├── techniques/              <- active-directory, cloud, web, osint, cracking, network,
│   │                              red-team, linux, exploit-dev, methodology, mobile-iot
│   ├── payloads/                <- per-vuln-class payload arsenal (hunt skills pull from here)
│   ├── tools/                   <- per-tool reference pages
│   ├── cheatsheets/             <- quick-reference command sheets
│   └── courses/  CTF/           <- course notes; challenge writeups
├── session/
│   ├── hot.md                   <- rolling 3-entry summary (auto-loaded at startup)
│   ├── log.md                   <- append-only audit trail
│   └── memory.md                <- long-term editorial patterns
├── docs/
│   ├── workflows.md             <- step-by-step workflow guide
│   ├── page-types.md            <- required sections per page type
│   ├── setup.md                 <- machine setup and path config
│   ├── virtual-machine.md       <- Kali attack VM + vm.sh SSH bridge; when/how to run tooling vs. targets
│   ├── sharing.md               <- client-data boundary; how to share safely
│   ├── conventions.md           <- cross-referencing, log format, style guide
│   ├── auto-triggers.md         <- what auto-fires (hooks, triggers.json, playbook) and when
│   ├── skill-map.md             <- task -> skill/tool dispatch table (relocated from AGENTS.md)
│   ├── superpowers/             <- design specs/plans (git-ignored; machine paths, scrub before sharing)
│   └── layout.md                <- this file: full annotated directory tree
├── scripts/                     <- automation (self-documenting via docstrings): next_move,
│                                   status.py (on-demand engagement dashboard: phase/counts/evidence/deadends/moves),
│                                   wiki-query.sh (qmd CLI wiki-first fallback when the MCP drops),
│                                   wiki-eval.py (retrieval eval + regression gate over scripts/wiki-eval-gold.json: hit@3/hit@5/MRR; run --check before/after any qmd chunker/index change),
│                                   find-lint, lint-wiki, lint-md-tables.py (GFM table integrity), gen_index, build_moc, freshness,
│                                   check-hooks, check-leaks.sh, trigger-stats, wordlist-* (+wordlists/),
│                                   shot.py, capture.sh (one entrypoint, modes: ev=live cmd+url card / req=curl
│                                   request-response / tmux=real tmux-session card / burp=Burp Repeater PoC), vm-scan.sh, burp/ (burp-mcp-cli.py bridge + burp-transport.sh resolver + burp-scope-sync.py),
│                                   build-walkthrough.py (scaffold + auto-populate the walkthrough Evidence gallery),
│                                   wiring: wiki-wiring-audit.py (which wiki pages surface by context during an engagement) + apply-wiring.py (applies a merged wiring-proposal JSON to playbook.json/triggers.json/hubs/hunt SKILL.mds) + wiring-exempt.txt (deliberately-unwired pages) + bench.py (scores a completed engagement dir against an expected-coverage manifest),
│                                   handroll.py (DORMANT: detects a hand-rolled request loop that should have been a tool; documented only, wired into no hook),
│                                   playbook.json
├── setup/                       <- bootstrap.sh, install-hooks.sh (per-device hook reg), install-skills.sh, new-engagement.sh, new-research.sh, templates/<type>/ + templates/research/, burp/ (disable-lock.sh)
├── tests/                       <- pytest suite for engagement + wiki automation
├── skills/                      <- hooks/ (hook scripts) + skills-setup.md at root; the rest grouped by role
│   │                               (nesting is organizational only, skills are discovered by basename;
│   │                               flow-scope skills carry paired workflow.md + checklist.md per dir,
│   │                               machine-gated by scripts/check-runbooks.py + scripts/completion-gate.py):
│   ├── exploit/                 <- hunt/ (hunt-* vuln-class skills (38) + hunt-core spine + triggers.json), exec/ (delegate, metasploit, redteamlead)
│   ├── orchestrate/             <- offensive (driver) + engage (router) + brain (subagent dispatch) + kali-seat
│   ├── platform/                <- caveman, graphify, ponytail + ponytail-debt + ponytail-review, obsidian-lint, wiki, agents-md-improver (offline instruction-file reviewer)
│   ├── research/                <- research, nday, searchsploit, wiki-arsenal, wiki-recon
│   ├── surface/                 <- vector-workflow (board-seeding reference; not a loop step), browser/ (chrome-devtools-browser, screenshot), burp/ (hunt-burp MCP driver + screenshot-burp), caido (headless driver; caido-mode SDK vendored), fuzz, interceptor, js-discover, js-parser
│   ├── report/                  <- disclosure, walkthrough
│   └── workflow/                <- bb-workflow, nightmare (Windows LPE arsenal, CTF/lab), closeout/ (engagement-retro, evidence, learn, triage), ctf/ (ctf-box, ctf-category), recon/ (ingest, research-ingest); workflow-brain + active-workflow + osint-workflow + js-extractor (flow-scope run skills, each a workflow.md + checklist.md pair)
└── raw/
    ├── research/                <- CVE writeups/blogs/advisories + active research projects (<project>/ from new-research.sh; the research skill writes loop state here)
    ├── assets/                  <- screenshots and other non-text files (read-only)
    └── git/                     <- cloned repos (WSL path, not Windows mount)
```

## Section helper

Long SKILL.md and wiki pages open with a `## Sections` index, and
`bash scripts/wiki-section.sh <page> <slug>` prints one named `## ` section body
(`--list` prints slugs) so a caller loads only the section it needs.
