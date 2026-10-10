# Skills & MCP Setup

Operational reference for managing plugins, MCP servers, and hooks in this vault.
Add new entries here whenever a plugin is added, removed, or breaks.

---

## Active MCP Servers

### wiki-search (qmd)

Semantic and keyword search across `wiki/`. Required for all vault search operations.

```json
"wiki-search": {
  "type": "stdio",
  "command": "qmd",
  "args": ["mcp"],
  "env": { "QMD_VAULT": "/mnt/c/Users/{user}/Documents/ObsidianVaults/ZTorch" }
}
```

Replace `{user}` with your Windows username (the WSL path is
`/mnt/c/Users/<you>/Documents/ObsidianVaults/ZTorch`). If you keep a
per-machine table, it lives in the git-ignored `AGENTS.local.md`.

Config location: `~/.zcode/cli/config.json` -> `mcp.servers` (user scope; `setup/bootstrap.sh`
writes it for you). Workspace config lives at `<vault>/.zcode/config.json` (committed, hooks only).
Manage/inspect via Settings -> MCP in ZCode.
Rebuild index: `qmd update && qmd embed` (run from vault root after bulk wiki changes; embed refreshes semantic vectors)

### wigolo (local web intelligence)

Keyless local-first search/fetch/crawl/cache MCP (Node >= 20; engine + on-device models
under `~/.wigolo/`, ~1.5 GB via `npx wigolo init`). Replaces metered WebSearch round-trips
for OSINT/vuln research and keeps every fetched page in a queryable local cache. Full tool
table + gotchas: `wiki/tools/wigolo.md`.

```json
"wigolo": { "command": "npx", "args": ["-y", "wigolo"] }
```

Registered in `~/.claude.json` top-level `mcpServers` (user scope, all projects). If the
browser component reports missing: `npx playwright install-deps chromium`.

### obsidian-vault (removed)

Previously used `mcp-obsidian` (Obsidian Local REST API). Removed because:
- Requires Obsidian app to be running on Windows - breaks if closed
- Not needed: ZCode's `Read` tool accesses vault files directly via WSL path

**Replacement:** `Read /mnt/c/Users/{user}/Documents/ObisidianVaults/ZTorch/<relative-path>` (see machine usernames above)

### MCP protocol rules (distilled from host client internals, 2026-09-09)

Transport wiring:
- A URL-based server needs its transport set EXPLICITLY (`http` for streamable-HTTP,
  `sse` for legacy SSE) - there is no runtime fallback chain between them; a mis-set
  transport just fails. stdio is the default when `type` is omitted.
- Timeouts to expect: ~30s connect, 60s per HTTP request (long-lived GET event streams
  are exempt), tool calls effectively unbounded. 3 consecutive terminal errors
  (ECONNRESET/ETIMEDOUT/EPIPE/REFUSED...) close the transport and force a reconnect on
  the next call; an HTTP session-expiry retries ONCE with a fresh session; a connect-time
  401 parks the server in needs-auth (~15 min) instead of probing.
- Budgets: server `instructions` and each tool description truncate at ~2k chars - keep
  our own MCP-facing descriptions short; endpoint docs belong in a file, not a
  description.

Big-output discipline (the protocol our own MCP-adjacent scripts must follow too):
- Oversized tool results (~25k tokens) are persisted to a file with instructions
  (path, size, shape) - read them SEQUENTIALLY in chunks (offset/limit), grep/jq to
  locate, and STATE what portion you read before summarizing. Never summarize a blob
  you have not verifiably read.
- An `[OUTPUT TRUNCATED ...]` notice means re-query with the server's filter/pagination
  parameters (or a tighter query) - never summarize from the truncated dump.
- Binary/base64 payloads come back as a one-line "saved to <path>" pointer; follow the
  path, do not re-request raw.
- Our equivalents: big recon/tool dumps go to `targets/<eng>/raw/` or the ingest dir
  (`scripts/capture.sh`), never pasted into context; `zg --limit N` keeps result pages
  bounded.

Client retry ladder (what the host does to OUR MCP servers when they misbehave):
- Retryable: 408/409/429/529/5xx + connection errors; backoff 500ms doubling to a 32s cap
  with 0-25% jitter, ~10 attempts total; a server-sent `Retry-After` overrides the backoff
  schedule; a context-overflow 400 is retried once with a recomputed max_tokens.
- Server-side implication for zg/qmd/Burp bridges: on overload return 429 WITH a
  `Retry-After` (the client honors it instead of hammering), keep tool calls idempotent
  (a retry re-sends the same arguments), and prefer one terminal error over repeated
  flappy 5xx (3 consecutive terminal errors make the client close the transport).
- Prompt-cache discipline (authoring side): the system prompt (AGENTS.md), the skill/tool
  list, model, and beta headers are cache invalidators -- editing a live skill's
  description or AGENTS.md mid-engagement busts a ~20-70k-token prefix for a one-line
  change. Batch such edits between sessions, not during one.

Caller-side cooldown + quarantine (our discipline when a foreign MCP server misbehaves):
- Dispatch order: a failing server gets at most 4 tools tried before the fallback path
  (deterministic CLI / direct API) takes over for the rest of the task; do not walk the
  whole tool list against a dead server.
- 3 consecutive dead calls (timeout/reset/refused) = quarantine that server for the
  session: stop calling it, note the quarantine in `session/hot.md` (one line), route
  around it. Re-probe at most once per cooldown window.
- Cooldown is exponential per server: 1 min, 2, 4 ... capped at 15 min, with jitter;
  a successful call resets it.
- Auth/permission errors (401/403, needs-auth, scope refusal) are NEVER retried in-task:
  they need an operator action (login, key, consent), so surface the ask and switch
  lanes. Retrying burns the same failure.
