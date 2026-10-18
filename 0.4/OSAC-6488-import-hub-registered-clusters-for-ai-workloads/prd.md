# Import HUB-Registered Clusters for AI Workloads

| Field       | Value |
|-------------|-------|
| Author(s)   | Eran Cohen |
| Jira        | [OSAC-6488](https://redhat.atlassian.net/browse/OSAC-6488) |
| Date        | 2026-10-18 |

## Problem Statement

OSAC currently has no workflow for a Cloud Infrastructure Admin to import a
cluster already registered with the hub cluster (HUB) and make it available as
workload capacity for AI workloads.

## In Scope

- Cloud Infrastructure Admins can import HUB-registered clusters through the
  OSAC UI and API. Each imported cluster is represented as a workload cluster
  exposed through the OSAC API.
- Admins can see import outcome and readiness status through the UI and API.
- Import failures show the cause. The import flow does not require an additional
  recovery action. [Clarify: R1.Q4]
- OSAC AI workloads can use workload clusters while preserving tenant
  isolation. [User]
- Cloud Infrastructure Admins can disconnect imported clusters through the UI
  and API. Disconnecting removes the link between the cluster and its OSAC
  workload cluster representation, removes the cluster as an AI workload
  target, and leaves its HUB registration unchanged. [User] Disconnect is
  rejected while workloads are active on an AI grid. [Clarify: R1.Q3]

## Out of Scope

- Importing clusters that are not registered with the HUB.
- Using imported clusters for VM workloads or adding VM workload scheduling
  and placement logic.
- Supporting non-AI workload types through this import capability.
- Provisioning new workload clusters or general lifecycle management beyond
  import and disconnect.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to import a HUB-registered cluster
  through the OSAC UI or API so supported AI workloads can use existing
  provider-managed capacity without reprovisioning the cluster.
- As a Cloud Infrastructure Admin, I want to see import outcome and readiness
  status through the OSAC UI and API so I can tell whether an imported cluster
  is available for AI workloads.
- As a Cloud Infrastructure Admin, I want to disconnect an imported cluster
  when no workloads are active on an AI grid so the cluster is unlinked from
  OSAC, remains registered with the HUB, and no longer receives AI workloads.
  [Clarify: R1.Q3] [User]

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want supported AI workloads to use
  provider-imported cluster capacity while preserving tenant isolation so my
  organization can consume provider-managed AI capacity without operating the
  underlying cluster.

## Dependencies

- **HUB registration:** A target cluster must already be registered with the
  HUB before it can be imported.
- **MaaS AI workload flows:** Supported AI workload flows must be able to use
  imported workload clusters. [User]

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

---

## Provenance

Authored: revise @ prd 0.11.3 - d9d66a5, workspace feat/OSAC-6344-keycloak-mcp-scope @ 16dcc4e78
Phases: draft, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"d9d66a5","source_repo":"16dcc4e78","source_repo_branch":"feat/OSAC-6344-keycloak-mcp-scope","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
