---
title: "Agentic Harness Patterns"
type: technique
tags: [methodology, agents, orchestration, reference-import, automation]
phase: exploitation
date_created: 2026-09-09
date_updated: 2026-09-09
sources: ["https://github.com/vxcontrol/pentagi", "https://arxiv.org/html/2504.06017v2", "https://github.com/aliasrobotics/CAI", "https://github.com/greydgl/pentestgpt"]
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
- **Self-regulation loops**: an Adviser in Mentor mode fires when identical tool calls exceed a
  threshold (5); a Reflector auto-invokes after 3 consecutive failed tool calls and steers the
  agent toward `done`/`ask` barrier tools; an optional Planner emits a 3 to 7 step execution plan.
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
| Failure-triggered reflection | Partially landed: drift-guard escalates to DENY at streak >= 6 (per-segment matching, command-position driver reset); `stallcheck.py` injects starvation/stop-cracking verdicts from the cmdlog battery after curl/hashcat runs | Per-lane consecutive-failure counting (PentAGI's Reflector at 3) still open | Extend the PostToolUse hook to count consecutive failures per lane and inject a redteamlead nudge at 3 | S |
| LLM-call observability and cost | eval.md metrics at close-out; hooks log tool calls to session/log.md | No per-lane token/cost attribution mid-engagement; cost surprises surface only at close-out | Require each lane's return line to carry model tier + token count; roll into eval.md Metrics; CAI's blackboard result (routing scaffolds through one telemetry-owning proxy, 19/33 vs 15/33 on Cybench) says the payoff is real | S |

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
