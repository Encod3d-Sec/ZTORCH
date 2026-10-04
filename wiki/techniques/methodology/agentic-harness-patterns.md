---
title: "Agentic Harness Patterns"
type: technique
tags: [methodology, agents, orchestration, reference-import, automation]
phase: exploitation
date_created: 2026-09-09
date_updated: 2026-10-05
sources: ["https://github.com/vxcontrol/pentagi", "https://arxiv.org/html/2504.06017v2", "https://github.com/aliasrobotics/CAI", "https://github.com/greydgl/pentestgpt", "https://github.com/usestrix/strix"]
---

# Agentic Harness Patterns

## What it is

A distillation of the orchestration patterns used by the three leading open-source AI-pentest
peer frameworks, mapped onto ZTorch: what ZTorch already has, where the gap is, and the concrete
upgrade path for each pattern. ZTorch is a prompt-driven harness (skills, hooks, markdown state
over Claude Code); the patterns below are filtered through that constraint. Anything that requires
owning infrastructure or a standalone codebase lands in the do-not-adopt list instead of the
upgrade table. For the in-wiki view of multi-agent coordination failure modes see
[[Multi-Agent Campaign Orchestration]]; for the report artifact these patterns feed see
[[Vulnerability Reports]].

## PentAGI (vxcontrol/pentagi)

- Orchestration model: a **Flow -> Task -> SubTask -> Action -> Artifact** hierarchy persisted in
  Postgres, each entity with its own status field; the orchestrator retrieves similar past tasks
  from a vector store before delegating.
- Two agent classes with **call budgets as governance**: general agents (Assistant, Primary,
  Pentester, Coder, Installer) get a 100 tool-call cap; limited support agents (Searcher, Enricher,
  Memorist, Generator, Reporter, Adviser, Reflector, Planner) get 20. Wide-reach agents pay more,
  narrow support roles pay less.
- **Sandbox-per-flow execution**: every agent operation runs in a per-flow Docker container
  (Docker-in-Docker over TLS; first action of a flow is an LLM tool call that selects the container
  image); core, monitoring and analytics services sit on separate Docker networks.
- **Self-regulation loops** (corrected 2026-10-04 against `backend/pkg/templates/prompts/*.tmpl`):
  Mentor analysis is injected INTO the tool result when same-tool calls reach a threshold (5) or a
  total-call budget threshold trips, reset-on-fire; the Reflector is a format-recovery agent that
  role-plays the user to steer the agent back to structured tool calls (not a failure counter);
  the primary agent's own prompt carries the 3-identical-attempts -> pivot-strategy rule and the
  pentester's carries max 3 identical tool calls + max 2 install attempts before switching tools;
  an optional Planner emits a 3 to 7 step execution plan.
- **Typed memory**: Memory entities typed `observation`/`conclusion` with vector embeddings in
  pgvector, layered long-term / working / episodic; an optional Graphiti temporal knowledge graph
  per flow (off by default).
- **Chain summarization with byte caps** keeps long tool chains in context (configurable last
  section and QA-pair budgets, e.g. 50KB).
- Observability is first-class: OpenTelemetry to VictoriaMetrics/Jaeger/Loki plus Langfuse for
  per-call LLM traces; flow files are mirrored into the container and surfaced to prompts as XML.
- A Reporter agent produces per-flow report artifacts (web view, Markdown, PDF).

Steal: per-agent call budgets, failure-triggered reflection, typed observation/conclusion memory,
per-flow artifacts and byte-capped summarization.

## CAI (aliasrobotics/CAI, arXiv:2504.06017)

- Architecture: six pillars, Agents, Tools, Handoffs, Patterns, Turns, HITL; an interaction is one
  LLM reasoning step plus tool actions, a turn ends when the agent stops or a human intervenes.
- **Autonomy-level vocabulary**: the paper's Table 1 grades systems on Planning/Scanning/Exploiting/
  Mitigating: Manual; LLM-Assisted (planning only; PentestGPT listed here); Semi-automated; and
  full Cybersecurity AI. The repo later separates automation from autonomy in a 6-level taxonomy
  (arXiv:2506.23592); the L0-L5 definitions were not in the fetched material [uncertain].
