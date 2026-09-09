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
| Per-lane report artifact | Lane output returns as chat text; durable artifacts (FIND files, poc/, ingest/) exist only after main-session triage | Lane work that never becomes a finding leaves nothing on disk | Require every lane to write a structured artifact (command, raw output path, verdict) into `targets/<eng>/ingest/` before returning; the ingest skill already consumes that directory (PentAGI's per-flow Artifacts, Reporter agent) | S |
| Autonomy-level vocabulary | Implicit bands exist: driver ranks, delegate executes, operator approves in Burp; scope.md RoE flags approximate limits | No named levels, so an engagement brief cannot state how autonomous a run may be | Adopt CAI's grading idea with 3-4 ZTorch bands (advice-only, execute-with-approval, autonomous-read-only, full) stamped into scope.md; keep the semi-autonomous stance, CAI's own paper judges full autonomy premature | S |
| Localization-then-reasoning prompt split | Read-first mandate + the ingest skill distill raw output, but lane prompts routinely carry raw tool output straight into reasoning context | No mandated two-step inside a lane's prompt | Amend the delegate lane contract: step 1 write raw output verbatim to a file, step 2 produce a localized-fact block (host, port, observation, evidence line) that the lane's reasoning must cite (PentestGPT's parsing/reasoning split) | S |
| Benchmark self-scoring | eval.md records tokens/time/drift per engagement; no fixed exercise set, no pass/fail score | Framework changes (skill edits, hook changes) are not regression-tested | Keep a small fixed public CTF set, run it after major framework changes, record solved/total plus cost in the scorecard; borrow CAI's capped-interaction pass@1 so runs terminate | M |
| Attack-memory | Memory is the markdown state set (state/loot/Deadends/Killchain), session/hot.md, and the wiki; cross-engagement recall via qmd search and `Skill(learn)` distillation | Entries are untyped prose; there is no observation/conclusion distinction, so conclusions and raw reads carry the same weight | Type hot.md entries as observation vs conclusion (PentAGI's Memory entities) and have `Skill(learn)` harvest conclusions first; PyRIT-style multi-turn conversational memory was not evidenced in the fetched sources [uncertain]; PentestGPT's PTT + session resume is the closest evidenced shape | S |
| Failure-triggered reflection | Drift-guard PreToolUse hook fires at >= 6 exploit-shaped calls with zero driver contact; stop-condition discipline is manual | Nothing injects reflection after repeated failures; a failing lane grinds until the drift-guard trips | Extend the PostToolUse hook to count consecutive failures per lane and inject a redteamlead nudge at 3 (PentAGI's Reflector), with a 5-identical-call monitor for loops (Mentor) | M |
| LLM-call observability and cost | eval.md metrics at close-out; hooks log tool calls to session/log.md | No per-lane token/cost attribution mid-engagement; cost surprises surface only at close-out | Require each lane's return line to carry model tier + token count; roll into eval.md Metrics; CAI's blackboard result (routing scaffolds through one telemetry-owning proxy, 19/33 vs 15/33 on Cybench) says the payoff is real | S |

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
