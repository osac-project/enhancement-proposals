# Test Plan — OSAC-23 Tenant Storage Onboarding

## Overview

- **Feature:** OSAC-23 — Rework tenant storage onboarding
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 7

#### TC-TO-01: Stage 1 provisions when the tenant has no hub Secret

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`

#### TC-TO-02: Stage 2 waits for Stage 1 and discovers StorageClasses

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`

#### TC-TO-03: Tier resolution covers tenant-specific, default, duplicate, and missing

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`

#### TC-TO-04: Teardown is ordered and removes the finalizer last

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`

#### TC-TO-05: An unmanaged tenant skips steady state but still finalizes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`

#### TC-TO-06: Onboarding against a real database and API

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Execution:** `fulfillment-service/it/it_tenant_storage_onboarding_test.go`

#### TC-TO-07: Tenant creation and deletion drive the full lifecycle

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/storage/test_tenant_storage_lifecycle.py`
