# Test Plan — OSAC-5813 CSP-managed NetApp storage

## Overview

- **Feature:** OSAC-5813 — Tenant onboarding for NetApp storage (Dev Preview)
- **Source:** [prd.md](prd.md) (§In Scope, §User Stories). The enhancement has no
  design document, so cases come from the PRD scope only.
- **Total test cases:** 5

#### TC-NA-01: CSP-managed NetApp backends and FC tiers can be registered

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no test covers NetApp-tier registration.

#### TC-NA-02: Onboarding requires every configured tier exactly once

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no test covers the one-of-each rule.

#### TC-NA-03: An onboarding failure names the missing or duplicated tier

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no diagnostic test exists.

#### TC-NA-04: A VM boots and attaches disks from a NetApp tier

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/storage/test_tenant_storage_lifecycle.py`

#### TC-NA-05: Non-FC transports are rejected in this preview

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Gap:** no validation test exists.
