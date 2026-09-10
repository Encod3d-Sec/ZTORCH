---
title: "Static Code Analysis"
type: technique
tags: [binary, git-poc, sast]
phase: recon
date_created: 2026-05-08
date_updated: 2026-09-10
sources: [git-raptor, InternalAllTheThings]
---

# Static Code Analysis

## What it is

Static code analysis finds vulnerabilities by examining source code (or bytecode) without executing it. It complements fuzzing and manual review — it scales to large codebases and finds injection paths, dataflow issues, and logic bugs that dynamic testing may miss.

## Two Primary Tools

| | [[semgrep|Semgrep]] | [[codeql|CodeQL]] |
|--|------------|-----------|
| Approach | Pattern-matching (AST-aware) | Full dataflow + semantic |
| Speed | Very fast (seconds) | Slower (minutes to hours) |
| False positive rate | Higher (context-unaware) | Lower (dataflow validated) |
| Languages | 30+ | Java, Python, JS, C/C++, Go, Ruby, C#, Swift |
| Offline | Yes (cache registry packs) | Requires DB build |
| Best for | Quick scan; custom pattern hunting | Deep source-to-sink analysis |

---

## Semgrep

### Installation & scan
```bash
pip install semgrep

# Scan with auto-detected rules
semgrep --config=auto ./src

# Target-specific packs
semgrep --config=p/ci ./src
semgrep --config=p/owasp-top-ten ./src
semgrep --config=p/python ./src

# Custom rule file
semgrep --config=my_rules.yaml ./src

# Offline (cache packs locally first)
semgrep --config=p/python --save-test-output-tar=cache.tgz
semgrep --config=cache.tgz ./src
```

### Custom rule structure
```yaml
rules:
  - id: sql-injection-f-string
    patterns:
      - pattern: |
          cursor.execute(f"... {$INPUT} ...")
      - pattern-not: |
          cursor.execute($QUERY, ($INPUT,))
    message: "Possible SQL injection via f-string"
    languages: [python]
    severity: ERROR
    metadata:
      cwe: CWE-89
```

### Taint mode (dataflow-lite)
```yaml
rules:
  - id: taint-request-to-shell
    mode: taint
    pattern-sources:
      - pattern: request.args.get(...)
      - pattern: request.form.get(...)
    pattern-sinks:
      - pattern: os.system(...)
      - pattern: subprocess.run(..., shell=True)
    message: "User input reaches shell execution"
    languages: [python]
    severity: ERROR
```

### Install and rule registries

**Install**:

* Binaries: [opengrep/opengrep](https://github.com/opengrep/opengrep) / [semgrep/semgrep](https://github.com/semgrep/semgrep)
* macOS: `brew install semgrep`
* Docker

```ps1
docker run -it -v "${PWD}:/src" semgrep/semgrep semgrep login
docker run -e SEMGREP_APP_TOKEN=<TOKEN> --rm -v "${PWD}:/src" semgrep/semgrep semgrep ci
```

**Semgrep rules**:

* [semgrep/semgrep-rules](https://github.com/semgrep/semgrep-rules) - Official Semgrep rules registry
* [trailofbits/semgrep-rules](https://github.com/trailofbits/semgrep-rules) - Semgrep queries developed by Trail of Bits
* [Decurity/semgrep-smart-contracts)](https://github.com/Decurity/semgrep-smart-contracts) - Semgrep rules for smart contracts based on DeFi exploits
* [0xdea/semgrep-rules](https://github.com/0xdea/semgrep-rules) - A collection of Semgrep rules to facilitate vulnerability research.
* [elttam/semgrep-rules](https://github.com/elttam/semgrep-rules) - Elttam's public semgrep rules repository.

**Other Tools**:

* [Orange-Cyberdefense/grepmarx](https://github.com/Orange-Cyberdefense/grepmarx) - A source code static analysis platform for AppSec enthusiasts, based on semgrep engine.

---

## CodeQL

### Database build
```bash
# Auto-detect language and build system
codeql database create ./codeql-db --language=python --source-root=./src

# Explicit build command (for compiled languages)
codeql database create ./codeql-db --language=cpp \
  --command="make -j4" --source-root=./src

# Multiple languages
codeql database create ./codeql-db --language=java,kotlin \
  --build-mode=autobuild --source-root=./src
```

### Run queries
```bash
# Run built-in query pack
codeql database analyze ./codeql-db \
  codeql/python-queries:Security/CWE-089 \
  --format=sarif-latest --output=results.sarif

# Run all security queries
codeql database analyze ./codeql-db \
  codeql/python-queries \
  --format=sarif-latest --output=results.sarif

# Custom query file
codeql database analyze ./codeql-db my_query.ql \
  --format=sarif-latest --output=results.sarif

# View results
cat results.sarif | python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d['runs'][0]['results']:
    loc = r['locations'][0]['physicalLocation']
    print(loc['artifactLocation']['uri'], ':', loc['region']['startLine'], '-', r['message']['text'][:80])
"
```

### CodeQL query (source-to-sink dataflow)
```ql
import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking

class SqlInjectionConfig extends TaintTracking::Configuration {
  SqlInjectionConfig() { this = "SqlInjection" }

  override predicate isSource(DataFlow::Node source) {
    source.asExpr() instanceof Call and
    source.asExpr().(Call).getFunc().toString() = "get"
    // request.get(), request.args.get() etc.
  }

  override predicate isSink(DataFlow::Node sink) {
    exists(Call c |
      c.getFunc().toString() = "execute" and
      sink.asExpr() = c.getArg(0)
    )
  }
}

from SqlInjectionConfig config, DataFlow::PathNode source, DataFlow::PathNode sink
where config.hasFlowPath(source, sink)
select sink.getNode(), source, sink, "SQL injection from $@", source.getNode(), "user input"
```

### Configuration

```ps1
codeql resolve packs
codeql resolve languages
codeql database analyze /codeql-dbs/example-repo javascript-code-scanning.qls --sarif-category=javascript-typescript  --format=sarif-latest --output=/temp/example-repo-js.sarif
codeql database analyze <database> microsoft/coding-standards@1.0.0 github/security-queries --format=sarifv2.1.0 --output=query-results.sarif --download
```

---

## AI Analysis

* [trailofbits/skills](https://github.com/trailofbits/skills) - Trail of Bits Claude Code skills for security research, vulnerability detection, and audit workflows.

```ps1
npm install -g @github/copilot
copilot
/login
/model
/plugin marketplace add trailofbits/skills
/plugin marketplace browse trailofbits
/plugin install ask-questions-if-underspecified@trailofbits
/plugin install static-analysis@trailofbits
/plugin install entry-point-analyzer@trailofbits
/plugin install semgrep-rule-creator@trailofbits
/plugin install semgrep-rule-variant-creator@trailofbits
/plugin install sharp-edges@trailofbits
/plugin install insecure-defaults@trailofbits
```

## SonarQube

> Continuous Inspection

**Install**

* Docker

```ps1
docker run -d --name sonarqube -p 9000:9000 sonarqube:community
```

**Configuration**

* Go to localhost:9000
* Login with `admin:admin`
* Create a local project
* Generate a token for the project
* Use `sonar-scanner-cli` with the generated token

```ps1
docker run --rm -e SONAR_HOST_URL="http://10.10.10.10:9000" -v "/tmp/www:/usr/src" sonarsource/sonar-scanner-cli -Dsonar.projectKey=sonar-project-name -Dsonar.sources=. -Dsonar.host.url=http://10.10.10.10:9000 -Dsonar.token=sqp_redacted
```

* Check the Security Hotspots tab: `http://10.10.10.10:9000/security_hotspots?id=sonar-project-name`

:warning: remove dead symbolic links before scanning a folder.

## Psalm

> A static analysis tool for finding errors in PHP applications

**Install**

```ps1
composer require --dev vimeo/psalm
```

**Configuration**

* Create a project and initiate a scan of the codebase

```ps1
./vendor/bin/psalm --init
./vendor/bin/psalm --taint-analysis
./vendor/bin/psalm --report=results.sarif
```

* Use a Sarif viewer to see the results: [microsoft.github.io/sarif-web-component](https://microsoft.github.io/sarif-web-component/)

## Snyk

> Snyk CLI scans and monitors your projects for security vulnerabilities.

**Install**

* [Snyk Security - Visual Studio](https://marketplace.visualstudio.com/items?itemName=snyk-security.snyk-vulnerability-scanner-vs)
* [Snyk Code / Snyk Open Source](https://app.snyk.io)

```ps1
curl https://static.snyk.io/cli/latest/snyk-linux -o snyk
chmod +x ./snyk
mv ./snyk /usr/local/bin/ 

docker run -it \
    -e "SNYK_TOKEN=<TOKEN>" \
    -v "<PROJECT_DIRECTORY>:/project" \
    -v "/home/user/.gradle:/home/node/.gradle" \
snyk/snyk:gradle:6.4 test --org=my-org-name
```

**Configuration**

```ps1
snyk auth
snyk ignore --file-path=<directory_or_file>
snyk code test

# npm install snyk-to-html -g
snyk code test --json | snyk-to-html -o results-opensource.html
```

## Vulnerability Validation Pipeline (7 Stages)

After static tools generate findings, validate them through this pipeline before investing in exploit development. Validates that findings are real, reachable, and exploitable.

```
Stage 0 → A → B → C → D → E → F → Report
```

### Stage 0: Inventory (automated)
Build a complete function/method checklist for the target. Establishes coverage tracking.

### Stage A: One-Shot Discovery
Read all source files and assess each function for vulnerabilities. If binary available, run it to gather PoC evidence. **Output:** findings array with `origin` and initial summary.

**ASSUME-EXPLOIT:** Treat everything as exploitable until proven otherwise.

### Stage B: Attack Tree + Systematic Analysis
For each finding, form *value-level predictions* (e.g., "if I send `'; DROP TABLE--`, column count will mismatch and produce error X"). Test them. Track:
- `hypotheses.json` — predictions with expected vs. actual
- `disproven.json` — what was tried and why it failed
- `PROXIMITY` score (0–10) — how close to exploitation

**Why this matters:** Forces evidence-backed analysis. Even "obvious" false positives sometimes turn exploitable once you trace the full path.

### Stage C: Sanity Check
Open each file and verify code verbatim. Confirm:
- Source-to-sink dataflow exists in actual code (not LLM hallucination)
- Code path is reachable (not dead code, not test-only)
- Sanitizer isn't applied somewhere missed in stage B

### Stage D: Ruling
Synthesize evidence from A/B/C. Apply disqualifier checks:
- **D-0**: Is this test/mock code only?
- **D-1**: Is the source truly attacker-controlled?
- **D-2**: Are preconditions realistic (requires auth, specific state)?
- **D-3**: Is there a sanitizer that's actually effective?
- **D-4**: Is the sink truly dangerous in this context?

Assign CVSS vector. Output final verdict per finding.

### Stage E: Binary Feasibility (memory corruption only)
Run constraint analysis on the compiled binary:
```bash
libexec/raptor-run-feasibility ./binary findings.json output/
```

| Feasibility verdict | Final status |
|--------------------|-------------|
| Likely / Likely exploitable | `exploitable` |
| Difficult | `confirmed_constrained` |
| Unlikely | `confirmed_blocked` |
| Not applicable | `confirmed` |
| Binary not found | `confirmed_unverified` |

Skip if no memory corruption findings or no binary available.

### Stage F: Self-Review
Review all findings as if you're a skeptical peer reviewer. Ask: "What did I get wrong?" Catch misclassifications, weak evidence, inconsistent CVSS, missed instances.

### MUST-GATEs (apply throughout)

| Gate | Rule |
|------|------|
| **ASSUME-EXPLOIT** | Investigate as exploitable until proven otherwise |
| **FULL-COVERAGE** | Check ALL code, no sampling |
| **POC-EVIDENCE** | PoC must produce observable output, not just "ran without error" |
| **NO-HEDGING** | Verify all "if/maybe/uncertain" claims before stating them |
| **PROOF** | Show vulnerable code for every finding |

---

## Attack Surface Mapping

Before scanning, map the attack surface to prioritize findings:

```
Entry points    → trust boundaries → sinks
(HTTP params)     (auth middleware)   (DB queries, shell, files)
```

**Attacker-controlled sources (high confidence):**
- HTTP request parameters (GET, POST, headers, cookies)
- User input (form fields, file uploads, URL path segments)
- External API responses (treat as untrusted)

**Conditional sources (requires some access):**
- Config files (need server access)
- Environment variables (need shell access)
- Database content (need SQL access or indirect injection)

**Internal only (false positive if flagged as source):**
- Hardcoded constants
- Framework-generated values
- Trusted internal services

---

## Sanitizer Effectiveness Analysis

For each sanitizer in a dataflow path, assess:

1. **Does it match the vuln type?**
   - SQLi needs parameterized queries OR proper SQL escaping
   - XSS needs HTML entity encoding (context-aware: HTML/JS/CSS/URL)
   - CMDi needs argument list (no `shell=True`) OR strict allowlist
   - Path traversal needs canonicalization + whitelist

2. **Can it be bypassed?**
   - Incomplete (only filters some chars) — look for missing chars
   - Encoding bypass (URL encode, double encode, Unicode normalize)
   - Case sensitivity (blacklist checks lowercase only)
   - Logic error (sanitizes var A, uses var B)
   - Order of operations (validate → sanitize → use ORIGINAL)

3. **Applied to all paths?**
   - Check branches (if/else gaps)
   - Error handling paths (exception thrown before sanitize)
   - Alternative routes to same sink

---

## Verdict System

| Verdict | Criteria |
|---------|----------|
| **EXPLOITABLE** | Source is attacker-controlled; sanitizer absent or bypassable; code path reachable in production; significant impact |
| **FALSE POSITIVE** | Source is internal only; effective sanitizer verified; dead code; framework protection present |
| **NEEDS TESTING** | Source requires some access; sanitizer unclear; reachability conditional; impact depends on data |

**Confidence levels:**
- **High** — Direct exploitation, simple payload, confirmed dataflow
- **Medium** — Requires bypass technique or specific conditions
- **Low** — Complex chain or uncertain reachability

---

## SARIF Output Processing

Most scanners output SARIF. Quick processing:
```bash
# Count findings by severity
cat results.sarif | python3 -c "
import json, sys
d = json.load(sys.stdin)
from collections import Counter
levels = [r.get('level','note') for r in d['runs'][0]['results']]
print(Counter(levels))
"

# Extract unique rules triggered
cat results.sarif | python3 -c "
import json, sys
d = json.load(sys.stdin)
rules = {r['ruleId'] for r in d['runs'][0]['results']}
print('\n'.join(sorted(rules)))
"
```

## References

* [Code auditing 101 - Rodolphe Ghio - August 2, 2025](https://blog.rodolpheg.xyz/posts/code-auditing--101/)
* [Detect PHP security vulnerabilities with Psalm - Matt Brown - June 23, 2020](https://psalm.dev/articles/detect-security-vulnerabilities-with-psalm)
* [Security Analysis in Psalm - Official Documentation](https://psalm.dev/docs/security_analysis/)