- Cap concurrent calls to any one MCP server at 4; queue the rest. A fan-out against a
  local bridge (zg/qmd) just multiplies the timeout.

---

## Third-party skill intake (hard rule)

Before registering ANY third-party skill (plugin cache, marketplace, git clone) into
`skills/` or linking it from `~/.claude/skills`, scan it first:

```bash
skillspector scan <skill-dir> --no-llm        # vet before trusting
bash scripts/skill-scan.sh --root <parent-dir>   # whole third-party tree at once
```

HIGH/CRITICAL (injection, exfil, unpinned fetch) = do not register; read the flagged
lines yourself before overriding. First-party vault skills are swept against the
baseline by `bash scripts/skill-scan.sh` (incremental; `offensive-doctor` runs it as an
advisory check). Details: `wiki/tools/skillspector.md`.

---

## Third-party skill intake (hard rule)

Before registering ANY third-party skill (plugin cache, marketplace, git clone) into
`skills/` or linking it from `~/.claude/skills`, scan it first:

```bash
skillspector scan <skill-dir> --no-llm        # vet before trusting
bash scripts/skill-scan.sh --root <parent-dir>   # whole third-party tree at once
```

HIGH/CRITICAL (injection, exfil, unpinned fetch) = do not register; read the flagged
lines yourself before overriding. First-party vault skills are swept against the
baseline by `bash scripts/skill-scan.sh` (incremental; `offensive-doctor` runs it as an
advisory check). Details: `wiki/tools/skillspector.md`.

---

## Plugin Troubleshooting

### context7 - stale lock files crash the plugin

**Symptom:** context7 fails to start or crashes sessions on startup.

**Cause:** context7 is an external plugin (`npx -y @upstash/context7-mcp`) with no version
in its manifest, so all sessions share one `unknown/` cache directory. When a session exits
uncleanly (WSL restart, force-kill), its PID lock file is never removed. On next startup
ZCode sees orphaned locks and fails to connect.

**Manual fix:**
```bash
rm -f ~/.zcode/cli/plugins/cache/*/context7/unknown/.in_use/*
```
Safe to run any time ZCode is not actively running.

**Automatic fix:** SessionStart hook (see below).

---

## Hooks

### Hook JSON output contract (verified against host client internals, 2026-09-10)

When multiple hooks run on one event, or a hook mixes JSON with legacy fields:

- **Precedence across hooks: `deny` > `ask` > `allow`.** One denying hook blocks the call
  even if every other hook allows it.
- **JSON beats legacy fields.** A hook printing a JSON `hookSpecificOutput` object has its
  exit code and plain stdout ignored for decisions; write decisions in JSON only.
- **`permissionDecision: "deny"` blocks; `"ask"` is the third tier** (prompts the operator)
  between allow and deny. Our guards use deny (deterministic enforcement) and plain
  additionalContext (advisory); `ask` is available if a future guard needs a human call.
- **`additionalContext` is model-visible; `systemMessage` is operator-visible ONLY**
  (excluded from the API payload). Use systemMessage for operator alerts that would cost
  model context (recon-capture emits one on an OOB HIT correlation).
- **PostToolUse/Stop plain stdout is NEVER model-visible**; only `additionalContext` (or
  exit 2 + stderr, which surfaces as an error) reaches the model.
- Unused-but-available for future guards: `updatedInput` (rewrite tool input without
  denying), `async`/`asyncRewake` (deferred checks), `suppressOutput`, and `if`
  prefilters in config (skip a hook entirely on matcher).

### SessionStart - context7 lock cleanup

Stale context7 PID lock files can crash the plugin on startup. The registered
`session-start.sh` SessionStart hook links vault skills and loads `session/hot.md`;
the lock cleanup itself stays a manual/one-off snippet:
the registration ships in the committed `.zcode/config.json`, and
`bash setup/install-hooks.sh` verifies it, so no manual edit is needed.
The cleanup logic:

```bash
LOCK_DIR="$HOME/.zcode/cli/plugins/cache"   # glob every marketplace root
find "$LOCK_DIR" -maxdepth 4 -type d -name .in_use 2>/dev/null | while read -r d; do
  for f in "$d"/*; do
    [ -f "$f" ] || continue
    pid=$(python3 -c "import json; print(json.load(open('$f')).get('pid',''))" 2>/dev/null)
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null || rm -f "$f"
  done
done
```

---

## Disabled Plugins

| Plugin | Reason |
|--------|--------|
| obsidian-vault MCP | Requires Obsidian running; replaced by direct Read tool |
| context7 (was crashing) | Fixed via lock cleanup above; now re-enabled |

## Skill authoring (house rules)

- Baseline-first pressure testing: run the pressure scenario WITHOUT the skill and
  record the model's rationalizations verbatim (that is the RED); write the minimal
  counter (GREEN); close the loopholes the run exposed. A skill edit without a recorded
  baseline is a vibes edit.
- Recipe over prohibition: prohibitions for discipline slips (skipped steps), positive
  recipes for wrong-shaped output; prohibition wording measurably backfires on shape
  problems.
- Behavior, never text: tests assert a blocked call or a fired skill, not that a file
  contains a line.
- Invoke shell scripts as `bash scripts/...` (exec bits unreliable on the NTFS vault).
- Plans under `docs/superpowers/plans/` carry a `## Review Focus` block: up to five
  failure modes the design implies but no planned test exercises, one line each, each
  pinned by a test in the owning task.
- Two measured findings worth trusting: decision-only plans cost about 3x less than
  code-writing plans at equal outcomes; persuasion prose degrades unless its content
  lands at the point of use (rationalization-table rows, not essay paragraphs).
