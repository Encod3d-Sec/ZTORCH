---
title: spring-actuator-exposure
---

# spring-actuator-exposure

Staged content promotes here.

## Spring Boot Actuator: unauth exposure to credential mining and RCE

Probe order on any Java/Spring host: `GET /actuator` index first (Boot 2+ nests all under `/actuator/`; Boot 1 serves them at root: `/env`, `/heapdump`, `/mappings`). A 200 on `/actuator/health` only proves the module exists; the money endpoints are `/env`, `/heapdump`, `/mappings`, `/configprops`, `/jolokia`.

Escalation ladder:
1. `/actuator/env`: values are masked (`******`) but property NAMES leak the stack (datasources, SMTP, token endpoints). Pivot to `/configprops` and `/actuator/loggers`; on Spring Cloud, POST to `/env` can set properties and `refresh` rebinds the context.
2. `/actuator/heapdump`: a full memory-exfiltration primitive. Pull the HPROF and strings/grep it for `password`, `secret`, `jdbc:`, `Authorization`, JWT signing keys. In-the-wild: CVE-2025-48927 (TeleMessage) - one unauth `GET /heapdump` returned plaintext credentials, CISA KEV 2025-07-01.
3. `/jolokia` (JMX over HTTP): MBean gadgets (logback `JNDIRealm` class) turn read access into RCE.
4. Spring Cloud Gateway with actuator exposed: POST `/actuator/gateway/routes/{id}` with a SpEL payload in a filter definition is RCE, CVE-2025-41243.
5. Matcher-gap class (CVE-2025-22235): Spring Security rules built with `EndpointRequest.to()` silently fail to match when an actuator endpoint is not exposed at the expected path. Verify access with live requests, never trust the security config.

Root cause in the wild: `management.endpoints.web.exposure.include=*` plus no Spring Security gate on the management port.

### Sources
- https://secrecon.dev/research/exposed-spring-boot-actuator-endpoints
- https://dev.to/roxdavirox/exposed-spring-boot-actuator-heapdump-delivers-credentials-in-production-354p
- https://nvd.nist.gov/vuln/detail/cve-2025-48927
- https://www.miggo.io/vulnerability-database/cve/CVE-2025-41243
- https://spring.io/security/cve-2025-22235/

<!-- promoted-slug: spring-actuator-exposure-to-rce -->
