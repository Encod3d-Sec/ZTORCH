# Approach

Plan board fixture for tests/test_bench.py (example.test data only).
`offensive.py board` fills the 4a coverage matrix below.

### 4a. Coverage matrix

| id | asset | vuln class | arsenal | skill | tool | status | poc | poc_kind |
|----|-------|------------|---------|-------|------|--------|-----|----------|
| 4a:1 | lab.example.test | sqli | payloads/sqli | hunt-sqli | sqlmap | [x] | poc/sqli-union.png | req |
| 4a:2 | lab.example.test | ssrf | payloads/ssrf | hunt-ssrf | nuclei | [x] | | burp |
