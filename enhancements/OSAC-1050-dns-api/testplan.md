# Test Plan — OSAC-1050 DNS API

## Overview

- **Feature:** OSAC-1050 — Pluggable DNS backend abstraction
- **Source:** [README.md](README.md)
- **Total test cases:** 4

#### TC-DNS-01: A DNS backend can be registered and selected

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no test covers backend registration.

#### TC-DNS-02: An unknown backend is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no validation test exists.

#### TC-DNS-03: Cluster provisioning uses the configured backend

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Gap:** no journey covers DNS provisioning.

#### TC-DNS-04: A backend failure surfaces in cluster conditions

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no failure-path test exists.
