---
title: "Port spec: hermes sandboxing, toolsets, budgets"
type: docs
tags: [docs, port-spec, hermes, sandbox]
date_created: "2026-10-12"
sources: [raw/git/hermes-agent]
---

# Sandbox/tooling port spec (from hermes-agent source audit)

## Hermes policy (evidence in raw/git/hermes-agent)

Docker baseline (tools/environments/docker.py): --cap-drop ALL + only DAC_OVERRIDE/CHOWN/FOWNER back; no-new-privileges; tmpfs /tmp rw,nosuid,512m + /var/tmp + /run noexec; --pids-limit 2048; cpus/memory cgroup-probed; --shm-size 1g; --init; credentials/skills/cache mounted :ro; host cwd NOT mounted by default; network default ON, --network=none when off, contradiction with extra-args fails CLOSED; secrets reach container via subprocess env, never /proc cmdline. Config defaults in hermes_cli/config_defaults.py:351-388.

Toolsets (toolsets.py + model_tools.py): one TOOLSETS dict {description, tools, includes}, recursive resolve with cycle detection; safe preset = web+vision (no terminal); enforcement = enabled-union resolved then DISABLED SUBTRACTED LAST at schema-build AND re-checked at call dispatch (a named call can never reach a tool outside the resolved set); delegation children get narrowed toolsets, leaf role drops delegate/clarify/memory/send_message/cronjob.

File write guards (tools/file_tools_write_guards.py): hard deny /etc /boot /usr/lib/systemd /private/etc /var/run/docker.sock + the profile config.yaml; protected instruction files (agents.md, claude.md, soul.md, .cursorrules, .hermes/*) = ALWAYS human-approval, never persisted, NOT bypassed by yolo, fail-closed headless; ssh config write gated; binary-corrupt and stale-overwrite refuses.

Credential scrubbing (tools/environments/local_env_policy.py): static blocklist = every inference key (OPENAI/ANTHROPIC/GOOGLE/XAI/GROQ/TOGETHER/PERPLEXITY/COHERE/DEEPSEEK/MISTRAL/OPENROUTER/NOUS/QWEN), messaging tokens, GH_TOKEN, MODAL/DAYTONA/VERCEL, dashboard secrets; tier-1 always-strip even under inherit_credentials; dynamic shapes AUXILIARY_*_API_KEY etc.; venv markers; applied in EVERY terminal/execute_code/delegation/MCP child; env_passthrough can never re-allow a blocklisted name.

Budgets: --usage-file report (cost, tokens by class, api_calls, session_id, completed/partial/interrupted, turn_exit_reason) written even on failure; no hard dollar cap; runaway containment structural: IterationBudget (default 500), delegation caps (child max_iterations 250, max_concurrent_children 10, max_spawn_depth 1, oneshot_max_children 2 with "do it inline" error), tool-result size budgets (100K/result, 200K/turn, 50K MCP).

Terminal command safety (tools/approval_detection.py + approval.py): HARDLINE tier never bypassable (rm -rf / + system dirs, mkfs, dd-to-device, fork bomb, kill -1, shutdown, sudo -S probing, parser fail-closed); ~90 DANGEROUS approval-gated patterns (recursive deletes, chmod 777, SQL DROP/DELETE-no-WHERE, curl|sh + all decode variants, cloud metadata IPs, credential-file uploads, invisible unicode, tee/sed -i onto system files, git reset --hard/force-push, ssh/rc/.env/config.yaml targets); detection normalizes ANSI/NFKC/$IFS/backslash-continuations and deobfuscates r\m, $(echo rm) shapes; gate order: container-fast-path -> floor (hardline+deny-rules) -> yolo -> allowlist -> unattended -> pattern -> human prompt (fail-closed headless).

## Native ZTORCH port (design)

scripts/lane-run.sh: docker-wrapped lane execution. docker run --rm with hermes baseline flags (cap-drop ALL + 3 caps back, no-new-privileges, pids-limit 512, cpus/memory caps, shm 1g, the three tmpfs mounts); mounts: vault wiki/ read-only at /ztorch/wiki, engagement cwd rw at /eng (-w /eng), per-lane extra mounts from manifest; default network NONE (a lane needing egress sets network: true in manifest + carries the scope note; scope-guard stays the one hard deny); secrets never -e passed, only lane-explicit vars; output teed to ingest/lane-<ts>.out. SSH-to-Kali lanes stay on the VM seat (docker adds nothing there).

Lane manifest (targets/<eng>/lanes/<lane>.json): {"image", "network": false, "mounts": [], "tools": [...], "writes": ["/eng/**"], "budget": {"max_iters": 250, "child_max": 2}}. tools = the lane allowlist (dispatch-side check, subtraction-last semantics), writes bounds file paths, budget caps iterations + child spawns (dispatch rejects beyond child_max with a do-it-inline error).

Hook translations: hardline tier -> PreToolUse DENY (root wipe, mkfs/dd-device, fork bomb, kill -1, shutdown, cloud-metadata fetch); dangerous tier -> advisory with pattern name (pre-approvable via lane marker, same shape as .roe-ok); sensitive-path + instruction-file writes -> deny class; iteration caps -> lane dispatcher.

