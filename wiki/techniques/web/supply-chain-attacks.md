---
title: "Supply Chain & Dependency Confusion"
type: technique
tags: [cloud, dependency-confusion, supply-chain, cicd, exploitation, linux, windows]
phase: exploitation
date_created: 2026-05-13
date_updated: 2026-10-05
sources: [payloadsallthethings-dependencyconfusion, pillar-rules-file-backdoor, github-usestrix-strix]
---

# Supply Chain & Dependency Confusion

## What it is

Compromising software by attacking what it *depends on* or *how it is built*, rather than the app itself. The headline variant, **dependency confusion**, tricks a package manager into pulling a malicious public package in place of an intended internal one of the same name. Pairs with `cicd-attacks` and [[trivy]] (find vulnerable deps).

## How it works (dependency confusion)
Many resolvers, when configured with both a public registry and a private one, will pull whichever has the **higher version** - or fall back to public when the private name is not found. Register the internal name publicly at `v99.99.99` and the build grabs yours, running your `preinstall`/`postinstall` (npm), `setup.py` (pip), or build hook.

### Attack flow (npm)
1. **Recon:** find internal package names - leaked `package.json`/`requirements.txt`/`pom.xml` on public GitHub, `require()`/import in client JS bundles, SBOMs, error pages.
2. **Verify:** the name is unregistered on the public registry (`npmjs.com`, `pypi.org`) - if absent, it is claimable.
3. **Exploit:** publish that name publicly with a high version + an install script that beacons out (DNS/HTTP) and/or runs code.
4. **Execute:** the target's CI runs `npm install`/`pip install` and pulls + executes your package.

Ecosystem files to mine: npm `package.json`, pip `requirements.txt`, maven `pom.xml`, composer `composer.json`, gem `Gemfile`, Dockerfile base images.

## Other supply-chain vectors
- **Typosquatting / combosquatting:** `reqeusts`, `python-sqlite`, `electron-prebuilt` - names close to popular packages.
- **Starjacking:** claim a package and point its repo URL at a popular project to borrow trust.
- **Install-script abuse:** malicious `postinstall`/`setup.py`/Gradle task - code runs at install, not import.
- **Maintainer takeover:** expired domain on a maintainer email, leaked npm token, no 2FA -> push a trojaned version (event-stream, ua-parser-js, ctx).
- **Build/CI poisoning:** compromise the pipeline (GitHub Actions, `npm publish` token, codecov bash uploader) to inject into legit releases.
- **Lockfile / `--extra-index-url`:** pip's `extra-index-url` checks public too; a lockfile poisoned in a PR.
- **Backdoored upstream:** the xz/`liblzma` (CVE-2024-3094) social-engineered backdoor.

### Rules File Backdoor (AI coding-assistant config poisoning)
A newer supply-chain carrier: hide malicious instructions inside an AI coding assistant's rules file (Cursor `.cursor/rules`, GitHub Copilot instruction files) or a project README using invisible Unicode (zero-width joiners/spaces, bidirectional/bidi markers, Unicode Tags-block chars). The text is invisible to a human reviewer and to the GitHub PR diff, but the model reads it and silently emits backdoored code without disclosing the change. Once the poisoned file is committed it taints every future generation in that repo and survives forking, so a single popular rules pack or starter template weaponizes every downstream project that adopts it, the same trust-inheritance abuse as a trojaned dependency or starjacked package. Full mechanism, test/grep recipe, and defence in [[mcp-server-attacks]].

## Real-world
Alex Birsan's 2021 dependency confusion hit Apple, Microsoft, PayPal and dozens more (>$130k bounties). event-stream (2018, crypto-wallet theft), codecov (2021), SolarWinds/SUNBURST (2020), ua-parser-js (2021), and xz (2024) are the canonical supply-chain incidents.