- **Semi-autonomous stance**: HITL is called a critical cornerstone and fully autonomous operation
  is judged premature; the user interrupts with Ctrl+C. HITL at strategic points measurably lifts
  success, especially on crypto and rev.
- Agent **patterns**: a Red Team Agent (linux_commands, ssh_command, execute_code; objective "gain
  root"), a Bug Bounty Hunter (adds shodan_search, google_search), and a one_tool_agent used for
  controlled model comparisons; handoffs chain agents; per-exercise instances run **stateless** to
  avoid context contamination.
- **Benchmark self-scoring**: 54 CTF exercises (CSAW, HTB, picoCTF, VulnHub and others) on Kali,
  pass@1 with a 100-interaction cap, humans as baseline. Headline: 11x faster and 156x cheaper than
  humans on that set; claude-3.7-sonnet solved 19/23 against seven models. A later CAIBench
  meta-benchmark spans CTFs, ranges and knowledge tasks.
- Findings worth internalizing: the framework excels at well-defined single-task challenges via
  pattern recognition and struggles with multi-step exploitation chains, crypto math and advanced
  binary exploitation.
- A **Retester agent** (modeled on HackerOne's triage agent) deduplicates findings; MCP integration
  of Ghidra and Burp links static RE, triage and exploitation.

Steal: the autonomy vocabulary, stateless per-exercise instances, capped-interaction self-scoring,
verifier/retester dedup, strategic-point HITL.

## PentestGPT (greydgl/pentestgpt)

- The v1.0 agentic upgrade turns it into an **orchestrator over external agent CLIs**: it drives
  Claude Code or Codex to run tools and reason without human intervention; the backend is
  pluggable and the Docker image bundles both CLIs with idempotent, persisted auth.
- **Localization-then-reasoning prompt split** (inherited from the USENIX 2024 three-session
  design): a parsing session condenses raw tool output into structured, localized facts; a
  reasoning session works only over those facts; a generation session produces next commands.
  Per-role model flags exist (`--reasoning-model`, `--parsing-model`).
- A **Pentesting Task Tree (PTT)** is the shared task-state structure maintained live across the
  cooperating sessions; the interactive mode exposes `next`, `more`, `todo`, `discuss` against it.
- **Staged pipelines with explicit handoff**: recon -> exploit -> walkthrough for CTF,
  asset discovery -> vulnerability identification -> report for pentest; each stage's findings feed
  the next stage's context.
- **Session save/resume** (`pentestgpt --list-sessions`) so a run survives harness restarts.
- Telemetry is opt-out (Langfuse session metadata and tool-usage patterns only); the 86.5% XBOW
  figure is labeled a historical research result, not a shipped benchmark.

Steal: parse-before-reason as a prompt contract, an explicit task tree, stage-to-stage context
handoff, session resume.

## Strix (usestrix/strix)

- Architecture: a single ROOT agent that only orchestrates (it never runs scanners, crawlers, or
  payloads itself, "not even a quick basic test on a discovered endpoint") spawning named async
  subagents inside one shared Docker sandbox; an in-process coordinator owns the agent graph
  (statuses, parent links, mailboxes) and persists atomically on every state change; termination
  is lifecycle-tool-only (`finish_scan` for root, `agent_finish` for children), so plain text can
  never end a run.
- **Doctrine library over prompt cleverness**: 68 internal skill files sharing one fixed
  13-section skeleton (thesis / Attack Surface / High-Value Targets / Reconnaissance / Key
  Vulnerabilities / Bypasses / Chaining / Methodology / **Validation as a numbered evidence
  bar** / **False Positives as a first-class section** / Impact / Pro Tips); an always-on spine
  (counterevidence, severity calibration) injected into EVERY agent; scan-mode overlays
  (quick/standard/deep/diff) composed at prompt-build time over that fixed spine, changing
  breadth and skip lists but never the PoC bar; cross-skill routing carried by "Load X when"
  lines inside doctrine bodies (including negative routing); a stale-payload guard convention:
  every historical gadget carries "resolve the deployed build and check current advisories
  before claiming".
- **Findings pipeline with structural gates**: CVSS computed from the agent-supplied 8-metric
  breakdown, so severity is never agent-chosen; counterevidence + confidence +
  severity_change_conditions mandatory and validated at creation; a revise/delete split (delete
  is only for things that were never vulnerabilities, tombstoned with never-reissued ids; real
  but weaker is revised, and a changed rating DROPS its stale rationale field so a finding never
  shows a new severity beside the old reasoning); two-layer dedupe: deterministic dependency
  identity (CVE x package x manifest) with zero model calls, then a dedicated cheap judge model,
  tools off, own endpoint, fail-open.
- **Coverage as provenance-separated negative space**: an agent-reported ledger with a five-outcome
  enum (evidence-gated, one row per surface, history preserved on update) kept deliberately apart
  from machine-observed facts flattened from the runtime graph; "machine facts contradict rather
  than confirm"; equipped-but-unrecorded skill classes and silent agents are emitted as gaps
  meaning unexamined, not clean; `finish_scan` reflects the coverage census, unresolved rows and
  skill gaps back INSIDE the tool response, the last point the root can still dispatch work.
- Budget as governance: shared USD ceiling with graduated role-differentiated wrap-up warnings
  (70/85/95 percent bands) and a 90 percent sub-agent reserve so the root can always afford its
  report; a stop-vs-pause policy where pause parks an agent right before its next paid call and
  resumes it on the exact same call.
- Report rendering treated as a security boundary: CSV formula-injection guards on
  attacker-influenced titles, code fences opened one backtick longer than the longest run inside
  agent-authored PoC content, atomic temp+rename writes, no internal identifiers in the
  customer-facing report.

Steal: the fixed skill skeleton with mandatory Validation/False Positives sections, three-state
closure with the named-control test, the evidence-gated outcome enum, computed severity with
mandatory counterevidence, coverage gaps as unexamined-not-clean, budget bands + reserve,
fail-open dedupe with "would be fixed by the same patch" as the duplicate test.

## Pattern-to-ZTorch map

| Pattern | ZTorch today | Gap | Upgrade path | Effort |
|---|---|---|---|---|
| Sandbox-per-lane execution | Delegate lanes (slots a-h) are disjoint by contract but share one Kali VM seat; the drift-guard hook caps exploit-shaped calls, not blast radius | A runaway lane can clobber another lane's files and state on the shared VM | Give each delegate slot its own working dir on the VM (or a per-lane container) and name it in the lane contract; PentAGI's general/limited call-cap split maps onto Sonnet-vs-Haiku lane tiering | M |
| CVE-research correlation agent | `nday` skill + wiki + fingerprint playbook cover known-tech lookup; correlation happens ad hoc inside exploit lanes | No dedicated lane whose only job is external CVE/exploit correlation; it competes with the exploit lane for context | Add a delegate slot spec: researcher lane with web search + nday + wiki only, no exploit tools; wire a `chains.json`/playbook edge from fingerprint to that lane (PentAGI's Researcher/Searcher split, CAI's Bug Bounty Hunter toolset) | S |
| Per-lane report artifact | Landed: delegate slot (h) output-landing contract (every load-bearing command's full request+response in the lane capture dir, tmux-windowed) + the Scope/Result/Key files/Issues return envelope | Closed for capture; artifact-to-ingest still routes through main-session triage by design (triage is a judgement act) | none | done |
| Autonomy-level vocabulary | Landed 2026-09-09: L0-L3 scope envelope in both scope templates, offensive.py banner, L0/L1 exploit advisories, doctor check (advisory-only; RoE hooks stay the enforcement layer) | Closed | Keep the semi-autonomous stance, CAI's own paper judges full autonomy premature | done |
| Localization-then-reasoning prompt split | Read-first mandate + the ingest skill distill raw output, but lane prompts routinely carry raw tool output straight into reasoning context | No mandated two-step inside a lane's prompt | Amend the delegate lane contract: step 1 write raw output verbatim to a file, step 2 produce a localized-fact block (host, port, observation, evidence line) that the lane's reasoning must cite (PentestGPT's parsing/reasoning split) | S |
| Benchmark self-scoring | Landed 2026-09-09: `scripts/bench.py` + `bench-labs.json` (starter = 10 PortSwigger labs), score_engagement 0/1/2 per expected class, wired into `eval_metrics.py` (an engagement named after a scenario id auto-scores into the eval.md auto block at close-out) | Closed for the starter set | Extend bench-labs.json as labs are run; cadence = one lab a week through the full driver | done |
| Attack-memory | Memory is the markdown state set (state/loot/Deadends/Killchain), session/hot.md, and the wiki; cross-engagement recall via qmd search and `Skill(learn)` distillation | Entries are untyped prose; there is no observation/conclusion distinction, so conclusions and raw reads carry the same weight | Type hot.md entries as observation vs conclusion (PentAGI's Memory entities) and have `Skill(learn)` harvest conclusions first; PyRIT-style multi-turn conversational memory was not evidenced in the fetched sources [uncertain]; PentestGPT's PTT + session resume is the closest evidenced shape | S |
| Failure-triggered reflection | Landed 2026-10-04: mentor counters (same-tool >= 5, reset-on-fire, PostToolUse additionalContext) + identical-retry steer at 2/3 in drift-guard | Closed | none | done |
| Identical-call replay steer | Landed 2026-10-04: drift-guard steer advisory one fire below the loop-break deny | Closed | none | done |
| LLM-call observability and cost | eval.md metrics at close-out; hooks log tool calls to session/log.md | No per-lane token/cost attribution mid-engagement; cost surprises surface only at close-out | Require each lane's return line to carry model tier + token count; roll into eval.md Metrics; CAI's blackboard result (routing scaffolds through one telemetry-owning proxy, 19/33 vs 15/33 on Cybench) says the payoff is real | S |
| Three-state closure + outcome enum (strix) | Deadends.md + stop conditions; Approach 4a rows are binary checked/gap | A deadend needs no named control; no needs_follow_up outcome, so "unsure" silently reads as clean | Deadends row template gains the named-control sentence (`safe because <control> at <location> ...`); 4a rows gain a needs_follow_up outcome; find-lint flags a deadend without a control sentence | S |
| Counterevidence/confidence/severity_change_conditions as validated fields (strix) | find-lint verification ladder + placeholder gate; card template carries CVSS/status/severity | No mandatory strongest-case-against field; confidence is implicit in status only | Extend `setup/templates/_find.md` with counterevidence + confidence + severity_change_conditions; find-lint requires all three on CONFIRMED cards | S |
| Close-out census + chaining gate (strix) | close-out.py drift-count + flag accounting; escalate-and-chain is a memory rule, not a gate | No equipped-but-unrecorded census; chaining is not checked at close | close-out.py emits an open-class census (4a rows for classes the engagement actually carried, unresolved rows listed) plus one chaining-gate advisory line | S |
| Security-exhaustive compaction checkpoint (strix) | pre-compact.sh steer-only via stdout | Compaction summary shape is left entirely to the model; findings can be merged/paraphrased away | Bake a fixed section list (findings verbatim, creds, dead ends, work state, next move) plus "be EXHAUSTIVE not concise, copy values verbatim" into pre-compact.sh steering | S |
| Hunt-skill fixed skeleton (strix) | hunt skills share a loose shape: "Use when" line + doctrine body | Validation evidence bar and False Positives are not mandatory sections, so negative doctrine is uneven across the 27 skills | Adopt the 13-section skeleton (trimmed to what fits) in docs/conventions; retrofit hunt skills in one batch; a style/lint check enforces Validation + False Positives presence | M |
| "Load X when" cross-skill routing (strix) | triggers.json + playbook.json route the FIRST skill from the prompt/fingerprint | No in-doctrine handoff to the NEXT skill mid-test | One "Load X when" line per hunt skill pointing at siblings, negative routing included (do not load this for pure X) | S |
| Scan-mode overlays (strix) | autonomy L0-L3 covers scope, not depth; depth is improvised per engagement | quick/standard/deep choices are implicit and inconsistent | One scan-mode doctrine block (skip list, priority order, evidence bar stays invariant across modes) selectable in the engage prompt | S |
| Fleet budget bands + reserve (strix) | ZT_MAX_ENG_USD advisory + status.py spend render | Overspend surfaces at close-out; no graduated warnings; no close-out reserve concept | status.py adds band advisories at 70/85/95 percent of the engagement cap and a reserve line at 90 (brain stops spawning, starts closing) | S |
| Proxy error-page tell (strix) | tells battery (82 rows) | No Caido/proxy error-page signature row | tells.json row: proxy-title boilerplate HTML under 502/500 means proxy page, never target behavior | S |
| Safe fences for PoC content (strix) | angle-bracket rule; PoC code in fenced blocks | A PoC script containing its own triple-backtick run breaks the card render | Card/PoC rule: open the fence one backtick longer than the longest backtick run inside the content | S |

## Host-harness internals (Claude Code leak, 2026-09-09)

A second source family: the host harness ZTorch runs on (claimed leaked Claude Code source,
github.com/tanbiralam/claude-code; analyzed for architecture patterns only, no code copied).
These are VERIFIED internals, not [uncertain]; each maps to a landed ZTorch change.

- **Hook channels**: PreCompact stdout is steer-only (appended to the summarizer prompt as
  additional instructions; its JSON context is ignored); SessionStart with source `compact` is
  the only verbatim re-injection channel. ZTorch: pre-compact.sh is plain-stdout steering;
  engagement-init re-injects the open board rows + last driver move on compact.
- **Compaction discipline**: rehydration order is fixed (summary -> kept tail -> attachments ->
  SessionStart hooks); invoked SKILL.md files re-attach head-truncated at ~5k tokens. ZTorch:
  load-bearing skill rules live in the first 5k tokens (skill-map authoring rule); durable
  state lives in files the hooks re-inject (last_move in .offensive.json, lane-in-flight lines
  in log.md).
- **Guard matching**: deny rules strip env prefixes and wrappers to a fixed point and match
  EVERY command segment; parser differentials (CR, unicode whitespace, backslash escapes,
  mid-word `#`, brace expansion) are rejected outright. ZTorch: `_cmdnorm.py` shared
  normalization + per-segment matching in scope/sleep/drift guards.
- **Lane fleets**: frozen shared contract body with only the trailing lane directive differing
  (prompt-cache hit across concurrent children); fixed return envelope; few long lanes over
  many short forks. ZTorch: brain fleet rules + the delegate Scope/Result/Key files/Issues
  envelope.
- **MCP protocol**: transports fixed per config (no fallback chain), 30s connect / 60s request
  timeouts, 3-terminal-error reconnect, ~2k description budgets, big outputs persisted to file
  with chunked-read instructions, `[OUTPUT TRUNCATED]` means re-query never summarize.
  ZTorch: skills-setup.md MCP protocol rules (the discipline our own bridges follow).
- **Retry + cache**: 500ms-doubling backoff to 32s with jitter, Retry-After overrides;
  system prompt / tool list / model / beta headers are cache invalidators (a mid-session
  skill-description edit busts a 20-70k-token prefix). ZTorch: batch live-skill edits
  between sessions; our MCP bridges return 429 + Retry-After and stay idempotent.
- **Conditional skills**: a `paths:` frontmatter parks a skill outside the command list until
  a matching file is touched -- wrong shape for prompt-routed skills (ZTorch documented it as
  deliberately unused rather than adopting it).

## Do not adopt

- **Self-hosted LLM provider infrastructure.** PentAGI's 10+ provider matrix, per-agent model YAML
  and vLLM multi-GPU guide exist because it owns its inference; ZTorch is a prompt layer over a
  hosted harness, so owning inference is pure ops cost.
- **Porting orchestration into a standalone codebase.** PentAGI (Go backend, GraphQL) and CAI
  (Python framework on openai-agents) exist as code because their users do not run inside an agent
  harness; Claude Code already provides subagents, hooks and session state, so a Go/Python
  orchestrator duplicates the platform.
- **Knowledge-graph memory services.** PentAGI's Graphiti/Neo4j store has value at its scale of
  12+ concurrent flows; ZTorch's markdown state files plus qmd recall already answer the same
  questions, and a graph database adds infrastructure with no second consumer.
- **Full-automation as the goal.** CAI's own paper calls fully autonomous operation premature and
  credits HITL for its best results; ZTorch's Burp-first operator loop is the product, not a
  limitation to engineer away.
- **Strix's runtime mechanics: stop-vs-pause budget parking, the atomic agents.json + SQLite
  resume stack, per-response tool-call flood limiting, agent mailboxes, SARIF cross-run
  fingerprints.** All of these exist because strix owns its agent runtime end to end; Claude Code
  already owns termination, resume, and tool dispatch for our lanes, so reimplementing them in
  scripts is the porting-orchestration-into-a-standalone-codebase trap already listed above. We
  take the DOCTRINE those mechanics encode (budget bands, one terminal notice per lane,
  security-exhaustive compaction) and leave the machinery.
- **Strix's 500-turn force-stop default.** Our lanes are bounded by the checklist + envelope
  contract and the drift-guard, not by turn caps; a turn cap on a reasoning harness mostly
  converts "unfinished" into "truncated mid-chain".

## Sources

- [PentAGI](https://github.com/vxcontrol/pentagi): architecture, agent classes and call caps,
  sandbox model, memory and observability from the repository README.
- [CAI paper](https://arxiv.org/html/2504.06017v2) (arXiv:2504.06017): autonomy table, pillars,
  benchmark harness and results.
- [CAI repository](https://github.com/aliasrobotics/CAI): CAIBench, Retester agent, MCP and
  tracing notes.
- [PentestGPT](https://github.com/greydgl/pentestgpt): agentic-upgrade architecture, three-session
  split, PTT, staged pipelines and session persistence.
- [claude-code leak mirror](https://github.com/tanbiralam/claude-code): claimed leaked Claude Code
  source; host-harness internals section distilled from it for architecture patterns only, no code
  copied (proprietary Anthropic source).
- [Strix](https://github.com/usestrix/strix): orchestration/lifecycle, skills library, and
  findings/coverage doctrine sections distilled from a full read of the repo (3 lanes: core+runtime
  +llm, strix/skills 68 files, report+tools pipeline) on 2026-10-05. Operational usage lives in
  [[wiki/tools/strix]]; the portable closure/evidence doctrine in
  [[safe-probing-and-controls]]; fleet coordination doctrine in
  [[multi-agent-campaign-orchestration]].

Split-lane parallel-seat pattern: one lane's battery split across two seats writes into ONE ingest/laneNNN/ dir. Collision-avoidance contract: each seat prefixes its pairs (a*/b* vs c*/d*), the shared summary.txt is DEFERRED - each seat writes its own fragment (summary-a1a2.txt / cd-summary.txt) - and the bridge merges behind the a+b sections at pass end. Ledger self-append gap pattern: when a seat claims 'rows appended' but the envelope lacks paste text, Scribe verifies disk first and inserts rows marked DERIVED (facts quoted from the seat's own log row + card artifacts), never inventing verbatim text. Re-verify clause: any family 'unreachable' verdict needs a fresh 1-GET control before standing - walls shift between host+path classes (526-vs-200 on one zone).

<!-- promoted-slug: parallel-seat-split-lane-collision-avoidance -->

Response-only-capture evidence ruling -> FULL request+response pair mandate: a captured response body alone (200 43,603B shell, calcite x6) proves reachability but not request shape; every evidence capture must be a complete raw PAIR (headers + body, both directions) saved as `<id>-h.txt`/`<id>-b.txt` plus a `<id>-pair.txt` concat. Count corrections (calcite x13 -> x6 precedent) are applied artifact-first with a one-line log erratum; RETURN rows stay untouched (append-only audit). Count miscounts never change verdicts - record the erratum, keep the verdict.

<!-- promoted-slug: response-pair-capture-mandate -->
