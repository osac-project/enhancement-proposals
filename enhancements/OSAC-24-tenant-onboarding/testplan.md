# Test Plan — OSAC-24 Tenant onboarding automation

## Overview

- **Feature:** OSAC-24 — Tenant on-boarding automation
- **Source:** [README.md](README.md)
- **Total test cases:** 4

#### TC-ONB-01: Creating a tenant onboards it end to end

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/regression/test_tenant_onboarding.py`

#### TC-ONB-02: Onboarding is idempotent when re-run

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no idempotency test exists.

#### TC-ONB-03: A failed onboarding step is retried and reported

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no failure-path test exists.

#### TC-ONB-04: Deleting a tenant cleans up onboarded resources

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no offboarding test exists.
