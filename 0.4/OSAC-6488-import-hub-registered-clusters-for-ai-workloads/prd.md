# Import HUB-Registered Clusters for AI Workloads

| Field       | Value |
|-------------|-------|
| Author(s)   | Eran Cohen |
| Jira        | [OSAC-6488](https://redhat.atlassian.net/browse/OSAC-6488) |
| Date        | 2026-10-18 |

## Problem Statement

Cloud providers already manage Kubernetes clusters through an ACM hub cluster
(HUB), but that capacity cannot serve OSAC AI inference workloads. To offer
the same capacity through OSAC today, providers must provision separate
clusters or leave HUB-managed capacity unavailable to OSAC tenants, increasing
provisioning effort and limiting available AI inference capacity. [User]

## In Scope

- Cloud Provider Admins can import clusters registered with an ACM hub cluster
  (HUB) through the OSAC UI, CLI, and API. Each imported cluster is represented
  as a workload cluster exposed through the OSAC API. [User]
- Cloud Provider Admins can see import outcome and readiness status through
  the UI, CLI, and API.
- Import failures show the cause. The import flow does not require an additional
  recovery action. [Clarify: R1.Q4]
- MaaS AI inference workloads can use imported workload clusters while
  preserving tenant isolation. [User]

## Out of Scope

- Importing clusters that are not registered with the HUB.
- Using imported clusters for VMaaS, CaaS, or BMaaS workloads, or adding their
  workload scheduling and placement logic.
- Disconnecting imported clusters from OSAC and removing their workload-cluster
  representations in this increment.
- Provisioning new workload clusters or general lifecycle management beyond
  import.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to import an ACM HUB-registered cluster
  through the OSAC UI, CLI, or API so its existing provider-managed capacity
  can serve OSAC AI inference workloads without provisioning a separate
  cluster.
- As a Cloud Provider Admin, I want to see import outcome and readiness status
  through the OSAC UI, CLI, and API so I can verify the import and understand
  the cluster's reported readiness.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want OSAC AI inference workloads to use
  imported workload clusters while preserving tenant isolation so my
  organization can consume provider-managed AI capacity without operating the
  underlying cluster.

## Dependencies

- **HUB registration:** A target cluster must already be registered with the
  HUB before it can be imported.
- **MaaS AI inference workload flows:** Workload flows must be able to use
  imported workload clusters while preserving tenant isolation. [User]

## Open Questions

### 1. Workload cluster readiness

What user-visible status and criteria should indicate whether a workload
cluster is ready or not ready? [User]

- **Owner:** OSAC-MaaS
- **Impact:** Determines how admins and API users interpret workload-cluster
  readiness.

### 2. Tenant allocation and visibility

Are imported workload clusters shared provider capacity or assigned to one
tenant, and what cluster information can Tenant Admins and Tenant Users see?
[Clarify: R1.Q2]

- **Owner:** OSAC-MaaS
- **Impact:** Determines how imported capacity is allocated and what cluster
  information tenant personas can see while preserving tenant isolation.

### 3. Disconnecting imported clusters

Should a later increment support disconnecting an imported cluster from OSAC,
and what must happen to MaaS AI inference workloads that use the cluster?
[User]

- **Owner:** OSAC-MaaS
- **Impact:** Defines whether and when an imported workload cluster can be
  unlinked, including the effect on active AI workloads and the cluster's HUB
  registration.

---

## Provenance

Authored: respond @ prd 0.11.3 - d9d66a5, workspace feat/OSAC-6344-keycloak-mcp-scope @ 16dcc4e78
Phases: draft, revise, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"d9d66a5","source_repo":"16dcc4e78","source_repo_branch":"feat/OSAC-6344-keycloak-mcp-scope","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
