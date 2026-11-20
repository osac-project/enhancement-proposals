# Test Plan — OSAC-1111 Storage Backend Definition & Private API

## Overview

- **Feature:** OSAC-1111 — Storage backend definition and private API
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 6

#### TC-SB-01: Private backend CRUD lifecycle

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`

#### TC-SB-02: Required fields and DNS-label validation

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`

#### TC-SB-03: Provider and name are immutable

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`

#### TC-SB-04: Duplicate active name returns ALREADY_EXISTS, reuse after delete succeeds

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`

#### TC-SB-05: Deleting a referenced backend returns FAILED_PRECONDITION

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_storage_backends_server_test.go`

#### TC-SB-06: Backend ownership survives a real database round trip

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Execution:** `fulfillment-service/it/it_storage_backend_ownership_test.go`
