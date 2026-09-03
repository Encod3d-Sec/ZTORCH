---
title: "gitleaks"
type: tool
tags: [secrets, git, cicd, recon, osint]
date_created: 2026-09-03
date_updated: 2026-09-03
sources: []
phase: recon
---

## Purpose

**gitleaks** scans git history (and plain directories) for hardcoded secrets via a large built-in
regex/entropy ruleset -- a fast complement to [[trufflehog]] when you want a quick, dependency-free
pass over a cloned repo or CI checkout, especially in a pipeline where trufflehog's verification
step (live-checking each candidate against its provider API) is unnecessary or too slow.

## Install / setup

```bash
apt install gitleaks
```

## Core usage

```bash
gitleaks detect -s /path/to/repo -v                       # scan a local clone, verbose
gitleaks detect -s . --report-path findings.json           # scan cwd, write JSON
gitleaks detect --source . --log-opts="--all"               # scan every branch/ref, not just HEAD
```

## Common use cases

```bash
git clone --depth 1 https://github.com/org/repo && cd repo && gitleaks detect -v
gitleaks detect -s . --no-git                               # scan a directory that isn't a git repo
```

## Tips and gotchas

- `--depth 1` clones lose history -- gitleaks only sees the checked-out ref's diff-visible secrets,
  not the FULL history. Drop `--depth 1` (or `git fetch --unshallow`) when a shallow scan comes up
  empty; secrets are routinely committed then "removed" in a later commit while staying in history.
- No live verification (unlike [[trufflehog]]) -- every hit needs manual confirmation the credential
  is still valid before reporting.
- `.gitleaksignore` / inline rule config lets a target repo suppress known false positives; check
  for one before trusting a "clean" scan.

## Related techniques

[[trufflehog]], [[secret-hunting]]

## Sources

Vault-resident; gitleaks project docs.
