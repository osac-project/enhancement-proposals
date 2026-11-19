# Test Plan — OSAC-984 Create, update, and delete standalone volumes

## Overview

- **Feature:** OSAC-984 — Create, update, and delete standalone volumes through OSAC
- **Design:** [design.md](design.md) (§Requirement Traceability, §Test Plan)
- **Total test cases:** 8

#### TC-V-01: Create requires name, tier, size, and access mode

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`

#### TC-V-02: The name is unique per tenant and immutable

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`

#### TC-V-03: Spec fields are immutable after create

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`

#### TC-V-04: Metadata updates are accepted in every non-terminal state

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`

#### TC-V-05: Status is server-owned and client input is ignored

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`

#### TC-V-06: Delete is idempotent and an archived volume returns not found

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`

#### TC-V-07: Full volume lifecycle against the database

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Execution:** `fulfillment-service/it/it_volume_lifecycle_test.go`

#### TC-V-08: A user creates, updates, and deletes a volume end to end

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Gap:** the design's E2E-1 case has no test under `tests/e2e/`.
