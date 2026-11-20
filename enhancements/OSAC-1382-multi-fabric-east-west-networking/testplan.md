# Test Plan — OSAC-1382 Multi-fabric east-west networking

## Overview

- **Feature:** OSAC-1382 — Multi-fabric east-west networking
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 6

#### TC-FD-01: FabricDomain type must match the NetworkClass capability

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no validation unit test exists.

#### TC-FD-02: An empty servers list is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no validation unit test exists.

#### TC-FD-03: Phase 1 accepts exactly one virtual network

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no validation unit test exists.

#### TC-FD-04: A virtual network from another tenant is rejected

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no cross-tenant validation test exists.

#### TC-FD-05: FabricDomain status and conditions converge

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Execution:** `osac-operator/internal/controller/fabricdomain_observability_test.go`

#### TC-FD-06: A shared subnet connects a BMaaS instance and a VM

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/networking/stretched/test_shared_subnet_bmi_compute_instance.py`
