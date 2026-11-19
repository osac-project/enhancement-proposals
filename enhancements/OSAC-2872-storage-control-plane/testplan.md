# Test Plan — OSAC-2872 Storage Control Plane

## Overview

- **Feature:** OSAC-2872 — OSAC storage control plane
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 7

#### TC-SCP-01: Volume API validates, forces the tenant, and persists CREATING

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`

#### TC-SCP-02: Volume delete transitions to DELETING and duplicate names return 409

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`

#### TC-SCP-03: The reconciler creates the Volume CR on the hub

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Execution:** `osac-operator/internal/controller/volume_controller_test.go`

#### TC-SCP-04: Tier lookup returns NOT_FOUND for a missing tier or backend

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Gap:** no test covers the lookup failure paths.

#### TC-SCP-05: The policy engine denies a tier not assigned to the tenant

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Gap:** no policy-engine test exists.

#### TC-SCP-06: Volume lifecycle through the API and the database

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Execution:** `fulfillment-service/it/it_volume_lifecycle_test.go`

#### TC-SCP-07: CSI CreateVolume polls until the volume is AVAILABLE

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Execution:** `osac-csi-driver/pkg/driver/controller_test.go`
