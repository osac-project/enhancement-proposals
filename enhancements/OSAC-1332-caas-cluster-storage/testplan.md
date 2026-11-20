# Test Plan — OSAC-1332 CaaS Cluster Storage

## Overview

- **Feature:** OSAC-1332 — CaaS cluster storage (v0.1)
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 7

#### TC-CS-01: ClusterOrder maps to its tenant from the annotation

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Execution:** `osac-operator/internal/controller/storage_controller_cluster_storage_test.go`

#### TC-CS-02: A missing kubeconfig source is reported, not ignored

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Execution:** `osac-operator/internal/controller/storage_controller_cluster_storage_test.go`

#### TC-CS-03: Provisioning starts only when tenant and order are ready

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Execution:** `osac-operator/internal/controller/storage_controller_cluster_storage_test.go`

#### TC-CS-04: Teardown completes before the finalizer is removed

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Execution:** `osac-operator/internal/controller/storage_controller_cluster_storage_test.go`

#### TC-CS-05: Duplicate StorageClass detection emits a warning event

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Envtest
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`

#### TC-CS-06: A CaaS cluster gets usable StorageClasses

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/storage/test_caas_cluster_storage.py`

#### TC-CS-07: StorageClasses are not visible to another tenant

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Gap:** no case covers tenant isolation.
