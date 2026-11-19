# Test Plan — OSAC-1110 Storage Tier Definition & Private API

## Overview

- **Feature:** OSAC-1110 — Storage tier definition and private API
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 7

#### TC-ST-01: Private tier CRUD lifecycle

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`

#### TC-ST-02: Create or update with a non-existent backend is rejected

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`

#### TC-ST-03: The tier name is immutable

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`

#### TC-ST-04: A stale version is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`

#### TC-ST-05: Tier CRUD through gRPC and REST on a kind cluster

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Execution:** `fulfillment-service/it/it_public_storage_tiers_test.go`

#### TC-ST-06: Deleting a backend referenced by a tier fails with Z0003

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Gap:** no integration case covers the rejection.

#### TC-ST-07: A tenant can consume a tier end to end

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/storage/test_tenant_storage_lifecycle.py`