## Methodology / tools
```bash
# scan a repo's manifests for confusable / claimable internal names
confused -l npm package.json          # also pip, mvn, composer, rubygems
depfuzzer -d https://target ...        # find confusion + takeoverable owner emails
# inventory + known-CVE deps:
trivy fs --scanners vuln,license .     # see [[trivy]]
```
- [visma-prodsec/confused](https://github.com/visma-prodsec/confused), [synacktiv/DepFuzzer](https://github.com/synacktiv/DepFuzzer).

## Detection and defence
Use **scoped/namespaced** packages (`@org/pkg`) and reserve your names publicly; pin versions + commit lockfiles with **integrity hashes**; configure the private registry to NOT fall back to public for owned scopes; verify publisher 2FA + signed provenance (npm provenance, Sigstore); SBOM + SCA ([[trivy]]/grype) and dependency review in CI; vendor critical deps.

## Known-CVE reporting: the reachability evidence ladder

A known CVE is the one exception to "every vulnerability claim needs a dynamic PoC": proof =
lockfile + scanner output + the published advisory. But the reported reachability of the
vulnerable code must follow an explicit evidence ladder, and the ladder is evidence, never a
verdict: it never changes severity (that stays the published `advisory_cvss` base score,
mandatory on every finding), and it never gates whether you report at all.

| Level | Meaning |
|---|---|
| `reachable_call_path` | A call graph proves an entry point reaches the vulnerable symbol. Govulncheck call-graph output ONLY; a symbol grep hit is never this level. |
| `vulnerable_symbol_used` | The vulnerable function/class is referenced in code (grep/import analysis), no full call path. |
| `imported` | The package is imported but the vulnerable symbol is not referenced. |
| `not_imported` | Manifest contains it, source never imports it. NOT safe: dynamic `import()`, reflection, and plugin loaders can still reach it. |
| `unknown` | Check not performed, with the reason recorded. An honest unknown beats an unverified claim. |

Rules that keep the ladder honest:

- **Per-CVE, not per-package.** Never copy one CVE's verdict onto sibling CVEs in the same
  package; only the import check is shared. If the symbol check was skipped for a CVE, the
  finding may still say `imported` but `reachability_evidence` must state the check was not
  performed (skipped search is not the same as an empty search).
- **Import names differ from registry names** (PyPI `PyYAML` imports as `yaml`); map before
  concluding `not_imported`.
- **Source-to-sink traces start at the sink and walk back** hop by hop to the entry point,
  recording `file:line` at each hop and what that hop enforces. A call that only forwards
  arguments to the dangerous call is a thin wrapper: go one level deeper. If no source reaches
  the sink, the level stays `vulnerable_symbol_used`.
- **Per-CVE per-manifest granularity.** The same CVE present in two manifests is two findings;
  one dependency report per CVE, no batching across CVEs.
- `manifest_path` is repo-relative; no absolute paths, no `..`.
- **Introduced-by attribution** walks the dependency graph backwards (DependsOn edges) to the
  direct dependency and the path to root; omit both fields when the vulnerable package IS the
  direct dependency. Graph fallback ladder when the primary tool fails: `npm ls` / `pnpm why` /
  `yarn why` / `pipdeptree --reverse -p <pkg>` / `go mod graph` / `mvn dependency:tree`. Every
  fallback terminates in omission, never invention.
- **Remediation is stated at the direct-dependency level** (the thing the target controls) and
  names the override mechanism: `npm overrides` / `yarn resolutions` / `pnpm.overrides` / Maven
  `dependencyManagement` / Gradle resolution strategy / `go mod edit`.
- **Zero vulns on a repo that clearly has dependencies is suspicious**, not clean. Check the
  scanner actually parsed the manifests.
- Trivy DB freshness is evidence: record `.VulnerabilityDB.UpdatedAt` from the scan JSON. A
  stale DB with partial results looks like a normal scan; only the recorded age reveals it.
  Offline fallback chain: `--offline-scan --list-all-pkgs` -> `--skip-db-update` -> `|| true`
  (with the degradation noted in the finding).
- CVE ids are verified via web lookup before reporting; GHSA ids are mapped to their CVE or not
  reported.
- Budget order: import check always; symbol matches batched; prioritize critical/high/KEV.

## Package-runner confusion (npx, bunx, pnpm dlx, yarn dlx)

The sibling of dependency confusion: instead of the resolver picking the wrong package, the
package RUNNER resolves an ambiguous token to the wrong executable. The bug class is
identity-of-resolution, not ownership: even a package you own can be the wrong resolution if
the workflow meant a different one.

Two branches, decide first:

1. **Fallback runners** (`npx`, `npm exec`, `bunx`) can silently fetch and run a remote package
   when a local executable is absent. A finding needs ALL five conjuncts:
   a target-controlled workflow invokes a bare/ambiguous token; the intended package name
   differs from the executable name; the token is NOT resolved by a real local binary,
   workspace binary, or global install; the runner therefore selects an unintended remote spec;
   and the workflow reaches it with security-relevant authority. Missing any conjunct: not a
   finding.
2. **Explicit-fetch runners** (`pnpm dlx`, `yarn dlx`, `deno run npm:`) always download; there
   is no fallback claim. The only finding there is package/publisher mismatch (the named
   package is not the one the workflow's author meant).

Resolution-order model for npx (record the npm version in the finding): ancestor `.bin` ->
global bin -> matching package name -> npx cache -> treat the token as a package spec -> fetch
manifest -> infer ONE executable -> install and run. The manifest fetch and the bin inference
are two separate failure points: a controlled package whose bin name does not match the token
still runs its inferred bin.

Per-runner semantics that change the verdict: `npx --package <pkg> <cmd>` binds the command to
an explicit package (kills the fallback claim); `npx --no` fetches without executing; `bunx
--no-install` refuses network; `yarn dlx` always temp-downloads; mutable tags (`latest`,
`^2`) are selectors, not pins.

Verification without executing: `npx --no --loglevel=http <candidate>` and read the HTTP log
with four caveats: a local executable may run immediately (check which one answered); the HTTP
request proves fallback, not execution; a cancellation line names the spec npm chose;
cache/global/workspaces/registry config change the result, so repeat in EVERY real context
(repo root, launch dir, CI checkout, agent bootstrap). Never test by running `npm ci` in the
target tree: it mutates the lockfile and executes lifecycle scripts, which is the exploit
primitive itself.

Registry-state taxonomy for the candidate name: intended/owned; unrelated same-name (exists,
different maintainer); 404 unregistered; 401/403 private (name may still exist privately);
429/5xx transient; placeholder/reserved (0.0.1-security style; inspect the packument for
maintainers, `_npmUser`, dist-tags before deciding). Negative-control pair through the TARGET's
`.npmrc`/scope/proxy path: `npm view <known-good>` plus `npm view <random-hex-12>`; if the pair
fails, the state is UNKNOWN. A 404 proves absence, not registrability. Ownership is `npm owner
ls` plus version publisher; repo/homepage links are self-asserted and ambiguous means UNKNOWN.

Name normalization is bidirectional: `.`, `-`, `_` are stripped when matching; looking up only
the stripped form catches `some-tool` vs `sometool` but misses the reverse direction. The
scoped-package/unscoped-bin pattern (`@org/tooling` exposing bin `org-tool`) is the classic
mismatch shape: a workflow invoking `org-tool` resolves the public unscoped `org-tool` unless
the workspace provides it.

Report shape: a five-link resolver statement (token -> resolution -> context -> authority ->
outcome), because a 404 alone is candidate evidence, not a PoC. There is no CVE, so this
reports as a vulnerability finding, not a dependency finding. False-positive shapes to
explicitly rule out: explicit `--package` binding; fetch-without-exec probes misread as
execution; registry errors read as takeoverable names; `dlx` runners treated as fallback;
locally-resolved binaries; pin-pinned versions; CI offline mode; maintainer-owned same-name
packages; test-only workflows; tokens that match the package name exactly.

## Namespace-risk inventory (source-aware SAST)

When auditing a repo for namespace confusion beyond manifests, inventory the lookup-order
fallbacks: local/PATH resolution that falls back to a public registry; writable plugin,
template, or autoload directories on the load path; and missing local artifacts that activate
a remote fallback. Each row is reportable ONLY when the target actually resolves the
attacker-contestable name in its real invocation context; a hypothetical fallback is a note,
not a finding. SCA tooling is structurally blind to this class: it checks versions and CVEs,
not which name a runner resolves at call time.

## Sources
- PayloadsAllTheThings - Dependency Confusion

## Wired sub-techniques

<!-- auto-wired: context-reachable sub-technique pages -->
- [[package-managers-and-build-files]]
