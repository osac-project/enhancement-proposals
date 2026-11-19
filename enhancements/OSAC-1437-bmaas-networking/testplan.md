# Test Plan — OSAC-1437 BMaaS networking

## Overview

- **Feature:** OSAC-1437 — BMaaS networking
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-BN-01: Apply, delete, and lease query run through NetworkAttachment jobs

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Execution:** `osac-operator/internal/controller/fabricdomain_observability_test.go`
- **Gap:** this suite covers the FabricDomain controller, not the BMaaS job path.

#### TC-BN-02: A BMaaS instance reaches its fabric

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/networking/bmaas/test_bmaas_networking.py`

#### TC-BN-03: A tenant cannot claim another tenant's external IP

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/networking/bmaas/test_external_ip_ownership.py`

#### TC-BN-04: Cross-tenant BMaaS networking is isolated

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/networking/bmaas/test_cross_tenant_bmaas_networking.py`

#### TC-BN-05: A CaaS worker on a shared subnet uses the same path

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** E2E
- **Gap:** owned by OSAC-5688.
