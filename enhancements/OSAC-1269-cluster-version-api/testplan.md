# Test Plan — OSAC-1269 Cluster version API

## Overview

- **Feature:** OSAC-1269 — Cluster version API
- **Design:** [design.md](design.md) (§Test Plan)
- **Total test cases:** 5

#### TC-CV-01: Version validation and default selection

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/private_cluster_versions_server_test.go`

#### TC-CV-02: Lifecycle state handling and image resolution

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `fulfillment-service/internal/servers/cluster_versions_server_test.go`

#### TC-CV-03: Version creation flows into cluster creation and reconciliation

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Component integration
- **Execution:** `fulfillment-service/it/it_private_cluster_versions_test.go`

#### TC-CV-04: Delete protection and default fallback

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Gap:** no integration case covers delete protection or fallback.

#### TC-CV-05: Admin version management and tenant cluster creation

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Gap:** no E2E case covers version administration.
