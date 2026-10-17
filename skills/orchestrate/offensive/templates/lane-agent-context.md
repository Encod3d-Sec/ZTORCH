# Lane-agent context template (fresh-context wave dispatch)

Skeleton for the `context` field when dispatching a fresh-context lane subagent under the
wave pattern (offensive SKILL.md). Every block is load-bearing; order matters (scope before
capability). Fill EVERY `<...>` before dispatch - a lane that guesses scope probes blind.

---

SEAT: Windows git-bash, repo <REPO>. Engagement tree (seat): <ENG_DIR_SEAT>. Authorized
<bug-bounty|pentest> on <target>. READ <REPO>/targets/<ENG>/scope.md FIRST and obey it
exactly - <in-scope list>; everything else OUT (other subdomains, third parties, apex).

VM transport (one documented channel):
wsl.exe -d kali-linux -u root bash -c "cd <REPO> && bash scripts/vm-ssh.sh 'echo <b64-script> | base64 -d | bash'"
- lands as user tz; ship multi-line scripts base64-wrapped (raw $-constructs die in the
  WSL re-parse); target HTTP via /opt/scope-shim/bin/<tool> absolute paths (rc 126 =
  out-of-scope deny, never work around; ADVISORY on unknown host != approval).

ETHICS (per scope.md RoE): own/disposable accounts only; <no purchases | no real listings |
no real-user data>; bounded races/probes = <N>-request ceiling absolute; every mutation on
own harmless objects; teardown ALL sessions at the end (LogoutAllSessions or equivalent,
verify 401) and revert/delete every stored payload.

FRESH CONTEXT: you hold no prior findings - explore without exhaustion bias. Record every
request (ts, method, url, status, note) appended to <ENG_DIR>/_requests.md. Evidence: full
req/resp pairs to <ENG_DIR>/agent-reports/<lane>/<topic>/ (.md files, headers + bodies).

PRIOR ART TO READ FIRST (adjudication-safe pointers only): <paths to method docs the lane
NEEDS - login method, APQ recipe - never the Deadends/board record>.

---

Then `goal` = the lane's concrete numbered steps + per-step verdict vocabulary + the
output_schema. Rules that made waves work:

- ONE surface theme per lane (gateway behaviors / auth flows / money logic); disjoint lanes
  run concurrently, cap at 5 agents.
- Give each lane a bounded call ceiling it can self-enforce; state it in BOTH goal and schema
  (a `calls_made` field makes the ceiling machine-checkable).
- Demand a one-line verdict per probed surface (clean | anomaly-detail) - free-text summaries
  bury signals.
- Require teardown verification as a schema field (teardown_verified) - sessions that
  outlive their lane are the recurring hygiene leak.
- The main session adjudicates every returned anomaly against Deadends BEFORE boarding it;
  fresh-context agents rediscover known-dead surface constantly, and that is the point - but
  only the adjudicator says so.
